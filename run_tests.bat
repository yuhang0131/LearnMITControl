@echo off
REM Run all tests (sim core + offscreen UI smoke test + screenshot to docs\screenshot.png)
cd /d "%~dp0"
set QT_QPA_PLATFORM=offscreen
.venv\Scripts\python.exe -m pip show pytest >nul 2>nul || .venv\Scripts\python.exe -m pip install pytest
.venv\Scripts\python.exe -m pytest -v %*
