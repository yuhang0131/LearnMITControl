"""界面主题（配色参考 Motor Studio 的浅色设计规范）与中文字体选择。"""
from __future__ import annotations

import sys

T = dict(
    brand="#F9A509", brand_hover="#E09400", brand_press="#C27F00", brand_text="#965F00",
    brand_50="#FFF7E6", brand_100="#FDE8B8", on_brand="#1F1606",
    bg="#F4F5F7", surface="#FFFFFF", surface2="#F0F2F5", surface3="#E6E9EE",
    border="#DCE0E6", border_strong="#C3C9D2", text="#1F2329", text2="#545C68", text3="#8A919C",
    text_dis="#B4BAC3", ok="#15803D", err="#DC2626", info="#2563EB",
)

# 曲线/摆杆配色
COLOR_A = "#2563EB"
COLOR_B = "#E8590C"
COLOR_TARGET = "#8A919C"
COLOR_KP = "#16A34A"
COLOR_KD = "#9333EA"
COLOR_FF = "#0891B2"
COLOR_CMD = "#545C68"
COLOR_EXT = "#DC2626"

WIN_FONTS = ["Microsoft YaHei UI", "Microsoft YaHei", "SimHei"]
LINUX_FONTS = ["Noto Sans CJK SC", "Noto Sans SC", "Source Han Sans SC", "WenQuanYi Micro Hei",
               "WenQuanYi Zen Hei", "Noto Serif CJK SC", "Droid Sans Fallback"]
MAC_FONTS = ["PingFang SC", "Hiragino Sans GB"]
MONO_FONTS = '"JetBrains Mono", "Cascadia Mono", Consolas, "DejaVu Sans Mono", monospace'


def preferred_families() -> list:
    if sys.platform.startswith("win"):
        return WIN_FONTS + LINUX_FONTS
    if sys.platform == "darwin":
        return MAC_FONTS + LINUX_FONTS
    return LINUX_FONTS + WIN_FONTS


def _font_files() -> list:
    """系统字体数据库为空时（例如 Windows 上的 offscreen 平台）手动加载的字体文件。"""
    import glob
    import os
    if sys.platform.startswith("win"):
        d = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        names = ["msyh.ttc", "msyhbd.ttc", "segoeui.ttf", "consola.ttf", "simhei.ttf"]
        return [os.path.join(d, n) for n in names if os.path.exists(os.path.join(d, n))]
    pats = ["/usr/share/fonts/**/NotoSansCJK*.tt[cf]", "/usr/share/fonts/**/NotoSansSC*.[ot]tf",
            "/usr/share/fonts/**/wqy-*.tt[cf]", "/usr/share/fonts/**/DejaVuSans*.ttf",
            os.path.expanduser("~/.local/share/fonts/**/*CJK*.tt[cf]")]
    out = []
    for p in pats:
        out += glob.glob(p, recursive=True)
    return out[:12]


def setup_fonts(app) -> str:
    """选择可用的中文字体并设置为应用默认字体，返回选中的字体族名。"""
    from PySide6.QtGui import QFont, QFontDatabase

    available = set(QFontDatabase.families())
    chosen = [f for f in preferred_families() if f in available]
    if not chosen:      # 字体数据库为空/缺中文字体：直接加载字体文件
        for path in _font_files():
            QFontDatabase.addApplicationFont(path)
        available = set(QFontDatabase.families())
        chosen = [f for f in preferred_families() if f in available]
    font = QFont()
    fams = (chosen or []) + ["Segoe UI", "DejaVu Sans", "sans-serif"]
    font.setFamilies(fams)
    font.setPointSizeF(9.5)
    app.setFont(font)
    return chosen[0] if chosen else ""


def qss(ui_family: str = "") -> str:
    t = T
    fam = f'"{ui_family}", ' if ui_family else ""
    return f"""
* {{ font-family: {fam}"Microsoft YaHei UI", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif; font-size: 13px; color: {t['text']}; }}
QMainWindow, QWidget#root {{ background: {t['bg']}; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
QFrame#card {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 10px; }}
QFrame#topbar {{ background: {t['surface']}; border-bottom: 1px solid {t['border']}; }}
QLabel {{ background: transparent; }}
QLabel#cardTitle {{ font-weight: 600; font-size: 13.5px; }}
QLabel#appTitle {{ font-size: 16px; font-weight: 700; }}
QLabel#hint {{ color: {t['text3']}; font-size: 11.5px; }}
QLabel#label {{ color: {t['text2']}; font-size: 12px; }}
QLabel#mono {{ font-family: {MONO_FONTS}; font-size: 12px; }}
QLabel#timeLabel {{ font-family: {MONO_FONTS}; color: {t['text2']}; }}
QPushButton {{ background: {t['surface']}; border: 1px solid {t['border_strong']}; border-radius: 6px;
    padding: 0 12px; min-height: 28px; }}
QPushButton:hover {{ background: {t['surface2']}; }}
QPushButton:pressed {{ background: {t['surface3']}; }}
QPushButton:checked {{ background: {t['brand_50']}; border: 1px solid {t['brand']}; color: {t['brand_text']}; font-weight: 600; }}
QPushButton[kind="primary"] {{ background: {t['brand']}; color: {t['on_brand']}; border: 1px solid {t['brand']}; font-weight: 600; }}
QPushButton[kind="primary"]:hover {{ background: {t['brand_hover']}; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background: {t['surface']}; border: 1px solid {t['border_strong']};
    border-radius: 6px; min-height: 26px; padding: 0 6px; selection-background-color: {t['brand']}; selection-color: {t['on_brand']}; }}
QDoubleSpinBox, QSpinBox {{ font-family: {MONO_FONTS}; }}
QDoubleSpinBox:focus, QComboBox:focus {{ border: 1px solid {t['brand']}; }}
QComboBox QAbstractItemView {{ background: {t['surface']}; border: 1px solid {t['border']}; selection-background-color: {t['brand_50']}; selection-color: {t['text']}; }}
QListWidget#presets {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 10px; outline: none; }}
QListWidget#presets::item {{ height: 30px; padding-left: 8px; border-radius: 6px; margin: 1px 4px; }}
QListWidget#presets::item:hover {{ background: {t['surface2']}; }}
QListWidget#presets::item:selected {{ background: {t['brand_50']}; color: {t['brand_text']}; font-weight: 600; }}
QTextBrowser {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 10px; padding: 6px; }}
QGroupBox {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 10px; margin-top: 14px; padding: 8px 8px 6px 8px; font-weight: 600; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {t['text']}; }}
QSlider::groove:horizontal {{ height: 4px; background: {t['surface3']}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {t['brand']}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {t['brand']}; width: 12px; margin: -5px 0; border-radius: 6px; }}
QCheckBox::indicator {{ width: 15px; height: 15px; }}
QSplitter::handle {{ background: {t['bg']}; }}
QToolTip {{ background: {t['surface']}; color: {t['text']}; border: 1px solid {t['border']}; }}
QTableWidget::item {{ padding: 0px 2px; }}
QTableWidget {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 6px; gridline-color: {t['border']}; font-size: 12px; }}
QHeaderView::section {{ background: {t['surface2']}; border: none; border-bottom: 1px solid {t['border']}; padding: 3px 6px; color: {t['text2']}; font-size: 12px; font-weight: 600; }}
"""
