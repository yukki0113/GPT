#!/usr/bin/env python3
"""P2 research gate: validate LLM-authored ticket judgments, never predict or score."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "racenote-p2-ticket-structure-v0.1"
BET_TYPES = {"WIDE": 2, "QUINELLA": 2, "TRIO": 3}
REF_TYPES = ("evidence", "other_context", "historical_race_lap_contexts", "rrdb_v05")
FORBIDDEN_KEYS = re.compile(
    r"(?:^|_)(?:confidence|result|finish|payout|refund|dividend|odds|popularity|settlement)(?:_|$)", re.I
)


def _load(path: Path) -> Any:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"unsafe or missing file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _text(row: dict, key: str, label: str, minimum: int = 12) -> str:
    value = row.get(key)
    _require(isinstance(value, str) and len(value.strip()) >= minimum,
             f"{label}.{key}: substantive rationale required")
    return value.strip()


def _check_blind_fields(value: Any, loc: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            _require(not FORBIDDEN_KEYS.search(str(key)),
                     f"forbidden outcome/market/confidence field: {loc}.{key}")
            _check_blind_fields(child, f"{loc}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            _check_blind_fields(child, f"{loc}[{i}]")


def _refs(reader: dict, references: Any, horses: set[int], label: str) -> None:
    _require(isinstance(references, list) and 1 <= len(references) <= 10,
             f"{label}: expected 1–10 Reader evidence references")
    for pointer in references:
        _require(isinstance(pointer, str) and pointer.startswith("/horses/"),
                 f"{label}: invalid JSON pointer")
        parts = pointer.split("/")[1:]
        _require(len(parts) >= 4 and parts[1].isdigit(), f"{label}: horse evidence pointer required")
        index = int(parts[1])
        _require(0 <= index < len(reader["horses"]), f"{label}: horse index out of range")
        horse_no = reader["horses"][index]["identity"]["horse_no"]
        _require(horse_no in horses and parts[2] in REF_TYPES,
                 f"{label}: pointer must cite the relevant horse: {pointer}")
        node: Any = reader
        for raw_part in parts:
            part = raw_part.replace("~1", "/").replace("~0", "~")
            if isinstance(node, dict) and part in node:
                node = node[part]
            elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
                node = node[int(part)]
            else:
                raise ValueError(f"{label}: missing evidence pointer {pointer}")
        _require(node is not None and node != "" and node != [] and node != {},
                 f"{label}: evidence is empty: {pointer}")


def _validate_race(row: dict, old: dict, reader: dict, label: str) -> dict:
    _check_blind_fields(row)
    _require(set(row) == {
        "venue", "race_no", "marks", "reader_sha256", "decision_core_sha256",
        "five_roles", "outside_screen", "outside_summary", "cooccurrence_cases",
        "purchase_decision", "tickets", "no_bet_reason", "market_available",
    }, f"{label}: invalid record fields")
    marks = old["decision_core"]["marks"]
    _require(row["marks"] == marks, f"{label}: changed frozen marks")
    _require(row["reader_sha256"] == old["reader_sha256"] and
             row["decision_core_sha256"] == old["decision_core_sha256"],
             f"{label}: frozen SHA mismatch")
    horse_nos = [h["identity"]["horse_no"] for h in reader["horses"]]
    _require(len(set(horse_nos)) == len(horse_nos) and set(marks) <= set(horse_nos),
             f"{label}: inconsistent Reader")
    outside = set(horse_nos) - set(marks)

    roles = row["five_roles"]
    _require(isinstance(roles, list) and len(roles) == 5 and
             {r.get("horse_no") for r in roles if isinstance(r, dict)} == set(marks),
             f"{label}: all five distinct horse roles required")
    for role in roles:
        _require(set(role) == {
            "horse_no", "win_path", "top2_path", "top3_path", "failure_path", "evidence_refs"
        }, f"{label}: invalid horse role fields")
        for field in ("win_path", "top2_path", "top3_path", "failure_path"):
            _text(role, field, label)
        _refs(reader, role["evidence_refs"], {role["horse_no"]}, label)

    screening = row["outside_screen"]
    _require(isinstance(screening, list) and len(screening) == len(outside) and
             {x.get("horse_no") for x in screening if isinstance(x, dict)} == outside,
             f"{label}: every non-marked horse must be screened exactly once")
    for x in screening:
        _require(set(x) == {"horse_no", "classification", "top3_path", "evidence_refs"},
                 f"{label}: invalid outsider screening fields")
        _require(x["classification"] in {
            "THREAT", "MONITOR", "LOW", "INSUFFICIENT_EVIDENCE"
        }, f"{label}: unknown outsider classification")
        _text(x, "top3_path", label)
        _refs(reader, x["evidence_refs"], {x["horse_no"]}, label)
    _text(row, "outside_summary", label, 20)

    cases = row["cooccurrence_cases"]
    _require(isinstance(cases, list), f"{label}: invalid simultaneous-finish cases")
    case_index = {}
    for case in cases:
        _require(set(case) == {
            "case_id", "horse_nos", "bet_type", "shared_scenario",
            "conflict_scenario", "evidence_refs"
        }, f"{label}: invalid cooccurrence case")
        case_id = case.get("case_id")
        _require(isinstance(case_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,40}", case_id)
                 and case_id not in case_index, f"{label}: invalid/duplicate case ID")
        numbers, kind = case["horse_nos"], case["bet_type"]
        _require(kind in BET_TYPES and isinstance(numbers, list) and
                 len(numbers) == BET_TYPES[kind] and len(set(numbers)) == len(numbers)
                 and numbers == sorted(numbers) and set(numbers) <= set(marks),
                 f"{label}: invalid cooccurrence horses")
        _text(case, "shared_scenario", label, 20)
        _text(case, "conflict_scenario", label)
        _refs(reader, case["evidence_refs"], set(numbers), label)
        cited = {reader["horses"][int(pointer.split("/")[2])]["identity"]["horse_no"]
                 for pointer in case["evidence_refs"]}
        _require(set(numbers) <= cited, f"{label}: each case horse needs Reader evidence")
        case_index[case_id] = case

    _require(row["market_available"] is False,
             f"{label}: target odds/market not permitted in blind structure trial")
    state, tickets = row["purchase_decision"], row["tickets"]
    _require(state in ("PROVISIONAL_BET", "PASS"), f"{label}: invalid purchase decision")
    _require(isinstance(tickets, list) and len(tickets) <= 12,
             f"{label}: no more than 12 tickets / 1,200 yen per race")
    unique = set()
    for ticket in tickets:
        _require(set(ticket) == {"bet_type", "horse_nos", "stake_yen", "case_id"},
                 f"{label}: invalid ticket fields")
        _require(type(ticket["stake_yen"]) is int and ticket["stake_yen"] == 100,
                 f"{label}: stake must be exactly 100 yen")
        kind, numbers = ticket["bet_type"], ticket["horse_nos"]
        _require(kind in BET_TYPES and isinstance(numbers, list) and
                 len(numbers) == BET_TYPES[kind] and len(set(numbers)) == len(numbers)
                 and numbers == sorted(numbers) and set(numbers) <= set(marks),
                 f"{label}: invalid ticket horses")
        ident = (kind, tuple(numbers))
        _require(ident not in unique, f"{label}: duplicate ticket")
        unique.add(ident)
        case = case_index.get(ticket["case_id"])
        _require(case is not None and case["bet_type"] == kind and case["horse_nos"] == numbers,
                 f"{label}: each ticket requires a matching cooccurrence case")
    if state == "PASS":
        _require(not tickets, f"{label}: PASS must have zero tickets")
        _text(row, "no_bet_reason", label, 16)
    else:
        _require(bool(tickets) and row["no_bet_reason"] is None,
                 f"{label}: PROVISIONAL_BET requires tickets and null PASS reason")
    return {"tickets": len(tickets), "stake_yen": 100 * len(tickets),
            "outside_threats": sum(x["classification"] == "THREAT" for x in screening)}


def validate(root: Path, draft_path: Path) -> dict:
    """Read-only structural validation, bound to complete v056 Prediction Freeze."""
    original = root / "frozen" / "records.json"
    handoff = _load(root / "frozen" / "day_handoff.json")
    _require(handoff.get("status") == "PREDICTION_FROZEN_CLEAN_BLIND" and
             handoff.get("market_blind") is True and
             handoff.get("result_opened") is False and
             handoff.get("target_market_opened") is False and
             handoff.get("records_sha256") == _digest(original),
             "Prediction Freeze not clean or hash verified")
    manifest_path = root / "reader_manifest.json"
    manifest = _load(manifest_path)
    _require(_digest(manifest_path) == handoff.get("reader_manifest_sha256"),
             "Reader manifest checksum mismatch")
    frozen, draft = _load(original), _load(draft_path)
    _require(set(draft) == {
        "schema_version", "selection_id", "target_date", "result_opened",
        "target_market_opened", "confidence_used", "records"
    }, "invalid draft envelope")
    _require(draft["schema_version"] == SCHEMA and
             draft["selection_id"] == handoff["selection_id"] and
             draft["target_date"] == handoff["target_date"] and
             draft["result_opened"] is False and draft["target_market_opened"] is False
             and draft["confidence_used"] is False,
             "draft identity or blind status mismatch")
    _require(isinstance(frozen, list) and isinstance(draft["records"], list) and
             len(frozen) == len(draft["records"]) ==
             len(manifest["entries"]) == handoff["record_count"], "roster count mismatch")
    pred = {(r["venue"], r["race_no"]): r for r in frozen}
    readers = {(r["venue"], r["race_no"]): r for r in manifest["entries"]}
    _require(len(pred) == len(frozen) and len(readers) == len(manifest["entries"]),
             "duplicate prediction/manifest race")
    seen = set()
    total = {"races": 0, "provisional_bet": 0, "pass": 0,
             "tickets": 0, "stake_yen": 0, "outside_threats": 0}
    for row in draft["records"]:
        _require(isinstance(row, dict), "draft record must be object")
        identity = (row.get("venue"), row.get("race_no"))
        _require(identity not in seen and identity in pred and identity in readers,
                 f"unknown/duplicate race {identity}")
        seen.add(identity)
        info = readers[identity]
        name = info["derived_normal_filename"]
        _require("/" not in name and "\\" not in name and name.endswith(".json"),
                 "unsafe Reader filename")
        reader_path = root / "reader" / name
        _require(_digest(reader_path) == info["derived_normal_sha256"] ==
                 pred[identity]["reader_sha256"], f"Reader SHA mismatch {identity}")
        reader = _load(reader_path)
        _require(reader["race"]["venue"] == identity[0] and
                 reader["race"]["race_no"] == identity[1],
                 f"Reader identity mismatch {identity}")
        stats = _validate_race(row, pred[identity], reader, str(identity))
        total["races"] += 1
        total["provisional_bet" if row["purchase_decision"] == "PROVISIONAL_BET"
              else "pass"] += 1
        for key in ("tickets", "stake_yen", "outside_threats"):
            total[key] += stats[key]
    _require(seen == set(pred) == set(readers), "incomplete day roster")
    return {"status": "PASS", "gate_version": SCHEMA, "totals": total,
            "selection_id": draft["selection_id"], "target_date": draft["target_date"],
            "prediction_frozen_sha256": _digest(original),
            "reader_manifest_sha256": _digest(manifest_path),
            "draft_sha256": _digest(draft_path),
            "result_opened": False, "confidence_used": False,
            "note": "Structural gate only; no semantic calibration, positive ROI, or odds validation."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--draft", required=True, type=Path)
    parser.add_argument("--freeze-output", type=Path)
    args = parser.parse_args()
    report = validate(args.root, args.draft)
    if args.freeze_output is not None:
        dest = args.freeze_output
        _require(not dest.exists() and not dest.is_symlink(), "refuse overwrite of research Freeze")
        root = args.root.resolve()
        _require(root not in dest.resolve().parents and root != dest.resolve(),
                 "research Freeze must stay outside the original v056 tree")
        dest.parent.mkdir(parents=True, exist_ok=True)
        sealed = {"schema_version": "racenote-p2-research-freeze-v0.1",
                  "status": "RESEARCH_TICKET_STRUCTURE_FROZEN", "quality": report,
                  "submission": _load(args.draft)}
        with dest.open("x", encoding="utf-8") as output:
            json.dump(sealed, output, ensure_ascii=False, indent=2)
            output.write("\n")
        report["research_freeze_output"] = str(dest)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
