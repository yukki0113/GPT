#!/usr/bin/env python3
"""Compatibility wrapper for the unified GPT I/O Git binary tool."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.gpt_io.git.git_binary_tool import *  # noqa: F401,F403
from tools.gpt_io.git.git_binary_tool import main

if __name__ == "__main__":
    raise SystemExit(main())
