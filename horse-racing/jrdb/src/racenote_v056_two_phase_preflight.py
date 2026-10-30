#!/usr/bin/env python3
"""v0.5.6 independent two-phase submission preflight; no legacy Freeze shortcuts.

Read-only validator for prepared v056 sessions. Refuses any v055 session/root
and never authors decisions, writes canonical files or opens results.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from racenote_v056_contract_gates import check_prediction_audit_comment, check_confidence_review

CONTRACT = "v056-prediction-confidence-audit-newspaper-v1"
LOGIC = "RaceNote-Human-Context-Reader-0.5.6-candidate"
ROOT = re.compile(r"^horse-racing/jrdb/(?:backtests/BTDAY-\d{4}/\d{8}/v056|daily/\d{8}/v056_day/v056)$")

def _read(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Missing or unsafe file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))

def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def validate(root: Path, draft: Path, phase: str):
    if not ROOT.fullmatch(root.as_posix().rstrip("/")) or root.is_symlink():
        raise ValueError("Only canonical v056 execution roots are permitted")
    session = _read(root / "session.json")
    if session.get("contract_revision") != CONTRACT or session.get("logic_version") != LOGIC:
        raise ValueError("v056 sealed session contract mismatch")
    if session.get("market_blind") is not True or session.get("result_opened") is not False or session.get("target_market_opened") is not False:
        raise ValueError("CLEAN BLIND violation")
    expected = {(str(r["venue"]), int(r["race_no"])) for r in session["race_roster"]}
    if not expected:
        raise ValueError("Empty race roster")
    records = _read(draft)
    if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
        raise ValueError("Draft must be a JSON array")
    try:
        keys = [(str(r["venue"]), int(r["race_no"])) for r in records]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid race identity") from exc
    if len(keys) != len(expected) or len(set(keys)) != len(keys) or set(keys) != expected:
        raise ValueError("Race roster mismatch")
    frozen_dir = root / "frozen"
    confidence_dir = root / "confidence_frozen"
    if phase == "prediction":
        if frozen_dir.exists() or confidence_dir.exists():
            raise ValueError("Prediction is already frozen")
        for r in records:
            if set(r) != {"venue", "race_no", "decision_core"}:
                raise ValueError("Unexpected Prediction payload fields")
            core = r["decision_core"]
            if not isinstance(core, dict) or core.get("venue") != r["venue"] or core.get("race_no") != r["race_no"]:
                raise ValueError("Decision Core race identity mismatch")
            check_prediction_audit_comment(core)
            if core.get("honmei_win", {}).get("confidence") is not None:
                raise ValueError("Prediction cannot assign Confidence")
        dest = root / "incoming/llm_decisions.json"
    elif phase == "confidence":
        if confidence_dir.exists():
            raise ValueError("Confidence is already frozen")
        pred_handoff = _read(frozen_dir / "day_handoff.json")
        prediction_path = frozen_dir / "records.json"
        if pred_handoff.get("status") != "PREDICTION_FROZEN_CLEAN_BLIND" or pred_handoff.get("contract_revision") != CONTRACT or pred_handoff.get("session_id") != session.get("session_id") or pred_handoff.get("records_sha256") != _sha(prediction_path):
            raise ValueError("Verified v056 Prediction Freeze required")
        frozen = _read(prediction_path)
        if not isinstance(frozen, list) or len(frozen) != len(expected):
            raise ValueError("Frozen roster incomplete")
        frozen_by_key = {(str(r["venue"]), int(r["race_no"])): r for r in frozen}
        if set(frozen_by_key) != expected:
            raise ValueError("Frozen roster differs")
        for r in records:
            if set(r) != {"venue", "race_no", "honmei", "confidence", "reason", "confidence_review"}:
                raise ValueError("Unexpected Confidence payload fields")
            key = (r["venue"], r["race_no"])
            frozen_honmei = frozen_by_key[key]["decision_core"]["marks"][0]
            if not isinstance(r["reason"], str) or len(r["reason"].strip()) < 12:
                raise ValueError("Confidence reason is insufficient")
            # The official reader-based special-race classification must be supplied
            # by the sealed v056 input; never infer Z from grade.
            special = _read(root / "reader" / f"{r['venue']}_{r['race_no']:02d}.json")
            race = special.get("race") or {}
            z_required = race.get("class") == "新馬" or race.get("surface") == "障害" or race.get("race_type") == "障害"
            check_confidence_review(r, frozen_honmei, z_required=z_required)
        dest = root / "incoming/llm_confidence.json"
    else:
        raise ValueError("Unsupported phase")
    return {"status": "READY_FOR_V056_INTEGRATION", "phase": phase, "race_count": len(records), "session_id": session["session_id"], "draft_sha256": _sha(draft), "target_path": str(dest), "note": "Validation only: production v056 Freeze workflow not implemented"}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--phase", choices=("prediction", "confidence"), required=True)
    parser.add_argument("--draft", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(validate(args.root, args.draft, args.phase), ensure_ascii=False, sort_keys=True))

if __name__ == "__main__":
    main()
