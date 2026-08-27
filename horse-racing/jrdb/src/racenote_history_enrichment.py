#!/usr/bin/env python3
"""Production RaceNote history enrichment entrypoint.

The validated enrichment engine currently lives in
``racenote_history_enrichment_poc.py``. This module is the stable production
entrypoint and owns the final RaceNote v1.0 contract:

- detailed PACI recent history: up to 5 runs
- compact Analysis Lite older history: up to 3 runs
- as-of-safe horse / sire / jockey / frame summaries
- overlapping distance ranges
- sample-size bands
- explicit history coverage / run-layer metadata

The internal engine may be refactored later without changing this CLI or the
v1.0 output contract.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import racenote_history_enrichment_poc as engine

SCHEMA_VERSION = "1.0"
OLDER_RUNS_LIMIT = 3
DEFAULT_STATS_WINDOW_YEARS = 5


def parse_args() -> argparse.Namespace:
    """Parse production enrichment CLI arguments."""
    parser = argparse.ArgumentParser(description="Production RaceNote v1.0 history enrichment")
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--mart", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--stats-window-years",
        type=int,
        default=DEFAULT_STATS_WINDOW_YEARS,
    )
    return parser.parse_args()


def production_metadata(
    base_schema_version: object,
    race_date: str,
    stats_window_years: int,
    warnings: list[str],
) -> dict:
    """Return metadata describing the stable RaceNote v1.0 enrichment contract."""
    return {
        "version": SCHEMA_VERSION,
        "base_schema_version": base_schema_version,
        "recent_runs_max": 5,
        "older_runs_max": OLDER_RUNS_LIMIT,
        "stats_window_years": stats_window_years,
        "as_of_exclusive": race_date,
        "future_leakage_policy": (
            "prior completed years from Stats Mart; target year from Analysis Lite "
            "with race_date < target_date"
        ),
        "distance_range_policy": {
            "ranges": [dict(item) for item in engine.DISTANCE_RANGE_DEFINITIONS],
            "overlap_boundaries_m": [1400, 1800],
            "long_distance_min_m": 2500,
        },
        "sample_size_band_policy": {
            "none": "starts = 0",
            "small": "starts = 1-19",
            "moderate": "starts = 20-49",
            "sufficient": "starts >= 50",
            "semantic": "descriptive sample-size band only; not statistical significance",
        },
        "history_scope": "jrdb_jra_history",
        "overseas_history_policy": "not_guaranteed",
        "warning_count": len(warnings),
        "warnings": warnings,
    }


def enrich_production(
    base: dict,
    analysis: sqlite3.Connection,
    mart: sqlite3.Connection,
    stats_window_years: int,
) -> tuple[dict, list[str]]:
    """Build one stable RaceNote v1.0 bundle from the validated enrichment engine."""
    base_schema_version = base.get("schema_version")
    enriched, warnings = engine.enrich(
        base,
        analysis,
        mart,
        OLDER_RUNS_LIMIT,
        stats_window_years,
    )

    race_date = enriched["race"]["date"]
    metadata = enriched.setdefault("metadata", {})
    metadata.pop("history_enrichment_poc", None)
    metadata["history_enrichment"] = production_metadata(
        base_schema_version,
        race_date,
        stats_window_years,
        warnings,
    )
    enriched["schema_version"] = SCHEMA_VERSION
    return enriched, warnings


def main() -> int:
    """Enrich one base RaceNote bundle and write stable v1.0 JSON."""
    args = parse_args()
    base = json.loads(args.bundle.read_text(encoding="utf-8"))

    analysis = sqlite3.connect(args.analysis)
    mart = sqlite3.connect(args.mart)
    analysis.row_factory = sqlite3.Row
    mart.row_factory = sqlite3.Row
    try:
        enriched, warnings = enrich_production(
            base,
            analysis,
            mart,
            args.stats_window_years,
        )
    finally:
        analysis.close()
        mart.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(enriched, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "success",
                "schema_version": SCHEMA_VERSION,
                "output": str(args.output),
                "warning_count": len(warnings),
                "warnings": warnings,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
