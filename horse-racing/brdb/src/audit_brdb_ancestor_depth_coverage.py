#!/usr/bin/env python3
"""Audit canonical BRDB ancestry coverage and unresolved parent-year demand.

Uses pinned BRDB CURRENT, DuckDB, and the canonical ancestor_graph module.
This is a retrospective source-coverage audit, not an as-of race prediction.
"""
from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path

from brdb_ancestor_graph import ancestor_crosses, ancestor_graph
from brdb_current import DEFAULT_TRANSPORT_MANIFEST, resolve_brdb_current


def audit(reader, *, cohort_year: str = "2025") -> dict:
    import duckdb

    con = duckdb.connect(":memory:")
    try:
        cohort = con.execute(
            "SELECT horse_id FROM read_parquet(?) "
            "WHERE substr(profile_data_date,1,4)=? ORDER BY horse_id",
            [str(reader._paths["pedigree_fact.parquet"]), cohort_year],
        ).fetchall()
        relation_rows = con.execute(
            "SELECT child_horse_id, role, resolved_parent_horse_id, "
            "resolution_status, parent_birth_year FROM read_parquet(?)",
            [str(reader._paths["parent_relation.parquet"])],
        ).fetchall()
    finally:
        con.close()
    relations = {}
    year_counts = Counter()
    for child, role, parent, status, year in relation_rows:
        relations.setdefault(str(child), []).append({
            "role": role,
            "resolved_parent_horse_id": parent,
            "resolution_status": status,
        })
        if status not in ("RESOLVED_EXACT", "RESOLVED_ALIAS"):
            year_counts[(str(year) if year is not None else "UNKNOWN", role, status)] += 1

    ids = [str(x[0]) for x in cohort]
    out = {
        "generation_id": reader.generation_id,
        "cohort": {"definition": "canonical profile_data_date calendar year", "year": cohort_year,
                   "horse_count": len(ids)},
        "depths": {},
        "unresolved_parent_birth_year_all_master": [
            {"parent_birth_year": y, "role": role, "resolution_status": status, "count": count}
            for (y, role, status), count in sorted(year_counts.items())
        ],
    }
    if not ids:
        raise ValueError("empty cohort: check year and cohort definition")
    def get_relations(horse_id):
        return relations.get(horse_id, [])
    for depth in (2,3,4,5):
        resolved_hist = Counter()
        statuses = Counter()
        full = 0
        crosses = 0
        for horse_id in ids:
            graph = ancestor_graph(horse_id, get_relations, max_depth=depth)
            full += graph["coverage"] == "FULL"
            resolved_hist[graph["resolved_paths"]] += 1
            crosses += bool(ancestor_crosses(graph)["crosses"])
            statuses.update(str(node["status"]) for node in graph["paths"] if node["horse_id"] is None)
        out["depths"][str(depth)] = {
            "full_horse_count": full,
            "observed_cross_horse_count": crosses,
            "resolved_paths_histogram": dict(sorted(resolved_hist.items())),
            "unresolved_path_status_count": dict(sorted(statuses.items())),
        }
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--current-zip", type=Path, required=True)
    p.add_argument("--cache-root", type=Path, required=True)
    p.add_argument("--cohort-year", default="2025")
    p.add_argument("--output-json", type=Path, required=True)
    args = p.parse_args()

    def pinned_fetch(_manifest: Path, root: Path) -> Path:
        dest = root / "BloodReviewDB_CURRENT.zip"
        shutil.copyfile(args.current_zip, dest)
        return dest

    resolved = resolve_brdb_current(args.cache_root,
                                    transport_manifest=DEFAULT_TRANSPORT_MANIFEST,
                                    fetcher=pinned_fetch)
    result = audit(resolved.reader, cohort_year=args.cohort_year)
    result["source_current_zip_sha256"] = resolved.provenance["transport"]["zip_sha256"]
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    if args.output_json.exists():
        raise FileExistsError(args.output_json)
    args.output_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"generation_id": result["generation_id"], "cohort": result["cohort"],
                      "full_by_depth": {k:v["full_horse_count"] for k,v in result["depths"].items()}},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
