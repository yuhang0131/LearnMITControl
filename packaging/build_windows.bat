@echo off
REM Build a Windows onedir bundle: dist\MITControlLab\MITControlLab.exe
cd /d "%~dp0\.."
if not exist .venv\Scripts\python.exe (py -3.11 -m venv .venv || python -m venv .venv)
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt || .venv\Scripts\python.exe -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements-dev.txt
.venv\Scripts\python.exe -m PyInstaller packaging\mitlab.spec --noconfirm --clean
echo.
echo Done: dist\MITControlLab\MITControlLab.exe
