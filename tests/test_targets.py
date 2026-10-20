import math

import numpy as np
import pytest

from mitlab.targets import TRAJ_KINDS, Target, min_jerk


def test_const_and_sine():
    tg = Target(kind="const", p_des=0.7, v_des=0.2)
    assert tg.sample(3.0) == (0.7, 0.2)
    s = Target(kind="sine", p_des=0.1, sine_amp=0.5, sine_freq=1.0)
    p, v = s.sample(0.25)
    assert p == pytest.approx(0.6) and v == pytest.approx(0.0, abs=1e-9)
    s.use_traj_v = False
    s.v_des = 0.3
    assert s.sample(0.0)[1] == 0.3


def test_min_jerk_boundary():
    assert min_jerk(0) == (0, 0)
    x, dx = min_jerk(1)
    assert x == pytest.approx(1) and dx == pytest.approx(0)
    assert min_jerk(0.5)[0] == pytest.approx(0.5)


@pytest.mark.parametrize("kind", TRAJ_KINDS)
def test_traj_velocity_is_derivative(kind):
    tg = Target(kind="traj", traj_kind=kind, traj_amp=1.2, traj_T=0.8, traj_hold=0.4)
    t = np.linspace(0, 5, 50001)
    pv = np.array([tg.sample(x) for x in t])
    dp = np.gradient(pv[:, 0], t)
    jump = np.abs(np.diff(pv[:, 1], prepend=pv[0, 1])) > 1e-2   # 速度不连续点及其邻点不参与比较
    mask = ~(jump | np.roll(jump, 1) | np.roll(jump, -1) | np.roll(jump, 2) | np.roll(jump, -2))
    assert np.max(np.abs(dp[mask] - pv[mask, 1])) < 0.05
    assert pv[:, 0].max() == pytest.approx(1.2, abs=1e-3) and pv[:, 0].min() == pytest.approx(0.0, abs=1e-3)


def test_signal_buffer_rolls():
    from mitlab.buffer import SignalBuffer
    b = SignalBuffer(("t", "p"), capacity=100)
    for i in range(50):
        ts = list(range(i * 7, i * 7 + 7))
        b.extend({"t": ts, "p": [x * 2 for x in ts]})
    v = b.view()
    assert len(v["t"]) == 100 and v["t"][-1] == 349 and v["t"][0] == 250
    assert np.all(np.diff(v["t"]) == 1) and np.all(v["p"] == 2 * v["t"])
    assert b.view(t_min=340)["t"][0] == 340
    b.clear()
    assert len(b) == 0
