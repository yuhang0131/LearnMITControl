@echo off
REM MIT Control Lab - one-click launcher for Windows
REM Creates .venv if missing, installs dependencies (falls back to the Tsinghua mirror), then launches.
setlocal
cd /d "%~dp0"
set "PYEXE="
if exist ".venv\Scripts\python.exe" goto :have_venv
where py >nul 2>nul && (py -3.11 -c "import sys" >nul 2>nul && set "PYEXE=py -3.11")
if not defined PYEXE where py >nul 2>nul && (py -3 -c "import sys" >nul 2>nul && set "PYEXE=py -3")
if not defined PYEXE set "PYEXE=python"
echo [MITControlLab] Creating virtual environment with %PYEXE% ...
%PYEXE% -m venv .venv
if errorlevel 1 (echo [MITControlLab] Failed to create venv. Please install Python 3.10+ from python.org & pause & exit /b 1)
:have_venv
".venv\Scripts\python.exe" -c "import PySide6, pyqtgraph, numpy" >nul 2>nul
if not errorlevel 1 goto :run
echo [MITControlLab] Installing dependencies ...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --timeout 20 -r requirements.txt
if errorlevel 1 (
  echo [MITControlLab] Default index failed, retrying with Tsinghua mirror ...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
  if errorlevel 1 (echo [MITControlLab] pip install failed. & pause & exit /b 1)
)
:run
start "" ".venv\Scripts\pythonw.exe" run.py %*
endlocal
