#!/usr/bin/env python3
"""Run the frozen prototype contract suite and instruction-003 history fixtures."""
from __future__ import annotations
import importlib.util
import sys
import unittest
from pathlib import Path

tests = Path(__file__).resolve().parents[1] / "tests"
paths = [tests / "test_jrdb_edge_v05_prototype_aggregation.py",
         tests / "test_jrdb_edge_v05_first_history.py"]
loader = unittest.TestLoader()
suite = unittest.TestSuite()
for index, path in enumerate(paths):
    spec = importlib.util.spec_from_file_location(f"v05_history_suite_{index}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    suite.addTests(loader.loadTestsFromModule(module))
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
