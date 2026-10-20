"""关节/摆杆动画：实际摆杆、目标“幽灵”摆杆、A/B 对比、重力箭头、鼠标拖拽施力。"""
from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from .theme import COLOR_A, COLOR_B, COLOR_EXT, T


class ArmView(QWidget):
    dragStarted = Signal(float)
    dragMoved = Signal(float)
    dragEnded = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(260, 240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(False)
        self.setCursor(Qt.OpenHandCursor)
        self.p_a = 0.0
        self.p_b: Optional[float] = None
        self.p_des = 0.0
        self.tau_a = 0.0
        self.tau_b = 0.0
        self.tau_max = 10.0
        self.gravity = False
        self.mass = 0.0
        self.drag_angle: Optional[float] = None
        self.ext_a = 0.0

    # ----------------------------------------------------------------- data
    def set_state(self, p_a: float, p_des: float, tau_a: float = 0.0, p_b: Optional[float] = None,
                  tau_b: float = 0.0, gravity: bool = False, mass: float = 0.0, tau_max: float = 10.0,
                  ext_a: float = 0.0):
        self.p_a, self.p_des, self.tau_a, self.p_b, self.tau_b = p_a, p_des, tau_a, p_b, tau_b
        self.gravity, self.mass, self.tau_max, self.ext_a = gravity, mass, tau_max, ext_a
        self.update()

    # ------------------------------------------------------------- geometry
    def _geom(self):
        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0 + 6
        r = 0.40 * min(w, h - 24)
        return cx, cy, r

    @staticmethod
    def _tip(cx, cy, r, ang):
        return QPointF(cx + r * math.cos(ang), cy - r * math.sin(ang))

    def angle_at(self, x: float, y: float) -> float:
        cx, cy, _ = self._geom()
        return math.atan2(-(y - cy), x - cx)

    # --------------------------------------------------------------- mouse
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            pos = e.position()
            self.drag_angle = self.angle_at(pos.x(), pos.y())
            self.setCursor(Qt.ClosedHandCursor)
            self.dragStarted.emit(self.drag_angle)
            self.update()

    def mouseMoveEvent(self, e):
        if self.drag_angle is not None:
            pos = e.position()
            self.drag_angle = self.angle_at(pos.x(), pos.y())
            self.dragMoved.emit(self.drag_angle)
            self.update()

    def mouseReleaseEvent(self, e):
        if self.drag_angle is not None:
            self.drag_angle = None
            self.setCursor(Qt.OpenHandCursor)
            self.dragEnded.emit()
            self.update()

    # ---------------------------------------------------------------- paint
    def _draw_arm(self, qp: QPainter, cx, cy, r, ang, color: str, width: float, alpha: int = 255,
                  dashed: bool = False, mass_r: float = 9.0):
        c = QColor(color)
        c.setAlpha(alpha)
        pen = QPen(c, width, Qt.DashLine if dashed else Qt.SolidLine, Qt.RoundCap)
        qp.setPen(pen)
        tip = self._tip(cx, cy, r, ang)
        qp.drawLine(QPointF(cx, cy), tip)
        qp.setBrush(QBrush(c if not dashed else Qt.NoBrush))
        qp.drawEllipse(tip, mass_r, mass_r)
        return tip

    def _draw_torque_arc(self, qp, cx, cy, rad, ang, tau, color):
        """在关节处画一段圆弧箭头表示电机输出力矩（长度 ∝ |τ|/τmax）。"""
        if self.tau_max <= 0 or abs(tau) < 1e-6:
            return
        frac = max(-1.0, min(1.0, tau / self.tau_max))
        span = frac * 150.0
        c = QColor(color)
        c.setAlpha(170)
        qp.setPen(QPen(c, 3.5, Qt.SolidLine, Qt.RoundCap))
        qp.setBrush(Qt.NoBrush)
        start_deg = math.degrees(ang)
        qp.drawArc(QRectF(cx - rad, cy - rad, 2 * rad, 2 * rad), int(start_deg * 16), int(span * 16))
        end = math.radians(start_deg + span)
        tip = self._tip(cx, cy, rad, end)
        d = 1 if span > 0 else -1
        tang = end + d * math.pi / 2
        a1 = tang + math.pi - 0.5
        a2 = tang + math.pi + 0.5
        qp.drawLine(tip, QPointF(tip.x() + 8 * math.cos(a1), tip.y() - 8 * math.sin(a1)))
        qp.drawLine(tip, QPointF(tip.x() + 8 * math.cos(a2), tip.y() - 8 * math.sin(a2)))

    def paintEvent(self, ev):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.Antialiasing)
        qp.fillRect(self.rect(), QColor(T["surface"]))
        cx, cy, r = self._geom()
        # 刻度盘
        qp.setPen(QPen(QColor(T["border"]), 1))
        qp.setBrush(Qt.NoBrush)
        qp.drawEllipse(QPointF(cx, cy), r, r)
        f = QFont(self.font())
        f.setPointSizeF(8)
        qp.setFont(f)
        for k in range(12):
            a = k * math.pi / 6
            p1 = self._tip(cx, cy, r - 4, a)
            p2 = self._tip(cx, cy, r + 4, a)
            qp.setPen(QPen(QColor(T["border_strong"]), 1))
            qp.drawLine(p1, p2)
            lab = self._tip(cx, cy, r + 16, a)
            qp.setPen(QColor(T["text3"]))
            qp.drawText(QRectF(lab.x() - 18, lab.y() - 8, 36, 16), Qt.AlignCenter, f"{k * 30}°")
        # 水平参考线
        qp.setPen(QPen(QColor(T["surface3"]), 1, Qt.DotLine))
        qp.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy))
        mass_r = 7.0 + 6.0 * min(1.0, self.mass / 1.0)
        # 目标幽灵摆杆
        self._draw_arm(qp, cx, cy, r, self.p_des, T["text3"], 6, alpha=90, dashed=True, mass_r=mass_r)
        # 力矩弧
        self._draw_torque_arc(qp, cx, cy, 30, self.p_a, self.tau_a, COLOR_A)
        if self.p_b is not None:
            self._draw_torque_arc(qp, cx, cy, 42, self.p_b, self.tau_b, COLOR_B)
            self._draw_arm(qp, cx, cy, r * 0.97, self.p_b, COLOR_B, 7, alpha=210, mass_r=mass_r)
        tip_a = self._draw_arm(qp, cx, cy, r, self.p_a, COLOR_A, 8, mass_r=mass_r)
        # 重力箭头
        if self.gravity and self.mass > 0:
            qp.setPen(QPen(QColor(T["ok"]), 2))
            L = 18 + 16 * min(1.0, self.mass)
            end = QPointF(tip_a.x(), tip_a.y() + L)
            qp.drawLine(tip_a, end)
            qp.drawLine(end, QPointF(end.x() - 5, end.y() - 7))
            qp.drawLine(end, QPointF(end.x() + 5, end.y() - 7))
            qp.drawText(QRectF(end.x() + 4, end.y() - 10, 40, 16), Qt.AlignLeft, "mg")
        # 拖拽弹簧
        if self.drag_angle is not None:
            m = self._tip(cx, cy, r, self.drag_angle)
            qp.setPen(QPen(QColor(COLOR_EXT), 2, Qt.DashLine))
            qp.drawLine(tip_a, m)
            qp.setBrush(QColor(COLOR_EXT))
            qp.drawEllipse(m, 4, 4)
        # 轴心
        qp.setPen(QPen(QColor(T["text"]), 2))
        qp.setBrush(QColor(T["surface2"]))
        qp.drawEllipse(QPointF(cx, cy), 10, 10)
        # 文字
        f.setPointSizeF(9)
        qp.setFont(f)
        qp.setPen(QColor(T["text2"]))
        txt = f"p = {math.degrees(self.p_a):7.1f}°   p_des = {math.degrees(self.p_des):7.1f}°   τ = {self.tau_a:+.2f} N·m"
        if self.p_b is not None:
            txt += f"   |  B: p = {math.degrees(self.p_b):.1f}°"
        qp.drawText(QRectF(8, 4, self.width() - 16, 18), Qt.AlignLeft | Qt.AlignVCenter, txt)
        qp.setPen(QColor(T["text3"]))
        qp.drawText(QRectF(8, self.height() - 20, self.width() - 16, 18), Qt.AlignLeft | Qt.AlignVCenter,
                    "提示：按住鼠标左键拖动可对摆杆施加外力（虚拟弹簧）；灰色虚线为目标位置")
        qp.end()
