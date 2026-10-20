"""离屏 UI 冒烟测试：启动主窗口，逐个运行预设、切换对比模式/目标类型/扰动，并截图。"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")

from PySide6.QtTest import QTest  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT = os.path.join(ROOT, "docs", "screenshot.png")


@pytest.fixture(scope="module")
def win():
    from ui.app import create_app
    from ui.main_window import MainWindow

    errors = []
    old_hook = sys.excepthook
    sys.excepthook = lambda *a: errors.append(a)   # Qt 槽函数中的异常会走 excepthook
    app, fam = create_app()
    w = MainWindow()
    w.resize(1600, 940)
    w.show()
    w._errors = errors
    w._font = fam
    yield w
    w.close()
    sys.excepthook = old_hook
    assert not errors, errors


def test_font_selected(win):
    if sys.platform.startswith("win"):
        assert win._font.startswith("Microsoft YaHei")
    else:
        assert win._font, "未找到中文字体（请安装 Noto Sans CJK）"


def test_all_presets_run(win):
    from mitlab.presets import PRESETS

    for pr in PRESETS:
        win.apply_preset(pr.key)
        assert win.running and win.compare == pr.compare
        t0 = win.sims["A"].t
        QTest.qWait(300)
        assert win.sims["A"].t > t0, pr.key
        win.chk_compare.setChecked(not win.chk_compare.isChecked())   # 切换对比模式
        QTest.qWait(80)
        win.chk_compare.setChecked(not win.chk_compare.isChecked())
        QTest.qWait(80)
        win.refresh_metrics()
    assert not win._errors


def test_controls_and_interactions(win):
    win.apply_preset("impedance")
    win.chk_compare.setChecked(True)
    win.set_edit_set("B")
    win.r_kp.setValue(5.0, emit=True)
    assert win.gains["B"].kp == 5.0 and win.gains["A"].kp == 1.0
    win.set_critical_damping()
    win.copy_a_to_b()
    win.apply_disturbance()
    QTest.qWait(150)
    win._drag_start(1.2)
    QTest.qWait(150)
    win._drag_move(1.5)
    QTest.qWait(150)
    win._drag_end()
    for i in range(win.cmb_kind.count()):
        win.cmb_kind.setCurrentIndex(i)
        QTest.qWait(120)
    for i in range(win.cmb_traj.count()):
        win.cmb_traj.setCurrentIndex(i)
        QTest.qWait(80)
    win.cmb_kind.setCurrentIndex(0)
    win.toggle_step()
    win.r_ts.setValue(10.0, emit=True)
    win.chk_grav.setChecked(True)
    win.r_m.setValue(1.0, emit=True)
    win.r_nv.setValue(0.5, emit=True)
    win.cmb_speed.setCurrentIndex(win.cmb_speed.count() - 1)
    QTest.qWait(200)
    win.toggle_run()
    assert not win.running
    win.reset()
    assert win.sims["A"].t == 0.0
    assert not win._errors


def test_screenshot(win):
    from ui.app import make_screenshot

    path = make_screenshot(win, SHOT, "kd_small", 3.0)
    assert os.path.getsize(path) > 50_000
    from PySide6.QtGui import QImage
    img = QImage(path)
    assert img.width() >= 1400 and img.height() >= 800
    print("screenshot:", path)
