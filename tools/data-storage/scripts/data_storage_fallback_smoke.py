#!/usr/bin/env python3
"""Minimal smoke target for the repository data-storage Actions fallback."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import pyarrow as pa


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "PASS",
        "duckdb_version": duckdb.__version__,
        "pyarrow_version": pa.__version__,
    }
    (args.output_dir / "data-storage-fallback-smoke.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
