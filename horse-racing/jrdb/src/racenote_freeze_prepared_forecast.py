#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic RaceNote Freeze packager.

This module MUST NOT choose horses or write forecast prose.
It accepts complete model-authored race records, validates them against the
DAY PREP Reader identities, strips target-day market from archived Reader
copies, computes semantic prediction hashes, and writes canonical day files.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "racenote-freeze-prepared-forecast-0.1.0"

DEFAULT_LOGIC = "RaceNote-Human-Context-Reader-0.4.2-candidate"
LOGIC_SCHEMAS = {
    DEFAULT_LOGIC: "RaceNote-Forecast-Research-Record-0.4.2",
    "RaceNote-Human-Context-Reader-0.4.3-candidate": "RaceNote-Forecast-Research-Record-0.4.3",
}
REQUIRED_PROSE = "FORECAST_READER_FACING_PROSE_v0_1"
REQUIRED_RRDB = "rrdb-recommendation-signals-v0.3"
REQUIRED_AUTHORING_MODE = "MODEL_RACE_BY_RACE_REASONING"
REQUIRED_PROSE_ORIGIN = "MODEL_AUTHORED_NOT_SCRIPT_GENERATED"


def load_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, list) else [value]


def horse_no(h: dict[str, Any]) -> int:
    basic = h.get("basic") or {}
    return int(basic.get("horse_no"))


def horse_name(h: dict[str, Any]) -> str:
    return str((h.get("basic") or {}).get("horse_name") or "").strip()


def mark_entries(record: dict[str, Any]) -> list[dict[str, Any]]:
    marks = ((record.get("prediction") or {}).get("marks") or {})
    others = marks.get("others") if isinstance(marks.get("others"), list) else []
    return [marks.get("main") or {}, marks.get("second") or {}, marks.get("third") or {}, *others[:2]]


def contains_key(value: Any, forbidden: str) -> bool:
    if isinstance(value, dict):
        if forbidden in value:
            return True
        return any(contains_key(v, forbidden) for v in value.values())
    if isinstance(value, list):
        return any(contains_key(v, forbidden) for v in value)
    return False


def semantic_payload(record: dict[str, Any]) -> dict[str, Any]:
    source = record.get("source") or {}
    research = record.get("research") or {}
    trace = record.get("decision_trace") or {}
    rrdb = trace.get("rrdb_evidence") or {}
    return {
        "identity": record.get("identity") or {},
        "logic_version": research.get("logic_version"),
        "reader_facing_prose_contract": research.get("reader_facing_prose_contract"),
        "source_semantic_sha256": source.get("racenote_semantic_sha256"),
        "rrdb_recommendation_contract": rrdb.get("recommendation_contract_version", REQUIRED_RRDB),
        "prediction": record.get("prediction") or {},
        "decision_trace": trace,
    }


def semantic_hash(record: dict[str, Any]) -> str:
    payload = json.dumps(
        semantic_payload(record),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_prepared_record(
    record: dict[str, Any],
    reader: dict[str, Any],
    selection_id: str,
    target_date: str,
    logic_version: str = DEFAULT_LOGIC,
) -> None:
    race = reader.get("race") or {}
    ident = record.get("identity") or {}
    research = record.get("research") or {}
    source = record.get("source") or {}
    prediction = record.get("prediction") or {}
    trace = record.get("decision_trace") or {}

    expected = (target_date, str(race.get("venue")), int(race.get("race_no")))
    got = (str(ident.get("target_date")), str(ident.get("venue")), int(ident.get("race_no")))
    assert got == expected, (got, expected)

    assert record.get("schema_version") == LOGIC_SCHEMAS[logic_version]
    assert research.get("logic_version") == logic_version
    if logic_version != DEFAULT_LOGIC:
        assert research.get("independent_forecast") is True
        assert research.get("baseline_marks_used_as_input") is False
        from validate_racenote_forecast_human_context import validate_consistency_pass
        assert not validate_consistency_pass(record), validate_consistency_pass(record)
    assert research.get("reader_facing_prose_contract") == REQUIRED_PROSE
    assert research.get("authoring_mode") == REQUIRED_AUTHORING_MODE
    assert research.get("prose_origin") == REQUIRED_PROSE_ORIGIN

    expected_source = reader.get("source_semantic_sha256")
    assert source.get("racenote_semantic_sha256") == expected_source
    assert source.get("reader_input_policy") == "TARGET_DAY_MARKET_OBJECT_REMOVED_BEFORE_FORECAST"
    assert str(source.get("racenote_identity") or "").startswith(f"{selection_id}/")

    assert not contains_key(record, "market"), "prepared forecast record must not contain target-day market"

    horses = {horse_no(h): horse_name(h) for h in reader.get("horses", [])}
    entries = mark_entries(record)
    assert len(entries) == 5
    numbers = [int(x.get("horse_no")) for x in entries]
    assert len(set(numbers)) == 5
    for entry in entries:
        n = int(entry.get("horse_no"))
        assert n in horses, (race, n)
        assert str(entry.get("horse_name") or "").strip() == horses[n], (race, n, entry)

    axis = prediction.get("axis") or {}
    assert int(axis.get("horse_no")) == numbers[0]
    assert str(axis.get("horse_name") or "").strip() == horses[numbers[0]]

    single = trace.get("single_shot_case") or {}
    single_horse = single.get("horse") or {}
    assert int(single_horse.get("horse_no")) == numbers[2]
    assert single.get("selected_independently_from_mainline") is True

    rrdb = trace.get("rrdb_evidence") or {}
    assert rrdb.get("reviewed") is True
    assert rrdb.get("recommendation_contract_version", REQUIRED_RRDB) == REQUIRED_RRDB
    assert isinstance(rrdb.get("used_in_decision"), bool)
    refs = rrdb.get("horse_refs")
    assert isinstance(refs, list)
    for ref in refs:
        assert ref.get("recommendation_contract_version") == REQUIRED_RRDB
        assert ref.get("next_watch_grade") in {None, ""}
        assert not ref.get("matched_rule_ids")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prep-root", type=Path, required=True)
    ap.add_argument("--prepared-records", type=Path, required=True)
    ap.add_argument("--output-root", type=Path, required=True)
    ap.add_argument("--selection-id", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--main-sha", required=True)
    ap.add_argument("--logic-version", choices=tuple(LOGIC_SCHEMAS), default=DEFAULT_LOGIC)
    args = ap.parse_args()

    prep = args.prep_root
    handoff = json.loads((prep / "day_prep_handoff.json").read_text(encoding="utf-8"))
    assert handoff.get("selection_id") == args.selection_id
    assert handoff.get("target_date") == args.date
    assert handoff.get("result_opened") is False

    readers = {}
    for path in sorted((prep / "reader").glob("*.json")):
        reader = json.loads(path.read_text(encoding="utf-8"))
        race = reader.get("race") or {}
        key = (str(race.get("venue")), int(race.get("race_no")))
        assert key not in readers
        readers[key] = (path, reader)

    records = load_records(args.prepared_records)
    assert len(records) == len(readers) == int(handoff.get("race_count"))

    by_key = {}
    for record in records:
        ident = record.get("identity") or {}
        key = (str(ident.get("venue")), int(ident.get("race_no")))
        assert key not in by_key, f"duplicate prepared race: {key}"
        assert key in readers, f"prepared race not in DAY PREP: {key}"
        validate_prepared_record(record, readers[key][1], args.selection_id, args.date, args.logic_version)
        by_key[key] = record

    assert set(by_key) == set(readers), "prepared records do not cover the full DAY PREP card"

    out = args.output_root
    if out.exists():
        raise FileExistsError(f"Freeze output already exists: {out}")
    for d in ("forecast", "reader_stripped", "day_merge"):
        (out / d).mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()
    compact = args.date.replace("-", "")
    frozen: list[dict[str, Any]] = []

    for key in sorted(readers):
        reader_path, reader = readers[key]
        record = copy.deepcopy(by_key[key])

        stripped = copy.deepcopy(reader)
        for horse in stripped.get("horses", []):
            horse.pop("market", None)
        (out / "reader_stripped" / reader_path.name).write_text(
            json.dumps(stripped, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

        source = record.setdefault("source", {})
        source["main_sha_at_forecast"] = args.main_sha

        audit = record.setdefault("audit", {})
        audit.update({
            "freeze_packager_version": VERSION,
            "created_at": audit.get("created_at") or now,
            "frozen_at": now,
            "pre_result_guard": "PASS",
            "result_visible_at_freeze": False,
            "five_mark_role_guard": "PASS",
            "mainline_single_shot_guard": "PASS",
            "reader_facing_prose_guard": "PENDING_VALIDATOR",
            "market_blind_guard": "PASS_TARGET_DAY_MARKET_FIELDS_STRIPPED_BEFORE_FORECAST",
            "rrdb_contract_guard": "PASS_RECOMMENDATION_V0_3_GRADE_DISABLED",
            "prediction_hash_contract": "SEMANTIC_V1_EXECUTION_METADATA_EXCLUDED",
        })
        ph = semantic_hash(record)
        audit["prediction_hash"] = ph
        audit["prediction_semantic_hash"] = ph

        race = record["identity"]
        (out / "forecast" / f"forecast_{compact}_{race['venue']}{race['race_no']}R.json").write_text(
            json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        frozen.append(record)

    frozen.sort(key=lambda r: (str(r["identity"]["venue"]), int(r["identity"]["race_no"])))
    jsonl = out / "day_merge" / f"forecast_{compact}_all.jsonl"
    merged = out / "day_merge" / f"forecast_{compact}_all.json"
    jsonl.write_text(
        "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in frozen),
        encoding="utf-8",
    )
    merged.write_text(json.dumps(frozen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    hashes = [r["audit"]["prediction_semantic_hash"] for r in frozen]
    day_audit = {
        "status": "FROZEN_CLEAN_BLIND",
        "clean_blind_eligible": True,
        "result_opened": False,
        "record_count": len(frozen),
        "frozen_count": len(frozen),
        "prediction_hash_contract": "SEMANTIC_V1_EXECUTION_METADATA_EXCLUDED",
        "prediction_hash_unique_count": len(set(hashes)),
        "five_mark_role_guard": "PASS",
        "mainline_single_shot_guard": "PASS",
        "reader_facing_prose_guard": "PENDING_VALIDATOR",
        "market_blind_guard": "PASS_TARGET_DAY_MARKET_FIELDS_STRIPPED_BEFORE_FORECAST",
        "rrdb_contract_guard": "PASS_RECOMMENDATION_V0_3_GRADE_DISABLED",
    }
    (out / "day_merge" / f"forecast_{compact}_all_audit.json").write_text(
        json.dumps(day_audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    day_handoff = {
        "selection_id": args.selection_id,
        "target_date": args.date,
        "status": "FROZEN_CLEAN_BLIND",
        "clean_blind_eligible": True,
        "result_opened": False,
        "logic_version": args.logic_version,
        "reader_facing_prose_contract": REQUIRED_PROSE,
        "rrdb_recommendation_contract": REQUIRED_RRDB,
        "authoring_mode": REQUIRED_AUTHORING_MODE,
        "prose_origin": REQUIRED_PROSE_ORIGIN,
        "main_sha_at_forecast": args.main_sha,
        "race_count": len(frozen),
        "prediction_hash_contract": "SEMANTIC_V1_EXECUTION_METADATA_EXCLUDED",
        "prediction_hashes": hashes,
    }
    (out / "day_merge" / f"forecast_{compact}_all_handoff.json").write_text(
        json.dumps(day_handoff, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (out / "README.md").write_text(
        f"# {args.selection_id} / {args.date}\n\n"
        "Frozen clean-blind RaceNote forecast. Forecast judgment, marks, prose, and "
        "decision traces were authored before this deterministic packaging step. "
        "This packager did not select horses or generate forecast prose.\n",
        encoding="utf-8",
    )
    print(json.dumps(day_handoff, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
