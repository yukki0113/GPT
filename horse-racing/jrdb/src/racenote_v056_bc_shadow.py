#!/usr/bin/env python3
"""Validate and seal separate, LLM-authored RaceNote v0.5.6 B/C axis Shadow.

Only deterministic validation, never generates grades or modifies a source Freeze.
Requires result-blind attestation supplied at execution time by the operator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

CONTRACT = "v056-prediction-confidence-audit-newspaper-v1"
SHADOW_SCHEMA = "racenote-v056-bc-shadow-axis-v1"
TEXT_FIELDS = (
    "axis_positive_case", "relative_axis_case", "unverified_assumptions",
    "axis_failure_scenario", "final_reason",
)
RECORD_FIELDS = {"venue", "race_no", "honmei", "shadow_grade", "strongest_rival", *TEXT_FIELDS}
BANNED_KEYS = {"result", "finish", "payout", "odds", "market", "result_opened", "target_market_opened"}


class ShadowError(ValueError):
    pass


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def key(record):
    return (str(record["venue"]), int(record["race_no"]))


def validate(root: Path, draft: Path, *, asserted_unopened: bool):
    if not asserted_unopened:
        raise ShadowError("Explicit operator assertion of still-unopened results is mandatory")
    if root.name != "v056" or not root.is_dir() or root.is_symlink():
        raise ShadowError("Requires an existing non-symlink v056 root")
    session_path = root / "session.json"
    pred_path = root / "frozen/records.json"
    conf_path = root / "confidence_frozen/records.json"
    pred_handoff_path = root / "frozen/day_handoff.json"
    conf_handoff_path = root / "confidence_frozen/day_handoff.json"
    summary_path = root / "turn2_summary.json"
    for path in (session_path, pred_path, conf_path, pred_handoff_path, conf_handoff_path, summary_path):
        if path.is_symlink() or not path.is_file():
            raise ShadowError(f"Missing/nonregular source: {path}")
    session = read_json(session_path)
    pred_handoff = read_json(pred_handoff_path)
    conf_handoff = read_json(conf_handoff_path)
    turn2 = read_json(summary_path)
    prediction = read_json(pred_path)
    confidence = read_json(conf_path)
    if session.get("contract_revision") != CONTRACT:
        raise ShadowError("Only v0.5.6 confidence contract is accepted")
    for handoff, expected_status in (
        (pred_handoff, "PREDICTION_FROZEN_CLEAN_BLIND"),
        (conf_handoff, "CONFIDENCE_FROZEN_CLEAN_BLIND"),
    ):
        if (handoff.get("status") != expected_status
            or handoff.get("session_id") != session.get("session_id")
            or handoff.get("selection_id") != session.get("selection_id")
            or handoff.get("target_date") != session.get("target_date")
            or handoff.get("contract_revision") != CONTRACT
            or handoff.get("result_opened") is not False
            or handoff.get("target_market_opened") is not False):
            raise ShadowError("Invalid or unlocked source Freeze handoff")
    if (pred_handoff.get("records_sha256") != sha(pred_path)
        or conf_handoff.get("confidence_records_sha256") != sha(conf_path)
        or conf_handoff.get("prediction_records_sha256") != sha(pred_path)):
        raise ShadowError("Source Freeze SHA integrity failed")
    if (turn2.get("status") != "TURN2_COMPLETE"
        or turn2.get("session_id") != session.get("session_id")
        or turn2.get("result_opened") is not False
        or turn2.get("target_market_opened") is not False
        or turn2.get("prediction_records_sha256") != sha(pred_path)
        or turn2.get("confidence_records_sha256") != sha(conf_path)):
        raise ShadowError("Invalid TURN2_COMPLETE binding")
    if not isinstance(prediction, list) or not isinstance(confidence, list):
        raise ShadowError("Frozen records must be arrays")
    if len(prediction) != len(confidence) or len(prediction) != len(session.get("race_roster", [])):
        raise ShadowError("Prediction/confidence/session race counts disagree")
    by_pred = {}
    for p in prediction:
        k = key(p)
        marks = p["decision_core"]["marks"]
        if k in by_pred or not isinstance(marks, list) or len(marks) != 5 or len(set(marks)) != 5:
            raise ShadowError(f"Duplicate/invalid frozen marks: {k}")
        by_pred[k] = p
    by_conf = {}
    for c in confidence:
        k = key(c)
        if k in by_conf or k not in by_pred:
            raise ShadowError(f"Duplicate/unmatched frozen confidence: {k}")
        if int(c["honmei"]) != int(by_pred[k]["decision_core"]["marks"][0]):
            raise ShadowError(f"Frozen ◎ mismatch: {k}")
        if c.get("confidence") not in ("A", "B", "C", "Z"):
            raise ShadowError(f"Invalid canonical grade: {k}")
        by_conf[k] = c
    if set(by_pred) != set(by_conf):
        raise ShadowError("Canonical roster mismatch")
    records = read_json(draft)
    if not isinstance(records, list):
        raise ShadowError("Shadow draft must be an array")
    expected = {k for k, c in by_conf.items() if c["confidence"] in {"B", "C"}}
    if len(records) != len(expected):
        raise ShadowError("Shadow B/C exact coverage missing")
    seen = set()
    reviewed = []
    shifts = Counter()
    for item in records:
        if not isinstance(item, dict) or set(item) != RECORD_FIELDS or BANNED_KEYS.intersection(item):
            raise ShadowError("Incorrect Shadow record fields (result/market not permitted)")
        k = key(item)
        if k in seen or k not in expected:
            raise ShadowError(f"Duplicate/non B/C Shadow race: {k}")
        seen.add(k)
        pred = by_pred[k]
        conf = by_conf[k]
        marks = list(map(int, pred["decision_core"]["marks"]))
        if type(item["honmei"]) is not int or item["honmei"] != marks[0]:
            raise ShadowError(f"Shadow ◎ differs from Frozen Prediction: {k}")
        if type(item["strongest_rival"]) is not int or item["strongest_rival"] not in marks[1:]:
            raise ShadowError(f"Shadow rival not among other four frozen marks: {k}")
        if type(item["race_no"]) is not int or item["race_no"] < 1 or item["race_no"] > 12:
            raise ShadowError(f"Invalid race number: {k}")
        if item["shadow_grade"] not in {"B", "C"}:
            raise ShadowError(f"Shadow must be B or C: {k}")
        for field in TEXT_FIELDS:
            text = item[field]
            if not isinstance(text, str) or len(text.strip()) < 12 or len(text) > 1500:
                raise ShadowError(f"Missing/insufficient original LLM rationale {field}: {k}")
        shift = conf["confidence"] + "->" + item["shadow_grade"]
        shifts[shift] += 1
        reviewed.append({
            **item, "canonical_confidence": conf["confidence"],
            "canonical_confidence_reason": conf.get("reason"),
        })
    if seen != expected:
        raise ShadowError("Shadow exact roster mismatch")
    reviewed.sort(key=lambda x: (x["venue"], x["race_no"]))
    payload = {
        "schema_version": SHADOW_SCHEMA,
        "status": "SHADOW_BC_DRAFT_VALIDATED_NOT_CANONICAL_FREEZE",
        "research_only": True,
        "results_unopened_operator_assertion": True,
        "session_id": session["session_id"],
        "selection_id": session["selection_id"],
        "target_date": session["target_date"],
        "contract_revision": CONTRACT,
        "prediction_records_sha256": sha(pred_path),
        "confidence_records_sha256": sha(conf_path),
        "record_count": len(reviewed),
        "grade_transitions": dict(sorted(shifts.items())),
        "canonical_a_z_unchanged": True,
        "automated_shadows": False,
        "records": reviewed,
    }
    return payload


def seal(root: Path, draft: Path, output: Path, *, asserted_unopened: bool):
    resolved_root = root.resolve(strict=True)
    resolved_output = output.resolve(strict=False)
    if resolved_output.is_relative_to(resolved_root) or resolved_output == resolved_root:
        raise ShadowError("Shadow output must be outside canonical v056 root")
    if draft.resolve(strict=True) == resolved_output:
        raise ShadowError("Refusing to overwrite draft")
    payload = validate(root, draft, asserted_unopened=asserted_unopened)
    serialized = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    # Exclusive creation; no re-run may silently replace a previously sealed draft.
    output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(serialized)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return {
        "status": payload["status"],
        "output": str(output),
        "output_sha256": hashlib.sha256(serialized).hexdigest(),
        "record_count": payload["record_count"],
        "grade_transitions": payload["grade_transitions"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--draft", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--assert-results-unopened", action="store_true")
    args = parser.parse_args()
    try:
        result = seal(args.root, args.draft, args.output,
                      asserted_unopened=args.assert_results_unopened)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    except (ShadowError, ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(2, f"SHADOW_BC_FAILED: {exc}\n")


if __name__ == "__main__":
    main()
