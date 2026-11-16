#!/usr/bin/env python3
"""Read-only Stage3/Stage4 regression gate for GitHub Actions fallback."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    suite = root / "horse-racing" / "brdb" / "tests"
    jobs = [
        [sys.executable, "-m", "unittest", "discover", "-s", str(suite),
         "-p", "test_brdb_stage3*.py", "-v"],
        [sys.executable, "-m", "unittest", "discover", "-s", str(suite),
         "-p", "test_brdb_stage4*.py", "-v"],
    ]
    results = []
    for command in jobs:
        result = subprocess.run(command, cwd=root, capture_output=True,
                                text=True, check=False, timeout=240,
                                encoding="utf-8", errors="replace")
        results.append({
            "command": command, "return_code": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr,
        })
    output = {
        "research_only": True, "prediction_safe": False,
        "status": "PASS" if all(x["return_code"] == 0 for x in results)
        else "FAIL", "runs": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2,
                                     ensure_ascii=False) + "\n",
                           encoding="utf-8")
    for run in results:
        print(run["stderr"], file=sys.stderr)
    if output["status"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
