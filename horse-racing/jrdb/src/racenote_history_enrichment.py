#!/usr/bin/env python3
"""Production RaceNote history enrichment entrypoint.

The validated enrichment logic lives in ``racenote_history_engine.py``. This
module is the stable production entrypoint and owns the final RaceNote v1.0
contract:

- detailed PACI recent history: up to 5 runs
- compact Analysis Lite older history: up to 3 runs
- as-of-safe horse / sire / jockey / frame summaries
- overlapping distance ranges
- sample-size bands
- explicit history coverage / run-layer metadata

The shared engine can be refactored independently without changing this CLI or
the v1.0 output contract.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import racenote_history_engine as engine
import racenote_rrdb_enrichment as rrdb
from jrdb_postrace_review_reader import RaceReviewReader
from racenote_analysis_backend import AnalysisBackendError, open_analysis_backend
from racenote_racereview_current import resolve_racereview_current

SCHEMA_VERSION = "1.0"
OLDER_RUNS_LIMIT = 3
DEFAULT_STATS_WINDOW_YEARS = 5


def parse_args() -> argparse.Namespace:
    """Parse production enrichment CLI arguments."""
    parser = argparse.ArgumentParser(description="Production RaceNote v1.0 history enrichment")
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--analysis-root", type=Path, default=None)
    parser.add_argument("--analysis", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--analysis-backend", choices=("parquet", "sqlite"), default="parquet")
    parser.add_argument("--output", type=Path, required=True)
    rrdb_source = parser.add_mutually_exclusive_group(required=False)
    rrdb_source.add_argument("--racereview-root", type=Path)
    rrdb_source.add_argument("--racereview-current-cache", type=Path)
    parser.add_argument("--next-watch-rules", type=Path, default=None)
    parser.add_argument("--rrdb-work-root", type=Path, default=None)
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
            "all rolling statistics from JRDB Analysis canonical with race_date < target_date"
        ),
        "pedigree_enrichment": {
            "identity_version": "P1-0.1",
            "context_version": "P2-0.1",
            "status": "ACTIVE",
            "scoring": False,
            "identity_source": "JRDB Analysis canonical target identity projection",
            "historical_context_source": "JRDB Analysis canonical (as-of-exclusive)",
            "approved_identity_fields": [
                "horse_id",
                "sire_name",
                "dam_name",
                "broodmare_sire_name",
                "sire_line_code",
                "broodmare_sire_line_code",
            ],
            "historical_dimensions": [
                "sire_name",
                "broodmare_sire_name"
            ],
            "condition_scope": "venue_surface_exact_distance_plus_target_distance_ranges",
            "small_sample_policy": "retain_with_sample_size",
            "missing_field_policy": "null_no_guess",
            "result_fields_exposed": False,
        },
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
    analysis: object,
    stats_window_years: int,
) -> tuple[dict, list[str]]:
    """Build one stable RaceNote v1.0 bundle from the validated enrichment engine."""
    base_schema_version = base.get("schema_version")
    enriched, warnings = engine.enrich(
        base,
        analysis,
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


def enrich_production_many(
    bases: list[dict],
    analysis: object,
    stats_window_years: int,
) -> list[tuple[dict, list[str]]]:
    """Enrich a request's bundles using shared bulk SQL aggregates."""
    enriched_items = engine.enrich_many(
        bases,
        analysis,
        OLDER_RUNS_LIMIT,
        stats_window_years,
    )
    output: list[tuple[dict, list[str]]] = []
    for base, (enriched, warnings) in zip(bases, enriched_items):
        metadata = enriched.setdefault("metadata", {})
        metadata.pop("history_enrichment_poc", None)
        metadata["history_enrichment"] = production_metadata(
            base.get("schema_version"),
            enriched["race"]["date"],
            stats_window_years,
            warnings,
        )
        enriched["schema_version"] = SCHEMA_VERSION
        output.append((enriched, warnings))
    return output


def main() -> int:
    """Enrich one base RaceNote bundle and write stable v1.0 JSON."""
    args = parse_args()
    base = json.loads(args.bundle.read_text(encoding="utf-8"))

    try:
        analysis = open_analysis_backend(
            analysis_root=args.analysis_root,
            analysis_db=args.analysis,
            backend=args.analysis_backend,
        )
        enriched, warnings = enrich_production(
            base,
            analysis,
            args.stats_window_years,
        )
        enriched.setdefault("metadata", {})["history_enrichment"]["analysis_backend"] = (
            analysis.source_info.get("backend", "sqlite")
        )
        enriched["metadata"]["history_enrichment"]["analysis_source"] = analysis.source_info
        enriched["metadata"]["history_enrichment"]["analysis_source"].update(analysis.metrics())

        rrdb_requested = (
            args.racereview_root is not None
            or args.racereview_current_cache is not None
        )
        if rrdb_requested:
            if args.next_watch_rules is None:
                raise SystemExit(
                    "--next-watch-rules is required when RRDB enrichment is requested"
                )
            rrdb_work_root = args.rrdb_work_root or (
                args.output.parent / ".racenote_rrdb_work"
            )
            rrdb_work_root.mkdir(parents=True, exist_ok=True)
            contract = rrdb.load_frozen_contract(
                args.next_watch_rules,
                rrdb_work_root,
            )
            if args.racereview_root is not None:
                rrdb_reader = RaceReviewReader(args.racereview_root)
            else:
                resolved = resolve_racereview_current(
                    args.racereview_current_cache,
                )
                rrdb_reader = resolved.reader
            enriched = rrdb.enrich_bundle(
                enriched,
                rrdb_reader,
                contract,
                per_horse_limit=5,
            )
    except AnalysisBackendError as error:
        raise SystemExit(str(error)) from error
    finally:
        if "analysis" in locals():
            analysis.close()

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
                "rrdb_enrichment": (
                    enriched.get("metadata", {}).get("racereview_enrichment")
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
