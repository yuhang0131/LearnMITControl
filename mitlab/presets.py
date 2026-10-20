"""教学预设：每个预设包含被控对象、A/B 两组增益、目标与中文讲解。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .sim import MITGains, PlantParams
from .targets import Target


@dataclass
class Preset:
    key: str
    name: str
    explain: str                      # HTML（中文）
    plant: Dict = field(default_factory=dict)
    gains_a: Dict = field(default_factory=dict)
    gains_b: Optional[Dict] = None    # 不为 None 时自动开启 A/B 对比
    target: Dict = field(default_factory=dict)
    p0: float = 0.0
    duration_hint: float = 5.0        # 建议观察时长 s

    @property
    def compare(self) -> bool:
        return self.gains_b is not None

    def make_plant(self) -> PlantParams:
        return PlantParams(**self.plant)

    def make_gains_a(self) -> MITGains:
        return MITGains(**self.gains_a)

    def make_gains_b(self) -> MITGains:
        return MITGains(**(self.gains_b if self.gains_b is not None else self.gains_a))

    def make_target(self) -> Target:
        return Target(**self.target)


_LAW = "<p style='color:#545C68'>控制律：τ = K<sub>p</sub>(p<sub>des</sub>−p) + K<sub>d</sub>(v<sub>des</sub>−v) + τ<sub>ff</sub></p>"

PRESETS: List[Preset] = [
    Preset(
        "spring", "01 纯刚度：弹簧",
        "<h3>纯刚度（K<sub>d</sub>=0）——一根“虚拟弹簧”</h3>" + _LAW +
        "<p>只保留 K<sub>p</sub> 项时，电机输出 τ = K<sub>p</sub>(p<sub>des</sub>−p)，"
        "效果等同于在关节和目标位置之间挂了一根<b>刚度为 K<sub>p</sub> 的扭簧</b>。</p>"
        "<p>系统方程 J·p̈ + b·ṗ + K<sub>p</sub>·p = K<sub>p</sub>·p<sub>des</sub>，"
        "几乎没有阻尼（只有很小的粘性摩擦 b），所以摆杆会围绕目标<b>长时间来回振荡</b>。</p>"
        "<ul><li>振荡角频率 ω<sub>n</sub> = √(K<sub>p</sub>/J)，周期 T = 2π/ω<sub>n</sub>。</li>"
        "<li>试试把 K<sub>p</sub> 调到 4 倍：频率变为 2 倍（周期减半）。</li>"
        "<li>把惯量 J 调大：振荡变慢。</li></ul>"
        "<p><b>结论：</b>K<sub>p</sub> 决定“有多硬”和“多快”，但单靠 K<sub>p</sub> 停不下来。</p>",
        plant=dict(J=0.01, b=0.0005, tau_max=10.0),
        gains_a=dict(kp=2.0, kd=0.0),
        target=dict(kind="const", p_des=1.0)),
    Preset(
        "damping", "02 纯阻尼：速度控制",
        "<h3>纯阻尼（K<sub>p</sub>=0）——速度控制</h3>" + _LAW +
        "<p>K<sub>p</sub>=0 时 τ = K<sub>d</sub>(v<sub>des</sub>−v) + τ<sub>ff</sub>，"
        "相当于一个以 v<sub>des</sub> 运动的“粘滞阻尼器”拖着关节走，这就是 MIT 模式下的<b>速度模式</b>。</p>"
        "<ul><li>稳态速度 v = K<sub>d</sub>·v<sub>des</sub>/(K<sub>d</sub>+b)，b 越小越接近 v<sub>des</sub>。</li>"
        "<li>时间常数 τ<sub>c</sub> = J/(K<sub>d</sub>+b)：K<sub>d</sub> 越大速度建立越快。</li>"
        "<li>位置不受约束，会一直转下去（位置曲线是一条斜线）。</li>"
        "<li>把 v<sub>des</sub> 设为 0：关节变成一个“阻尼器”，用鼠标拖动摆杆能感到“黏稠”。</li></ul>",
        plant=dict(J=0.01, b=0.005),
        gains_a=dict(kp=0.0, kd=0.2),
        target=dict(kind="const", p_des=0.0, v_des=2.0)),
    Preset(
        "tracking", "03 位置跟踪：轨迹",
        "<h3>位置跟踪（K<sub>p</sub> + K<sub>d</sub> + 速度前馈）</h3>" + _LAW +
        "<p>目标是一条<b>最小加加速度（min-jerk）往返轨迹</b>，并把轨迹的导数作为 v<sub>des</sub> 输入。</p>"
        "<ul><li>阻尼比 ζ≈0.9，接近临界阻尼：跟踪平滑、几乎无超调。</li>"
        "<li>取消勾选“v<sub>des</sub> 取轨迹导数”，K<sub>d</sub> 项会变成“刹车”，跟踪滞后明显增大。</li>"
        "<li>换成三角波：速度突变处会出现跟踪误差尖峰。</li></ul>"
        "<p><b>结论：</b>v<sub>des</sub> 前馈让 K<sub>d</sub> 只惩罚“速度误差”而非速度本身。</p>",
        plant=dict(J=0.01, b=0.005),
        gains_a=dict(kp=20.0, kd=0.8),
        target=dict(kind="traj", traj_kind="minjerk", traj_amp=1.5, traj_T=1.0, traj_hold=0.5, use_traj_v=True)),
    Preset(
        "impedance", "04 阻抗 / 柔顺控制",
        "<h3>阻抗 / 柔顺控制（低 K<sub>p</sub>）</h3>" + _LAW +
        "<p>MIT 控制本质上是<b>阻抗控制</b>：K<sub>p</sub> 是虚拟刚度、K<sub>d</sub> 是虚拟阻尼。"
        "把 K<sub>p</sub> 设得很低，关节就会变“软”，外力能轻易推开它，撤掉外力后又会回到目标。</p>"
        "<ul><li>点击<b>“施加扰动”</b>按钮给关节一个力矩脉冲；</li>"
        "<li>或直接<b>用鼠标拖拽动画中的摆杆</b>（鼠标与摆杆之间是一根虚拟弹簧）；</li>"
        "<li>静态偏移 Δp ≈ τ<sub>ext</sub>/K<sub>p</sub>：K<sub>p</sub> 越小越“顺从”。</li></ul>"
        "<p>这正是足式机器人腿部关节常用的做法：低刚度吸收落地冲击。</p>",
        plant=dict(J=0.01, b=0.005),
        gains_a=dict(kp=1.0, kd=0.12),
        target=dict(kind="const", p_des=0.5)),
    Preset(
        "gravity_sag", "05 重力下垂（无前馈）",
        "<h3>重力下垂：稳态误差 = m·g·l·cos(p)/K<sub>p</sub></h3>" + _LAW +
        "<p>开启重力，末端挂 0.5 kg、臂长 0.2 m 的负载，目标是水平位置 p<sub>des</sub>=0。</p>"
        "<p>稳态时 K<sub>p</sub>·e = m·g·l·cos(p)，所以关节必须<b>“下垂”一个角度 e</b> 才能让弹簧力矩托住负载：</p>"
        "<p style='text-align:center'>e ≈ m g l cos(p<sub>des</sub>) / K<sub>p</sub> = 0.981/10 ≈ 0.098 rad ≈ 5.6°</p>"
        "<ul><li>把 K<sub>p</sub> 加大：下垂减小，但永远不为 0（P 控制的固有稳态误差）。</li>"
        "<li>下一个预设用 τ<sub>ff</sub> 前馈消除它。</li></ul>",
        plant=dict(J=0.01, b=0.005, m=0.5, l=0.2, gravity=True),
        gains_a=dict(kp=10.0, kd=0.6),
        target=dict(kind="const", p_des=0.0)),
    Preset(
        "gravity_ff", "06 重力补偿（τ_ff 前馈）",
        "<h3>重力补偿：τ<sub>ff</sub> = m·g·l·cos(p<sub>des</sub>)</h3>" + _LAW +
        "<p>与上一预设相同的负载，但勾选了<b>“自动重力前馈”</b>：每个控制周期把 "
        "τ<sub>ff</sub> = m g l cos(p<sub>des</sub>) 加到输出力矩上。</p>"
        "<p>重力由前馈“托住”，K<sub>p</sub> 只需处理剩余误差，稳态误差 → 0，"
        "而且<b>不需要提高刚度</b>——关节依然可以保持柔顺。</p>"
        "<ul><li>试试把目标改为正弦：前馈随 cos(p<sub>des</sub>) 实时变化。</li>"
        "<li>负载估计不准（改 m 但前馈按旧值）时会残留误差：可手动调 τ<sub>ff</sub> 体会。</li></ul>",
        plant=dict(J=0.01, b=0.005, m=0.5, l=0.2, gravity=True),
        gains_a=dict(kp=10.0, kd=0.6, auto_gravity_ff=True),
        target=dict(kind="const", p_des=0.0)),
    Preset(
        "gravity_ab", "07 对比：有/无重力补偿",
        "<h3>A/B 对比：重力补偿</h3>" + _LAW +
        "<p><span style='color:#2563EB'><b>A（蓝）</b></span>：无前馈，下垂约 5.6°；"
        "<span style='color:#E8590C'><b>B（橙）</b></span>：自动重力前馈，稳在水平。</p>"
        "<p>两组共用同一被控对象和目标，曲线叠加显示，动画中两根摆杆颜色不同。</p>",
        plant=dict(J=0.01, b=0.005, m=0.5, l=0.2, gravity=True),
        gains_a=dict(kp=10.0, kd=0.6),
        gains_b=dict(kp=10.0, kd=0.6, auto_gravity_ff=True),
        target=dict(kind="const", p_des=0.0)),
    Preset(
        "kd_small", "08 对比：K_d 过小振荡",
        "<h3>K<sub>d</sub> 过小：欠阻尼振荡</h3>" + _LAW +
        "<p>阻尼比 ζ = (K<sub>d</sub>+b) / (2√(K<sub>p</sub>J))。</p>"
        "<ul><li><span style='color:#2563EB'><b>A</b></span>：K<sub>d</sub>=0.05，ζ≈0.06，超调约 80%，振荡很久；</li>"
        "<li><span style='color:#E8590C'><b>B</b></span>：K<sub>d</sub>=0.85，ζ≈0.96，接近临界阻尼，几乎无超调。</li></ul>"
        "<p>经验：ζ≈0.7 时上升快且超调约 5%；ζ≥1 无超调但更慢。"
        "临界阻尼所需 K<sub>d</sub> ≈ 2√(K<sub>p</sub>J) − b。</p>",
        plant=dict(J=0.01, b=0.005, tau_max=30.0),
        gains_a=dict(kp=20.0, kd=0.05),
        gains_b=dict(kp=20.0, kd=0.85),
        target=dict(kind="const", p_des=1.0)),
    Preset(
        "saturation", "09 力矩饱和",
        "<h3>力矩饱和：大阶跃时线性理论失效</h3>" + _LAW +
        "<p>K<sub>p</sub>=50 时 1.5 rad 的阶跃需要 75 N·m，但电机限幅只有 1.5 N·m。</p>"
        "<ul><li>力矩曲线里 <b>τ<sub>cmd</sub>（指令）</b>远大于 <b>τ<sub>out</sub>（饱和后）</b>；</li>"
        "<li>饱和期间关节以最大加速度运动，响应时间远大于理论 4/(ζω<sub>n</sub>)；</li>"
        "<li>K<sub>d</sub> 项在高速时也会饱和，容易引起超调。把限幅调大对比一下。</li></ul>",
        plant=dict(J=0.01, b=0.005, tau_max=1.5),
        gains_a=dict(kp=50.0, kd=1.4),
        target=dict(kind="const", p_des=1.5)),
    Preset(
        "period", "10 控制周期过长",
        "<h3>控制周期 / 采样延迟</h3>" + _LAW +
        "<p>控制律只在每个控制周期 T<sub>s</sub> 计算一次并保持（零阶保持 ZOH），"
        "相当于引入约 T<sub>s</sub>/2 的延迟。当 ω<sub>n</sub>·T<sub>s</sub> 不够小时，阻尼会被“吃掉”。</p>"
        "<ul><li>这里 T<sub>s</sub>=15 ms、ω<sub>n</sub>≈45 rad/s，连续理论 ζ≈0.35，实际振荡明显更厉害；</li>"
        "<li>把控制周期改回 1 ms 对比；或继续加大到 25 ms 观察失稳。</li>"
        "<li>经验：ω<sub>n</sub>·T<sub>s</sub> &lt; 0.1~0.2 时离散化影响可忽略。</li></ul>",
        plant=dict(J=0.01, b=0.005, ctrl_period=0.015, tau_max=30.0),
        gains_a=dict(kp=20.0, kd=0.3),
        target=dict(kind="const", p_des=1.0)),
    Preset(
        "noise", "11 对比：传感器噪声与 K_d",
        "<h3>传感器噪声：K<sub>d</sub> 放大速度噪声</h3>" + _LAW +
        "<p>速度通常由编码器差分得到，噪声较大。力矩噪声 ≈ K<sub>p</sub>·σ<sub>p</sub> 与 K<sub>d</sub>·σ<sub>v</sub>。</p>"
        "<ul><li><span style='color:#2563EB'><b>A</b></span>：K<sub>d</sub>=0.8，阻尼好但力矩“毛刺”大；</li>"
        "<li><span style='color:#E8590C'><b>B</b></span>：K<sub>d</sub>=0.3，力矩更干净但超调变大。</li></ul>"
        "<p>实际调参就是在阻尼和噪声之间折中（还可对速度做低通滤波）。</p>",
        plant=dict(J=0.01, b=0.005, noise_p=0.002, noise_v=0.3, tau_max=30.0),
        gains_a=dict(kp=20.0, kd=0.8),
        gains_b=dict(kp=20.0, kd=0.3),
        target=dict(kind="const", p_des=1.0)),
    Preset(
        "coulomb", "12 库仑摩擦死区",
        "<h3>库仑摩擦：低刚度时的定位死区</h3>" + _LAW +
        "<p>库仑（静/动）摩擦 τ<sub>c</sub> 与速度方向相反、大小恒定。"
        "当 K<sub>p</sub>·|e| &lt; τ<sub>c</sub> 时弹簧力矩推不动关节，于是停在<b>死区</b>内：</p>"
        "<p style='text-align:center'>|e<sub>ss</sub>| ≤ τ<sub>c</sub>/K<sub>p</sub> = 0.2/2 = 0.1 rad</p>"
        "<ul><li>加大 K<sub>p</sub>：死区缩小；</li><li>也可以用 τ<sub>ff</sub> 做摩擦补偿（需要知道运动方向）。</li></ul>",
        plant=dict(J=0.01, b=0.002, tau_c=0.2),
        gains_a=dict(kp=2.0, kd=0.15),
        target=dict(kind="const", p_des=1.0)),
]

PRESET_BY_KEY = {p.key: p for p in PRESETS}
