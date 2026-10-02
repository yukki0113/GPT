#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit two independently frozen RaceNote forecasts against one blind DAY PREP.

This tool compares authored marks and records evidence. It never selects horses
or creates forecast prose. A failed audit writes only a diagnostic report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from racenote_freeze_prepared_forecast import (
    DEFAULT_LOGIC, LOGIC_SCHEMAS, REQUIRED_RRDB, contains_key, load_records,
    mark_entries, semantic_hash, validate_prepared_record,
)
from validate_racenote_forecast_human_context import audit_turn

BASELINE = DEFAULT_LOGIC
CANDIDATE = "RaceNote-Human-Context-Reader-0.4.3-candidate"


def digest(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def key(record: dict[str, Any]) -> tuple[str, int]:
    identity = record["identity"]
    return str(identity["venue"]), int(identity["race_no"])


def marks(record: dict[str, Any]) -> list[int]:
    return [int(entry["horse_no"]) for entry in mark_entries(record)]


def inspect_frozen(root: Path, logic: str, prep: dict, readers: dict, main_sha: str) -> tuple[dict, dict]:
    date = prep["target_date"]
    compact = date.replace("-", "")
    merged = root / "day_merge" / f"forecast_{compact}_all.json"
    handoff = json.loads((root / "day_merge" / f"forecast_{compact}_all_handoff.json").read_text(encoding="utf-8"))
    rows = load_records(merged)
    assert len(rows) == len(readers) == int(prep["race_count"]), "race count mismatch"
    assert handoff["selection_id"] == prep["selection_id"]
    assert handoff["target_date"] == date
    assert handoff["logic_version"] == logic
    assert handoff["rrdb_recommendation_contract"] == REQUIRED_RRDB
    assert handoff["main_sha_at_forecast"] == main_sha
    assert handoff["result_opened"] is False and handoff["status"] == "FROZEN_CLEAN_BLIND"
    assert handoff["prediction_hash_contract"] == "SEMANTIC_V1_EXECUTION_METADATA_EXCLUDED"
    indexed = {}
    for row in rows:
        k = key(row)
        assert k not in indexed and k in readers, f"duplicate or unexpected race: {k}"
        assert row["schema_version"] == LOGIC_SCHEMAS[logic]
        assert row["source"]["main_sha_at_forecast"] == main_sha
        assert not contains_key(row, "market")
        validate_prepared_record(row, readers[k], prep["selection_id"], date, logic)
        audit = row["audit"]
        assert audit["pre_result_guard"] == "PASS" and audit["result_visible_at_freeze"] is False
        assert audit["market_blind_guard"] == "PASS_TARGET_DAY_MARKET_FIELDS_STRIPPED_BEFORE_FORECAST"
        expected = semantic_hash(row)
        assert audit["prediction_hash"] == expected == audit["prediction_semantic_hash"]
        indexed[k] = row
    assert set(indexed) == set(readers), "incomplete card"
    assert handoff["prediction_hashes"] == [semantic_hash(indexed[k]) for k in sorted(indexed)]
    assert audit_turn(rows)["status"] == "PASS", f"{logic}: forecast validator failed"
    archived_readers = {}
    for path in (root / "reader_stripped").glob("*.json"):
        archived = json.loads(path.read_text(encoding="utf-8"))
        k = key({"identity": archived["race"]})
        assert k not in archived_readers, f"{logic}: duplicate archived Reader"
        archived_readers[k] = archived
    assert archived_readers == readers, f"{logic}: archived Reader differs from common DAY PREP"
    return indexed, handoff


def audit(prep_root: Path, baseline_root: Path, candidate_root: Path, main_sha: str) -> tuple[dict, dict | None]:
    try:
        prep = json.loads((prep_root / "day_prep_handoff.json").read_text(encoding="utf-8"))
        assert prep["result_opened"] is False
        readers = {}
        for path in (prep_root / "reader").glob("*.json"):
            reader = json.loads(path.read_text(encoding="utf-8"))
            assert not contains_key(reader, "market"), "DAY PREP Reader contains market"
            k = key({"identity": reader["race"]})
            assert k not in readers
            readers[k] = reader
        assert len(readers) == int(prep["race_count"])
        a, ah = inspect_frozen(baseline_root, BASELINE, prep, readers, main_sha)
        b, bh = inspect_frozen(candidate_root, CANDIDATE, prep, readers, main_sha)
        assert set(a) == set(b)
        assert ah["prediction_hashes"] != bh["prediction_hashes"], "A/B semantic hashes identical despite distinct logic"
        differences = []
        counts = {"five_set": 0, "main": 0, "second": 0, "single_shot": 0, "only_support_boundary": 0}
        for k in sorted(a):
            am, bm = marks(a[k]), marks(b[k])
            changed = am != bm
            cp = b[k]["decision_trace"]["consistency_pass"]
            if changed:
                assert cp["change_attribution"] != "UNCHANGED_AFTER_INDEPENDENT_REVIEW", f"{k}: unaccounted mark change"
            flags = {
                "five_set": set(am) != set(bm),
                "main": am[0] != bm[0],
                "second": am[1] != bm[1],
                "single_shot": am[2] != bm[2],
                "only_support_boundary": changed and am[:3] == bm[:3] and set(am[3:]) != set(bm[3:]),
            }
            for name, value in flags.items():
                counts[name] += int(value)
            if changed:
                differences.append({"venue": k[0], "race_no": k[1], "baseline_marks": am,
                                    "candidate_marks": bm, "change_attribution": cp["change_attribution"],
                                    "reasons": {name: cp.get(name) for name in
                                                ("hierarchy_reason", "single_shot_promotion_reason", "coverage_reason") if cp.get(name)},
                                    "difference_flags": flags})
        manifest = {
            "schema_version": "racenote-btday-ab-manifest-v0.1",
            "selection_id": prep["selection_id"], "target_date": prep["target_date"],
            "baseline_logic_id": BASELINE, "candidate_logic_id": CANDIDATE,
            "rrdb_contract": REQUIRED_RRDB, "same_reader_input_required": True,
            "market_blind": True, "result_opened_before_both_freezes": False, "main_sha_at_freeze": main_sha,
            "race_count": len(readers),
            "baseline_prediction_hash": digest(ah["prediction_hashes"]),
            "candidate_prediction_hash": digest(bh["prediction_hashes"]),
            "reader_day_hash": digest([readers[k] for k in sorted(readers)]),
        }
        report = {"status": "PASS", "schema_version": "racenote-btday-ab-audit-v0.1",
                  "selection_id": prep["selection_id"], "target_date": prep["target_date"],
                  "race_count": len(readers), "changed_race_count": len(differences),
                  "difference_counts": counts, "differences": differences, "errors": []}
        return report, manifest
    except (AssertionError, KeyError, ValueError, TypeError, OSError) as exc:
        return {"status": "FAIL", "schema_version": "racenote-btday-ab-audit-v0.1",
                "errors": [str(exc) or type(exc).__name__]}, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prep-root", required=True, type=Path)
    ap.add_argument("--baseline-root", required=True, type=Path)
    ap.add_argument("--candidate-root", required=True, type=Path)
    ap.add_argument("--main-sha", required=True)
    ap.add_argument("--output-dir", required=True, type=Path)
    args = ap.parse_args()
    if any((args.output_dir / name).exists() for name in ("ab_audit.json", "ab_manifest.json")):
        ap.error("output directory already contains an A/B audit artifact; use a new staging directory")
    report, manifest = audit(args.prep_root, args.baseline_root, args.candidate_root, args.main_sha)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "ab_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if manifest is not None:
        (args.output_dir / "ab_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
