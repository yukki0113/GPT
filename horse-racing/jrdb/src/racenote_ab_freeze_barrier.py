#!/usr/bin/env python3
"""Require two validated independent A/B lane Freezes before result opening."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from racenote_ab_lane import LANES, load_lane_freeze
from racenote_ab_session import load_session, read_json, write_json

BARRIER_VERSION = "racenote-ab-freeze-barrier-0.1"


def validated_barrier(ab_root: Path) -> dict[str, Any]:
    session, readers, derived = load_session(ab_root)
    lanes = {}
    race_keys = [(x["venue"], x["race_no"]) for x in session["race_roster"]]
    for lane in ("v046", "v050"):
        handoff, records = load_lane_freeze(ab_root, lane, session, readers, derived)
        if [(x["venue"], x["race_no"]) for x in records] != race_keys:
            raise ValueError(f"{lane}: shared A/B race identities differ")
        if any(len(x["decision_core"]["marks"]) != 5 for x in records):
            raise ValueError(f"{lane}: five-mark requirement failed")
        lanes[lane] = {
            "logic_version": LANES[lane],
            "reader_manifest_sha256": handoff["reader_manifest_sha256"],
            "original_clean_reader_manifest_sha256": handoff["original_clean_reader_manifest_sha256"],
            "records_sha256": handoff["records_sha256"],
            "record_count": handoff["record_count"],
            "status": handoff["status"],
            "validator_status": handoff["validator_status"],
        }
    if lanes["v046"]["original_clean_reader_manifest_sha256"] != lanes["v050"]["original_clean_reader_manifest_sha256"]:
        raise ValueError("lane original clean Reader manifests differ")
    return {
        "schema_version": BARRIER_VERSION,
        "status": "BOTH_LANES_FROZEN_CLEAN_BLIND",
        "session_id": session["session_id"],
        "selection_id": session["selection_id"],
        "target_date": session["target_date"],
        "base_main_sha": session["base_main_sha"],
        "clean_reader_manifest_sha256": session["clean_reader_manifest_sha256"],
        "race_roster": session["race_roster"],
        "expected_venues": session["expected_venues"],
        "market_blind": True,
        "target_market_opened": False,
        "result_opened": False,
        "sibling_forecast_input_used": False,
        "lanes": lanes,
    }


def create_barrier(ab_root: Path) -> dict[str, Any]:
    barrier = validated_barrier(ab_root)
    path = ab_root / "ab_freeze_barrier.json"
    if path.exists():
        raise FileExistsError(f"A/B Freeze barrier already exists: {path}")
    write_json(path, barrier)
    return barrier


def require_barrier(ab_root: Path) -> dict[str, Any]:
    """Call this from any future A/B result or market evaluation entry point."""
    path = ab_root / "ab_freeze_barrier.json"
    if not path.is_file():
        raise ValueError("A/B result/market opening blocked: both-lane Freeze barrier missing")
    actual = read_json(path)
    expected = validated_barrier(ab_root)
    if actual != expected:
        raise ValueError("A/B result/market opening blocked: Freeze barrier no longer matches lane evidence")
    return actual


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ab-root", type=Path, required=True)
    ap.add_argument("--verify-only", action="store_true")
    args = ap.parse_args()
    result = require_barrier(args.ab_root) if args.verify_only else create_barrier(args.ab_root)
    print(json.dumps({"status": result["status"], "session_id": result["session_id"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
