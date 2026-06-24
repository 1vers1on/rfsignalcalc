#!/usr/bin/env python3
"""RF Cascade Studio — entry point.

Run the GUI:        python main.py  [project.rfc]
Run engine tests:   python tests/test_cascade.py
"""

from __future__ import annotations

import sys

from rfcascade.gui.app import run

if __name__ == "__main__":
    sys.exit(run())
