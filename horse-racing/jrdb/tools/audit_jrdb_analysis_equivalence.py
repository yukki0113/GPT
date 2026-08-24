#!/usr/bin/env python3
"""Compare two JRDB Analysis Lite SQLite files row-for-row.

Intended use: validate Core->Analysis versus Raw->Analysis outputs before
promoting a Raw-direct build path or after parser/schema changes.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

TABLE = "fact_entry_result_lite"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--left", type=Path, required=True)
    ap.add_argument("--right", type=Path, required=True)
    ap.add_argument("--year-from", type=int)
    ap.add_argument("--year-to", type=int)
    args = ap.parse_args()

    conn = sqlite3.connect(args.left)
    conn.execute("ATTACH DATABASE ? AS rhs", (str(args.right),))
    columns = [row[1] for row in conn.execute(f"PRAGMA table_info({TABLE})")]
    rhs_columns = [row[1] for row in conn.execute(f"PRAGMA rhs.table_info({TABLE})")]
    if columns != rhs_columns:
        raise SystemExit(json.dumps({"status": "FAIL", "reason": "column_mismatch", "left": columns, "right": rhs_columns}, ensure_ascii=False))

    where = []
    params: list[int] = []
    if args.year_from is not None:
        where.append("year>=?")
        params.append(args.year_from)
    if args.year_to is not None:
        where.append("year<=?")
        params.append(args.year_to)
    where_sql = " WHERE " + " AND ".join(where) if where else ""

    quoted = ",".join(f'"{c}"' for c in columns)
    left_count = conn.execute(f"SELECT count(*) FROM {TABLE}{where_sql}", params).fetchone()[0]
    right_count = conn.execute(f"SELECT count(*) FROM rhs.{TABLE}{where_sql}", params).fetchone()[0]

    # EXCEPT detects rows that differ anywhere across the complete Analysis fact.
    left_minus_right = conn.execute(
        f"SELECT count(*) FROM (SELECT {quoted} FROM {TABLE}{where_sql} EXCEPT SELECT {quoted} FROM rhs.{TABLE}{where_sql})",
        params + params,
    ).fetchone()[0]
    right_minus_left = conn.execute(
        f"SELECT count(*) FROM (SELECT {quoted} FROM rhs.{TABLE}{where_sql} EXCEPT SELECT {quoted} FROM {TABLE}{where_sql})",
        params + params,
    ).fetchone()[0]

    result = {
        "status": "PASS" if left_count == right_count and left_minus_right == 0 and right_minus_left == 0 else "FAIL",
        "left_rows": left_count,
        "right_rows": right_count,
        "left_minus_right": left_minus_right,
        "right_minus_left": right_minus_left,
        "columns_compared": len(columns),
        "year_from": args.year_from,
        "year_to": args.year_to,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    conn.close()
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
