"""程序入口：python run.py [--preset KEY] [--smoke MS] [--screenshot FILE]"""
from __future__ import annotations

import argparse
import os
import sys


def create_app():
    from PySide6.QtWidgets import QApplication

    from mitlab import APP_NAME
    from .theme import qss, setup_fonts

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    fam = setup_fonts(app)
    app.setStyleSheet(qss(fam))
    return app, fam


def make_screenshot(win, path: str, preset: str = "kd_small", sim_seconds: float = 3.0) -> str:
    """加载预设、离线推进 sim_seconds 秒后截图（用于文档与测试）。"""
    win.apply_preset(preset)
    win.r_win.setValue(4.0, emit=True)
    win.pause()
    win.advance(sim_seconds)
    win.refresh_plots()
    win.refresh_arm()
    win.refresh_metrics()
    from PySide6.QtWidgets import QApplication
    QApplication.processEvents()
    win.fit_tables()
    QApplication.processEvents()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    win.grab().save(path)
    return os.path.abspath(path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="mitlab", description="MIT 控制学习实验室")
    ap.add_argument("--preset", help="启动后加载的预设 key，例如 spring / kd_small / gravity_ab")
    ap.add_argument("--smoke", type=int, metavar="MS", help="运行 MS 毫秒后自动退出（冒烟测试）")
    ap.add_argument("--screenshot", metavar="FILE", help="保存窗口截图后退出")
    ap.add_argument("--size", default="1600x940")
    args = ap.parse_args(argv)

    from PySide6.QtCore import QTimer

    from .main_window import MainWindow

    app, fam = create_app()
    win = MainWindow()
    w, h = (int(x) for x in args.size.lower().split("x"))
    win.resize(w, h)
    win.show()
    if args.preset:
        win.apply_preset(args.preset)
    if args.screenshot:
        p = make_screenshot(win, args.screenshot, args.preset or "kd_small")
        print(f"screenshot -> {p}  (font: {fam or 'default'})")
        if not args.smoke:
            return 0
    if args.smoke:
        def finish():
            print(f"SMOKE OK  t_sim={win.sims['A'].t:.3f}s  font={fam or 'default'}")
            win.close()
            app.exit(0)
        QTimer.singleShot(args.smoke, finish)
    return app.exec()
