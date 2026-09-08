#!/usr/bin/env python3
"""Compatibility wrapper for the shared GitHub Issue preflight validator."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.gpt_io.git.issue_preflight import main


if __name__ == "__main__":
    raise SystemExit(main())
