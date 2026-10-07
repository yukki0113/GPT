#!/usr/bin/env python3
"""Run focused instruction-003 unit and DuckDB fixture tests."""
from __future__ import annotations
import runpy
from pathlib import Path

test_file = Path(__file__).resolve().parents[1] / "tests" / "test_jrdb_edge_v05_first_history.py"
runpy.run_path(str(test_file), run_name="__main__")
