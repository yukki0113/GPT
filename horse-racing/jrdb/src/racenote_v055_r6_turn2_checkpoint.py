#!/usr/bin/env python3
"""Read-only, fail-closed RaceNote r6 T2 orchestration checkpoint.

Reports the next permitted LLM/commit action; never runs predictions, freezes,
Git pushes, or opens results/market data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from racenote_v055_turn2_two_phase import CONTRACT, resolve_root


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def inspect(root: Path):
    session = read(root / "session.json")
    manifest = read(root / "authoring_bundle/manifest.json")
    if session.get("contract_revision") != CONTRACT:
        raise ValueError("unsupported r6 contract")
    if (manifest.get("session_id") != session.get("session_id")
            or manifest.get("race_count") != len(session.get("race_roster", []))
            or manifest.get("status") != "READY_FOR_LLM_RACE_BY_RACE_REVIEW"):
        raise ValueError("sealed authoring bundle mismatch")
    if (session.get("market_blind") is not True
            or session.get("result_opened") is not False
            or session.get("target_market_opened") is not False):
        raise ValueError("CLEAN BLIND violation")
    pred = root / "frozen/day_handoff.json"
    conf = root / "confidence_frozen/day_handoff.json"
    summary = root / "turn2_summary.json"
    pred_draft = root / "incoming/llm_decisions.json"
    conf_draft = root / "incoming/llm_confidence.json"
    if (root / "confidence_frozen").exists() and not pred.exists():
        raise ValueError("confidence without committed prediction")
    if (root / "frozen").exists() and not pred.exists():
        raise ValueError("partial frozen directory; inspect workflow before retry")
    from racenote_v055_single_day import verify_freeze, verify_confidence_freeze
    stage = None
    if pred.exists():
        verify_freeze(root)
        p = read(pred)
        if p.get("status") != "PREDICTION_FROZEN_CLEAN_BLIND":
            raise ValueError("prediction handoff invalid")
        stage = "PREDICTION_FROZEN"
    if conf.exists():
        verify_confidence_freeze(root)
        c = read(conf)
        if c.get("status") != "CONFIDENCE_FROZEN_CLEAN_BLIND":
            raise ValueError("confidence handoff invalid")
        stage = "CONFIDENCE_FROZEN"
    if summary.exists():
        s = read(summary)
        if not conf.exists() or s.get("status") != "TURN2_COMPLETE":
            raise ValueError("turn2 summary invalid")
        if (s.get("session_id") != session.get("session_id")
                or s.get("prediction_records_sha256") != hashlib.sha256((root/"frozen/records.json").read_bytes()).hexdigest()
                or s.get("confidence_records_sha256") != hashlib.sha256((root/"confidence_frozen/records.json").read_bytes()).hexdigest()):
            raise ValueError("turn2 SHA/identity mismatch")
        stage = "TURN2_COMPLETE"
        action = "BATCH_SYNC_STATUS"
    elif conf.exists():
        action = "VERIFY_TURN2_SUMMARY"
    elif pred.exists():
        action = "WAIT_CONFIDENCE_FREEZE" if conf_draft.exists() else "LLM_CONFIDENCE_REVIEW"
    else:
        if conf_draft.exists():
            raise ValueError("confidence draft before prediction freeze")
        action = "WAIT_PREDICTION_FREEZE" if pred_draft.exists() else "LLM_PREDICTION_AUTHORING"
    return {
        "selection_id": session.get("selection_id"),
        "session_id": session["session_id"],
        "target_date": session["target_date"],
        "race_count": len(session["race_roster"]),
        "state": stage or "T1_READY",
        "next_action": action,
        "result_opened": False,
        "target_market_opened": False,
        "canonical_root": str(root),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True)
    args = p.parse_args()
    print(json.dumps(inspect(resolve_root(args.root)), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
