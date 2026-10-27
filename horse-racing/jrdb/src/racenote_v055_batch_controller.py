#!/usr/bin/env python3
"""RaceNote v0.5.5 r6 pseudo-batch controller.

Deterministic state/verification only: never produces predictions or confidence.
Consumes only already committed clean-blind T2 artifacts, never results/odds.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

SCHEMA = "racenote-v055-batch-controller-0.1"
CONTRACT = "v055-prediction-freeze-confidence-review-r6"
LOGIC = "RaceNote-Human-Context-Reader-0.5.5-candidate"
PRED = "PREDICTION_FROZEN_CLEAN_BLIND"
CONF = "CONFIDENCE_FROZEN_CLEAN_BLIND"
DONE = "TURN2_COMPLETE"
SEALED = "BATCH_COHORT_FROZEN_CLEAN_BLIND"
MODES = ("btday_count", "confidence_count", "either")
ID_RE = re.compile(r"^BTDAY-(\d{4})$")
BATCH_RE = re.compile(r"^V055-BATCH-[A-Z0-9][A-Z0-9_-]{0,63}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
COUNT_KEYS = ("A", "B", "C", "Z")
ROOT = Path("horse-racing/jrdb/backtests")
MAX_SCAN = 300


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def store(path, value, *, exclusive=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive and path.exists():
        raise FileExistsError(f"Immutable batch artifact exists: {path}")
    raw = canonical(value)
    if not exclusive and path.exists() and path.read_bytes() == raw:
        return False
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(raw)
    temp.replace(path)
    return True


def fail(condition, message):
    if not condition:
        raise ValueError(message)


def number_from_id(value):
    match = ID_RE.fullmatch(value)
    fail(match is not None, f"Invalid BTDAY id: {value}")
    return int(match.group(1))


def selection_id(n):
    fail(1 <= n <= 9999, "BTDAY id exhausted")
    return f"BTDAY-{n:04d}"


def validate_config(cfg):
    fail(isinstance(cfg, dict), "Invalid batch config")
    fail(BATCH_RE.fullmatch(str(cfg.get("batch_id", ""))) is not None, "Invalid batch_id")
    number_from_id(str(cfg.get("start_selection_id", "")))
    stop = cfg.get("stop_condition")
    fail(isinstance(stop, dict) and stop.get("mode") in MODES, "Invalid stop condition")
    mode = stop["mode"]
    if mode == "btday_count":
        fail(isinstance(stop.get("target_btday_count"), int)
             and 1 <= stop["target_btday_count"] <= MAX_SCAN, "Invalid BTDAY target")
        fail(set(stop) == {"mode", "target_btday_count"}, "Unexpected stop fields")
    else:
        fail(stop.get("target_confidence") in ("A", "B", "C"), "Invalid confidence grade")
        fail(isinstance(stop.get("target_count"), int)
             and 1 <= stop["target_count"] <= 100000, "Invalid confidence target")
        if mode == "either":
            fail(isinstance(stop.get("max_btday_count"), int)
                 and 1 <= stop["max_btday_count"] <= MAX_SCAN, "Invalid safety day limit")
            fail(set(stop) == {"mode", "target_confidence", "target_count", "max_btday_count"},
                 "Unexpected stop fields")
        else:
            fail(set(stop) == {"mode", "target_confidence", "target_count"},
                 "Unexpected stop fields")
    return stop


def path_for(base, batch_id):
    fail(BATCH_RE.fullmatch(batch_id) is not None, "Invalid batch_id")
    return base / "batches" / batch_id


def _assert_blind(*values):
    for obj in values:
        fail(obj.get("result_opened") is False
             and obj.get("target_market_opened") is False,
             "Clean-blind breach or missing result/market firewall")
        if "market_blind" in obj:
            fail(obj["market_blind"] is True, "Market-blind flag invalid")


def read_finished(base, sid):
    """Return verified immutable day snapshot and A cohort or incomplete stage.

    Uses only selection / T1 handoff / prediction + confidence frozen / T2.
    Never opens results, odds, settlement or a target-market file.
    """
    folder = base / sid
    sel = folder / "selection.json"
    if not sel.is_file():
        return None, [], "PICK"
    selection = load(sel)
    fail(selection.get("selection_id") == sid
         and selection.get("n") == 1
         and len(selection.get("dates", [])) == 1,
         f"{sid}: canonical selection invalid")
    target_date = selection["dates"][0]
    fail(bool(re.fullmatch(r"\d{4}-\d\d-\d\d", target_date)),
         f"{sid}: invalid target date")
    day = folder / target_date.replace("-", "")
    handoff_path = day / "operation_handoff.json"
    if not handoff_path.is_file():
        return None, [], "T1"
    handoff = load(handoff_path)
    fail(handoff.get("selection_id") == sid and handoff.get("target_date") == target_date
         and handoff.get("status") == "READY_FOR_V055_AUTHORING"
         and handoff.get("logic_version") == LOGIC
         and handoff.get("contract_revision") == CONTRACT
         and handoff.get("authoring_bundle_status") == "READY_FOR_LLM_RACE_BY_RACE_REVIEW",
         f"{sid}: unsupported T1 handoff")
    _assert_blind(handoff)
    root = day / "v055"
    fp = root / "frozen/day_handoff.json"
    if not fp.is_file():
        return None, [], "T2_PREDICTION"
    pred = load(fp)
    fail(pred.get("status") == PRED and pred.get("validator_status") == "PASS"
         and pred.get("confidence_pending") is True
         and pred.get("selection_id") == sid
         and pred.get("session_id") == handoff["session_id"]
         and pred.get("target_date") == target_date
         and pred.get("contract_revision") == CONTRACT,
         f"{sid}: Prediction Freeze invalid")
    _assert_blind(pred)
    if not (root / "confidence_frozen/day_handoff.json").is_file():
        return None, [], "T2_CONFIDENCE"
    conf = load(root / "confidence_frozen/day_handoff.json")
    summary_path = root / "turn2_summary.json"
    if not summary_path.is_file():
        return None, [], "T2_VERIFY"
    summary = load(summary_path)
    _assert_blind(conf, summary)
    fail(conf.get("status") == CONF and conf.get("confidence_frozen") is True
         and conf.get("prediction_freeze_status") == PRED
         and conf.get("contract_revision") == CONTRACT
         and conf.get("confidence_meaning") == "HONMEI_WIN_CONFIDENCE",
         f"{sid}: Confidence Freeze invalid")
    fail(summary.get("status") == DONE and summary.get("authoring_quality") == "PASS"
         and summary.get("prediction_status") == PRED and summary.get("confidence_status") == CONF
         and summary.get("prediction_origin") == "LLM_RACE_BY_RACE"
         and summary.get("automated_prediction") is False
         and summary.get("automated_scoring") is False,
         f"{sid}: TURN2 completion invalid")
    for obj in (pred, conf, summary):
        fail(obj.get("selection_id") == sid and obj.get("target_date") == target_date
             and obj.get("session_id") == handoff["session_id"]
             and obj.get("record_count") == handoff["race_count"],
             f"{sid}: T2 identity or race count mismatch")
    pred_file = root / "frozen/records.json"
    conf_file = root / "confidence_frozen/records.json"
    quality_file = root / "frozen/authoring_quality_report.json"
    fail(pred_file.is_file() and conf_file.is_file() and quality_file.is_file(),
         f"{sid}: missing frozen records or quality report")
    pbytes, cbytes, qbytes = (p.read_bytes() for p in (pred_file, conf_file, quality_file))
    psha, csha = digest(pbytes), digest(cbytes)
    fail(SHA_RE.fullmatch(psha) is not None
         and pred.get("records_sha256") == psha
         and conf.get("prediction_records_sha256") == psha
         and conf.get("confidence_records_sha256") == csha
         and summary.get("prediction_records_sha256") == psha
         and summary.get("confidence_records_sha256") == csha,
         f"{sid}: frozen SHA linkage invalid")
    fail(pred.get("authoring_quality_report_sha256") == digest(qbytes)
         and load(quality_file).get("status") == "PASS",
         f"{sid}: authoring quality seal invalid")
    p_records, c_records = json.loads(pbytes), json.loads(cbytes)
    expected = {}
    for r in p_records:
        key = (r["venue"], int(r["race_no"]))
        fail(key not in expected and r["selection_id"] == sid
             and r["session_id"] == handoff["session_id"]
             and r["target_date"] == target_date,
             f"{sid}: prediction race identity invalid")
        expected[key] = int(r["decision_core"]["marks"][0])
    counts = Counter()
    cohort = []
    seen = set()
    for r in c_records:
        key = (r["venue"], int(r["race_no"]))
        fail(key in expected and key not in seen and r["honmei"] == expected[key],
             f"{sid}: frozen honmei mismatch or duplicate race")
        grade = r["confidence"]
        fail(grade in COUNT_KEYS, f"{sid}: unsupported Confidence")
        seen.add(key)
        counts[grade] += 1
        if grade == "A":
            cohort.append({
                "selection_id": sid, "target_date": target_date,
                "venue": key[0], "race_no": key[1], "honmei": expected[key],
                "confidence": "A", "session_id": handoff["session_id"],
                "prediction_records_sha256": psha,
                "confidence_records_sha256": csha,
            })
    fail(len(expected) == len(seen) == handoff["race_count"],
         f"{sid}: frozen coverage mismatch")
    fail(dict(counts) == summary.get("confidence_counts"),
         f"{sid}: Confidence summary disagrees with frozen records")
    cohort.sort(key=lambda x: (x["venue"], x["race_no"]))
    snapshot = {
        "selection_id": sid, "target_date": target_date,
        "session_id": handoff["session_id"], "record_count": len(seen),
        "confidence_counts": {k: counts[k] for k in COUNT_KEYS if counts[k]},
        "prediction_records_sha256": psha, "confidence_records_sha256": csha,
    }
    return snapshot, cohort, "COMPLETE"


def reached(stop, sessions):
    count = len(sessions)
    totals = Counter()
    for s in sessions:
        totals.update(s["confidence_counts"])
    if stop["mode"] == "btday_count":
        return count >= stop["target_btday_count"]
    met = totals[stop["target_confidence"]] >= stop["target_count"]
    return met or (stop["mode"] == "either" and count >= stop["max_btday_count"])


def reconstruct(base, cfg):
    """Re-read committed days from start; stop only on whole-day boundary."""
    stop = validate_config(cfg)
    sessions, cohort = [], []
    number = number_from_id(cfg["start_selection_id"])
    stage = "PICK"
    for offset in range(MAX_SCAN):
        if reached(stop, sessions):
            return sessions, cohort, "READY_TO_SEAL", None
        sid = selection_id(number + offset)
        snapshot, rows, stage = read_finished(base, sid)
        if snapshot is None:
            return sessions, cohort, stage, sid
        sessions.append(snapshot)
        cohort.extend(rows)
    raise ValueError("Batch scan safety limit reached without stop condition")


def _progress(sessions, next_id):
    totals = Counter()
    for s in sessions:
        totals.update(s["confidence_counts"])
    return {
        "completed_btday_count": len(sessions),
        "confidence_counts": {k: totals[k] for k in COUNT_KEYS},
        "last_completed_selection_id": sessions[-1]["selection_id"] if sessions else None,
        "next_selection_id": next_id,
    }


def init(base, batch_id, start, mode, target_count=None, target_confidence="A",
         target_btday_count=None, max_btday_count=None):
    stop = {"mode": mode}
    if mode == "btday_count":
        stop["target_btday_count"] = target_btday_count
    else:
        stop.update(target_confidence=target_confidence, target_count=target_count)
        if mode == "either":
            stop["max_btday_count"] = max_btday_count
    cfg = {
        "schema_version": SCHEMA, "batch_id": batch_id, "start_selection_id": start,
        "stop_condition": stop, "status": "RUNNING", "completed_sessions": [],
        "progress": _progress([], start),
    }
    validate_config(cfg)
    directory = path_for(base, batch_id)
    fail(not directory.exists(), f"Batch already exists: {batch_id}")
    # No two active batches can own overlapping BTDAYs.
    for path in (base / "batches").glob("*/batch_manifest.json"):
        prior = load(path)
        if prior.get("status") in ("RUNNING", "READY_TO_SEAL"):
            raise ValueError(f"Another active batch exists: {prior.get('batch_id')}")
    store(directory / "batch_manifest.json", cfg, exclusive=True)
    return cfg


def inspect(base, batch_id, *, persist=False):
    directory = path_for(base, batch_id)
    cfg = load(directory / "batch_manifest.json")
    fail(cfg.get("schema_version") == SCHEMA and cfg.get("batch_id") == batch_id,
         "Invalid batch manifest")
    validate_config(cfg)
    old = cfg.get("completed_sessions")
    fail(isinstance(old, list), "Invalid completed_sessions")
    sessions, cohort, stage, sid = reconstruct(base, cfg)
    fail(sessions[:len(old)] == old, "Previously recorded BTDAY was altered")
    if cfg["status"] == SEALED:
        seal = load(directory / "cohort_seal.json")
        raw = (directory / "confidence_A_cohort.json").read_bytes()
        fail(seal.get("status") == SEALED and seal.get("cohort_sha256") == digest(raw)
             and seal.get("cohort_count") == len(cohort)
             and json.loads(raw) == cohort
             and seal.get("completed_sessions") == sessions
             and (directory / "completed_btday.json").is_file()
             and load(directory / "completed_btday.json") == sessions,
             "Immutable batch cohort seal invalid")
        fail(stage == "READY_TO_SEAL", "Sealed batch no longer meets stop condition")
        return {**cfg, "next_action": "COMPLETE", "cohort_A_count": len(cohort)}
    fail(cfg["status"] in ("RUNNING", "READY_TO_SEAL"),
         "Unsupported batch state")
    cfg["completed_sessions"] = sessions
    cfg["progress"] = _progress(sessions, sid)
    cfg["status"] = "READY_TO_SEAL" if stage == "READY_TO_SEAL" else "RUNNING"
    cfg["next_action"] = "SEAL" if stage == "READY_TO_SEAL" else stage
    if persist:
        safe = {k: v for k, v in cfg.items() if k != "next_action"}
        store(directory / "batch_manifest.json", safe)
    return cfg


def seal(base, batch_id):
    existing = load(path_for(base, batch_id) / "batch_manifest.json")
    if existing.get("status") == SEALED:
        raise FileExistsError("Immutable batch cohort already sealed")
    cfg = inspect(base, batch_id, persist=True)
    fail(cfg["status"] == "READY_TO_SEAL", "Batch stop condition not yet reached")
    directory = path_for(base, batch_id)
    sessions, cohort, stage, _ = reconstruct(base, cfg)
    fail(stage == "READY_TO_SEAL", "Batch changed during seal")
    for name in ("confidence_A_cohort.json", "completed_btday.json", "cohort_seal.json"):
        fail(not (directory / name).exists(), "Batch seal must be immutable")
    store(directory / "confidence_A_cohort.json", cohort, exclusive=True)
    store(directory / "completed_btday.json", sessions, exclusive=True)
    proof = {
        "schema_version": "racenote-v055-batch-cohort-seal-0.1",
        "batch_id": batch_id, "status": SEALED,
        "stop_condition": cfg["stop_condition"],
        "completed_sessions": sessions, "cohort_count": len(cohort),
        "cohort_sha256": digest(canonical(cohort)),
        "selection_count": len(sessions),
        "result_opened": False, "target_market_opened": False,
        "prediction_origin": "LLM_RACE_BY_RACE",
        "automated_prediction": False, "automated_scoring": False,
    }
    store(directory / "cohort_seal.json", proof, exclusive=True)
    cfg.pop("next_action", None)
    cfg["status"] = SEALED
    cfg["progress"]["next_selection_id"] = None
    store(directory / "batch_manifest.json", cfg)
    return {**proof, "next_action": "COMPLETE"}


def sync_active(base):
    """Reconcile all active batches after a committed clean-blind T2."""
    updated = []
    for path in sorted((base / "batches").glob("*/batch_manifest.json")):
        cfg = load(path)
        if cfg.get("status") in ("RUNNING", "READY_TO_SEAL"):
            updated.append(inspect(base, cfg["batch_id"], persist=True))
    return {"active_batches": len(updated), "batches": updated}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backtests-dir", type=Path, default=ROOT)
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("init")
    a.add_argument("--batch-id", required=True)
    a.add_argument("--start-selection-id", required=True)
    a.add_argument("--mode", choices=MODES, required=True)
    a.add_argument("--target-btday-count", type=int)
    a.add_argument("--target-confidence", choices=("A", "B", "C"), default="A")
    a.add_argument("--target-count", type=int)
    a.add_argument("--max-btday-count", type=int)
    for name in ("status", "sync", "seal"):
        a = sub.add_parser(name)
        a.add_argument("--batch-id", required=True)
    sub.add_parser("sync-active")
    args = parser.parse_args()
    if args.command == "init":
        result = init(args.backtests_dir, args.batch_id, args.start_selection_id,
                      args.mode, args.target_count, args.target_confidence,
                      args.target_btday_count, args.max_btday_count)
    elif args.command == "sync-active":
        result = sync_active(args.backtests_dir)
    elif args.command == "seal":
        result = seal(args.backtests_dir, args.batch_id)
    else:
        result = inspect(args.backtests_dir, args.batch_id, persist=args.command == "sync")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
