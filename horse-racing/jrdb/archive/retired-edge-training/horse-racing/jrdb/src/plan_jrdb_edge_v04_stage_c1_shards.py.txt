#!/usr/bin/env python3
"""Plan deterministic Stage C1 shards from a Stage B template catalog.

No outcomes, odds, popularity, payouts, or ROI are consulted. Assignment uses only
Stage B template metadata: search_lane, depth, template_id, and estimated cost.
Selection is applied before assignment; the source catalog is never modified.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pyarrow.parquet as pq

from jrdb_edge_v04_preflight import build_plan, sha256_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template-parquet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--search-lane", action="append", dest="search_lanes")
    parser.add_argument("--family", action="append", dest="families")
    parser.add_argument("--min-depth", type=int, default=2)
    parser.add_argument("--max-depth", type=int, default=6)
    parser.add_argument("--max-templates-per-shard", type=int, default=900)
    parser.add_argument("--target-estimated-cost", type=int, default=250_000_000)
    parser.add_argument("--max-total-shards", type=int, default=180)
    args = parser.parse_args()

    source_catalog = args.template_parquet.resolve()
    rows = pq.read_table(source_catalog).to_pylist()
    try:
        plan = build_plan(
            rows,
            source_catalog_sha256=sha256_file(source_catalog),
            search_lanes=args.search_lanes,
            families=args.families,
            min_depth=args.min_depth,
            max_depth=args.max_depth,
            max_templates_per_shard=args.max_templates_per_shard,
            target_estimated_cost=args.target_estimated_cost,
            max_total_shards=args.max_total_shards,
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    matrix = {"include": [{"shard_id": shard["shard_id"]} for shard in plan["shards"]]}
    args.output.with_name("matrix.json").write_text(json.dumps(matrix, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in plan.items() if key != "shards"}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
