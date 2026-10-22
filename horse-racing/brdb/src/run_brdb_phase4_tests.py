#!/usr/bin/env python3
"""Execute BRDB repository unittest suite in the canonical Python environment."""
from __future__ import annotations

import argparse
import json
import sys
import unittest
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=("phase4", "all"), default="all")
    parser.add_argument("--output-json", required=True, type=Path)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project / "src"))
    test_dir = project / "tests"
    discovered = unittest.TestLoader().discover(str(test_dir), pattern="test_brdb_ancestor_*.py" if args.suite == "phase4" else "test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(discovered)
    output = {
        "status": "PASS" if result.wasSuccessful() and result.testsRun > 0 else "FAIL",
        "suite": args.suite,
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output))
    return 0 if output["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
