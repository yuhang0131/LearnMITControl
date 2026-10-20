import math

import numpy as np
import pytest

from mitlab.metrics import step_metrics
from mitlab.sim import JointSim, MITGains, PlantParams, mit_torque, saturate, theory
from mitlab.targets import Target


def zero_crossing_period(t, x):
    s = np.signbit(x)
    idx = np.nonzero(s[1:] != s[:-1])[0]
    # 线性插值求过零时刻
    tc = t[idx] - x[idx] * (t[idx + 1] - t[idx]) / (x[idx + 1] - x[idx])
    return 2.0 * np.mean(np.diff(tc))


def test_mit_law_and_saturation_helpers():
    kp, kd, tot = mit_torque(10, 0.5, 1.0, 2.0, 0.3, 0.2, 1.0)
    assert kp == pytest.approx(8.0)
    assert kd == pytest.approx(0.5)
    assert tot == pytest.approx(8.8)
    assert saturate(5, 2) == 2 and saturate(-5, 2) == -2 and saturate(1, 2) == 1
    assert saturate(100, 0) == 100  # tau_max<=0 表示不限幅


@pytest.mark.parametrize("kp,J", [(2.0, 0.01), (8.0, 0.01), (5.0, 0.05)])
def test_spring_natural_frequency(kp, J):
    plant = PlantParams(J=J, b=0.0, tau_max=0.0, ctrl_period=0.0005)
    sim = JointSim(plant, MITGains(kp=kp, kd=0.0), Target(p_des=0.0), p0=0.5)
    log = sim.run(4.0)
    T_meas = zero_crossing_period(log["t"], log["p"])
    T_theory = 2 * math.pi / math.sqrt(kp / J)
    assert T_meas == pytest.approx(T_theory, rel=0.01)
    assert theory(plant, MITGains(kp=kp, kd=0))["wn"] == pytest.approx(math.sqrt(kp / J))
    # 无阻尼 + ZOH：采样保持相当于 Ts/2 延迟，带来负阻尼 c = -Kp*Ts/2，
    # 振幅按 exp(Kp*Ts/(4J) * t) 缓慢增长 —— 与理论一致
    sigma = kp * plant.ctrl_period / (4 * J)
    tail = log["t"] > 3.0
    amp_meas = np.max(np.abs(log["p"][tail]))
    t_peak = log["t"][tail][np.argmax(np.abs(log["p"][tail]))]
    assert amp_meas == pytest.approx(0.5 * math.exp(sigma * t_peak), rel=0.03)


@pytest.mark.parametrize("zeta", [0.2, 0.5, 0.7])
def test_damping_ratio_overshoot(zeta):
    J, kp, b = 0.01, 20.0, 0.005
    kd = zeta * 2 * math.sqrt(kp * J) - b
    plant = PlantParams(J=J, b=b, tau_max=0.0)
    g = MITGains(kp=kp, kd=kd)
    assert theory(plant, g)["zeta"] == pytest.approx(zeta)
    log = JointSim(plant, g, Target(p_des=1.0)).run(3.0)
    m = step_metrics(log["t"], log["p"], 1.0)
    os_theory = 100 * math.exp(-zeta * math.pi / math.sqrt(1 - zeta ** 2))
    # 1 kHz 控制带来轻微延迟，允许 2 个百分点误差
    assert m.overshoot == pytest.approx(os_theory, abs=2.0)


def test_critical_damping_no_overshoot_and_low_damping_rings():
    J, kp, b = 0.01, 20.0, 0.005
    plant = PlantParams(J=J, b=b, tau_max=0.0)
    crit = JointSim(plant, MITGains(kp=kp, kd=2 * math.sqrt(kp * J) - b), Target(p_des=1.0)).run(3.0)
    assert step_metrics(crit["t"], crit["p"], 1.0).overshoot < 0.5
    low = JointSim(plant, MITGains(kp=kp, kd=0.02), Target(p_des=1.0)).run(3.0)
    assert step_metrics(low["t"], low["p"], 1.0).overshoot > 50


def test_pure_damping_velocity_mode():
    plant = PlantParams(J=0.01, b=0.005)
    log = JointSim(plant, MITGains(kp=0.0, kd=0.2), Target(v_des=2.0)).run(2.0)
    assert log["v"][-1] == pytest.approx(0.2 * 2.0 / 0.205, rel=1e-3)


def gravity_setup(auto_ff, p_des=0.0, kp=10.0):
    plant = PlantParams(J=0.01, b=0.005, m=0.5, l=0.2, gravity=True, tau_max=0.0)
    g = MITGains(kp=kp, kd=0.6, auto_gravity_ff=auto_ff)
    log = JointSim(plant, g, Target(p_des=p_des), p0=p_des).run(5.0)
    return plant, g, log


@pytest.mark.parametrize("p_des,kp", [(0.0, 10.0), (0.0, 40.0), (0.6, 20.0)])
def test_gravity_steady_state_error(p_des, kp):
    plant, g, log = gravity_setup(False, p_des, kp)
    err = p_des - log["p"][-1]
    mgl = 0.5 * 9.81 * 0.2
    # 精确解满足 Kp*e = m g l cos(p_des - e)；小误差近似 e ≈ m g l cos(p_des)/Kp
    assert err == pytest.approx(mgl * math.cos(p_des) / kp, rel=0.05)
    assert err == pytest.approx(mgl * math.cos(p_des - err) / kp, rel=1e-3)
    assert theory(plant, g, p_des)["ss_err_gravity"] == pytest.approx(mgl * math.cos(p_des) / kp)


def test_gravity_compensation_removes_error():
    _, _, log = gravity_setup(True, 0.3)
    assert abs(0.3 - log["p"][-1]) < 1e-4
    assert log["tau_ff"][-1] == pytest.approx(0.5 * 9.81 * 0.2 * math.cos(0.3))
    # 手动 tau_ff 也等效
    plant = PlantParams(J=0.01, b=0.005, m=0.5, l=0.2, gravity=True)
    log2 = JointSim(plant, MITGains(kp=10, kd=0.6, tau_ff=plant.mgl), Target(p_des=0.0)).run(5.0)
    assert abs(log2["p"][-1]) < 1e-4


def test_torque_saturation_respected():
    plant = PlantParams(J=0.01, b=0.005, tau_max=1.5)
    log = JointSim(plant, MITGains(kp=50, kd=1.4), Target(p_des=1.5)).run(3.0)
    assert np.max(np.abs(log["tau_out"])) <= 1.5 + 1e-12
    assert np.max(np.abs(log["tau_cmd"])) > 50  # 指令远超限幅
    # 饱和期间加速度不超过 tau_max / J
    a = np.diff(log["v"]) / np.diff(log["t"])
    assert np.max(np.abs(a)) <= (1.5 + 0.005 * np.max(np.abs(log["v"]))) / 0.01 * 1.01
    assert log["p"][-1] == pytest.approx(1.5, abs=1e-3)


def test_control_period_zoh():
    plant = PlantParams(J=0.01, b=0.005, ctrl_period=0.01)
    sim = JointSim(plant, MITGains(kp=10, kd=0.5), Target(p_des=1.0))
    log = sim.run(1.0)
    assert len(log["t"]) == 100
    assert np.allclose(np.diff(log["t"]), 0.01)
    n, dt = sim.substeps()
    assert n == 10 and dt == pytest.approx(0.001)
    # 剩余时间累计：两次 0.005 s 正好产生一个控制周期
    sim2 = JointSim(plant, MITGains(), Target())
    assert len(sim2.advance(0.005)["t"]) == 0
    assert len(sim2.advance(0.005)["t"]) == 1


def test_long_period_reduces_damping():
    J, kp, kd = 0.01, 20.0, 0.3
    os = []
    for ts in (0.001, 0.015):
        plant = PlantParams(J=J, b=0.005, ctrl_period=ts, tau_max=0)
        log = JointSim(plant, MITGains(kp=kp, kd=kd), Target(p_des=1.0)).run(4.0)
        os.append(step_metrics(log["t"], log["p"], 1.0).overshoot)
    assert os[1] > os[0] + 10


def test_sensor_noise_affects_torque_only_through_measurement():
    plant = PlantParams(J=0.01, b=0.005, noise_p=0.0, noise_v=0.3)
    log = JointSim(plant, MITGains(kp=20, kd=0.8), Target(p_des=0.0), seed=1).run(2.0)
    assert np.std(log["v_meas"] - log["v"]) == pytest.approx(0.3, rel=0.1)
    assert np.std(log["tau_kd"][-1000:]) > 0.15


def test_disturbance_pulse_and_impedance_return():
    plant = PlantParams(J=0.01, b=0.005)
    sim = JointSim(plant, MITGains(kp=1.0, kd=0.12), Target(p_des=0.0))
    sim.run(0.5)
    sim.add_pulse(0.5, duration=0.2)
    log = sim.run(0.3)
    assert np.max(log["tau_ext"]) == pytest.approx(0.5)
    assert np.max(log["p"]) > 0.1
    log = sim.run(4.0)
    assert abs(log["p"][-1]) < 1e-3   # 撤掉外力后回到目标
    # 恒定外力 -> 偏移 tau/Kp
    sim.ext_fn = lambda t, p, v: 0.3
    log = sim.run(5.0)
    assert log["p"][-1] == pytest.approx(0.3 / 1.0, rel=1e-3)


def test_coulomb_friction_deadband():
    plant = PlantParams(J=0.01, b=0.002, tau_c=0.2)
    log = JointSim(plant, MITGains(kp=2.0, kd=0.15), Target(p_des=1.0)).run(5.0)
    err = 1.0 - log["p"][-1]
    assert abs(err) <= 0.2 / 2.0 + 1e-6
    assert log["v"][-1] == 0.0  # 被静摩擦粘住
    # 静止时力矩小于 tau_c 不会动
    sim = JointSim(plant, MITGains(kp=0.0, kd=0.0, tau_ff=0.15), Target())
    assert np.all(sim.run(1.0)["p"] == 0.0)
    sim.gains.tau_ff = 0.3
    assert sim.run(1.0)["p"][-1] > 0.1
