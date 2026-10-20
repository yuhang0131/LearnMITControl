# PyInstaller spec - works on both Windows and Linux.
#   pyinstaller packaging/mitlab.spec --noconfirm
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

a = Analysis(
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "README.md"), ".")],
    hiddenimports=[],
    excludes=["tkinter", "PyQt5", "PyQt6", "PySide2", "matplotlib", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="MITControlLab", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="MITControlLab")
