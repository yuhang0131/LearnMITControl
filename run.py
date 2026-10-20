"""启动 MIT 控制学习实验室：python run.py [--preset KEY]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
