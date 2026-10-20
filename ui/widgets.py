"""通用控件：滑块 + 数值框联动的参数行。"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDoubleSpinBox, QHBoxLayout, QLabel, QSlider, QWidget

SLIDER_STEPS = 1000


class ParamRow(QWidget):
    """标签 + 滑块 + 数值框，二者双向同步。log=True 时滑块按对数刻度映射。"""

    valueChanged = Signal(float)

    def __init__(self, label: str, lo: float, hi: float, value: float, decimals: int = 3,
                 step: float = 0.01, unit: str = "", tip: str = "", log: bool = False, parent=None):
        super().__init__(parent)
        self.lo, self.hi, self.log = lo, hi, log and lo > 0
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 1, 0, 1)
        lay.setSpacing(6)
        self.label = QLabel(label)
        self.label.setObjectName("label")
        self.label.setMinimumWidth(78)
        self.label.setTextFormat(Qt.RichText)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, SLIDER_STEPS)
        self.slider.setMinimumWidth(90)
        self.spin = QDoubleSpinBox()
        self.spin.setRange(lo, hi)
        self.spin.setDecimals(decimals)
        self.spin.setSingleStep(step)
        self.spin.setKeyboardTracking(False)
        self.spin.setMinimumWidth(124)
        if unit:
            self.spin.setSuffix(" " + unit)
        if tip:
            for w in (self.label, self.slider, self.spin):
                w.setToolTip(tip)
        lay.addWidget(self.label)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.spin)
        self.slider.valueChanged.connect(self._on_slider)
        self.spin.valueChanged.connect(self._on_spin)
        self.setValue(value)

    def _to_slider(self, v: float) -> int:
        if self.log:
            v = max(self.lo, v)
            r = (math.log(v) - math.log(self.lo)) / (math.log(self.hi) - math.log(self.lo))
        else:
            r = (v - self.lo) / (self.hi - self.lo) if self.hi > self.lo else 0
        return int(round(max(0.0, min(1.0, r)) * SLIDER_STEPS))

    def _from_slider(self, i: int) -> float:
        r = i / SLIDER_STEPS
        if self.log:
            return math.exp(math.log(self.lo) + r * (math.log(self.hi) - math.log(self.lo)))
        return self.lo + r * (self.hi - self.lo)

    def _on_slider(self, i: int):
        v = self._from_slider(i)
        self.spin.blockSignals(True)
        self.spin.setValue(v)
        self.spin.blockSignals(False)
        self.valueChanged.emit(self.spin.value())

    def _on_spin(self, v: float):
        self.slider.blockSignals(True)
        self.slider.setValue(self._to_slider(v))
        self.slider.blockSignals(False)
        self.valueChanged.emit(v)

    def value(self) -> float:
        return self.spin.value()

    def setValue(self, v: float, emit: bool = False):
        """设置数值；默认不发信号（用于加载预设）。"""
        self.spin.blockSignals(True)
        self.slider.blockSignals(True)
        self.spin.setValue(v)
        self.slider.setValue(self._to_slider(self.spin.value()))
        self.spin.blockSignals(False)
        self.slider.blockSignals(False)
        if emit:
            self.valueChanged.emit(self.spin.value())

    def setLabel(self, text: str):
        self.label.setText(text)
