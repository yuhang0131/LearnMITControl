#!/usr/bin/env bash
# MIT Control Lab - one-click launcher for Linux
# Creates .venv if missing, installs dependencies (falls back to the Tsinghua mirror), then launches.
set -euo pipefail
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
if [ ! -x .venv/bin/python ]; then
  echo "[MITControlLab] Creating virtual environment with $PY ..."
  "$PY" -m venv .venv || { echo "Failed: try 'sudo apt install python3-venv'"; exit 1; }
fi
if ! .venv/bin/python -c "import PySide6, pyqtgraph, numpy" >/dev/null 2>&1; then
  echo "[MITControlLab] Installing dependencies ..."
  .venv/bin/python -m pip install --disable-pip-version-check --timeout 20 -r requirements.txt || \
  .venv/bin/python -m pip install --disable-pip-version-check -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
fi
# Qt 6 on Linux needs a few system libraries (Debian/Ubuntu):
#   sudo apt install libegl1 libgl1 libxkbcommon-x11-0 libxcb-cursor0 fonts-noto-cjk
exec .venv/bin/python run.py "$@"
