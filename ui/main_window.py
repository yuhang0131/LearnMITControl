"""主窗口：参数面板 | 动画 + 理论/指标 + 实时曲线 | 预设与讲解。"""
from __future__ import annotations

import math
from typing import Dict, Optional

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QElapsedTimer, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QGridLayout,
                               QGroupBox, QHBoxLayout, QHeaderView, QLabel, QListWidget, QListWidgetItem,
                               QMainWindow, QPushButton, QScrollArea, QSplitter, QTableWidget,
                               QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget)

from mitlab import APP_NAME, __version__
from mitlab.buffer import SignalBuffer
from mitlab.metrics import step_metrics
from mitlab.presets import PRESET_BY_KEY, PRESETS, Preset
from mitlab.sim import LOG_FIELDS, JointSim, MITGains, PlantParams, theory, wrap_angle
from mitlab.targets import KIND_NAMES, KINDS, TRAJ_KINDS, TRAJ_NAMES, Target

from .arm_view import ArmView
from .theme import (COLOR_A, COLOR_B, COLOR_CMD, COLOR_EXT, COLOR_FF, COLOR_KD, COLOR_KP, COLOR_TARGET, T)
from .widgets import ParamRow

SPEEDS = [0.1, 0.25, 0.5, 1.0, 2.0, 4.0]
FRAME_MS = 16
MAX_SIM_PER_FRAME = 0.1  # s，防止卡顿时一次推进过多

WELCOME = """<h3>欢迎使用 MIT 控制学习实验室</h3>
<p>MIT 模式（源自 MIT Cheetah 关节驱动器）是一种<b>位置-速度-力矩混合</b>的阻抗控制：</p>
<p style='text-align:center'><b>τ = K<sub>p</sub>(p<sub>des</sub>−p) + K<sub>d</sub>(v<sub>des</sub>−v) + τ<sub>ff</sub></b></p>
<ul><li><b>K<sub>p</sub></b>：虚拟弹簧刚度 (N·m/rad)</li>
<li><b>K<sub>d</sub></b>：虚拟阻尼 (N·m·s/rad)</li>
<li><b>τ<sub>ff</sub></b>：前馈力矩，例如重力补偿</li></ul>
<p>线性化后关节就是一个二阶系统 J·p̈ + (K<sub>d</sub>+b)·ṗ + K<sub>p</sub>·p = …，于是：</p>
<p>ω<sub>n</sub> = √(K<sub>p</sub>/J)，ζ = (K<sub>d</sub>+b) / (2√(K<sub>p</sub>J))</p>
<p>在右上方列表中选择一个预设开始学习；左侧可实时调整全部参数。</p>"""


def fmt(v: Optional[float], spec: str = ".3f", unit: str = "") -> str:
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return "—"
    return f"{v:{spec}}{unit}"


def card(title: str) -> QGroupBox:
    g = QGroupBox(title)
    lay = QVBoxLayout(g)
    lay.setContentsMargins(8, 10, 8, 6)
    lay.setSpacing(3)
    return g


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}  v{__version__}  —  关节 MIT 控制可视化")
        pg.setConfigOptions(antialias=True, background=T["surface"], foreground=T["text2"])

        # ------------------------------------------------------- model state
        self.plant = PlantParams()
        self.target = Target(kind="const", p_des=1.0)
        self.gains: Dict[str, MITGains] = {"A": MITGains(kp=10.0, kd=0.3), "B": MITGains(kp=10.0, kd=0.3)}
        self.sims: Dict[str, JointSim] = {k: JointSim(self.plant, self.gains[k], self.target.sample, seed=i)
                                          for i, k in enumerate("AB")}
        self.bufs: Dict[str, SignalBuffer] = {k: SignalBuffer(LOG_FIELDS, 60000) for k in "AB"}
        self.compare = False
        self.edit_set = "A"
        self.running = False
        self.speed = 1.0
        self.window_s = 10.0
        self.p0 = 0.0
        self.drag_angle: Optional[float] = None
        self.drag_k = 1.0
        self.step_info: Dict[str, tuple] = {}
        self.current_preset: Optional[Preset] = None
        self._frame = 0

        self._build_ui()
        self.reset()

        self.clock = QElapsedTimer()
        self.timer = QTimer(self)
        self.timer.setInterval(FRAME_MS)
        self.timer.timeout.connect(self._on_frame)
        self.timer.start()

    # ================================================================= UI
    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self._build_topbar())
        split = QSplitter(Qt.Horizontal)
        split.setChildrenCollapsible(False)
        split.addWidget(self._build_left())
        split.addWidget(self._build_center())
        split.addWidget(self._build_right())
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setStretchFactor(2, 0)
        split.setSizes([400, 880, 320])
        v.addWidget(split, 1)

    def _build_topbar(self):
        bar = QFrame()
        bar.setObjectName("topbar")
        h = QHBoxLayout(bar)
        h.setContentsMargins(12, 6, 12, 6)
        h.setSpacing(8)
        title = QLabel(APP_NAME)
        title.setObjectName("appTitle")
        h.addWidget(title)
        h.addSpacing(12)
        self.btn_run = QPushButton("开始")
        self.btn_run.setProperty("kind", "primary")
        self.btn_run.setMinimumWidth(86)
        self.btn_run.clicked.connect(self.toggle_run)
        self.btn_reset = QPushButton("重置")
        self.btn_reset.clicked.connect(self.reset)
        h.addWidget(self.btn_run)
        h.addWidget(self.btn_reset)
        h.addWidget(QLabel("仿真速度"))
        self.cmb_speed = QComboBox()
        for s in SPEEDS:
            self.cmb_speed.addItem(f"{s:g}×", s)
        self.cmb_speed.setCurrentIndex(SPEEDS.index(1.0))
        self.cmb_speed.currentIndexChanged.connect(lambda i: setattr(self, "speed", SPEEDS[i]))
        h.addWidget(self.cmb_speed)
        h.addSpacing(16)
        self.chk_compare = QCheckBox("A/B 对比模式")
        self.chk_compare.toggled.connect(self.set_compare)
        h.addWidget(self.chk_compare)
        h.addWidget(QLabel("编辑参数组:"))
        self.btn_a = QPushButton("A")
        self.btn_b = QPushButton("B")
        grp = QButtonGroup(self)
        for b, k in ((self.btn_a, "A"), (self.btn_b, "B")):
            b.setCheckable(True)
            b.setFixedWidth(40)
            grp.addButton(b)
            b.clicked.connect(lambda _=False, k=k: self.set_edit_set(k))
            h.addWidget(b)
        self.btn_a.setChecked(True)
        self.btn_a.setStyleSheet(f"QPushButton:checked {{ color: {COLOR_A}; border-color: {COLOR_A}; background: #E8F0FE; }}")
        self.btn_b.setStyleSheet(f"QPushButton:checked {{ color: {COLOR_B}; border-color: {COLOR_B}; background: #FDEEE6; }}")
        self.btn_b.setEnabled(False)
        self.btn_copy = QPushButton("A→B 复制")
        self.btn_copy.setEnabled(False)
        self.btn_copy.clicked.connect(self.copy_a_to_b)
        h.addWidget(self.btn_copy)
        h.addStretch(1)
        self.lbl_time = QLabel("t = 0.000 s")
        self.lbl_time.setObjectName("timeLabel")
        h.addWidget(self.lbl_time)
        return bar

    # ------------------------------------------------------------ left
    def _build_left(self):
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setMinimumWidth(390)
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 6, 6, 10)
        lay.setSpacing(4)
        sc.setWidget(w)

        # --- MIT 增益
        self.grp_gain = card("MIT 增益 — 参数组 A")
        gl = self.grp_gain.layout()
        self.r_kp = ParamRow("K<sub>p</sub> 刚度", 0.0, 100.0, 10.0, 3, 0.1, "N·m/rad", "位置误差增益（虚拟弹簧刚度）")
        self.r_kd = ParamRow("K<sub>d</sub> 阻尼", 0.0, 5.0, 0.3, 4, 0.01, "N·m·s/rad", "速度误差增益（虚拟阻尼）")
        self.r_ff = ParamRow("τ<sub>ff</sub> 前馈", -10.0, 10.0, 0.0, 3, 0.05, "N·m", "前馈力矩")
        self.chk_autoff = QCheckBox("自动重力前馈  τ_ff += m·g·l·cos(p_des)")
        for r in (self.r_kp, self.r_kd, self.r_ff):
            gl.addWidget(r)
        gl.addWidget(self.chk_autoff)
        self.btn_crit = QPushButton("设为临界阻尼 (ζ=1)")
        self.btn_crit.setToolTip("Kd = 2√(Kp·J_tot) − b")
        self.btn_crit.clicked.connect(self.set_critical_damping)
        gl.addWidget(self.btn_crit)
        self.r_kp.valueChanged.connect(lambda v: self._set_gain("kp", v))
        self.r_kd.valueChanged.connect(lambda v: self._set_gain("kd", v))
        self.r_ff.valueChanged.connect(lambda v: self._set_gain("tau_ff", v))
        self.chk_autoff.toggled.connect(lambda b: self._set_gain("auto_gravity_ff", b))
        lay.addWidget(self.grp_gain)

        # --- 目标
        g = card("目标指令（A/B 共用）")
        gl = g.layout()
        row = QHBoxLayout()
        row.addWidget(QLabel("类型"))
        self.cmb_kind = QComboBox()
        for k in KINDS:
            self.cmb_kind.addItem(KIND_NAMES[k], k)
        self.cmb_kind.currentIndexChanged.connect(lambda i: self._set_target("kind", KINDS[i]))
        row.addWidget(self.cmb_kind, 1)
        gl.addLayout(row)
        self.r_pdes = ParamRow("p<sub>des</sub>", -6.28, 6.28, 1.0, 3, 0.05, "rad", "目标位置（正弦/轨迹时为偏置）")
        self.r_vdes = ParamRow("v<sub>des</sub>", -20.0, 20.0, 0.0, 3, 0.1, "rad/s", "目标速度")
        self.r_pdes.valueChanged.connect(lambda v: self._set_target("p_des", v))
        self.r_vdes.valueChanged.connect(lambda v: self._set_target("v_des", v))
        gl.addWidget(self.r_pdes)
        gl.addWidget(self.r_vdes)
        srow = QHBoxLayout()
        self.btn_step = QPushButton("阶跃切换")
        self.btn_step.setToolTip("在 0 与右侧幅值之间切换 p_des，产生阶跃并重新计算指标")
        self.btn_step.clicked.connect(self.toggle_step)
        self.spn_step = QDoubleSpinBox()
        self.spn_step.setRange(-6.28, 6.28)
        self.spn_step.setValue(1.0)
        self.spn_step.setSuffix(" rad")
        srow.addWidget(self.btn_step)
        srow.addWidget(QLabel("幅值"))
        srow.addWidget(self.spn_step, 1)
        self.w_step = QWidget()
        self.w_step.setLayout(srow)
        srow.setContentsMargins(0, 0, 0, 0)
        gl.addWidget(self.w_step)
        self.r_samp = ParamRow("正弦幅值", 0.0, 3.0, 0.5, 3, 0.05, "rad")
        self.r_sfreq = ParamRow("正弦频率", 0.02, 10.0, 0.5, 3, 0.05, "Hz", log=True)
        self.r_samp.valueChanged.connect(lambda v: self._set_target("sine_amp", v))
        self.r_sfreq.valueChanged.connect(lambda v: self._set_target("sine_freq", v))
        self.w_traj_kind = QWidget()
        tr = QHBoxLayout(self.w_traj_kind)
        tr.setContentsMargins(0, 0, 0, 0)
        tr.addWidget(QLabel("轨迹"))
        self.cmb_traj = QComboBox()
        for k in TRAJ_KINDS:
            self.cmb_traj.addItem(TRAJ_NAMES[k], k)
        self.cmb_traj.currentIndexChanged.connect(lambda i: self._set_target("traj_kind", TRAJ_KINDS[i]))
        tr.addWidget(self.cmb_traj, 1)
        self.r_tamp = ParamRow("轨迹幅值", -3.14, 3.14, 1.0, 3, 0.05, "rad")
        self.r_tT = ParamRow("运动时间", 0.1, 5.0, 1.0, 2, 0.05, "s")
        self.r_thold = ParamRow("停留时间", 0.0, 5.0, 1.0, 2, 0.05, "s")
        self.r_tamp.valueChanged.connect(lambda v: self._set_target("traj_amp", v))
        self.r_tT.valueChanged.connect(lambda v: self._set_target("traj_T", v))
        self.r_thold.valueChanged.connect(lambda v: self._set_target("traj_hold", v))
        self.chk_trajv = QCheckBox("v_des 取轨迹导数（速度前馈）")
        self.chk_trajv.setChecked(True)
        self.chk_trajv.toggled.connect(lambda b: self._set_target("use_traj_v", b))
        for wdg in (self.r_samp, self.r_sfreq, self.w_traj_kind, self.r_tamp, self.r_tT, self.r_thold, self.chk_trajv):
            gl.addWidget(wdg)
        lay.addWidget(g)

        # --- 被控对象
        g = card("被控对象（A/B 共用）")
        gl = g.layout()
        self.r_J = ParamRow("惯量 J", 0.001, 0.5, 0.01, 4, 0.001, "kg·m²", "关节/转子惯量（不含末端负载）", log=True)
        self.r_b = ParamRow("粘性摩擦 b", 0.0, 0.5, 0.005, 4, 0.001, "N·m·s/rad")
        self.r_tc = ParamRow("库仑摩擦", 0.0, 2.0, 0.0, 3, 0.01, "N·m", "与速度方向相反的恒值摩擦（含静摩擦）")
        self.chk_grav = QCheckBox("考虑重力（摆杆，角度从水平向右起算）")
        self.r_m = ParamRow("负载质量 m", 0.0, 5.0, 0.0, 3, 0.05, "kg")
        self.r_l = ParamRow("臂长 l", 0.02, 1.0, 0.2, 3, 0.01, "m")
        self.r_tmax = ParamRow("力矩限幅", 0.1, 50.0, 10.0, 2, 0.1, "N·m", "电机最大输出力矩（饱和）", log=True)
        self.r_ts = ParamRow("控制周期", 0.5, 50.0, 1.0, 1, 0.5, "ms", "控制律采样周期（零阶保持），物理以 ≤1 ms 步长 RK4 积分")
        self.r_np = ParamRow("位置噪声 σ", 0.0, 0.05, 0.0, 4, 0.001, "rad")
        self.r_nv = ParamRow("速度噪声 σ", 0.0, 3.0, 0.0, 3, 0.01, "rad/s")
        for wdg in (self.r_J, self.r_b, self.r_tc, self.chk_grav, self.r_m, self.r_l, self.r_tmax, self.r_ts,
                    self.r_np, self.r_nv):
            gl.addWidget(wdg)
        self.r_J.valueChanged.connect(lambda v: self._set_plant("J", v))
        self.r_b.valueChanged.connect(lambda v: self._set_plant("b", v))
        self.r_tc.valueChanged.connect(lambda v: self._set_plant("tau_c", v))
        self.chk_grav.toggled.connect(lambda b: self._set_plant("gravity", b))
        self.r_m.valueChanged.connect(lambda v: self._set_plant("m", v))
        self.r_l.valueChanged.connect(lambda v: self._set_plant("l", v))
        self.r_tmax.valueChanged.connect(lambda v: self._set_plant("tau_max", v))
        self.r_ts.valueChanged.connect(lambda v: self._set_plant("ctrl_period", v / 1000.0))
        self.r_np.valueChanged.connect(lambda v: self._set_plant("noise_p", v))
        self.r_nv.valueChanged.connect(lambda v: self._set_plant("noise_v", v))
        lay.addWidget(g)

        # --- 扰动
        g = card("外部扰动")
        gl = g.layout()
        self.r_dist = ParamRow("脉冲力矩", -5.0, 5.0, 0.5, 2, 0.05, "N·m")
        self.r_distT = ParamRow("持续时间", 0.01, 1.0, 0.1, 2, 0.01, "s")
        self.r_dragk = ParamRow("拖拽刚度", 0.05, 20.0, 1.0, 2, 0.05, "N·m/rad", "鼠标与摆杆之间虚拟弹簧的刚度", log=True)
        self.r_dragk.valueChanged.connect(lambda v: setattr(self, "drag_k", v))
        self.btn_dist = QPushButton("施加扰动")
        self.btn_dist.clicked.connect(self.apply_disturbance)
        for wdg in (self.r_dist, self.r_distT, self.btn_dist, self.r_dragk):
            gl.addWidget(wdg)
        hint = QLabel("也可以直接用鼠标拖拽动画中的摆杆（A/B 同时受力）。")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        gl.addWidget(hint)
        lay.addWidget(g)

        # --- 显示
        g = card("显示")
        gl = g.layout()
        self.r_win = ParamRow("时间窗口", 2.0, 30.0, 10.0, 1, 1.0, "s")
        self.r_win.valueChanged.connect(lambda v: setattr(self, "window_s", v))
        gl.addWidget(self.r_win)
        lay.addWidget(g)
        lay.addStretch(1)
        return sc

    # ------------------------------------------------------------ center
    def _build_center(self):
        vs = QSplitter(Qt.Vertical)
        vs.setChildrenCollapsible(False)
        top = QWidget()
        th = QHBoxLayout(top)
        th.setContentsMargins(6, 6, 6, 2)
        th.setSpacing(6)
        self.arm = ArmView()
        self.arm.dragStarted.connect(self._drag_start)
        self.arm.dragMoved.connect(self._drag_move)
        self.arm.dragEnded.connect(self._drag_end)
        frame = QFrame()
        frame.setObjectName("card")
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(4, 4, 4, 4)
        fl.addWidget(self.arm)
        th.addWidget(frame, 3)

        info = QWidget()
        info.setMinimumWidth(330)
        il = QVBoxLayout(info)
        il.setContentsMargins(0, 0, 0, 0)
        il.setSpacing(4)
        lab = QLabel("理论提示（线性化二阶系统，实时）")
        lab.setObjectName("cardTitle")
        il.addWidget(lab)
        self.tbl_theory = self._make_table(
            ["ω_n", "f_n", "阻尼比 ζ", "理论超调", "调节时间", "重力稳态误差", "ω_n·T_s", "J_tot"],
            ["固有角频率 ω_n = √(Kp/J_tot)", "固有频率 f_n = ω_n/2π", "ζ = (Kd+b) / (2√(Kp·J_tot))",
             "超调 = exp(−ζπ/√(1−ζ²))", "±2% 调节时间 ≈ 4/(ζ·ω_n)", "e_ss ≈ (m·g·l·cos(p_des) − τ_ff)/Kp",
             "离散化程度：ω_n × 控制周期，>0.2 时采样延迟影响明显", "等效惯量 J_tot = J + m·l²"])
        il.addWidget(self.tbl_theory)
        lab = QLabel("阶跃响应指标（每次阶跃后重新计算）")
        lab.setObjectName("cardTitle")
        il.addWidget(lab)
        self.tbl_metrics = self._make_table(
            ["超调量", "上升时间", "调节时间", "稳态误差", "终值"],
            ["(峰值−终值)/|终值−初值|", "10% → 90% 上升时间", "最后一次离开 ±2% 误差带之后的时刻",
             "目标值 p_des − 终值", "响应末段均值"])
        il.addWidget(self.tbl_metrics)
        self.lbl_metric_note = QLabel("")
        self.lbl_metric_note.setObjectName("hint")
        self.lbl_metric_note.setWordWrap(True)
        il.addWidget(self.lbl_metric_note)
        il.addStretch(1)
        th.addWidget(info, 2)
        vs.addWidget(top)

        # 曲线
        self.glw = pg.GraphicsLayoutWidget()
        self.glw.setMinimumHeight(300)
        self.pp = self.glw.addPlot(row=0, col=0)
        self.pv = self.glw.addPlot(row=1, col=0)
        self.pt = self.glw.addPlot(row=2, col=0)
        for p, lab in ((self.pp, "位置 p (rad)"), (self.pv, "速度 v (rad/s)"), (self.pt, "力矩 τ (N·m)")):
            p.showGrid(x=True, y=True, alpha=0.25)
            p.setLabel("left", lab)
            p.setDownsampling(auto=True, mode="peak")
            p.setClipToView(True)
            p.getAxis("left").setWidth(56)
            p.getAxis("left").enableAutoSIPrefix(False)
            p.getAxis("bottom").enableAutoSIPrefix(False)
            lg = p.addLegend(offset=(-4, 2), labelTextSize="8pt", colCount=4 if p is self.pt else 3)
            lg.setBrush(pg.mkBrush(255, 255, 255, 200))
            p.setMenuEnabled(False)
        self.pv.setXLink(self.pp)
        self.pt.setXLink(self.pp)
        self.pt.setLabel("bottom", "时间 t (s)")

        def pen(c, w=1.6, style=Qt.SolidLine):
            return pg.mkPen(QColor(c), width=w, style=style)
        self.c = {}
        self.c["p_des"] = self.pp.plot(pen=pen(COLOR_TARGET, 1.6, Qt.DashLine), name="目标 p_des")
        self.c["pA"] = self.pp.plot(pen=pen(COLOR_A, 2.0), name="A 实际 p")
        self.c["pB"] = self.pp.plot(pen=pen(COLOR_B, 2.0), name="B 实际 p")
        self.c["v_des"] = self.pv.plot(pen=pen(COLOR_TARGET, 1.6, Qt.DashLine), name="目标 v_des")
        self.c["vA"] = self.pv.plot(pen=pen(COLOR_A, 1.8), name="A 实际 v")
        self.c["vB"] = self.pv.plot(pen=pen(COLOR_B, 1.8), name="B 实际 v")
        self.c["kp"] = self.pt.plot(pen=pen(COLOR_KP, 1.3), name="A: Kp 项")
        self.c["kd"] = self.pt.plot(pen=pen(COLOR_KD, 1.3), name="A: Kd 项")
        self.c["ff"] = self.pt.plot(pen=pen(COLOR_FF, 1.3), name="A: τ_ff")
        self.c["cmd"] = self.pt.plot(pen=pen(COLOR_CMD, 1.3, Qt.DashLine), name="A: 合计 τ_cmd")
        self.c["outA"] = self.pt.plot(pen=pen(COLOR_A, 2.2), name="A: 饱和后 τ_out")
        self.c["outB"] = self.pt.plot(pen=pen(COLOR_B, 2.2), name="B: 饱和后 τ_out")
        self.c["ext"] = self.pt.plot(pen=pen(COLOR_EXT, 1.3, Qt.DotLine), name="外部扰动")
        self.lim_hi = pg.InfiniteLine(angle=0, pen=pg.mkPen(QColor(COLOR_EXT), width=1, style=Qt.DashDotLine))
        self.lim_lo = pg.InfiniteLine(angle=0, pen=pg.mkPen(QColor(COLOR_EXT), width=1, style=Qt.DashDotLine))
        self.pt.addItem(self.lim_hi)
        self.pt.addItem(self.lim_lo)
        vs.addWidget(self.glw)
        vs.setSizes([370, 500])
        return vs

    def _make_table(self, rows, tips=None):
        t = QTableWidget(len(rows), 2)
        t.setHorizontalHeaderLabels(["A", "B"])
        for i, r in enumerate(rows):
            it = QTableWidgetItem(r)
            if tips:
                it.setToolTip(tips[i])
            t.setVerticalHeaderItem(i, it)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        t.verticalHeader().setMinimumSectionSize(18)
        t.verticalHeader().setDefaultSectionSize(22)
        t.horizontalHeader().setFixedHeight(24)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setSelectionMode(QTableWidget.NoSelection)
        t.setFocusPolicy(Qt.NoFocus)
        t.setFixedHeight(t.horizontalHeader().sizeHint().height() + 22 * len(rows) + 4)
        t.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        t.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        for r in range(len(rows)):
            for c in range(2):
                it = QTableWidgetItem("—")
                it.setTextAlignment(Qt.AlignCenter)
                t.setItem(r, c, it)
        return t

    # ------------------------------------------------------------ right
    def _build_right(self):
        w = QWidget()
        w.setMinimumWidth(300)
        v = QVBoxLayout(w)
        v.setContentsMargins(6, 8, 10, 10)
        v.setSpacing(6)
        lab = QLabel("教学预设")
        lab.setObjectName("cardTitle")
        v.addWidget(lab)
        self.lst = QListWidget()
        self.lst.setObjectName("presets")
        for p in PRESETS:
            it = QListWidgetItem(p.name + ("   [A/B]" if p.compare else ""))
            it.setData(Qt.UserRole, p.key)
            self.lst.addItem(it)
        self.lst.setFixedHeight(32 * len(PRESETS) + 8)
        self.lst.itemClicked.connect(lambda it: self.apply_preset(it.data(Qt.UserRole)))
        v.addWidget(self.lst)
        lab = QLabel("讲解")
        lab.setObjectName("cardTitle")
        v.addWidget(lab)
        self.txt = QTextBrowser()
        self.txt.setOpenExternalLinks(True)
        self.txt.setHtml(WELCOME)
        v.addWidget(self.txt, 1)
        return w

    # ============================================================ actions
    def _set_gain(self, attr, value):
        setattr(self.gains[self.edit_set], attr, value)
        self.update_theory()

    def _set_plant(self, attr, value):
        setattr(self.plant, attr, value)
        self.update_theory()

    def _set_target(self, attr, value):
        setattr(self.target, attr, value)
        if attr == "kind":
            self._update_target_rows()
            self.mark_step()
        elif attr == "p_des" and self.target.kind == "const":
            self.mark_step()
        self.update_theory()

    def _update_target_rows(self):
        k = self.target.kind
        for wdg in (self.r_samp, self.r_sfreq):
            wdg.setVisible(k == "sine")
        for wdg in (self.w_traj_kind, self.r_tamp, self.r_tT, self.r_thold):
            wdg.setVisible(k == "traj")
        self.chk_trajv.setVisible(k != "const")
        self.w_step.setVisible(k == "const")
        self.r_pdes.setLabel("p<sub>des</sub>" if k == "const" else "偏置 p<sub>0</sub>")

    def set_edit_set(self, k: str):
        if k == "B" and not self.compare:
            k = "A"
        self.edit_set = k
        (self.btn_a if k == "A" else self.btn_b).setChecked(True)
        color = COLOR_A if k == "A" else COLOR_B
        self.grp_gain.setTitle(f"MIT 增益 — 参数组 {k}")
        self.grp_gain.setStyleSheet(f"QGroupBox {{ border: 1px solid {color}; }} QGroupBox::title {{ color: {color}; }}")
        self._load_gain_widgets()
        self.update_theory()

    def _load_gain_widgets(self):
        g = self.gains[self.edit_set]
        self.r_kp.setValue(g.kp)
        self.r_kd.setValue(g.kd)
        self.r_ff.setValue(g.tau_ff)
        self.chk_autoff.blockSignals(True)
        self.chk_autoff.setChecked(g.auto_gravity_ff)
        self.chk_autoff.blockSignals(False)

    def _load_all_widgets(self):
        pl, tg = self.plant, self.target
        for r, v in ((self.r_J, pl.J), (self.r_b, pl.b), (self.r_tc, pl.tau_c), (self.r_m, pl.m), (self.r_l, pl.l),
                     (self.r_tmax, pl.tau_max), (self.r_ts, pl.ctrl_period * 1000), (self.r_np, pl.noise_p),
                     (self.r_nv, pl.noise_v), (self.r_pdes, tg.p_des), (self.r_vdes, tg.v_des),
                     (self.r_samp, tg.sine_amp), (self.r_sfreq, tg.sine_freq), (self.r_tamp, tg.traj_amp),
                     (self.r_tT, tg.traj_T), (self.r_thold, tg.traj_hold)):
            r.setValue(v)
        for w, val in ((self.chk_grav, pl.gravity), (self.chk_trajv, tg.use_traj_v)):
            w.blockSignals(True)
            w.setChecked(val)
            w.blockSignals(False)
        for cmb, val, seq in ((self.cmb_kind, tg.kind, KINDS), (self.cmb_traj, tg.traj_kind, TRAJ_KINDS)):
            cmb.blockSignals(True)
            cmb.setCurrentIndex(seq.index(val))
            cmb.blockSignals(False)
        if tg.kind == "const" and abs(tg.p_des) > 1e-9:
            self.spn_step.setValue(tg.p_des)
        self._update_target_rows()
        self._load_gain_widgets()

    def set_compare(self, on: bool):
        on = bool(on)
        if self.chk_compare.isChecked() != on:
            self.chk_compare.blockSignals(True)
            self.chk_compare.setChecked(on)
            self.chk_compare.blockSignals(False)
        self.compare = on
        self.btn_b.setEnabled(on)
        self.btn_copy.setEnabled(on)
        if not on and self.edit_set == "B":
            self.set_edit_set("A")
        for k in ("pB", "vB", "outB"):
            self.c[k].setVisible(on)
        self.reset()

    def copy_a_to_b(self):
        self.gains["B"] = self.gains["A"].copy()
        self.sims["B"].gains = self.gains["B"]
        if self.edit_set == "B":
            self._load_gain_widgets()
        self.update_theory()

    def set_critical_damping(self):
        g = self.gains[self.edit_set]
        kd = max(0.0, 2 * math.sqrt(max(g.kp, 0.0) * self.plant.J_total) - self.plant.b)
        self.r_kd.setValue(min(kd, self.r_kd.hi), emit=True)

    def toggle_step(self):
        amp = self.spn_step.value()
        new = 0.0 if abs(self.target.p_des - amp) < 1e-9 else amp
        self.r_pdes.setValue(new, emit=True)

    def apply_disturbance(self):
        for k in self._active():
            self.sims[k].add_pulse(self.r_dist.value(), self.r_distT.value())
        if not self.running:
            self.start()

    # drag --------------------------------------------------------------
    def _drag_fn(self, sim: JointSim):
        def f(t, p, v):
            if self.drag_angle is None:
                return 0.0
            e = wrap_angle(self.drag_angle - p)
            d = 2 * 0.5 * math.sqrt(self.drag_k * sim.plant.J_total)
            return self.drag_k * e - d * v
        return f

    def _drag_start(self, ang):
        self.drag_angle = ang
        for k in "AB":
            self.sims[k].ext_fn = self._drag_fn(self.sims[k])
        if not self.running:
            self.start()

    def _drag_move(self, ang):
        self.drag_angle = ang

    def _drag_end(self):
        self.drag_angle = None
        for k in "AB":
            self.sims[k].ext_fn = None

    # run control ---------------------------------------------------------
    def _active(self):
        return ("A", "B") if self.compare else ("A",)

    def start(self):
        self.running = True
        self.clock.restart()
        self.btn_run.setText("暂停")

    def pause(self):
        self.running = False
        self.btn_run.setText("开始")

    def toggle_run(self):
        self.pause() if self.running else self.start()

    def reset(self):
        for k in "AB":
            s = self.sims[k]
            s.plant, s.gains, s.target_fn = self.plant, self.gains[k], self.target.sample
            s.rng = np.random.default_rng(0)   # 两组使用相同噪声序列 → 公平对比
            s.reset(self.p0, 0.0)
            if self.drag_angle is None:
                s.ext_fn = None
            self.bufs[k].clear()
        self.mark_step()
        self.update_theory()
        self.refresh_plots()
        self.refresh_arm()
        self.refresh_metrics()

    def mark_step(self):
        """记录一次阶跃事件（时刻与初值），之后的指标都相对它计算。"""
        self.step_info = {k: (self.sims[k].t, self.sims[k].p) for k in "AB"}

    def apply_preset(self, key: str):
        pr = PRESET_BY_KEY[key]
        self.current_preset = pr
        self.plant = pr.make_plant()
        self.target = pr.make_target()
        self.gains = {"A": pr.make_gains_a(), "B": pr.make_gains_b()}
        self.p0 = pr.p0
        for i in range(self.lst.count()):
            if self.lst.item(i).data(Qt.UserRole) == key:
                self.lst.setCurrentRow(i)
        self.txt.setHtml(pr.explain)
        self.edit_set = "A"
        self.set_compare(pr.compare)       # 内部会 reset
        self.set_edit_set("A")
        self._load_all_widgets()
        self.reset()
        self.start()

    # ============================================================== loop
    def advance(self, sim_seconds: float):
        """推进仿真并写入缓冲（供定时器和测试调用）。"""
        for k in self._active():
            logs = self.sims[k].advance(sim_seconds)
            self.bufs[k].extend(logs)
        if not self.compare:   # B 不运行时保持与 A 同步的时钟
            self.sims["B"].t = self.sims["A"].t

    def _on_frame(self):
        if self.running:
            dt = self.clock.restart() / 1000.0
            self.advance(min(dt * self.speed, MAX_SIM_PER_FRAME))
            self.refresh_plots()
            self.refresh_arm()
            self._frame += 1
            if self._frame % 12 == 0:
                self.refresh_metrics()
        elif self.drag_angle is not None:
            self.refresh_arm()

    def refresh_arm(self):
        a = self.sims["A"].last
        b = self.sims["B"].last if self.compare else None
        sa = self.sims["A"]
        self.arm.set_state(sa.p, a.get("p_des", self.target.p_des), a.get("tau_out", 0.0),
                           self.sims["B"].p if self.compare else None, b.get("tau_out", 0.0) if b else 0.0,
                           self.plant.gravity, self.plant.m, self.plant.tau_max, a.get("tau_ext", 0.0))
        self.lbl_time.setText(f"t = {sa.t:8.3f} s   {'运行中' if self.running else '已暂停'}")

    def refresh_plots(self):
        t_now = self.sims["A"].t
        t_min = t_now - self.window_s
        A = self.bufs["A"].view(t_min)
        t = A["t"]
        self.c["p_des"].setData(t, A["p_des"])
        self.c["pA"].setData(t, A["p"])
        self.c["v_des"].setData(t, A["v_des"])
        self.c["vA"].setData(t, A["v"])
        self.c["kp"].setData(t, A["tau_kp"])
        self.c["kd"].setData(t, A["tau_kd"])
        self.c["ff"].setData(t, A["tau_ff"])
        self.c["cmd"].setData(t, A["tau_cmd"])
        self.c["outA"].setData(t, A["tau_out"])
        self.c["ext"].setData(t, A["tau_ext"])
        if self.compare:
            B = self.bufs["B"].view(t_min)
            self.c["pB"].setData(B["t"], B["p"])
            self.c["vB"].setData(B["t"], B["v"])
            self.c["outB"].setData(B["t"], B["tau_out"])
        tm = self.plant.tau_max
        self.lim_hi.setPos(tm)
        self.lim_lo.setPos(-tm)
        self.lim_hi.setVisible(tm > 0 and tm < 1e3)
        self.lim_lo.setVisible(tm > 0 and tm < 1e3)
        self.pp.setXRange(max(0.0, t_min), max(self.window_s, t_now), padding=0)
        # 力矩图 y 轴：围绕数据自适应，但不被限幅线撑大
        if t.size:
            lo = float(min(A["tau_out"].min(), A["tau_cmd"].min(), A["tau_kp"].min(), A["tau_kd"].min(), A["tau_ff"].min()))
            hi = float(max(A["tau_out"].max(), A["tau_cmd"].max(), A["tau_kp"].max(), A["tau_kd"].max(), A["tau_ff"].max()))
            if self.compare and len(self.bufs["B"]):
                B = self.bufs["B"].view(t_min)
                lo, hi = min(lo, float(B["tau_out"].min())), max(hi, float(B["tau_out"].max()))
            span = max(hi - lo, 0.2)
            self.pt.setYRange(lo - 0.08 * span, hi + 0.08 * span, padding=0)

    def update_theory(self):
        for col, k in enumerate("AB"):
            if k == "B" and not self.compare:
                vals = ["—"] * 8
            else:
                th = theory(self.plant, self.gains[k], self.target.p_des)
                z = th["zeta"]
                vals = [fmt(th["wn"], ".2f", " rad/s"),
                        fmt(th["wn"] / (2 * math.pi) if th["wn"] else None, ".2f", " Hz"),
                        fmt(z, ".3f") + ("  欠阻尼" if z is not None and z < 1 else ("  过阻尼" if z and z > 1 else "")),
                        fmt(th["overshoot"], ".1f", " %"),
                        fmt(th["ts"], ".3f", " s"),
                        (fmt(th["ss_err_gravity"], ".4f", " rad") if self.plant.gravity else "无重力"),
                        fmt(th["wn_ts"], ".3f") + ("  (偏大)" if th["wn_ts"] and th["wn_ts"] > 0.2 else ""),
                        fmt(th["J_total"], ".4f", " kg·m²")]
            for r, s in enumerate(vals):
                self.tbl_theory.item(r, col).setText(s)
                self.tbl_theory.item(r, col).setForeground(QColor(COLOR_A if k == "A" else COLOR_B))

    def compute_metrics(self, k: str):
        t0, y0 = self.step_info.get(k, (0.0, 0.0))
        d = self.bufs[k].view(t0)
        if d["t"].size < 20:
            return None
        return step_metrics(d["t"], d["p"], self.target.p_des, y0=y0, t0=t0)

    def refresh_metrics(self):
        if self.target.kind != "const":
            for r in range(5):
                for c in range(2):
                    self.tbl_metrics.item(r, c).setText("—")
            self.lbl_metric_note.setText("指标仅针对“常值/阶跃”目标计算。")
            return
        t0 = self.step_info.get("A", (0.0, 0.0))[0]
        self.lbl_metric_note.setText(f"自 t={t0:.2f} s 的阶跃起算；终值取窗口末段均值（实时估计，等响应稳定后读数最准）。")
        for col, k in enumerate("AB"):
            m = self.compute_metrics(k) if (k == "A" or self.compare) else None
            if m is None:
                vals = ["—"] * 5
            elif m.overshoot is None:      # 没有实际位移（例如目标与初值相同）
                vals = ["无阶跃", "—", "—", fmt(m.ss_error, ".4f", " rad"), fmt(m.y_final, ".4f", " rad")]
            else:
                vals = [fmt(m.overshoot, ".1f", " %"), fmt(m.rise_time, ".3f", " s"),
                        fmt(m.settling_time, ".3f", " s") if m.settling_time is not None else "未稳定",
                        fmt(m.ss_error, ".4f", " rad"), fmt(m.y_final, ".4f", " rad")]
            for r, s in enumerate(vals):
                self.tbl_metrics.item(r, col).setText(s)
                self.tbl_metrics.item(r, col).setForeground(QColor(COLOR_A if k == "A" else COLOR_B))

    def fit_tables(self):
        for t in (self.tbl_theory, self.tbl_metrics):
            h = t.horizontalHeader().height() + t.verticalHeader().length() + 2 * t.frameWidth() + 2
            t.setFixedHeight(h)

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self.fit_tables)

    def closeEvent(self, e):
        self.timer.stop()
        super().closeEvent(e)
