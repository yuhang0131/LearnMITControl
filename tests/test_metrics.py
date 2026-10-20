import math

import numpy as np
import pytest

from mitlab.metrics import second_order_step, step_metrics


@pytest.mark.parametrize("zeta,wn", [(0.3, 10.0), (0.5, 10.0), (0.7, 20.0)])
def test_second_order_metrics(zeta, wn):
    t = np.linspace(0, 12 / (zeta * wn), 200001)
    y = second_order_step(t, wn, zeta)
    m = step_metrics(t, y, r=1.0, y_final=1.0)
    assert m.overshoot == pytest.approx(100 * math.exp(-zeta * math.pi / math.sqrt(1 - zeta ** 2)), rel=1e-3)
    assert m.peak_time == pytest.approx(math.pi / (wn * math.sqrt(1 - zeta ** 2)), rel=1e-3)
    # 调节时间：不晚于包络线进入 2% 的时刻，且接近经验公式 4/(zeta wn)
    t_env = -math.log(0.02 * math.sqrt(1 - zeta ** 2)) / (zeta * wn)
    assert m.settling_time <= t_env + 1e-6
    assert m.settling_time == pytest.approx(4 / (zeta * wn), rel=0.3)
    # 上升时间：与数值精确解比较
    i10 = np.argmax(y >= 0.1)
    i90 = np.argmax(y >= 0.9)
    assert m.rise_time == pytest.approx(t[i90] - t[i10], abs=2 * (t[1] - t[0]))
    assert m.ss_error == pytest.approx(0.0, abs=1e-9)


def test_rise_time_known_first_order():
    # 一阶系统 y = 1 - exp(-t/T)：t10-90 = T ln 9
    T = 0.2
    t = np.linspace(0, 3, 30001)
    y = 1 - np.exp(-t / T)
    m = step_metrics(t, y, r=1.0, y_final=1.0)
    assert m.rise_time == pytest.approx(T * math.log(9), rel=1e-3)
    assert m.overshoot == 0.0
    assert m.settling_time == pytest.approx(-T * math.log(0.02), rel=1e-3)


def test_steady_state_error_offset_and_negative_step():
    t = np.linspace(0, 5, 5001)
    y = 2.0 - 1.5 * second_order_step(t, 10, 0.5)   # 从 2.0 到 0.5，向下阶跃
    m = step_metrics(t, y, r=0.4)
    assert m.y_final == pytest.approx(0.5, abs=1e-3)
    assert m.ss_error == pytest.approx(-0.1, abs=1e-3)
    assert m.overshoot == pytest.approx(16.3, abs=0.2)


def test_not_settled_and_degenerate():
    t = np.linspace(0, 1, 1001)
    y = 1.0 + 0.5 * np.cos(2 * np.pi * 3 * t)   # 一直振荡，末尾不在 2% 带内
    assert step_metrics(t, y, r=1.0, y_final=1.0).settling_time is None
    m = step_metrics(t, np.zeros_like(t), r=1.0)
    assert m.overshoot is None and m.ss_error == pytest.approx(1.0)
    assert step_metrics(t[:3], t[:3], r=1.0).overshoot is None
