#!/usr/bin/env python3
"""Prepare a transient DuckDB workspace from canonical Edge Feature Mart Parquet.

This is an execution workspace only. Canonical storage remains Parquet.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import duckdb

from jrdb_edge_feature_mart_parquet import resolve_current


class EdgeFeatureMartWorkspaceError(RuntimeError):
    pass


def prepare_workspace(root: Path, output: Path) -> dict[str, Any]:
    report = resolve_current(root)
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    source = Path(report["fact_path"]).resolve()
    con = duckdb.connect(str(output))
    try:
        literal = str(source).replace("'", "''")
        con.execute(
            f"CREATE TABLE edge_runner_fact AS "
            f"SELECT * FROM read_parquet('{literal}')"
        )
        rows = int(con.execute("SELECT COUNT(*) FROM edge_runner_fact").fetchone()[0])
        duplicates = int(
            con.execute(
                """
                SELECT COUNT(*) - COUNT(DISTINCT race_key || ':' || CAST(horse_no AS VARCHAR))
                FROM edge_runner_fact
                """
            ).fetchone()[0]
        )
        if rows != int(report["rows"]):
            raise EdgeFeatureMartWorkspaceError(
                f"row mismatch: expected={report['rows']} actual={rows}"
            )
        if duplicates:
            raise EdgeFeatureMartWorkspaceError(
                f"duplicate canonical keys in workspace: {duplicates}"
            )
        con.execute(
            """
            CREATE TABLE edge_workspace_meta AS
            SELECT ?::VARCHAR AS source_mode,
                   ?::VARCHAR AS source_generation_id,
                   ?::BIGINT AS source_rows
            """,
            ["parquet_canonical", report["generation_id"], rows],
        )
        con.commit()
    except Exception:
        con.close()
        output.unlink(missing_ok=True)
        raise
    finally:
        try:
            con.close()
        except Exception:
            pass

    return {
        "status": "PASS",
        "workspace_engine": "duckdb",
        "workspace_role": "transient_execution",
        "source_mode": "parquet_canonical",
        "generation_id": report["generation_id"],
        "rows": rows,
        "duplicate_canonical_keys": 0,
        "output": str(output),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--result-json", type=Path)
    args = parser.parse_args()
    result = prepare_workspace(args.root, args.output)
    if args.result_json:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
