#!/usr/bin/env bash
# Build a Linux onedir bundle: dist/MITControlLab/MITControlLab (+ tar.gz)
set -euo pipefail
cd "$(dirname "$0")/.."
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt || \
  .venv/bin/python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements-dev.txt
.venv/bin/python -m PyInstaller packaging/mitlab.spec --noconfirm --clean
tar -C dist -czf dist/MITControlLab-linux-x86_64.tar.gz MITControlLab
echo "Done: dist/MITControlLab/MITControlLab  and  dist/MITControlLab-linux-x86_64.tar.gz"
