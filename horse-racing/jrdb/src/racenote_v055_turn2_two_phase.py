#!/usr/bin/env python3
"""RaceNote r5 two-phase mechanical finalizer. Never selects horses or grades."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from racenote_v055_single_day import (
    build_freeze, expected_by_venue, freeze_confidence, load_session,
    save_confidence_review, save_venue, verify_confidence_freeze,
    verify_freeze, write_json,
)

CONTRACT = "v055-prediction-freeze-confidence-review-r5"
DAILY = re.compile(r"^horse-racing/jrdb/daily/\d{8}/v055_day/v055$")
BACKTEST = re.compile(r"^horse-racing/jrdb/backtests/BTDAY-\d{4}/\d{8}/v055$")


def resolve_root(raw: str) -> Path:
    path = raw.strip().strip("/")
    if not (DAILY.fullmatch(path) or BACKTEST.fullmatch(path)):
        raise ValueError(f"Unapproved RaceNote root: {path}")
    root = Path(path)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Root must be an existing non-symlink directory")
    return root


def preflight(root: Path, draft: Path, phase: str):
    session, _, _ = load_session(root)
    if session.get("contract_revision") != CONTRACT:
        raise ValueError("Two-phase finalizer requires a new r5 session")
    manifest = json.loads((root / "authoring_bundle/manifest.json").read_text(encoding="utf-8"))
    mandatory = {
        "status": "READY_FOR_LLM_RACE_BY_RACE_REVIEW",
        "session_id": session["session_id"],
        "race_count": len(session["race_roster"]),
        "prediction_policy": "LLM_RACE_BY_RACE_ONLY",
        "automated_scoring": False,
        "automated_ranking": False,
        "automated_marks": False,
        "confidence_generation": False,
    }
    if any(manifest.get(k) != v for k, v in mandatory.items()):
        raise ValueError("LLM authoring bundle boundary invalid")
    if phase == "prediction":
        if (root / "frozen").exists() or (root / "confidence_frozen").exists():
            raise FileExistsError("Prediction already frozen")
    elif phase == "confidence":
        if not (root / "frozen/day_handoff.json").is_file() or (root / "confidence_frozen").exists():
            raise ValueError("Verified Prediction Freeze required; confidence must not already be frozen")
        verify_freeze(root)
    else:
        raise ValueError("Unknown phase")
    try:
        data = json.loads(draft.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"INVALID_JSON {draft}: {exc}") from exc
    if not isinstance(data, list) or any(not isinstance(x, dict) for x in data):
        raise ValueError("Draft must be an array of objects")
    expected = {(str(x["venue"]), int(x["race_no"])) for x in session["race_roster"]}
    try:
        keys = [(str(x["venue"]), int(x["race_no"])) for x in data]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Missing or invalid race identity") from exc
    if len(keys) != len(expected) or len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError("COVERAGE_MISMATCH: each sealed race must occur exactly once")
    if phase == "confidence":
        frozen = json.loads((root / "frozen/records.json").read_text(encoding="utf-8"))
        by_key = {(str(x["venue"]), int(x["race_no"])): x for x in frozen}
        for x in data:
            key = (str(x["venue"]), int(x["race_no"]))
            if int(x.get("honmei", -1)) != int(by_key[key]["decision_core"]["marks"][0]):
                raise ValueError(f"FROZEN_HONMEI_MISMATCH: {key}")
    return session, data


def run(root: Path, draft: Path, phase: str):
    session, records = preflight(root, draft, phase)
    incoming = root / "incoming"
    if phase == "prediction":
        for venue in expected_by_venue(session):
            path = incoming / f"{venue}.json"
            write_json(path, sorted((r for r in records if r["venue"] == venue), key=lambda r: int(r["race_no"])))
            save_venue(root, path)
        build_freeze(root)
        verify_freeze(root)
        result = {
            "status": "PREDICTION_FROZEN_CLEAN_BLIND", "session_id": session["session_id"],
            "record_count": len(records), "prediction_origin": "LLM_RACE_BY_RACE",
            "automated_prediction": False, "automated_scoring": False,
            "confidence_pending": True, "result_opened": False, "target_market_opened": False,
        }
        write_json(root / "prediction_phase_summary.json", result)
    else:
        path = incoming / "confidence.json"
        write_json(path, records)
        save_confidence_review(root, path)
        freeze_confidence(root)
        verify_confidence_freeze(root)
        pred = json.loads((root / "frozen/day_handoff.json").read_text(encoding="utf-8"))
        conf = json.loads((root / "confidence_frozen/day_handoff.json").read_text(encoding="utf-8"))
        quality = json.loads((root / "frozen/authoring_quality_report.json").read_text(encoding="utf-8"))
        result = {
            "schema_version": "racenote-v055-turn2-two-phase-0.1",
            "status": "TURN2_COMPLETE", "session_id": session["session_id"],
            "selection_id": session["selection_id"], "target_date": session["target_date"],
            "record_count": len(records), "prediction_status": pred["status"],
            "confidence_status": conf["status"],
            "confidence_counts": dict(sorted(Counter(x["confidence"] for x in records).items())),
            "prediction_records_sha256": pred["records_sha256"],
            "confidence_records_sha256": conf["confidence_records_sha256"],
            "authoring_quality": quality["status"],
            "prediction_origin": "LLM_RACE_BY_RACE",
            "automated_prediction": False, "automated_scoring": False,
            "result_opened": False, "target_market_opened": False,
        }
        write_json(root / "turn2_summary.json", result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", required=True)
    p.add_argument("--phase", choices=("prediction", "confidence"), required=True)
    p.add_argument("--draft", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(run(resolve_root(args.root), args.draft, args.phase), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
