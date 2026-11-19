#!/usr/bin/env python3
"""Export the repository-pinned DuckDB wheel from Actions for approved local E2E.

Open-source dependency transport only. No private input data is accepted or read.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

PIN = "1.1.3"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--python-version", choices=("312", "313"), default="313")
    args = ap.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "pip", "download", "--no-deps",
                    "--only-binary=:all:", "--python-version", args.python_version,
                    "--implementation", "cp", "--abi", "cp" + args.python_version,
                    "--platform", "manylinux2014_x86_64",
                    "--dest", str(args.output_dir),
                    f"duckdb=={PIN}"], check=True)
    files = list(args.output_dir.glob("duckdb-*.whl"))
    if len(files) != 1 or not files[0].name.startswith("duckdb-1.1.3-"):
        raise ValueError("expected one pinned wheel")
    f = files[0]
    audit = {"package": "duckdb", "version": PIN, "filename": f.name,
             "size_bytes": f.stat().st_size,
             "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}
    (args.output_dir / "wheel_integrity.json").write_text(
        json.dumps(audit, sort_keys=True, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(audit, sort_keys=True))

if __name__ == "__main__":
    main()
