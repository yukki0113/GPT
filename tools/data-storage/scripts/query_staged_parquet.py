#!/usr/bin/env python3
"""Run canonical DuckDB SQL against Parquet and persist a JSON query result."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from data_storage.query import execute_query

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--parquet", required=True, help="Parquet path, glob, or dataset folder")
    p.add_argument("--sql", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    columns, rows = execute_query(args.parquet, args.sql)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"status": "PASS", "columns": columns, "rows": rows}
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
                           encoding="utf-8")
    print(json.dumps({"status": "PASS", "output": str(args.output),
                      "row_count": len(rows)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
