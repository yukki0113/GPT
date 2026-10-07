#!/usr/bin/env python3
"""Immutable, isolated A/B venue authoring and research Freeze wrappers."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from typing import Any

from racenote_ab_session import digest, encoded, load_session, read_json, write_json
from racenote_reader_v050 import VERSION as V050
from racenote_reader_v051 import VERSION as V051
from racenote_save_venue_batch_v046 import LOGIC as V046, validate_core as validate_core_v046
from racenote_decision_core_v051 import validate_core as validate_core_v051

LANES = {"v046": V046, "v050": V050, "v051": V051}
VALIDATORS = {"v046": validate_core_v046, "v050": validate_core_v046, "v051": validate_core_v051}
AUTHORED_VERSION = "racenote-ab-authored-venue-0.1"
FROZEN_VERSION = "racenote-ab-lane-frozen-0.1"


def lane_reader_manifest_sha(ab_root: Path, lane: str, session: dict) -> str:
    if lane == "v046":
        return session["clean_reader_manifest_sha256"]
    if lane == "v050":
        return session["v050_reader_manifest_sha256"]
    return session["v051_reader_manifest_sha256"]


def lane_reader(ab_root: Path, lane: str, key: tuple[str, int], readers: dict, derived: dict) -> tuple[dict, str]:
    if lane == "v046":
        item = readers[key]
        return item["reader"], item["sha256"]
    entry = derived[key]
    normal = read_json(ab_root / lane / "reader" / entry["derived_normal_filename"])
    # Reuse the existing Decision Core validator only for identity and RRDB
    # citations. It receives the candidate normal view, never provenance or
    # the original v0.4.6 evidence values.
    adapted = {
        "race": normal["race"],
        "horses": [
            {
                "basic": h["identity"],
                "racereview": (h.get("other_context") or {}).get("racereview"),
            }
            for h in normal["horses"]
        ],
    }
    return adapted, entry["derived_normal_sha256"]


def expected_races_by_venue(session: dict) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    for row in session["race_roster"]:
        result.setdefault(row["venue"], []).append(row["race_no"])
    return {venue: sorted(races) for venue, races in sorted(result.items())}


def _validate_venue_cores(
    decisions: list[dict[str, Any]],
    venue: str,
    expected: list[int],
    ab_root: Path,
    lane: str,
    readers: dict,
    derived: dict,
) -> None:
    if not isinstance(decisions, list) or len(decisions) != len(expected):
        raise ValueError("venue card is incomplete")
    got = [x.get("race_no") for x in decisions]
    if sorted(got) != expected or len(set(got)) != len(got):
        raise ValueError("venue race roster mismatch")
    for core in decisions:
        key = (venue, core["race_no"])
        if core.get("venue") != venue or key not in readers:
            raise ValueError("Decision Core race identity mismatch")
        reader, _ = lane_reader(ab_root, lane, key, readers, derived)
        VALIDATORS[lane](core, reader)


def save_venue(ab_root: Path, lane: str, decisions_path: Path) -> dict[str, Any]:
    if lane not in LANES:
        raise ValueError("unknown A/B lane")
    session, readers, derived = load_session(ab_root)
    if lane not in session.get("lane_definitions", {}):
        raise ValueError("lane is not enabled in this sealed session")
    incoming = (ab_root / lane / "incoming").resolve()
    path = decisions_path.resolve()
    if path.parent != incoming or path.suffix != ".json":
        raise ValueError("authoring input must be this lane's incoming/<venue>.json; sibling inputs forbidden")
    venue = path.stem
    expected = expected_races_by_venue(session)
    if venue not in expected:
        raise ValueError("unexpected venue")
    decisions = json.loads(path.read_text(encoding="utf-8"))
    _validate_venue_cores(decisions, venue, expected[venue], ab_root, lane, readers, derived)
    manifest_sha = lane_reader_manifest_sha(ab_root, lane, session)
    payload = {
        "schema_version": AUTHORED_VERSION,
        "session_id": session["session_id"],
        "selection_id": session["selection_id"],
        "target_date": session["target_date"],
        "lane_id": lane,
        "logic_version": LANES[lane],
        "reader_manifest_sha256": manifest_sha,
        "original_clean_reader_manifest_sha256": session["clean_reader_manifest_sha256"],
        "venue": venue,
        "race_nos": expected[venue],
        "sibling_forecast_input_used": False,
        "input_sources": ["shared/reader_manifest.json", f"{lane}/reader_manifest.json"],
        "decisions": decisions,
        "decision_core_sha256": [digest(encoded(core)) for core in decisions],
    }
    out = ab_root / lane / "authored_decisions" / f"{venue}.json"
    if out.exists():
        raise FileExistsError(f"immutable authored venue already exists: {out}")
    write_json(out, payload)
    return payload


def _load_authored(ab_root: Path, lane: str, session: dict, readers: dict, derived: dict) -> list[dict[str, Any]]:
    expected = expected_races_by_venue(session)
    folder = ab_root / lane / "authored_decisions"
    files = sorted(folder.glob("*.json"))
    if {p.name for p in files} != {f"{venue}.json" for venue in expected}:
        raise ValueError(f"{lane}: complete expected venue set required")
    payloads = []
    for path in files:
        item = read_json(path)
        venue = path.stem
        if (
            item.get("schema_version") != AUTHORED_VERSION
            or item.get("session_id") != session["session_id"]
            or item.get("selection_id") != session["selection_id"]
            or item.get("target_date") != session["target_date"]
            or item.get("lane_id") != lane
            or item.get("logic_version") != LANES[lane]
            or item.get("reader_manifest_sha256") != lane_reader_manifest_sha(ab_root, lane, session)
            or item.get("original_clean_reader_manifest_sha256") != session["clean_reader_manifest_sha256"]
            or item.get("venue") != venue
            or item.get("race_nos") != expected[venue]
            or item.get("sibling_forecast_input_used") is not False
            or item.get("input_sources") != ["shared/reader_manifest.json", f"{lane}/reader_manifest.json"]
        ):
            raise ValueError(f"{lane}: authored venue seal mismatch: {venue}")
        cores = item.get("decisions")
        hashes = item.get("decision_core_sha256")
        if not isinstance(cores, list) or hashes != [digest(encoded(x)) for x in cores]:
            raise ValueError(f"{lane}: authored Decision Core hash mismatch: {venue}")
        _validate_venue_cores(cores, venue, expected[venue], ab_root, lane, readers, derived)
        payloads.append(item)
    return payloads


def build_freeze(ab_root: Path, lane: str) -> dict[str, Any]:
    if lane not in LANES:
        raise ValueError("unknown A/B lane")
    session, readers, derived = load_session(ab_root)
    if lane not in session.get("lane_definitions", {}):
        raise ValueError("lane is not enabled in this sealed session")
    authored = _load_authored(ab_root, lane, session, readers, derived)
    records = []
    for payload in authored:
        for core in payload["decisions"]:
            key = (payload["venue"], core["race_no"])
            _, lane_reader_sha = lane_reader(ab_root, lane, key, readers, derived)
            records.append({
                "session_id": session["session_id"],
                "selection_id": session["selection_id"],
                "target_date": session["target_date"],
                "lane_id": lane,
                "logic_version": LANES[lane],
                "venue": key[0],
                "race_no": key[1],
                "horse_nos": next(r["horse_nos"] for r in session["race_roster"] if (r["venue"], r["race_no"]) == key),
                "reader_manifest_sha256": lane_reader_manifest_sha(ab_root, lane, session),
                "original_clean_reader_manifest_sha256": session["clean_reader_manifest_sha256"],
                "original_clean_reader_sha256": readers[key]["sha256"],
                "lane_reader_sha256": lane_reader_sha,
                "source_semantic_sha256": readers[key]["reader"]["source_semantic_sha256"],
                "sibling_forecast_input_used": False,
                "decision_core": core,
                "decision_core_sha256": digest(encoded(core)),
            })
    records.sort(key=lambda x: (x["venue"], x["race_no"]))
    if [(x["venue"], x["race_no"]) for x in records] != [(x["venue"], x["race_no"]) for x in session["race_roster"]]:
        raise ValueError("lane frozen race roster mismatch")
    handoff = {
        "schema_version": FROZEN_VERSION,
        "status": "FROZEN_CLEAN_BLIND",
        "validator_status": "PASS",
        "validator": "racenote_save_venue_batch_v046.validate_core + A/B session integrity",
        "session_id": session["session_id"],
        "selection_id": session["selection_id"],
        "target_date": session["target_date"],
        "lane_id": lane,
        "logic_version": LANES[lane],
        "reader_manifest_sha256": lane_reader_manifest_sha(ab_root, lane, session),
        "original_clean_reader_manifest_sha256": session["clean_reader_manifest_sha256"],
        "race_roster": session["race_roster"],
        "expected_venues": session["expected_venues"],
        "record_count": len(records),
        "market_blind": True,
        "target_market_opened": False,
        "result_opened": False,
        "sibling_forecast_input_used": False,
        "records_sha256": digest(encoded(records) + b"\n"),
    }
    frozen_root = ab_root / lane / "frozen"
    if frozen_root.exists():
        raise FileExistsError(f"immutable lane Freeze already exists: {frozen_root}")
    with tempfile.TemporaryDirectory(prefix=f".{lane}.frozen-", dir=ab_root / lane) as temp:
        staging = Path(temp)
        write_json(staging / "records.json", records)
        write_json(staging / "lane_handoff.json", handoff)
        staging.rename(frozen_root)
    return handoff


def load_lane_freeze(ab_root: Path, lane: str, session: dict, readers: dict, derived: dict) -> tuple[dict, list[dict]]:
    if lane not in LANES:
        raise ValueError("unknown A/B lane")
    if lane not in session.get("lane_definitions", {}):
        raise ValueError("lane is not enabled in this sealed session")
    root = ab_root / lane / "frozen"
    handoff = read_json(root / "lane_handoff.json")
    raw = (root / "records.json").read_bytes()
    records = json.loads(raw)
    if (
        handoff.get("schema_version") != FROZEN_VERSION
        or handoff.get("status") != "FROZEN_CLEAN_BLIND"
        or handoff.get("validator_status") != "PASS"
        or handoff.get("session_id") != session["session_id"]
        or handoff.get("selection_id") != session["selection_id"]
        or handoff.get("target_date") != session["target_date"]
        or handoff.get("lane_id") != lane
        or handoff.get("logic_version") != LANES[lane]
        or handoff.get("reader_manifest_sha256") != lane_reader_manifest_sha(ab_root, lane, session)
        or handoff.get("original_clean_reader_manifest_sha256") != session["clean_reader_manifest_sha256"]
        or handoff.get("race_roster") != session["race_roster"]
        or handoff.get("expected_venues") != session["expected_venues"]
        or handoff.get("market_blind") is not True
        or handoff.get("target_market_opened") is not False
        or handoff.get("result_opened") is not False
        or handoff.get("sibling_forecast_input_used") is not False
        or handoff.get("records_sha256") != digest(raw)
    ):
        raise ValueError(f"{lane}: lane Freeze seal invalid")
    if not isinstance(records, list) or len(records) != len(session["race_roster"]) or handoff.get("record_count") != len(records):
        raise ValueError(f"{lane}: frozen record count mismatch")
    if [(r["venue"], r["race_no"]) for r in records] != [(r["venue"], r["race_no"]) for r in session["race_roster"]]:
        raise ValueError(f"{lane}: frozen race roster mismatch")
    authored = _load_authored(ab_root, lane, session, readers, derived)
    authored_by_key = {(x["venue"], core["race_no"]): core for x in authored for core in x["decisions"]}
    for row in records:
        key = (row["venue"], row["race_no"])
        reader, lane_sha = lane_reader(ab_root, lane, key, readers, derived)
        if (
            row.get("session_id") != session["session_id"]
            or row.get("selection_id") != session["selection_id"]
            or row.get("target_date") != session["target_date"]
            or row.get("lane_id") != lane
            or row.get("logic_version") != LANES[lane]
            or row.get("reader_manifest_sha256") != lane_reader_manifest_sha(ab_root, lane, session)
            or row.get("original_clean_reader_manifest_sha256") != session["clean_reader_manifest_sha256"]
            or row.get("original_clean_reader_sha256") != readers[key]["sha256"]
            or row.get("lane_reader_sha256") != lane_sha
            or row.get("source_semantic_sha256") != readers[key]["reader"]["source_semantic_sha256"]
            or row.get("horse_nos") != next(r["horse_nos"] for r in session["race_roster"] if (r["venue"], r["race_no"]) == key)
            or row.get("sibling_forecast_input_used") is not False
            or row.get("decision_core_sha256") != digest(encoded(row["decision_core"]))
            or row["decision_core"] != authored_by_key[key]
        ):
            raise ValueError(f"{lane}: frozen record binding mismatch: {key}")
        VALIDATORS[lane](row["decision_core"], reader)
    return handoff, records


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=["save", "freeze"])
    ap.add_argument("--ab-root", type=Path, required=True)
    ap.add_argument("--lane", choices=sorted(LANES), required=True)
    ap.add_argument("--decisions", type=Path)
    args = ap.parse_args()
    if args.action == "save":
        if args.decisions is None:
            raise ValueError("--decisions is required for save")
        result = save_venue(args.ab_root, args.lane, args.decisions)
        summary = {"status": "SAVED", "lane": args.lane, "venue": result["venue"]}
    else:
        if args.decisions is not None:
            raise ValueError("--decisions is not accepted for freeze")
        result = build_freeze(args.ab_root, args.lane)
        summary = {"status": result["status"], "lane": args.lane, "record_count": result["record_count"]}
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
