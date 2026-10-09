#!/usr/bin/env python3
"""Run a 2010-2025 Raw/Warehouse golden day through the common v0.5.2 path.

This is an acceptance probe. It never enables historical BTDAY. A separate
operation may use Warehouse input only after its full report says PASS.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from datetime import date
from pathlib import Path

from build_racenote_daily import (
    build_daily_package, build_reader_views, enrich_history_bundles,
    enrich_rrdb_bundles, validate_daily_bundles, write_daily_package,
)
from jrdb_raw import Parser, iter_archive_records, race_key
from jrdb_racenote_raw_adapter import build_paci_equivalent
from racenote_analysis_backend import open_analysis_backend
from racenote_prepare_forecast_input import bind
from racenote_request import RaceNoteRequest, build_historical_warehouse_base
from racenote_v052_equivalence import compare
from racenote_v052_single_day import init_session


def build_warehouse_daily(
    *, day: date, warehouse_current: Path, warehouse_asset_root: Path,
    analysis_root: Path, racereview_root: Path, output_root: Path,
    rrdb_work_root: Path,
) -> tuple[dict, dict]:
    """Use the canonical Warehouse Reader and existing common D2-D4 stages."""
    request = RaceNoteRequest(day, None, None, date.today())
    base_dir, warehouse_report = build_historical_warehouse_base(
        request, warehouse_current,
        [f"{family}={warehouse_asset_root}" for family in
         ("BAC", "KYI", "CHA", "CYB", "ZED", "ZKB")],
        rrdb_work_root / "base",
    )
    warehouse = {}
    for path in sorted(base_dir.glob("race_bundle_*.json")):
        bundle = json.loads(path.read_text(encoding="utf-8"))
        race = bundle["race"]
        key = (race["venue"], race["race_no"])
        if key in warehouse:
            raise ValueError(f"duplicate Warehouse race: {key}")
        warehouse[key] = bundle
    for bundle in warehouse.values():
        if bundle["race"]["date"] != day.isoformat():
            raise ValueError("Warehouse race date differs from target")
        for horse in bundle["horses"]:
            for run in horse.get("recent_runs") or []:
                run_date = (run.get("race") or {}).get("date")
                if isinstance(run_date, str) and run_date >= day.isoformat():
                    raise ValueError("target/future result in Warehouse recent_runs")
    analysis = open_analysis_backend(analysis_root=analysis_root, backend="parquet")
    try:
        bases = [warehouse[key] for key in sorted(warehouse)]
        history_bundles, history_report = enrich_history_bundles(bases, analysis)
    finally:
        analysis.close()
    enriched, rrdb_report = enrich_rrdb_bundles(
        history_bundles, racereview_root=racereview_root,
        racereview_current_cache=None, next_watch_rules=None,
        work_root=rrdb_work_root,
    )
    views, reader_report = build_reader_views(enriched)
    target_date = day.isoformat()
    report = {
        "base": {"target_date": target_date, "date_raw": day.strftime("%Y%m%d"),
                 "race_count": len(bases), "target_result_contamination": 0,
                 "record_counts": warehouse_report["record_counts"]},
        "history": history_report, "rrdb": rrdb_report, "reader": reader_report,
    }
    validation = validate_daily_bundles(enriched, views, report, target_date)
    package = write_daily_package(
        bundles=enriched, views=views, report=report, validation=validation,
        target_date=target_date, output_root=output_root,
    )
    manifest_path = Path(package["manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["sources"].pop("paci", None)
    manifest["sources"]["historical_warehouse"] = {
        "generation_id": warehouse_report["generation_id"],
        "target_date": target_date,
        "as_of_exclusive": target_date,
        "record_counts": warehouse_report["record_counts"],
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return warehouse, warehouse_report


def run(args: argparse.Namespace) -> dict:
    day = date.fromisoformat(args.date)
    if not 2010 <= day.year <= 2025:
        raise ValueError("historical golden day must be in 2010-2025")
    if args.output_root.exists():
        raise FileExistsError(args.output_root)
    args.output_root.mkdir(parents=True)
    compact = day.strftime("%y%m%d")
    parser = Parser()
    keys = [race_key(row) for _, row in iter_archive_records(
        args.raw_root / "BAC" / f"BAC_{day.year}.zip", "BAC"
    ) if parser.bac(row).get("date_raw") == day.strftime("%Y%m%d")]
    if not keys:
        raise ValueError(f"no annual Raw BAC rows for {day}")
    paci = args.output_root / "paci_equivalent.zip"

    def require_raw(year: int, families: list[str]) -> None:
        for family in families:
            path = args.raw_root / family / f"{family}_{year}.zip"
            if not path.is_file():
                raise FileNotFoundError(path)

    raw_report = build_paci_equivalent(
        args.raw_root, day.year, compact, keys, paci, require_raw,
    )
    raw_root = args.output_root / "raw"
    warehouse_root = args.output_root / "warehouse"
    with tempfile.TemporaryDirectory(prefix="v052-historical-rrdb-") as tmp:
        build_daily_package(
            paci_path=paci, target_date=args.date,
            analysis_root=args.analysis_root, racereview_root=args.racereview_root,
            racereview_current_cache=None, next_watch_rules=None,
            output_root=raw_root / "day_prep", rrdb_work_root=Path(tmp) / "raw",
        )
        warehouse, warehouse_report = build_warehouse_daily(
            day=day, warehouse_current=args.warehouse_current,
            warehouse_asset_root=args.warehouse_asset_root,
            analysis_root=args.analysis_root,
            racereview_root=args.racereview_root,
            output_root=warehouse_root / "day_prep",
            rrdb_work_root=Path(tmp) / "warehouse",
        )

    for root in (raw_root, warehouse_root):
        daily = root / "day_prep" / f"RaceNote_{day:%Y%m%d}"
        prep = root / "forecast_prep"
        bind(daily, prep, args.selection_id, args.date, args.main_sha)
        init_session(prep, root / "v052", args.main_sha,
                     binding_path=args.binding, policy_path=args.policy)
    result = compare(raw_root, warehouse_root, args.date)
    result["raw_reconstruction"] = raw_report
    result["warehouse_reconstruction"] = warehouse_report
    result["golden_day"] = args.date
    result["as_of_exclusive"] = args.date
    (args.output_root / "equivalence_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument("--raw-root", required=True, type=Path)
    parser.add_argument("--warehouse-current", required=True, type=Path)
    parser.add_argument("--warehouse-asset-root", required=True, type=Path)
    parser.add_argument("--analysis-root", required=True, type=Path)
    parser.add_argument("--racereview-root", required=True, type=Path)
    parser.add_argument("--binding", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--selection-id", default="BTDAY-GOLDEN-20251228")
    parser.add_argument("--main-sha", required=True)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    result = run(args)
    print(json.dumps({"status": result["status"], "race_count": result["race_count"],
                      "horse_count": result["horse_count"],
                      "mismatches": result["mismatches"]}, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
