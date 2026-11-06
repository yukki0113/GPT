#!/usr/bin/env python3
"""PR2430 research-only merge gate: run actual Stage 3 unit tests.

This script validates the checked-out PR code. It does not mutate CURRENT,
production review, PWA, RaceNote or repository state.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Run all stage3 Python unit tests and export machine-readable status."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[3]
    test_dir = repository / "horse-racing" / "brdb" / "tests"
    command = [
        sys.executable, "-m", "unittest", "discover",
        "-s", str(test_dir), "-p", "test_brdb_stage3*.py", "-v",
    ]
    result = subprocess.run(
        command, cwd=repository, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False, timeout=180,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "research_only": True,
        "test_pattern": "test_brdb_stage3*.py",
        "checkout": str(repository),
        "return_code": result.returncode,
        "command": command,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(result.stdout)
    print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
