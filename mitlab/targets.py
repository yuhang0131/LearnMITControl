"""目标指令生成：常值/阶跃、正弦、轨迹（最小加加速度 min-jerk / 梯形 / 三角）。

所有目标都返回 (p_des, v_des)。对正弦和轨迹，若 use_traj_v=True，
v_des 取轨迹的解析导数（速度前馈），否则 v_des 取用户设定值（通常为 0）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Tuple

KINDS = ("const", "sine", "traj")
KIND_NAMES = {"const": "常值 / 阶跃", "sine": "正弦", "traj": "轨迹序列"}
TRAJ_KINDS = ("minjerk", "trapezoid", "triangle")
TRAJ_NAMES = {"minjerk": "最小加加速度 (min-jerk)", "trapezoid": "梯形（往返+停留）", "triangle": "三角波"}


@dataclass
class Target:
    kind: str = "const"
    p_des: float = 0.0          # 常值目标 / 正弦与轨迹的偏置
    v_des: float = 0.0          # 用户设定的速度目标
    sine_amp: float = 0.5
    sine_freq: float = 0.5      # Hz
    traj_kind: str = "minjerk"
    traj_amp: float = 1.0       # 轨迹幅值 rad
    traj_T: float = 1.0         # 单段运动时间 s
    traj_hold: float = 1.0      # 段间停留时间 s
    use_traj_v: bool = True     # 用轨迹导数作为 v_des

    def copy(self, **kw) -> "Target":
        return replace(self, **kw)

    def sample(self, t: float) -> Tuple[float, float]:
        if self.kind == "sine":
            w = 2 * math.pi * self.sine_freq
            p = self.p_des + self.sine_amp * math.sin(w * t)
            dv = self.sine_amp * w * math.cos(w * t)
            return p, (dv if self.use_traj_v else self.v_des)
        if self.kind == "traj":
            p, dv = traj_sample(self.traj_kind, t, self.traj_amp, self.traj_T, self.traj_hold)
            return self.p_des + p, (dv if self.use_traj_v else self.v_des)
        return self.p_des, self.v_des

    __call__ = sample


def min_jerk(s: float) -> Tuple[float, float]:
    """归一化最小加加速度曲线，s∈[0,1]：返回 (位置比例, 对 s 的导数)。"""
    s = min(1.0, max(0.0, s))
    return 10 * s ** 3 - 15 * s ** 4 + 6 * s ** 5, 30 * s ** 2 - 60 * s ** 3 + 30 * s ** 4


def traj_sample(kind: str, t: float, amp: float, T: float, hold: float) -> Tuple[float, float]:
    """周期轨迹：0 → amp → 0 往返。返回相对偏置的 (位置, 速度)。"""
    T = max(1e-3, T)
    hold = max(0.0, hold)
    if kind == "triangle":
        period = 2 * T
        ph = t % period
        if ph < T:
            return amp * ph / T, amp / T
        return amp * (2 - ph / T), -amp / T
    period = 2 * (T + hold)
    ph = t % period
    if kind == "trapezoid":
        # 梯形速度：加速 25%，匀速 50%，减速 25%
        def trap(s: float) -> Tuple[float, float]:
            a = 0.25
            vmax = 1.0 / (1 - a)
            if s < a:
                return 0.5 * vmax / a * s * s, vmax * s / a
            if s < 1 - a:
                return 0.5 * vmax * a + vmax * (s - a), vmax
            r = 1 - s
            return 1 - 0.5 * vmax / a * r * r, vmax * r / a
        f = trap
    else:
        f = min_jerk
    if ph < hold:
        return 0.0, 0.0
    if ph < hold + T:
        x, dx = f((ph - hold) / T)
        return amp * x, amp * dx / T
    if ph < 2 * hold + T:
        return amp, 0.0
    x, dx = f((ph - 2 * hold - T) / T)
    return amp * (1 - x), -amp * dx / T
