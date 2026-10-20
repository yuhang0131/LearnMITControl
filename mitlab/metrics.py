"""阶跃响应指标：超调量、上升时间 (10%→90%)、调节时间 (±2%)、稳态误差。

约定（与经典控制教材一致）：
* 终值 y_final 取响应末尾一段的平均值（也可显式传入）；
* 超调量、上升时间、调节带都以“实际阶跃幅度” |y_final - y0| 为基准；
* 稳态误差 = 目标值 r - y_final（例如重力下垂时不为 0）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class StepMetrics:
    overshoot: Optional[float]      # %
    rise_time: Optional[float]      # s
    settling_time: Optional[float]  # s（None 表示窗口内尚未稳定）
    ss_error: Optional[float]       # rad
    y_final: Optional[float]
    peak_time: Optional[float] = None


def _cross_time(t: np.ndarray, x: np.ndarray, level: float) -> Optional[float]:
    idx = np.nonzero(x >= level)[0]
    if idx.size == 0:
        return None
    i = int(idx[0])
    if i == 0:
        return float(t[0])
    x0, x1 = x[i - 1], x[i]
    if x1 == x0:
        return float(t[i])
    return float(t[i - 1] + (level - x0) / (x1 - x0) * (t[i] - t[i - 1]))


def step_metrics(t, y, r: float, y0: Optional[float] = None, t0: Optional[float] = None,
                 y_final: Optional[float] = None, band: float = 0.02,
                 tail_frac: float = 0.05) -> StepMetrics:
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    none = StepMetrics(None, None, None, None, None)
    if t.size < 5:
        return none
    if t0 is None:
        t0 = float(t[0])
    if y0 is None:
        y0 = float(y[0])
    if y_final is None:
        n_tail = max(1, int(t.size * tail_frac))
        y_final = float(np.mean(y[-n_tail:]))
    delta = y_final - y0
    ss_err = float(r - y_final)
    if abs(delta) < 1e-9:
        return StepMetrics(None, None, None, ss_err, y_final)
    sgn = 1.0 if delta > 0 else -1.0
    x = sgn * (y - y0) / abs(delta)          # 归一化：0 → 1
    ipk = int(np.argmax(x))
    overshoot = max(0.0, float(x[ipk] - 1.0) * 100.0)
    t10 = _cross_time(t, x, 0.1)
    t90 = _cross_time(t, x, 0.9)
    rise = (t90 - t10) if (t10 is not None and t90 is not None) else None
    outside = np.nonzero(np.abs(x - 1.0) > band)[0]
    if outside.size == 0:
        ts = 0.0
    elif int(outside[-1]) >= t.size - 1:
        ts = None
    else:
        ts = float(t[int(outside[-1]) + 1] - t0)
    return StepMetrics(overshoot, rise, ts, ss_err, y_final, float(t[ipk] - t0))


def second_order_step(t, wn: float, zeta: float):
    """标准二阶系统单位阶跃响应（0<zeta<1 欠阻尼；zeta>=1 时数值近似）。"""
    t = np.asarray(t, dtype=float)
    if zeta < 1:
        wd = wn * np.sqrt(1 - zeta ** 2)
        phi = np.arccos(zeta)
        return 1 - np.exp(-zeta * wn * t) / np.sqrt(1 - zeta ** 2) * np.sin(wd * t + phi)
    if zeta == 1:
        return 1 - np.exp(-wn * t) * (1 + wn * t)
    s1 = -wn * (zeta - np.sqrt(zeta ** 2 - 1))
    s2 = -wn * (zeta + np.sqrt(zeta ** 2 - 1))
    return 1 + (s2 * np.exp(s1 * t) - s1 * np.exp(s2 * t)) / (s1 - s2)
