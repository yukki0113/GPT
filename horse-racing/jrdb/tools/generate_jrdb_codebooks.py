#!/usr/bin/env python3
"""Generate the bundled JRDB codebooks from the official CP932 source tables.

Usage:
  python generate_jrdb_codebooks.py --tokki /path/to/tokki_code.txt \
      --ashimoto /path/to/ashimoto_code.txt --output jrdb_codebooks.json
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROW = re.compile(r"^\s*(\d{3})\s+\S+\s{2,}(.+?)\s*$")


def read_table(path: Path) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in path.read_bytes().decode("cp932").splitlines():
        match = ROW.match(line)
        if match:
            rows[match.group(1)] = match.group(2)
    if not rows:
        raise ValueError(f"コード表を解析できません: {path}")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="JRDB公式コード表からJSON codebookを生成")
    parser.add_argument("--tokki", required=True, type=Path)
    parser.add_argument("--ashimoto", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    codebooks = {"schema_version": 1, "TOKKI": read_table(args.tokki), "ASHIMOTO": read_table(args.ashimoto)}
    args.output.write_text(json.dumps(codebooks, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"TOKKI={len(codebooks['TOKKI'])} ASHIMOTO={len(codebooks['ASHIMOTO'])} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
