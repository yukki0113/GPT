#!/usr/bin/env python3
"""Day-level RaceNote production orchestrator.

D2 connects deterministic Stage A (PACI -> all base RaceNotes) and Stage B
(Analysis/history/P1/P2 bulk enrichment). RRDB/Reader/package cutover remains
fail-closed until D3-D4.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import racenote_history_enrichment as history
import racenote_jrdb as jrdb
from racenote_analysis_backend import AnalysisBackendError, open_analysis_backend

PIPELINE_VERSION = "RaceNote-Daily-Build-0.1"
MANIFEST_SCHEMA_VERSION = "RaceNote-Daily-Build-Manifest-0.1"
STAGE_NAMES = ("base", "history", "rrdb", "reader", "validation", "package")


class DailyBuildError(RuntimeError):
    """Raised when a connected daily-build stage cannot complete safely."""


class DailyBuildNotImplementedError(RuntimeError):
    """Raised when execution reaches a later D-stage not yet connected."""


def iso_date(value: str) -> str:
    """Normalize YYYY-MM-DD / YYYYMMDD into ISO date."""
    text = value.strip()
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "target date must be YYYY-MM-DD or YYYYMMDD"
        ) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build one day's RaceNote packages through base -> history/P1/P2 "
            "-> RRDB -> Reader View -> validation -> package."
        )
    )
    parser.add_argument("--date", required=True, type=iso_date, dest="target_date")
    parser.add_argument("--paci", required=True, type=Path)
    parser.add_argument("--analysis-root", required=True, type=Path)
    rrdb_source = parser.add_mutually_exclusive_group(required=True)
    rrdb_source.add_argument("--racereview-root", type=Path)
    rrdb_source.add_argument("--racereview-current-cache", type=Path)
    parser.add_argument("--next-watch-rules", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--keep-intermediate",
        action="store_true",
        help="Debug only; retain non-canonical connected-stage outputs.",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Print the execution plan without building RaceNote.",
    )
    return parser.parse_args()


def build_plan(args: argparse.Namespace) -> dict[str, Any]:
    rrdb_source: dict[str, str]
    if args.racereview_root is not None:
        rrdb_source = {
            "mode": "generation_root",
            "path": str(args.racereview_root),
        }
    else:
        rrdb_source = {
            "mode": "current_cache",
            "path": str(args.racereview_current_cache),
        }
    output_root = args.output / f"RaceNote_{args.target_date.replace('-', '')}"
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "target_date": args.target_date,
        "status": "PLANNED",
        "pipeline_version": PIPELINE_VERSION,
        "stages": {
            "base": "PLANNED",
            "history": "PLANNED",
            "rrdb": "NOT_RUN",
            "reader": "NOT_RUN",
            "validation": "NOT_RUN",
            "package": "NOT_RUN",
        },
        "sources": {
            "paci": {"path": str(args.paci)},
            "analysis": {"root": str(args.analysis_root), "backend": "parquet"},
            "rrdb": rrdb_source,
            "next_watch": {"path": str(args.next_watch_rules)},
        },
        "counts": {
            "races_expected": None,
            "races_built": 0,
            "reader_views": 0,
            "horses": 0,
            "technical_skips": 0,
        },
        "firewall": {
            "target_result_exposed": None,
            "market_exposed": None,
            "analysis_as_of_violations": None,
            "rrdb_as_of_violations": None,
        },
        "validation": {
            "base": "PLANNED",
            "history": "PLANNED",
            "pedigree": "PLANNED",
            "rrdb": "NOT_RUN",
            "reader_roundtrip": "NOT_RUN",
        },
        "artifacts": {
            "authoritative_dir": str(output_root / "authoritative"),
            "reader_dir": str(output_root / "reader"),
            "manifest": str(output_root / "manifest.json"),
            "validation_report": str(output_root / "validation_report.json"),
        },
        "warnings": [
            "D2 connects BASE/HISTORY only; RRDB/Reader/package are not yet production-active."
        ],
        "errors": [],
    }


def _migration_semantic_copy(bundle: dict[str, Any]) -> dict[str, Any]:
    """Drop execution-only metadata before old-vs-daily migration hashing.

    This does not alter the RaceNote artifact. It exists only because independent
    executions naturally differ in generated_at, local source paths and query
    telemetry even when the evidence payload is identical.
    """
    value = copy.deepcopy(bundle)
    metadata = value.get("metadata")
    if isinstance(metadata, dict):
        metadata.pop("generated_at", None)
        enrichment = metadata.get("history_enrichment")
        if isinstance(enrichment, dict):
            source = enrichment.get("analysis_source")
            if isinstance(source, dict):
                for key in (
                    "path",
                    "manifest_path",
                    "query_count",
                    "parquet_scan_count",
                ):
                    source.pop(key, None)
    return value


def evidence_semantic_sha256(bundle: dict[str, Any]) -> str:
    """Return migration hash excluding execution-only metadata."""
    encoded = json.dumps(
        _migration_semantic_copy(bundle),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_base_bundles(
    paci_path: Path,
    target_date: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Parse PACI once and build every base RaceNote bundle for one date."""
    if not paci_path.is_file():
        raise DailyBuildError(f"PACI ZIP not found: {paci_path}")

    audit = jrdb.Audit()
    parsed = jrdb.parse_zip(paci_path, audit)
    date_raw = parsed["BAC"][0]["date_raw"] if parsed.get("BAC") else None
    if not date_raw:
        raise DailyBuildError("BAC does not contain a target date")
    actual_date = jrdb.ymd(date_raw)
    if actual_date != target_date:
        raise DailyBuildError(
            f"PACI target date mismatch: requested={target_date} actual={actual_date}"
        )

    horses_by_race: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for horse in parsed["KYI"]:
        horses_by_race[horse["race_key_raw"]].append(horse)

    builder = jrdb.BundleBuilder(parsed, audit)
    bundles: list[dict[str, Any]] = []
    identities: list[dict[str, Any]] = []
    for bac in parsed["BAC"]:
        key = bac["race_key_raw"]
        parts = jrdb.race_key_parts(key)
        venue = jrdb.decode(
            parts["venue_code"],
            jrdb.VENUES,
            "venue",
            audit,
        ) or parts["venue_code"]
        label = f"{venue}{parts['race_no']}R"
        try:
            bundle = builder.build(bac, horses_by_race.get(key, []))
        except Exception as exc:
            audit.bundle_errors.append(f"{label}: {type(exc).__name__}: {exc}")
            continue
        bundles.append(bundle)
        identities.append({
            "venue": venue,
            "race_no": parts["race_no"],
            "label": label,
            "horse_count": len(bundle.get("horses", [])),
        })

    errors = list(audit.bundle_errors)
    if len(bundles) != len(parsed["BAC"]):
        errors.append(
            f"bundle count mismatch BAC={len(parsed['BAC'])} generated={len(bundles)}"
        )
    if errors:
        raise DailyBuildError("; ".join(errors))

    report = {
        "target_date": actual_date,
        "date_raw": date_raw,
        "race_count": len(bundles),
        "horse_count": sum(len(x.get("horses", [])) for x in bundles),
        "record_counts": {name: len(rows) for name, rows in parsed.items()},
        "unknown_code_count": sum(audit.warnings.values()),
        "warnings": [f"{key}:{count}" for key, count in audit.warnings.most_common()],
        "target_result_contamination": audit.target_result_contamination,
        "races": identities,
    }
    return bundles, report


def enrich_history_bundles(
    bases: list[dict[str, Any]],
    analysis: Any,
    stats_window_years: int = history.DEFAULT_STATS_WINDOW_YEARS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Bulk-enrich all daily RaceNotes through History/Trend/P1/P2."""
    items = history.enrich_production_many(
        bases,
        analysis,
        stats_window_years,
    )
    metrics = analysis.metrics()
    source_info = copy.deepcopy(analysis.source_info)
    source_info.update(metrics)

    bundles: list[dict[str, Any]] = []
    warnings: list[str] = []
    for enriched, item_warnings in items:
        history_meta = enriched.setdefault("metadata", {}).setdefault(
            "history_enrichment",
            {},
        )
        history_meta["analysis_backend"] = analysis.source_info.get(
            "backend",
            "sqlite",
        )
        history_meta["analysis_source"] = copy.deepcopy(source_info)
        bundles.append(enriched)
        warnings.extend(item_warnings)

    return bundles, {
        "race_count": len(bundles),
        "horse_count": sum(len(x.get("horses", [])) for x in bundles),
        "warning_count": len(warnings),
        "warnings": warnings,
        "analysis_source": source_info,
    }


def build_through_history(
    *,
    paci_path: Path,
    target_date: str,
    analysis_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Execute D2: parse PACI once, open Analysis once, bulk-enrich all races."""
    bases, base_report = build_base_bundles(paci_path, target_date)
    try:
        analysis = open_analysis_backend(
            analysis_root=analysis_root,
            backend="parquet",
        )
        enriched, history_report = enrich_history_bundles(bases, analysis)
    except AnalysisBackendError as exc:
        raise DailyBuildError(str(exc)) from exc
    finally:
        if "analysis" in locals():
            analysis.close()

    report = {
        "pipeline_version": PIPELINE_VERSION,
        "target_date": target_date,
        "status": "D2_PASS",
        "stages": {
            "base": "PASS",
            "history": "PASS",
            "rrdb": "NOT_RUN",
            "reader": "NOT_RUN",
            "validation": "NOT_RUN",
            "package": "NOT_RUN",
        },
        "base": base_report,
        "history": history_report,
        "migration_hashes": [
            {
                "race": {
                    "venue": bundle["race"]["venue"],
                    "race_no": bundle["race"]["race_no"],
                },
                "evidence_semantic_sha256": evidence_semantic_sha256(bundle),
            }
            for bundle in enriched
        ],
    }
    return enriched, report


def _write_d2_debug(
    args: argparse.Namespace,
    bundles: list[dict[str, Any]],
    report: dict[str, Any],
) -> Path:
    root = (
        args.output
        / f"RaceNote_{args.target_date.replace('-', '')}"
        / ".debug"
        / "history"
    )
    root.mkdir(parents=True, exist_ok=True)
    for bundle in bundles:
        race = bundle["race"]
        path = root / (
            f"race_bundle_{args.target_date.replace('-', '')}_"
            f"{race['venue']}{race['race_no']}R.json"
        )
        path.write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    report_path = root / "d2_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report_path


def run(args: argparse.Namespace) -> int:
    if args.plan:
        print(json.dumps(build_plan(args), ensure_ascii=False, indent=2))
        return 0

    bundles, report = build_through_history(
        paci_path=args.paci,
        target_date=args.target_date,
        analysis_root=args.analysis_root,
    )
    if args.keep_intermediate:
        report["debug_report"] = str(_write_d2_debug(args, bundles, report))

    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise DailyBuildNotImplementedError(
        "D2 BASE/HISTORY completed successfully, but RRDB/Reader/package are "
        "not connected yet. D3 will connect formal RRDB daily enrichment."
    )


def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except DailyBuildNotImplementedError as exc:
        print(json.dumps({
            "status": "NOT_IMPLEMENTED_AFTER_D2",
            "pipeline_version": PIPELINE_VERSION,
            "error": str(exc),
        }, ensure_ascii=False))
        return 3
    except DailyBuildError as exc:
        print(json.dumps({
            "status": "FAIL",
            "pipeline_version": PIPELINE_VERSION,
            "error": str(exc),
        }, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
