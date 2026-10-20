"""单关节 MIT 控制仿真核心（纯 Python，无 Qt 依赖，可单独测试）。

控制律（MIT 模式 / 阻抗控制）::

    tau = Kp * (p_des - p) + Kd * (v_des - v) + tau_ff

被控对象（单关节 + 摆杆负载）::

    J_tot * a = sat(tau) - b * v - tau_c * sign(v) + tau_g(p) + tau_ext
    J_tot     = J + m * l^2                      (转子/关节惯量 + 末端点质量)
    tau_g(p)  = -m * g * l * cos(p)               (角度从水平向右起算，逆时针为正)

控制器按控制周期 Ts 采样（零阶保持 ZOH），物理以更细的固定步长（默认 1 kHz）
用 RK4 积分；Ts 总是物理步长的整数倍。
库仑摩擦采用 Karnopp 型静/动摩擦：速度过零且合力小于 tau_c 时关节被“粘住”。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

G = 9.81
PHYS_DT = 1e-3  # 默认物理积分步长 1 ms

LOG_FIELDS = ("t", "p", "v", "p_meas", "v_meas", "p_des", "v_des",
              "tau_kp", "tau_kd", "tau_ff", "tau_cmd", "tau_out", "tau_ext")


@dataclass
class PlantParams:
    J: float = 0.01          # 关节自身惯量 kg·m²
    b: float = 0.005         # 粘性摩擦系数 N·m·s/rad
    tau_c: float = 0.0       # 库仑摩擦 N·m
    m: float = 0.0           # 末端负载质量 kg
    l: float = 0.2           # 摆杆长度 m
    gravity: bool = False    # 是否考虑重力
    g: float = G
    tau_max: float = 10.0    # 力矩限幅 N·m（<=0 表示不限幅）
    ctrl_period: float = 0.001  # 控制周期 s
    noise_p: float = 0.0     # 位置传感器噪声标准差 rad
    noise_v: float = 0.0     # 速度传感器噪声标准差 rad/s

    @property
    def J_total(self) -> float:
        return self.J + self.m * self.l ** 2

    @property
    def mgl(self) -> float:
        return self.m * self.g * self.l if self.gravity else 0.0

    def gravity_torque(self, p: float) -> float:
        """重力对关节产生的力矩（使摆杆下垂方向）。"""
        if not self.gravity or self.m == 0.0:
            return 0.0
        return -self.m * self.g * self.l * math.cos(p)

    def copy(self, **kw) -> "PlantParams":
        return replace(self, **kw)


@dataclass
class MITGains:
    kp: float = 10.0
    kd: float = 0.5
    tau_ff: float = 0.0
    auto_gravity_ff: bool = False  # 自动前馈 tau_ff += m g l cos(p_des)

    def copy(self, **kw) -> "MITGains":
        return replace(self, **kw)


def mit_torque(kp: float, kd: float, p_des: float, v_des: float, tau_ff: float,
               p: float, v: float) -> Tuple[float, float, float]:
    """返回 (Kp 项, Kd 项, 总力矩)。"""
    t_kp = kp * (p_des - p)
    t_kd = kd * (v_des - v)
    return t_kp, t_kd, t_kp + t_kd + tau_ff


def saturate(tau: float, tau_max: float) -> float:
    if tau_max is None or tau_max <= 0:
        return tau
    return max(-tau_max, min(tau_max, tau))


def theory(plant: PlantParams, gains: MITGains, p_des: float = 0.0) -> Dict[str, Optional[float]]:
    """线性化后的二阶系统理论量：J s² + (Kd+b) s + Kp。"""
    J = plant.J_total
    kp, c = gains.kp, gains.kd + plant.b
    out: Dict[str, Optional[float]] = dict(J_total=J, wn=None, zeta=None, wd=None, overshoot=None,
                                           ts=None, ss_err_gravity=0.0, wn_ts=None)
    if kp > 0 and J > 0:
        wn = math.sqrt(kp / J)
        zeta = c / (2.0 * math.sqrt(kp * J))
        out.update(wn=wn, zeta=zeta, wn_ts=wn * plant.ctrl_period)
        if zeta < 1.0:
            out["wd"] = wn * math.sqrt(1 - zeta ** 2)
            out["overshoot"] = 100.0 * math.exp(-zeta * math.pi / math.sqrt(1 - zeta ** 2)) if zeta > 0 else 100.0
        if zeta > 0:
            out["ts"] = 4.0 / (zeta * wn) if zeta < 1 else None
        # 重力导致的稳态误差（小误差近似）：Kp*e = m g l cos(p) - tau_ff
        ff = gains.tau_ff + (plant.mgl * math.cos(p_des) if gains.auto_gravity_ff else 0.0)
        out["ss_err_gravity"] = (plant.mgl * math.cos(p_des) - ff) / kp if plant.gravity else 0.0
    return out


@dataclass
class Pulse:
    t0: float
    duration: float
    torque: float


TargetFn = Callable[[float], Tuple[float, float]]
ExtFn = Callable[[float, float, float], float]


class JointSim:
    """单关节仿真器。

    target_fn(t) -> (p_des, v_des)；ext_fn(t, p, v) -> 外部扰动力矩（例如鼠标拖拽弹簧）。
    """

    def __init__(self, plant: Optional[PlantParams] = None, gains: Optional[MITGains] = None,
                 target_fn: Optional[TargetFn] = None, p0: float = 0.0, v0: float = 0.0,
                 seed: Optional[int] = 0, phys_dt: float = PHYS_DT):
        self.plant = plant or PlantParams()
        self.gains = gains or MITGains()
        self.target_fn: TargetFn = target_fn or (lambda t: (0.0, 0.0))
        self.ext_fn: Optional[ExtFn] = None
        self.phys_dt_nominal = phys_dt
        self.rng = np.random.default_rng(seed)
        self.pulses: List[Pulse] = []
        self.reset(p0, v0)

    # ------------------------------------------------------------------ state
    def reset(self, p0: float = 0.0, v0: float = 0.0) -> None:
        self.t = 0.0
        self.p = float(p0)
        self.v = float(v0)
        self._acc = 0.0          # 未满一个控制周期的剩余时间
        self._tau_hold = 0.0     # ZOH 保持的输出力矩
        self.pulses.clear()
        self.last: Dict[str, float] = {k: 0.0 for k in LOG_FIELDS}
        self.last.update(t=0.0, p=self.p, v=self.v)

    def add_pulse(self, torque: float, duration: float = 0.1, t0: Optional[float] = None) -> None:
        """施加一个矩形扰动力矩脉冲。"""
        self.pulses.append(Pulse(self.t if t0 is None else t0, duration, torque))

    def substeps(self) -> Tuple[int, float]:
        ts = max(1e-5, float(self.plant.ctrl_period))
        n = max(1, int(round(ts / self.phys_dt_nominal)))
        return n, ts / n

    # ------------------------------------------------------------ dynamics
    def _pulse_torque(self, t: float) -> float:
        return sum(pl.torque for pl in self.pulses if pl.t0 <= t < pl.t0 + pl.duration)

    def _ext(self, t: float, p: float, v: float) -> float:
        tau = self._pulse_torque(t)
        if self.ext_fn is not None:
            tau += self.ext_fn(t, p, v)
        return tau

    def _drive(self, t: float, p: float, v: float, tau_m: float) -> float:
        """除库仑摩擦外的合力矩。"""
        pl = self.plant
        return tau_m - pl.b * v + pl.gravity_torque(p) + self._ext(t, p, v)

    def _accel(self, t: float, p: float, v: float, tau_m: float) -> float:
        pl = self.plant
        f = self._drive(t, p, v, tau_m)
        if pl.tau_c > 0:
            if v > 0:
                f -= pl.tau_c
            elif v < 0:
                f += pl.tau_c
            elif abs(f) <= pl.tau_c:   # 静摩擦：粘住
                f = 0.0
            else:                      # 克服静摩擦开始滑动
                f -= math.copysign(pl.tau_c, f)
        return f / pl.J_total

    def _rk4(self, dt: float, tau_m: float) -> None:
        t, p, v = self.t, self.p, self.v
        k1p, k1v = v, self._accel(t, p, v, tau_m)
        k2p, k2v = v + 0.5 * dt * k1v, self._accel(t + 0.5 * dt, p + 0.5 * dt * k1p, v + 0.5 * dt * k1v, tau_m)
        k3p, k3v = v + 0.5 * dt * k2v, self._accel(t + 0.5 * dt, p + 0.5 * dt * k2p, v + 0.5 * dt * k2v, tau_m)
        k4p, k4v = v + dt * k3v, self._accel(t + dt, p + dt * k3p, v + dt * k3v, tau_m)
        p1 = p + dt / 6.0 * (k1p + 2 * k2p + 2 * k3p + k4p)
        v1 = v + dt / 6.0 * (k1v + 2 * k2v + 2 * k3v + k4v)
        tc = self.plant.tau_c
        if tc > 0 and v != 0.0 and (v1 == 0.0 or (v1 > 0) != (v > 0)):
            # 速度过零（Karnopp 型处理）：若合力不足以克服静摩擦则粘住
            if abs(self._drive(t + dt, p1, 0.0, tau_m)) <= tc:
                v1 = 0.0
        self.p, self.v, self.t = p1, v1, t + dt

    # ------------------------------------------------------------ control
    def control_tick(self) -> Dict[str, float]:
        """在当前时刻采样传感器、计算 MIT 力矩并保持（ZOH）。"""
        pl, g = self.plant, self.gains
        p_m = self.p + (self.rng.normal(0.0, pl.noise_p) if pl.noise_p > 0 else 0.0)
        v_m = self.v + (self.rng.normal(0.0, pl.noise_v) if pl.noise_v > 0 else 0.0)
        p_des, v_des = self.target_fn(self.t)
        tau_ff = g.tau_ff + (pl.mgl * math.cos(p_des) if g.auto_gravity_ff else 0.0)
        t_kp, t_kd, tau = mit_torque(g.kp, g.kd, p_des, v_des, tau_ff, p_m, v_m)
        out = saturate(tau, pl.tau_max)
        self._tau_hold = out
        rec = dict(t=self.t, p=self.p, v=self.v, p_meas=p_m, v_meas=v_m, p_des=p_des, v_des=v_des,
                   tau_kp=t_kp, tau_kd=t_kd, tau_ff=tau_ff, tau_cmd=tau, tau_out=out,
                   tau_ext=self._ext(self.t, self.p, self.v))
        self.last = rec
        return rec

    def advance(self, duration: float) -> Dict[str, List[float]]:
        """推进仿真 duration 秒（不足一个控制周期的部分累积到下次）。

        返回本次新产生的控制周期采样记录（每个字段一个列表）。
        """
        logs: Dict[str, List[float]] = {k: [] for k in LOG_FIELDS}
        n, dt = self.substeps()
        ts = n * dt
        self._acc += max(0.0, duration)
        while self._acc >= ts - 1e-12:
            rec = self.control_tick()
            for k in LOG_FIELDS:
                logs[k].append(rec[k])
            for _ in range(n):
                self._rk4(dt, self._tau_hold)
            self._acc -= ts
        if self.pulses:
            self.pulses = [pl for pl in self.pulses if pl.t0 + pl.duration > self.t]
        return logs

    def run(self, duration: float) -> Dict[str, np.ndarray]:
        """便捷函数：推进并以 numpy 数组返回整段记录（用于测试/离线分析）。"""
        logs = self.advance(duration)
        return {k: np.asarray(v, dtype=float) for k, v in logs.items()}


def wrap_angle(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi
