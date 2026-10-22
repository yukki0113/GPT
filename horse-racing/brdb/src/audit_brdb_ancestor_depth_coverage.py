#!/usr/bin/env python3
"""Audit BRDB 2025 cohort ancestry coverage and missing-parent birth years.

Uses the canonical BRDB CURRENT Reader and canonical ancestor_graph; no
alternate Parquet engine, no fuzzy identity joins, no mutation of artifacts.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from brdb_ancestor_graph import graph_from_reader
from brdb_pedigree_reader import BloodReviewReader


def audit(reader, *, cohort_date_prefix="2025", depths=(2, 3, 4, 5)):
    import duckdb
    profile_path = reader._paths["pedigree_fact.parquet"]
    connection = duckdb.connect(":memory:")
    try:
        rows = connection.execute(
            "SELECT horse_id FROM read_parquet(?) WHERE substr(birth_date,1,4) = ? ORDER BY horse_id",
            [str(profile_path), cohort_date_prefix],
        ).fetchall()
    finally:
        connection.close()
    ids = [str(row[0]) for row in rows]
    out = {"generation_id": reader.generation_id,
           "cohort": {"birth_year": cohort_date_prefix, "horse_count": len(ids)},
           "depths": {}}
    # The cohort here means horses born in the chosen year; it is NOT the same
    # as the original 2025 UKC target cohort defined by profile_data_date.
    for depth in depths:
        status = Counter()
        depths_resolved = Counter()
        count_full = 0
        with_any_cross = 0
        for horse_id in ids:
            graph = graph_from_reader(reader, horse_id, max_depth=depth)
            count_full += graph["coverage"] == "FULL"
            depths_resolved[graph["resolved_paths"]] += 1
            for node in graph["paths"]:
                if node["horse_id"] is None:
                    status[str(node["status"])] += 1
            from brdb_ancestor_graph import ancestor_crosses
            with_any_cross += bool(ancestor_crosses(graph)["crosses"])
        out["depths"][str(depth)] = {
            "full_horse_count": count_full,
            "any_observed_cross_horse_count": with_any_cross,
            "resolved_paths_histogram": dict(sorted(depths_resolved.items())),
            "missing_node_status_count": dict(sorted(status.items())),
        }
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-root", required=True, type=Path)
    parser.add_argument("--birth-year", default="2025")
    parser.add_argument("--output-json", required=True, type=Path)
    args = parser.parse_args()
    reader = BloodReviewReader(args.current_root)
    result = audit(reader, cohort_date_prefix=args.birth_year)
    if args.output_json.exists():
        raise FileExistsError(args.output_json)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"generation_id": result["generation_id"], "horse_count": result["cohort"]["horse_count"], "depths": {k:v["full_horse_count"] for k,v in result["depths"].items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
