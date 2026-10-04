#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic RaceNote Freeze packager.

This module MUST NOT choose horses or write forecast prose.
It accepts complete model-authored race records, validates them against the
market-blind Forecast Reader identities, computes semantic prediction hashes,
and writes canonical day files. It cannot repair an exposed authoring input.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from typing import Any

VERSION = "racenote-freeze-prepared-forecast-0.1.0"

DEFAULT_LOGIC = "RaceNote-Human-Context-Reader-0.4.2-candidate"
LOGIC_SCHEMAS = {
    DEFAULT_LOGIC: "RaceNote-Forecast-Research-Record-0.4.2",
    "RaceNote-Human-Context-Reader-0.4.3-candidate": "RaceNote-Forecast-Research-Record-0.4.3",
    "RaceNote-Human-Context-Reader-0.4.4-candidate": "RaceNote-Forecast-Research-Record-0.4.4",
    "RaceNote-Human-Context-Reader-0.4.5-candidate": "RaceNote-Forecast-Research-Record-0.4.5",
    "RaceNote-Human-Context-Reader-0.4.6-candidate": "RaceNote-Forecast-Research-Record-0.4.6",
}
REQUIRED_PROSE = "FORECAST_READER_FACING_PROSE_v0_1"
REQUIRED_RRDB = "rrdb-recommendation-signals-v0.3"
REQUIRED_AUTHORING_MODE = "MODEL_RACE_BY_RACE_REASONING"
V045_AUTHORING_MODE = "MODEL_RACE_BY_RACE_DECISION_CORE"
V046_AUTHORING_MODE = "MODEL_UNIFIED_RACE_JUDGMENT"
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
    if not __debug__:
        raise RuntimeError("Forecast validation must run without Python optimization; integrity guards use assertions")
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
        if logic_version != "RaceNote-Human-Context-Reader-0.4.6-candidate":
            from validate_racenote_forecast_human_context import validate_consistency_pass
            assert not validate_consistency_pass(record), validate_consistency_pass(record)
    assert research.get("reader_facing_prose_contract") == REQUIRED_PROSE
    if logic_version == "RaceNote-Human-Context-Reader-0.4.6-candidate":
        expected_authoring_mode = V046_AUTHORING_MODE
    elif logic_version == "RaceNote-Human-Context-Reader-0.4.5-candidate":
        expected_authoring_mode = V045_AUTHORING_MODE
    else:
        expected_authoring_mode = REQUIRED_AUTHORING_MODE
    assert research.get("authoring_mode") == expected_authoring_mode
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

    if logic_version == "RaceNote-Human-Context-Reader-0.4.4-candidate":
        cp = trace.get("consistency_pass") or {}
        scan = cp.get("coverage_scan") or {}
        boundary = cp.get("coverage_boundary") or {}
        provisional = boundary.get("current_delta2") or {}
        provisional_no = int(provisional.get("horse_no"))
        assert provisional_no in horses and provisional.get("horse_name") == horses[provisional_no], (
            race, "provisional delta2 identity mismatch"
        )
        assert provisional_no not in numbers[:4], (race, "provisional delta2 overlaps main/second/third/delta1")
        assert scan.get("unmarked_count") == len(horses) - 5, (race, "unmarked_count mismatch")
        direct = scan.get("direct_condition_candidate_count")
        assert isinstance(direct, int) and 0 <= direct <= len(horses) - 5, (race, "direct candidate count mismatch")
        provisional_five = set(numbers[:4]) | {provisional_no}
        shortlist = scan.get("shortlisted_horse_nos") or []
        assert all(n in horses and n not in provisional_five for n in shortlist), (
            race, "Coverage shortlist must contain only unmarked roster horses"
        )
        challenger = cp.get("coverage_best_challenger")
        if challenger is not None:
            n = int(challenger.get("horse_no"))
            assert n in horses and challenger.get("horse_name") == horses[n], (race, "challenger identity mismatch")
        mainline = trace.get("mainline_cases") or []
        expected_mainline = provisional_five - {numbers[2]}
        assert len(mainline) == 4 and {int(x["horse"]["horse_no"]) for x in mainline} == expected_mainline, (
            race, "v0.4.4 mainline must document main, second, delta1 and provisional delta2"
        )
        assert all(len(str(x.get("case") or "").strip()) >= 10 for x in mainline), (
            race, "v0.4.4 mainline case missing"
        )

    if logic_version == "RaceNote-Human-Context-Reader-0.4.5-candidate":
        cp = trace.get("consistency_pass") or {}
        scan = cp.get("coverage_scan") or {}
        boundary = cp.get("coverage_boundary") or {}
        provisional = boundary.get("current_delta2") or {}
        provisional_no = int(provisional.get("horse_no"))
        assert provisional_no in horses and provisional.get("horse_name") == horses[provisional_no], (
            race, "v0.4.5 provisional delta2 identity mismatch"
        )
        assert provisional_no not in numbers[:4], (race, "v0.4.5 provisional delta2 overlaps first four marks")
        assert scan.get("unmarked_count") == len(horses) - 5, (race, "v0.4.5 unmarked_count mismatch")
        provisional_five = set(numbers[:4]) | {provisional_no}
        shortlist = scan.get("shortlisted_horse_nos") or []
        assert all(n in horses and n not in provisional_five for n in shortlist), (
            race, "v0.4.5 Coverage shortlist must contain only unmarked roster horses"
        )
        challenger = cp.get("coverage_best_challenger")
        if challenger is not None:
            n = int(challenger.get("horse_no"))
            assert n in horses and challenger.get("horse_name") == horses[n], (
                race, "v0.4.5 challenger identity mismatch"
            )
        mainline = trace.get("mainline_cases") or []
        expected_mainline = provisional_five - {numbers[2]}
        assert len(mainline) == 4 and {int(x["horse"]["horse_no"]) for x in mainline} == expected_mainline, (
            race, "v0.4.5 mainline must document main, second, delta1 and provisional delta2"
        )
        assert all(len(str(x.get("case") or "").strip()) >= 10 for x in mainline), (
            race, "v0.4.5 mainline case missing"
        )

    if logic_version == "RaceNote-Human-Context-Reader-0.4.6-candidate":
        mainline = trace.get("mainline_cases") or []
        expected_mainline = {numbers[0], numbers[1], numbers[3], numbers[4]}
        assert len(mainline) == 4 and {int(x["horse"]["horse_no"]) for x in mainline} == expected_mainline, (
            race, "v0.4.6 mainline must document ◎ ○ △1 △2"
        )
        assert all(len(str(x.get("case") or "").strip()) >= 8 for x in mainline), (
            race, "v0.4.6 mainline case missing"
        )
        boundary = trace.get("support_boundary") or {}
        final_delta2 = boundary.get("final_delta2") or {}
        assert int(final_delta2.get("horse_no")) == numbers[4], (
            race, "v0.4.6 support boundary final_delta2 mismatch"
        )
        assert final_delta2.get("horse_name") == horses[numbers[4]], (
            race, "v0.4.6 final delta2 identity mismatch"
        )
        alternative = boundary.get("alternative")
        if alternative is not None:
            n = int(alternative.get("horse_no"))
            assert n in horses and alternative.get("horse_name") == horses[n], (
                race, "v0.4.6 boundary alternative identity mismatch"
            )
            assert n not in numbers, (race, "v0.4.6 boundary alternative must remain outside final five")
        assert len(str(boundary.get("reason") or "").strip()) >= 8, (
            race, "v0.4.6 boundary reason missing"
        )

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
    ap.add_argument("--preflight-only", action="store_true", help="Validate the full authored card without creating Freeze files")
    args = ap.parse_args()

    prep = args.prep_root
    handoff = json.loads((prep / "day_prep_handoff.json").read_text(encoding="utf-8"))
    assert handoff.get("selection_id") == args.selection_id
    assert handoff.get("target_date") == args.date
    assert handoff.get("result_opened") is False
    assert handoff.get("target_market_opened", False) is False

    if args.logic_version != DEFAULT_LOGIC:
        assert handoff.get("market_blind") is True
        assert handoff.get("stripped_at_input_bind") is True
        assert handoff.get("main_sha") == args.main_sha
        assert handoff.get("rrdb_contract") == REQUIRED_RRDB
        manifest_bytes = (prep / "reader_stripped_manifest.json").read_bytes()
        assert hashlib.sha256(manifest_bytes).hexdigest() == handoff.get("reader_stripped_manifest_sha256")
        stripped_manifest = json.loads(manifest_bytes)
        assert stripped_manifest.get("selection_id") == args.selection_id
        assert stripped_manifest.get("target_date") == args.date
        assert stripped_manifest.get("race_count") == handoff.get("race_count")
        assert stripped_manifest.get("market_blind") is True
        assert stripped_manifest.get("result_opened") is False
        expected_hashes = stripped_manifest.get("reader_sha256") or {}
    else:
        expected_hashes = None

    readers = {}
    reader_paths = sorted((prep / "reader").glob("*.json"))
    if expected_hashes is not None:
        assert set(expected_hashes) == {p.name for p in reader_paths}, "Reader manifest file set mismatch"
    for path in reader_paths:
        content = path.read_bytes()
        if expected_hashes is not None:
            assert hashlib.sha256(content).hexdigest() == expected_hashes[path.name], f"Reader digest mismatch: {path.name}"
        reader = json.loads(content)
        assert not contains_key(reader, "market"), f"Forecast input still contains market: {path.name}"
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

    from validate_racenote_forecast_human_context import audit_turn
    validation = audit_turn(records)
    if validation["status"] != "PASS":
        raise ValueError("Prepared forecast validator FAIL: " + "; ".join(validation["errors"]))
    if args.preflight_only:
        print(json.dumps({"status": "PASS", "preflight_only": True,
                          "selection_id": args.selection_id, "race_count": len(records),
                          "validator": validation}, ensure_ascii=False, indent=2))
        return 0

    final_out = args.output_root
    if final_out.exists():
        raise FileExistsError(f"Freeze output already exists: {final_out}")
    final_out.parent.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix=f".{final_out.name}.freeze-", dir=final_out.parent))
    for d in ("forecast", "reader_stripped", "day_merge"):
        (out / d).mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()
    compact = args.date.replace("-", "")
    frozen: list[dict[str, Any]] = []

    for key in sorted(readers):
        reader_path, reader = readers[key]
        record = copy.deepcopy(by_key[key])

        stripped = copy.deepcopy(reader)
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
        "authoring_mode": (V046_AUTHORING_MODE if args.logic_version == "RaceNote-Human-Context-Reader-0.4.6-candidate" else (V045_AUTHORING_MODE if args.logic_version == "RaceNote-Human-Context-Reader-0.4.5-candidate" else REQUIRED_AUTHORING_MODE)),
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
    if final_out.exists():
        raise FileExistsError(f"Freeze output already exists: {final_out}")
    out.rename(final_out)
    print(json.dumps(day_handoff, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
