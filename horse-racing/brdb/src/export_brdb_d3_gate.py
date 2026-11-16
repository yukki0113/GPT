#!/usr/bin/env python3
"""GitHub-tracked BRDB D3 source export and regression gate, no raw data upload."""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

EXPORT = (
    "horse-racing/brdb/src/brdb_d3_condition_research.py",
    "horse-racing/brdb/src/brdb_d3_temporal_validation.py",
    "horse-racing/brdb/src/run_brdb_d3_research_e2e.py",
    "horse-racing/brdb/tests/test_brdb_d3_condition_research.py",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    receipt = {"research_only": True, "prediction_safe": False, "files": {}}
    for relative in EXPORT:
        file = root / relative
        if not file.is_file():
            raise FileNotFoundError(str(file))
        target = args.output_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file, target)
        receipt["files"][relative] = hashlib.sha256(target.read_bytes()).hexdigest()
    suite = root / "horse-racing" / "brdb" / "tests"
    results = []
    for pattern in ("test_brdb_stage3*.py", "test_brdb_stage4*.py",
                    "test_brdb_d3*.py"):
        command = [sys.executable, "-m", "unittest", "discover", "-s",
                   str(suite), "-p", pattern, "-v"]
        result = subprocess.run(command, cwd=root, text=True,
                                encoding="utf-8", errors="replace",
                                capture_output=True, timeout=240, check=False)
        results.append({"pattern": pattern, "return_code": result.returncode,
                        "stdout": result.stdout, "stderr": result.stderr})
        print(result.stderr, file=sys.stderr)
    receipt["tests"] = results
    receipt["status"] = ("PASS" if all(x["return_code"] == 0 for x in results)
                         else "FAIL")
    (args.output_dir / "brdb_d3_export_audit.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True)+"\n",
        encoding="utf-8")
    if receipt["status"] != "PASS":
        sys.exit(1)


if __name__ == "__main__":
    main()
