#!/usr/bin/env python3
"""Day-level RaceNote production orchestrator.

Stages A-F are connected: PACI -> base -> History/P1/P2 -> RRDB -> Reader View
-> validation -> package. D5 real-data semantic equivalence passed on
2026-09-30; this is the production day-level RaceNote entrypoint.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import racenote_history_enrichment as history
import racenote_jrdb as jrdb
import racenote_rrdb_enrichment as rrdb
import racenote_reader_view as reader_view
from jrdb_postrace_review_reader import RaceReviewReader
from racenote_analysis_backend import AnalysisBackendError, open_analysis_backend
from racenote_racereview_current import (
    RaceReviewCurrentResolverError,
    resolve_racereview_current,
)

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
    parser.add_argument(
        "--next-watch-rules",
        required=False,
        type=Path,
        default=None,
        help="Deprecated legacy compatibility input; current RRDB recommendation v0.2 does not require it.",
    )
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
            "rrdb_recommendation": {
                "contract_version": rrdb.RECOMMENDATION_VERSION,
                "grade_status": "DISABLED",
                "lookback_days": rrdb.OPERATIONAL_LOOKBACK_DAYS,
            },
            "legacy_next_watch": (
                {"path": str(args.next_watch_rules)}
                if args.next_watch_rules is not None
                else None
            ),
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
            "Daily builder is the production day-level entrypoint; one-race builders remain supported for single-race use, audit and rollback."
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


def enrich_rrdb_bundles(
    bundles: list[dict[str, Any]],
    *,
    racereview_root: Path | None,
    racereview_current_cache: Path | None,
    next_watch_rules: Path | None,
    work_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Resolve RRDB once and enrich all daily RaceNotes with recommendation v0.2."""
    work_root.mkdir(parents=True, exist_ok=True)
    try:
        contract = (
            rrdb.load_frozen_contract(next_watch_rules, work_root)
            if next_watch_rules is not None
            else None
        )

        if racereview_root is not None:
            reader = RaceReviewReader(racereview_root)
            rrdb_source = {
                "mode": "generation_root",
                "root": str(racereview_root),
                "generation_id": reader.generation_id,
            }
        else:
            if racereview_current_cache is None:
                raise DailyBuildError("RRDB current cache is required")
            resolved = resolve_racereview_current(racereview_current_cache)
            reader = resolved.reader
            rrdb_source = {
                "mode": "current_cache",
                "root": str(resolved.root),
                "generation_id": reader.generation_id,
                "provenance": resolved.provenance,
            }

        enriched = rrdb.enrich_bundles(
            bundles,
            reader,
            contract,
            per_horse_limit=5,
        )
    except (
        rrdb.RRDBEnrichmentError,
        RaceReviewCurrentResolverError,
    ) as exc:
        raise DailyBuildError(str(exc)) from exc

    return enriched, {
        "race_count": len(enriched),
        "horse_count": sum(len(x.get("horses", [])) for x in enriched),
        "rrdb_source": rrdb_source,
        "rrdb_generation_id": reader.generation_id,
        "recommendation_contract_version": rrdb.RECOMMENDATION_VERSION,
        "recommendation_grade_status": "DISABLED",
        "operational_lookback_days": rrdb.OPERATIONAL_LOOKBACK_DAYS,
        "legacy_next_watch_rule_version": (
            contract.get("rule_version") if contract is not None else None
        ),
        "enrichment_version": rrdb.VERSION,
        "source_resolutions": {
            "rrdb": 1,
            "legacy_next_watch_contract": 1 if contract is not None else 0,
        },
    }


def build_through_rrdb(
    *,
    paci_path: Path,
    target_date: str,
    analysis_root: Path,
    racereview_root: Path | None,
    racereview_current_cache: Path | None,
    next_watch_rules: Path | None,
    rrdb_work_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Execute D3: D2 stages plus one shared daily RRDB enrichment."""
    bundles, report = build_through_history(
        paci_path=paci_path,
        target_date=target_date,
        analysis_root=analysis_root,
    )
    enriched, rrdb_report = enrich_rrdb_bundles(
        bundles,
        racereview_root=racereview_root,
        racereview_current_cache=racereview_current_cache,
        next_watch_rules=next_watch_rules,
        work_root=rrdb_work_root,
    )
    report["status"] = "D3_PASS"
    report["stages"]["rrdb"] = "PASS"
    report["rrdb"] = rrdb_report
    report["migration_hashes"] = [
        {
            "race": {
                "venue": bundle["race"]["venue"],
                "race_no": bundle["race"]["race_no"],
            },
            "evidence_semantic_sha256": evidence_semantic_sha256(bundle),
        }
        for bundle in enriched
    ]
    return enriched, report



def _bundle_identity(bundle: dict[str, Any]) -> dict[str, Any]:
    race = bundle.get("race")
    if not isinstance(race, dict):
        raise DailyBuildError("RaceNote bundle is missing race")
    return {
        "venue": race.get("venue"),
        "race_no": race.get("race_no"),
        "race_key": race.get("race_key"),
    }


def _artifact_stem(target_date: str, bundle: dict[str, Any]) -> str:
    race = bundle["race"]
    venue = str(race.get("venue") or "UNKNOWN")
    race_no = str(race.get("race_no") or "00")
    safe_venue = "".join(ch for ch in venue if ch.isalnum() or ch in ("-", "_"))
    if not safe_venue:
        safe_venue = "UNKNOWN"
    return f"{target_date.replace('-', '')}_{safe_venue}{race_no}R"


def build_reader_views(
    bundles: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build and round-trip validate one lossless Reader View per bundle."""
    views: list[dict[str, Any]] = []
    races: list[dict[str, Any]] = []
    for bundle in bundles:
        try:
            view = reader_view.build_reader_view(bundle)
            expanded = reader_view.expand_reader_view(view, validate_hash=True)
        except reader_view.ReaderViewError as exc:
            ident = _bundle_identity(bundle)
            raise DailyBuildError(
                f"Reader View failed for {ident['venue']}{ident['race_no']}R: {exc}"
            ) from exc
        if expanded != bundle:
            ident = _bundle_identity(bundle)
            raise DailyBuildError(
                f"Reader View semantic round-trip mismatch for "
                f"{ident['venue']}{ident['race_no']}R"
            )
        views.append(view)
        races.append({
            "race": _bundle_identity(bundle),
            "source_semantic_sha256": view["source_semantic_sha256"],
            "roundtrip_validation": "PASS",
        })
    return views, {
        "race_count": len(views),
        "view_version": reader_view.VIEW_VERSION,
        "roundtrip_validation": "PASS",
        "races": races,
    }


def _iter_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_dicts(child)


def validate_daily_bundles(
    bundles: list[dict[str, Any]],
    views: list[dict[str, Any]],
    report: dict[str, Any],
    target_date: str,
) -> dict[str, Any]:
    """Apply request/race-level D4 gates without changing RaceNote semantics."""
    errors: list[str] = []
    warnings: list[str] = []

    if len(bundles) != len(views):
        errors.append(
            f"Reader count mismatch bundles={len(bundles)} views={len(views)}"
        )

    base = report.get("base", {})
    contamination = int(base.get("target_result_contamination") or 0)
    if contamination:
        errors.append(f"target-result contamination count={contamination}")

    analysis_as_of_violations = 0
    rrdb_as_of_violations = 0
    for bundle in bundles:
        race = bundle.get("race") or {}
        if race.get("date") != target_date:
            errors.append(
                f"race target date mismatch: {race.get('venue')}{race.get('race_no')}R "
                f"date={race.get('date')}"
            )

        for node in _iter_dicts(bundle):
            if "as_of_exclusive" in node:
                as_of = node.get("as_of_exclusive")
                if as_of not in (None, target_date):
                    analysis_as_of_violations += 1

        horses = bundle.get("horses") or []
        for horse in horses:
            if not isinstance(horse, dict):
                continue
            block = horse.get("racereview")
            if not isinstance(block, dict):
                continue
            for node in _iter_dicts(block):
                race_date = node.get("race_date")
                if isinstance(race_date, str) and race_date >= target_date:
                    rrdb_as_of_violations += 1

    if analysis_as_of_violations:
        errors.append(
            f"Analysis/history as-of violations={analysis_as_of_violations}"
        )
    if rrdb_as_of_violations:
        errors.append(f"RRDB as-of violations={rrdb_as_of_violations}")

    rrdb_report = report.get("rrdb") or {}
    if not rrdb_report.get("rrdb_generation_id"):
        errors.append("RRDB generation provenance is missing")
    if rrdb_report.get("recommendation_contract_version") != rrdb.RECOMMENDATION_VERSION:
        errors.append("RRDB recommendation contract provenance is missing or stale")
    if rrdb_report.get("recommendation_grade_status") != "DISABLED":
        errors.append("RRDB recommendation grade must remain disabled")

    status = "PASS" if not errors else "FAIL"
    return {
        "status": status,
        "target_date": target_date,
        "race_count": len(bundles),
        "reader_view_count": len(views),
        "firewall": {
            "target_result_exposed": bool(contamination),
            "market_exposed": False,
            "analysis_as_of_violations": analysis_as_of_violations,
            "rrdb_as_of_violations": rrdb_as_of_violations,
        },
        "checks": {
            "race_structure": status,
            "provenance": "PASS" if not any("provenance" in x for x in errors) else "FAIL",
            "reader_roundtrip": "PASS" if len(bundles) == len(views) else "FAIL",
        },
        "warnings": warnings,
        "errors": errors,
    }


def write_daily_package(
    *,
    bundles: list[dict[str, Any]],
    views: list[dict[str, Any]],
    report: dict[str, Any],
    validation: dict[str, Any],
    target_date: str,
    output_root: Path,
) -> dict[str, Any]:
    """Write canonical D4 authoritative/reader package and manifest."""
    if validation.get("status") != "PASS":
        raise DailyBuildError(
            "D4 validation failed: " + "; ".join(validation.get("errors") or [])
        )

    root = output_root / f"RaceNote_{target_date.replace('-', '')}"
    authoritative_dir = root / "authoritative"
    reader_dir = root / "reader"
    authoritative_dir.mkdir(parents=True, exist_ok=True)
    reader_dir.mkdir(parents=True, exist_ok=True)

    authoritative_files: list[str] = []
    reader_files: list[str] = []
    for bundle, view in zip(bundles, views, strict=True):
        stem = _artifact_stem(target_date, bundle)
        authoritative = authoritative_dir / f"race_bundle_{stem}.json"
        reader = reader_dir / f"racenote_reader_{stem}.json"
        authoritative.write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        reader_view.write_reader_view(reader, view, pretty=False)
        authoritative_files.append(str(authoritative))
        reader_files.append(str(reader))

    validation_path = root / "validation_report.json"
    validation_path.write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "target_date": target_date,
        "status": "PASS",
        "pipeline_version": PIPELINE_VERSION,
        "stages": {name: "PASS" for name in STAGE_NAMES},
        "sources": {
            "paci": {
                "target_date": report["base"].get("target_date"),
                "date_raw": report["base"].get("date_raw"),
                "record_counts": report["base"].get("record_counts"),
            },
            "analysis": report["history"].get("analysis_source"),
            "rrdb": report["rrdb"].get("rrdb_source"),
            "rrdb_recommendation": {
                "contract_version": report["rrdb"].get("recommendation_contract_version"),
                "grade_status": report["rrdb"].get("recommendation_grade_status"),
                "lookback_days": report["rrdb"].get("operational_lookback_days"),
            },
            "legacy_next_watch": {
                "rule_version": report["rrdb"].get("legacy_next_watch_rule_version"),
                "status": "HISTORICAL_COMPATIBILITY_ONLY",
            },
        },
        "counts": {
            "races_expected": report["base"].get("race_count"),
            "races_built": len(bundles),
            "reader_views": len(views),
            "horses": sum(len(x.get("horses", [])) for x in bundles),
            "technical_skips": 0,
        },
        "firewall": validation["firewall"],
        "validation": {
            "base": "PASS",
            "history": "PASS",
            "pedigree": "PASS",
            "rrdb": "PASS",
            "reader_roundtrip": validation["checks"]["reader_roundtrip"],
        },
        "artifacts": {
            "authoritative_dir": str(authoritative_dir),
            "reader_dir": str(reader_dir),
            "manifest": str(root / "manifest.json"),
            "validation_report": str(validation_path),
        },
        "warnings": list(report["base"].get("warnings") or [])
        + list(report["history"].get("warnings") or [])
        + list(validation.get("warnings") or []),
        "errors": [],
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return {
        "root": str(root),
        "authoritative_files": authoritative_files,
        "reader_files": reader_files,
        "manifest": str(manifest_path),
        "validation_report": str(validation_path),
        "manifest_payload": manifest,
    }


def build_daily_package(
    *,
    paci_path: Path,
    target_date: str,
    analysis_root: Path,
    racereview_root: Path | None,
    racereview_current_cache: Path | None,
    next_watch_rules: Path | None,
    output_root: Path,
    rrdb_work_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Execute D4 through Reader, validation and final package."""
    bundles, report = build_through_rrdb(
        paci_path=paci_path,
        target_date=target_date,
        analysis_root=analysis_root,
        racereview_root=racereview_root,
        racereview_current_cache=racereview_current_cache,
        next_watch_rules=next_watch_rules,
        rrdb_work_root=rrdb_work_root,
    )
    views, reader_report = build_reader_views(bundles)
    report["reader"] = reader_report
    report["stages"]["reader"] = "PASS"

    validation = validate_daily_bundles(
        bundles,
        views,
        report,
        target_date,
    )
    if validation["status"] != "PASS":
        raise DailyBuildError(
            "D4 validation failed: " + "; ".join(validation["errors"])
        )
    report["validation"] = validation
    report["stages"]["validation"] = "PASS"

    package = write_daily_package(
        bundles=bundles,
        views=views,
        report=report,
        validation=validation,
        target_date=target_date,
        output_root=output_root,
    )
    report["package"] = package
    report["stages"]["package"] = "PASS"
    report["status"] = "PASS"
    return package["manifest_payload"], report, bundles


def _write_d3_debug(
    args: argparse.Namespace,
    bundles: list[dict[str, Any]],
    report: dict[str, Any],
) -> Path:
    root = (
        args.output
        / f"RaceNote_{args.target_date.replace('-', '')}"
        / ".debug"
        / "rrdb"
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
    report_path = root / "d3_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report_path


def run(args: argparse.Namespace) -> int:
    if args.plan:
        print(json.dumps(build_plan(args), ensure_ascii=False, indent=2))
        return 0

    if args.keep_intermediate:
        rrdb_work_root = (
            args.output
            / f"RaceNote_{args.target_date.replace('-', '')}"
            / ".debug"
            / "rrdb_work"
        )
        manifest, report, bundles = build_daily_package(
            paci_path=args.paci,
            target_date=args.target_date,
            analysis_root=args.analysis_root,
            racereview_root=args.racereview_root,
            racereview_current_cache=args.racereview_current_cache,
            next_watch_rules=args.next_watch_rules,
            output_root=args.output,
            rrdb_work_root=rrdb_work_root,
        )
        report["debug_report"] = str(_write_d3_debug(args, bundles, report))
    else:
        with tempfile.TemporaryDirectory(prefix="racenote-daily-rrdb-") as tmp:
            manifest, report, bundles = build_daily_package(
                paci_path=args.paci,
                target_date=args.target_date,
                analysis_root=args.analysis_root,
                racereview_root=args.racereview_root,
                racereview_current_cache=args.racereview_current_cache,
                next_watch_rules=args.next_watch_rules,
                output_root=args.output,
                rrdb_work_root=Path(tmp),
            )

    print(json.dumps({
        "status": "success",
        "pipeline_version": PIPELINE_VERSION,
        "daily_status": report["status"],
        "manifest": manifest,
    }, ensure_ascii=False, indent=2, default=str))
    return 0

def main() -> int:
    args = parse_args()
    try:
        return run(args)
    except DailyBuildError as exc:
        print(json.dumps({
            "status": "FAIL",
            "pipeline_version": PIPELINE_VERSION,
            "error": str(exc),
        }, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
