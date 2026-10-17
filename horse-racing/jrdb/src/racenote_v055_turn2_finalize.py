#!/usr/bin/env python3
"""Mechanical v0.5.5 T2 finalizer for LLM-authored race judgments.

This module never predicts. It accepts complete Decision Core and Confidence
drafts already authored by an LLM race-by-race, validates coverage, then runs
the canonical save / Prediction Freeze / Confidence Freeze / verify sequence.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from racenote_v055_single_day import (
    build_freeze,
    expected_by_venue,
    freeze_confidence,
    load_session,
    save_confidence_review,
    save_venue,
    verify_confidence_freeze,
    verify_freeze,
    write_json,
)

VERSION = "racenote-v055-turn2-finalizer-0.1"


def _load_array(path: Path, label: str) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list) or not all(isinstance(x, dict) for x in value):
        raise ValueError(f"{label} must be a JSON array of objects")
    return value


def finalize(root: Path, decisions_path: Path, confidence_path: Path) -> dict[str, Any]:
    session, _, _ = load_session(root)
    if (root / "frozen").exists() or (root / "confidence_frozen").exists():
        raise FileExistsError("T2 immutable Freeze already exists")

    decisions = _load_array(decisions_path, "decisions")
    confidence = _load_array(confidence_path, "confidence")
    expected = {
        (str(x["venue"]), int(x["race_no"]))
        for x in session["race_roster"]
    }

    decision_keys = [(str(x.get("venue")), int(x.get("race_no"))) for x in decisions]
    if len(decision_keys) != len(set(decision_keys)) or set(decision_keys) != expected:
        raise ValueError("LLM Decision Core draft must cover every race exactly once")

    confidence_keys = [(str(x.get("venue")), int(x.get("race_no"))) for x in confidence]
    if len(confidence_keys) != len(set(confidence_keys)) or set(confidence_keys) != expected:
        raise ValueError("LLM Confidence draft must cover every race exactly once")

    incoming = root / "incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    expected_venues = expected_by_venue(session)
    for venue in sorted(expected_venues):
        rows = sorted(
            [x for x in decisions if str(x.get("venue")) == venue],
            key=lambda x: int(x["race_no"]),
        )
        path = incoming / f"{venue}.json"
        write_json(path, rows)
        save_venue(root, path)

    build_freeze(root)
    verify_freeze(root)

    confidence_copy = incoming / "confidence.json"
    write_json(confidence_copy, confidence)
    save_confidence_review(root, confidence_copy)
    freeze_confidence(root)
    verify_confidence_freeze(root)

    frozen_confidence = json.loads((root / "confidence_frozen" / "records.json").read_text(encoding="utf-8"))
    pred = json.loads((root / "frozen" / "day_handoff.json").read_text(encoding="utf-8"))
    conf = json.loads((root / "confidence_frozen" / "day_handoff.json").read_text(encoding="utf-8"))
    quality = json.loads((root / "frozen" / "authoring_quality_report.json").read_text(encoding="utf-8"))

    summary = {
        "schema_version": VERSION,
        "status": "TURN2_COMPLETE",
        "session_id": session["session_id"],
        "selection_id": session["selection_id"],
        "target_date": session["target_date"],
        "record_count": len(expected),
        "prediction_status": pred["status"],
        "confidence_status": conf["status"],
        "confidence_counts": dict(sorted(Counter(x["confidence"] for x in frozen_confidence).items())),
        "prediction_records_sha256": pred["records_sha256"],
        "confidence_records_sha256": conf["confidence_records_sha256"],
        "authoring_quality": quality["status"],
        "prediction_origin": "LLM_RACE_BY_RACE",
        "automated_prediction": False,
        "automated_scoring": False,
        "result_opened": False,
        "target_market_opened": False,
    }
    write_json(root / "turn2_summary.json", summary)
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--decisions", type=Path, required=True)
    ap.add_argument("--confidence", type=Path, required=True)
    args = ap.parse_args()
    result = finalize(args.root, args.decisions, args.confidence)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
