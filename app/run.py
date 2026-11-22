#!/usr/bin/env python3
"""Launch the Colbert app:  python3 app/run.py   (see colbert_app/__main__.py for options).
Also the entry point for frozen (PyInstaller) builds."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if sys.version_info < (3, 8):
    sys.exit("Colbert needs Python 3.8 or newer")

from colbert_app.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
