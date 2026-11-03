#!/usr/bin/env python3
"""Foldknife – a Python multitool.

Start:  python foldknife.py            (menu)
        python foldknife.py list       (all tools)
        python foldknife.py calc 2+2   (quick command)
"""
import os
import sys

if sys.version_info < (3, 9):
    sys.exit("Foldknife needs Python 3.9 or newer. Get the latest: https://www.python.org/downloads/")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from foldknife.core.cli import main  # noqa: E402

if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        # output was piped into something that closed early (e.g. "| head") – exit quietly
        try:
            sys.stdout = open(os.devnull, "w")
        except OSError:
            pass
        sys.exit(0)
