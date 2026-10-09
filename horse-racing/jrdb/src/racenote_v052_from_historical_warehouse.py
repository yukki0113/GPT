#!/usr/bin/env python3
"""Prepare a 2010-2025 historical BTDAY after a full Raw/Warehouse gate PASS.

The output enters the unchanged forecast_prep and v0.5.2 single-day session.
Authoring, freeze and verify remain the existing single-day commands.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from datetime import date
from pathlib import Path

from racenote_prepare_forecast_input import bind
from racenote_v052_historical_probe import build_warehouse_daily
from racenote_v052_single_day import init_session

VERSION = "racenote-v052-from-historical-warehouse-0.1"
REQUIRED_PASS = (
    "race_roster_equal", "horse_roster_equal", "racenote_semantic_equal",
    "normal_view_semantic_equal", "reader_manifest_identity_equal",
    "source_semantic_normalized_equal",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_gate(path: Path, current: Path) -> dict:
    report = json.loads(path.read_text(encoding="utf-8"))
    pointer = json.loads(current.read_text(encoding="utf-8"))
    if report.get("status") != "PASS" or report.get("mismatch_count") != 0:
        raise ValueError("historical equivalence gate is not PASS")
    for key in REQUIRED_PASS:
        if report.get(key) is not True:
            raise ValueError(f"historical equivalence gate lacks {key}=true")
    views = report.get("normal_view_semantic_sha256") or {}
    raw_hashes = views.get("raw")
    warehouse_hashes = views.get("warehouse")
    if (not isinstance(raw_hashes, dict) or not raw_hashes
            or raw_hashes != warehouse_hashes
            or len(raw_hashes) != report.get("race_count")
            or not isinstance(report.get("horse_count"), int)
            or report["horse_count"] <= 0):
        raise ValueError("historical equivalence gate has inconsistent normal_view hashes")
    golden = date.fromisoformat(report["target_date"])
    if not 2010 <= golden.year <= 2025 or report.get("golden_day") != report["target_date"]:
        raise ValueError("historical equivalence gate has invalid golden day")
    generation = (report.get("warehouse_reconstruction") or {}).get("generation_id")
    if (pointer.get("status") != "accepted"
            or pointer.get("generation_id") != generation):
        raise ValueError("historical equivalence gate Warehouse generation differs")
    return report


def prepare(args: argparse.Namespace) -> dict:
    day = date.fromisoformat(args.date)
    if not 2010 <= day.year <= 2025:
        raise ValueError("Historical Warehouse source is limited to 2010-2025")
    if args.output_root.exists():
        raise FileExistsError(args.output_root)
    if len(args.main_sha) != 40 or any(c not in "0123456789abcdef" for c in args.main_sha):
        raise ValueError("--main-sha must be a full lowercase commit SHA")
    gate = validate_gate(args.equivalence_report, args.warehouse_current)
    args.output_root.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="v052-historical-rrdb-") as tmp:
        _, reconstruction = build_warehouse_daily(
            day=day, warehouse_current=args.warehouse_current,
            warehouse_asset_root=args.warehouse_asset_root,
            analysis_root=args.analysis_root,
            racereview_root=args.racereview_root,
            output_root=args.output_root / "day_prep",
            rrdb_work_root=Path(tmp),
        )
    if reconstruction["generation_id"] != gate["warehouse_reconstruction"]["generation_id"]:
        raise ValueError("Warehouse generation changed after acceptance gate")
    daily = args.output_root / "day_prep" / f"RaceNote_{day:%Y%m%d}"
    forecast_prep = args.output_root / "forecast_prep"
    handoff = bind(daily, forecast_prep, args.selection_id, args.date, args.main_sha)
    v052_root = args.output_root / "v052"
    session = init_session(forecast_prep, v052_root, args.main_sha,
                           binding_path=args.binding, policy_path=args.policy)
    operation = {
        "schema_version": VERSION,
        "status": "READY_FOR_V052_AUTHORING",
        "source_backend": "historical_warehouse",
        "source_generation_id": reconstruction["generation_id"],
        "source_current_sha256": sha256(args.warehouse_current),
        "equivalence_report_sha256": sha256(args.equivalence_report),
        "golden_day": gate["target_date"],
        "selection_id": args.selection_id,
        "target_date": args.date,
        "as_of_exclusive": args.date,
        "logic_version": session["logic_version"],
        "session_id": session["session_id"],
        "forecast_prep": str(forecast_prep),
        "v052_root": str(v052_root),
        "race_count": len(session["race_roster"]),
        "expected_venues": session["expected_venues"],
        "market_blind": handoff["market_blind"],
        "result_opened": handoff["result_opened"],
        "target_market_opened": handoff["target_market_opened"],
    }
    (args.output_root / "operation_handoff.json").write_text(
        json.dumps(operation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return operation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument("--selection-id", required=True)
    parser.add_argument("--main-sha", required=True)
    parser.add_argument("--equivalence-report", required=True, type=Path)
    parser.add_argument("--warehouse-current", required=True, type=Path)
    parser.add_argument("--warehouse-asset-root", required=True, type=Path)
    parser.add_argument("--analysis-root", required=True, type=Path)
    parser.add_argument("--racereview-root", required=True, type=Path)
    parser.add_argument("--binding", required=True, type=Path)
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    operation = prepare(args)
    print(json.dumps(operation, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
