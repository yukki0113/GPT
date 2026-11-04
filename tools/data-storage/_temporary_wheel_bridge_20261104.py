#!/usr/bin/env python3
"""One-time offline wheel transfer for BRDB PRIVATE local replay.

This script downloads only a pinned published CPython 3.13 x86_64 DuckDB
wheel on the GitHub runner. NO JRDB data is received or uploaded.
This is in an isolated temporary branch and is not intended for main.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

EXPECTED = "d5724fd8a49e24d730be34846b814b98ba7c304ca904fbdc98b47fa95c0b0cee"

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "pip", "download",
        "--disable-pip-version-check",
        "--only-binary=:all:", "--no-deps",
        "--python-version", "313",
        "--implementation", "cp", "--abi", "cp313",
        "--platform", "manylinux2014_x86_64",
        "--dest", str(out),
        "duckdb==1.1.3",
    ]
    subprocess.run(cmd, check=True)
    wheels = list(out.glob("duckdb-1.1.3-cp313-cp313-manylinux*.whl"))
    if len(wheels) != 1:
        raise ValueError(f"unexpected wheel candidates: {wheels}")
    digest = hashlib.sha256(wheels[0].read_bytes()).hexdigest()
    if digest != EXPECTED:
        raise ValueError("Pinned PyPI wheel SHA-256 mismatch: " + digest)
    audit = {"status": "PASS", "purpose": "private_local_dependency_only",
             "version": "duckdb==1.1.3", "wheel_file": wheels[0].name,
             "sha256": digest, "contains_jrdb_data": False}
    (out / "wheel_audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit))

if __name__ == "__main__":
    main()
