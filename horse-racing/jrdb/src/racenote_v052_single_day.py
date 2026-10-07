#!/usr/bin/env python3
"""RaceNote v0.5.2 single-day authoring / Freeze path.

This is the canonical non-A/B v0.5.2 path. It consumes one market-blind
forecast_prep and exposes one v0.5.2 Reader set, one venue-authoring surface,
and one immutable day Freeze.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from racenote_decision_core_v052 import validate_core
from racenote_reader_v050 import DEFAULT_BINDING
from racenote_reader_v052 import VERSION as LOGIC, load_binding, transform
from racenote_save_venue_batch_v046 import load_clean

VERSION = "racenote-v052-single-day-0.1"
SESSION_VERSION = "racenote-v052-single-day-session-0.1"
MANIFEST_VERSION = "racenote-v052-single-day-reader-manifest-0.1"
AUTHORED_VERSION = "racenote-v052-single-day-authored-venue-0.1"
FROZEN_VERSION = "racenote-v052-single-day-frozen-0.1"
DEFAULT_POLICY = (
    Path(__file__).resolve().parents[1]
    / "docs" / "racenote" / "research-work" / "results" / "stage_c"
    / "reader_feature_policy_v0_5_candidate.json"
)


def encoded(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded(value) + b"\n")


def roster_from_readers(readers: dict) -> list[dict[str, Any]]:
    rows = []
    for (venue, race_no), item in sorted(readers.items()):
        horse_nos = [int(h["basic"]["horse_no"]) for h in item["reader"]["horses"]]
        if not horse_nos or len(horse_nos) != len(set(horse_nos)):
            raise ValueError(f"invalid horse roster: {venue}{race_no}R")
        rows.append({
            "venue": venue,
            "race_no": race_no,
            "file": item["file"],
            "horse_nos": sorted(horse_nos),
        })
    return rows


def session_identity(session: dict[str, Any]) -> dict[str, Any]:
    return {
        k: session[k]
        for k in (
            "schema_version", "selection_id", "target_date", "base_main_sha",
            "clean_reader_manifest_sha256", "race_roster", "expected_venues",
            "logic_version", "binding_sha256", "policy_sha256",
        )
    }


def expected_session_id(session: dict[str, Any]) -> str:
    return "V052-" + digest(encoded(session_identity(session)))[:20]


def _validator_reader(normal: dict[str, Any]) -> dict[str, Any]:
    return {
        "race": normal["race"],
        "horses": [
            {
                "basic": h["identity"],
                "racereview": (h.get("other_context") or {}).get("racereview"),
            }
            for h in normal["horses"]
        ],
    }


def expected_by_venue(session: dict[str, Any]) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    for row in session["race_roster"]:
        result.setdefault(row["venue"], []).append(int(row["race_no"]))
    return {venue: sorted(v) for venue, v in sorted(result.items())}


def init_session(
    prep_root: Path,
    root: Path,
    base_main_sha: str,
    binding_path: Path = DEFAULT_BINDING,
    policy_path: Path = DEFAULT_POLICY,
) -> dict[str, Any]:
    if root.exists():
        raise FileExistsError(f"v0.5.2 single-day root already exists: {root}")
    if len(base_main_sha) != 40 or any(c not in "0123456789abcdef" for c in base_main_sha):
        raise ValueError("base_main_sha must be a full lowercase commit SHA")

    handoff, clean_manifest, readers = load_clean(prep_root)
    if handoff.get("main_sha") != base_main_sha:
        raise ValueError("base SHA must equal forecast_prep handoff main_sha")
    if handoff.get("market_blind") is not True or handoff.get("stripped_at_input_bind") is not True:
        raise ValueError("forecast_prep must be market-blind and stripped")
    if handoff.get("result_opened") is not False or handoff.get("target_market_opened") is not False:
        raise ValueError("forecast_prep result/market boundary is not clean")

    clean_sha = digest((prep_root / "reader_stripped_manifest.json").read_bytes())
    if clean_sha != handoff.get("reader_stripped_manifest_sha256"):
        raise ValueError("forecast_prep clean manifest SHA mismatch")

    roster = roster_from_readers(readers)
    original_hashes = {item["file"]: item["sha256"] for item in readers.values()}
    if original_hashes != clean_manifest.get("reader_sha256"):
        raise ValueError("forecast_prep Reader hash set mismatch")

    binding = load_binding(binding_path)
    policy = read_json(policy_path)
    # v0.5.2 shares the exact v0.5 Reader evidence contract.
    from racenote_reader_v050 import validate_policy_binding
    validate_policy_binding(binding, policy)

    session: dict[str, Any] = {
        "schema_version": SESSION_VERSION,
        "selection_id": handoff["selection_id"],
        "target_date": handoff["target_date"],
        "base_main_sha": base_main_sha,
        "logic_version": LOGIC,
        "decision_core_version": "racenote-decision-core-0.5.2",
        "source_prep_root": os.path.relpath(prep_root.resolve(), root.resolve()),
        "clean_reader_manifest_sha256": clean_sha,
        "original_clean_reader_sha256": original_hashes,
        "race_roster": roster,
        "expected_venues": sorted({x["venue"] for x in roster}),
        "binding_sha256": digest(binding_path.read_bytes()),
        "policy_sha256": digest(policy_path.read_bytes()),
        "market_blind": True,
        "target_market_opened": False,
        "result_opened": False,
        "status": "SESSION_SEALED",
    }
    session["session_id"] = expected_session_id(session)

    root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{root.name}.build-", dir=root.parent) as temp:
        staging = Path(temp)
        entries = []
        for row in roster:
            source = readers[(row["venue"], row["race_no"])]["reader"]
            candidate = transform(source, binding)
            path = staging / "reader" / row["file"]
            write_json(path, candidate["normal_view"])
            entries.append({
                "venue": row["venue"],
                "race_no": row["race_no"],
                "original_clean_reader_filename": row["file"],
                "original_clean_reader_sha256": original_hashes[row["file"]],
                "source_semantic_sha256": source["source_semantic_sha256"],
                "derived_normal_filename": row["file"],
                "derived_normal_sha256": digest(path.read_bytes()),
                "candidate_version": LOGIC,
                "horse_nos": row["horse_nos"],
            })
        manifest = {
            "manifest_version": MANIFEST_VERSION,
            "session_id": session["session_id"],
            "selection_id": session["selection_id"],
            "target_date": session["target_date"],
            "clean_reader_manifest_sha256": clean_sha,
            "logic_version": LOGIC,
            "model_input": "normal_view_only",
            "projection_equivalent_to": "RaceNote-Human-Context-Reader-0.5.0-candidate",
            "entries": entries,
        }
        write_json(staging / "reader_manifest.json", manifest)
        session["reader_manifest_sha256"] = digest((staging / "reader_manifest.json").read_bytes())
        # session_id deliberately excludes reader_manifest_sha256 because it is
        # derived from already sealed identity fields.
        write_json(staging / "session.json", session)
        (staging / "incoming").mkdir(parents=True, exist_ok=True)
        staging.rename(root)
    return session


def load_session(root: Path) -> tuple[dict[str, Any], dict, dict[tuple[str, int], dict[str, Any]]]:
    session = read_json(root / "session.json")
    if (
        session.get("schema_version") != SESSION_VERSION
        or session.get("status") != "SESSION_SEALED"
        or session.get("logic_version") != LOGIC
        or session.get("market_blind") is not True
        or session.get("target_market_opened") is not False
        or session.get("result_opened") is not False
        or session.get("session_id") != expected_session_id(session)
    ):
        raise ValueError("v0.5.2 single-day session seal invalid")

    prep_root = (root / session["source_prep_root"]).resolve()
    handoff, clean_manifest, readers = load_clean(prep_root)
    if (
        handoff.get("selection_id") != session["selection_id"]
        or handoff.get("target_date") != session["target_date"]
        or handoff.get("main_sha") != session["base_main_sha"]
        or digest((prep_root / "reader_stripped_manifest.json").read_bytes())
        != session["clean_reader_manifest_sha256"]
    ):
        raise ValueError("forecast_prep changed after v0.5.2 session seal")
    if {item["file"]: item["sha256"] for item in readers.values()} != session["original_clean_reader_sha256"]:
        raise ValueError("forecast_prep Reader hashes changed")

    manifest_path = root / "reader_manifest.json"
    if digest(manifest_path.read_bytes()) != session["reader_manifest_sha256"]:
        raise ValueError("v0.5.2 Reader manifest digest mismatch")
    manifest = read_json(manifest_path)
    entries = {(x["venue"], int(x["race_no"])): x for x in manifest["entries"]}
    if roster_from_readers(readers) != session["race_roster"] or set(entries) != set(readers):
        raise ValueError("v0.5.2 single-day race roster mismatch")
    for key, entry in entries.items():
        path = root / "reader" / entry["derived_normal_filename"]
        if digest(path.read_bytes()) != entry["derived_normal_sha256"]:
            raise ValueError(f"v0.5.2 Reader changed: {key}")
    return session, readers, entries


def save_venue(root: Path, decisions_path: Path) -> dict[str, Any]:
    session, _, entries = load_session(root)
    incoming = (root / "incoming").resolve()
    path = decisions_path.resolve()
    if path.parent != incoming or path.suffix != ".json":
        raise ValueError("authoring input must be single-day incoming/<venue>.json")
    venue = path.stem
    expected = expected_by_venue(session)
    if venue not in expected:
        raise ValueError("unexpected venue")

    decisions = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(decisions, list) or len(decisions) != len(expected[venue]):
        raise ValueError("venue Decision Core card is incomplete")
    if sorted(int(x.get("race_no")) for x in decisions) != expected[venue]:
        raise ValueError("venue race roster mismatch")
    for core in decisions:
        key = (venue, int(core["race_no"]))
        normal = read_json(root / "reader" / entries[key]["derived_normal_filename"])
        if core.get("venue") != venue:
            raise ValueError("Decision Core venue mismatch")
        validate_core(core, _validator_reader(normal))

    payload = {
        "schema_version": AUTHORED_VERSION,
        "session_id": session["session_id"],
        "selection_id": session["selection_id"],
        "target_date": session["target_date"],
        "logic_version": LOGIC,
        "reader_manifest_sha256": session["reader_manifest_sha256"],
        "venue": venue,
        "race_nos": expected[venue],
        "decisions": decisions,
        "decision_core_sha256": [digest(encoded(x)) for x in decisions],
    }
    out = root / "authored_decisions" / f"{venue}.json"
    if out.exists():
        raise FileExistsError(f"immutable authored venue already exists: {out}")
    write_json(out, payload)
    return payload


def _load_authored(root: Path, session: dict, entries: dict) -> list[dict[str, Any]]:
    expected = expected_by_venue(session)
    folder = root / "authored_decisions"
    files = sorted(folder.glob("*.json"))
    if {p.name for p in files} != {f"{v}.json" for v in expected}:
        raise ValueError("complete expected venue set required before Freeze")
    payloads = []
    for path in files:
        item = read_json(path)
        venue = path.stem
        cores = item.get("decisions")
        if (
            item.get("schema_version") != AUTHORED_VERSION
            or item.get("session_id") != session["session_id"]
            or item.get("selection_id") != session["selection_id"]
            or item.get("target_date") != session["target_date"]
            or item.get("logic_version") != LOGIC
            or item.get("reader_manifest_sha256") != session["reader_manifest_sha256"]
            or item.get("venue") != venue
            or item.get("race_nos") != expected[venue]
            or not isinstance(cores, list)
            or item.get("decision_core_sha256") != [digest(encoded(x)) for x in cores]
        ):
            raise ValueError(f"authored venue seal mismatch: {venue}")
        for core in cores:
            key = (venue, int(core["race_no"]))
            normal = read_json(root / "reader" / entries[key]["derived_normal_filename"])
            validate_core(core, _validator_reader(normal))
        payloads.append(item)
    return payloads


def build_freeze(root: Path) -> dict[str, Any]:
    session, readers, entries = load_session(root)
    authored = _load_authored(root, session, entries)
    records = []
    for payload in authored:
        for core in payload["decisions"]:
            key = (payload["venue"], int(core["race_no"]))
            entry = entries[key]
            records.append({
                "session_id": session["session_id"],
                "selection_id": session["selection_id"],
                "target_date": session["target_date"],
                "logic_version": LOGIC,
                "venue": key[0],
                "race_no": key[1],
                "horse_nos": entry["horse_nos"],
                "reader_manifest_sha256": session["reader_manifest_sha256"],
                "original_clean_reader_manifest_sha256": session["clean_reader_manifest_sha256"],
                "original_clean_reader_sha256": readers[key]["sha256"],
                "reader_sha256": entry["derived_normal_sha256"],
                "source_semantic_sha256": readers[key]["reader"]["source_semantic_sha256"],
                "decision_core": core,
                "decision_core_sha256": digest(encoded(core)),
            })
    records.sort(key=lambda x: (x["venue"], x["race_no"]))
    if [(x["venue"], x["race_no"]) for x in records] != [(x["venue"], x["race_no"]) for x in session["race_roster"]]:
        raise ValueError("frozen race roster mismatch")

    handoff = {
        "schema_version": FROZEN_VERSION,
        "status": "FROZEN_CLEAN_BLIND",
        "validator_status": "PASS",
        "validator": "racenote_decision_core_v052.validate_core + single-day session integrity",
        "session_id": session["session_id"],
        "selection_id": session["selection_id"],
        "target_date": session["target_date"],
        "logic_version": LOGIC,
        "reader_manifest_sha256": session["reader_manifest_sha256"],
        "race_roster": session["race_roster"],
        "expected_venues": session["expected_venues"],
        "record_count": len(records),
        "market_blind": True,
        "target_market_opened": False,
        "result_opened": False,
        "records_sha256": digest(encoded(records) + b"\n"),
    }
    frozen = root / "frozen"
    if frozen.exists():
        raise FileExistsError(f"immutable single-day Freeze already exists: {frozen}")
    with tempfile.TemporaryDirectory(prefix=".v052.frozen-", dir=root) as temp:
        staging = Path(temp)
        write_json(staging / "records.json", records)
        write_json(staging / "day_handoff.json", handoff)
        staging.rename(frozen)
    return handoff


def verify_freeze(root: Path) -> dict[str, Any]:
    session, readers, entries = load_session(root)
    authored = _load_authored(root, session, entries)
    authored_by_key = {
        (p["venue"], int(core["race_no"])): core
        for p in authored for core in p["decisions"]
    }
    handoff = read_json(root / "frozen" / "day_handoff.json")
    raw = (root / "frozen" / "records.json").read_bytes()
    records = json.loads(raw)
    if (
        handoff.get("schema_version") != FROZEN_VERSION
        or handoff.get("status") != "FROZEN_CLEAN_BLIND"
        or handoff.get("validator_status") != "PASS"
        or handoff.get("session_id") != session["session_id"]
        or handoff.get("selection_id") != session["selection_id"]
        or handoff.get("target_date") != session["target_date"]
        or handoff.get("logic_version") != LOGIC
        or handoff.get("reader_manifest_sha256") != session["reader_manifest_sha256"]
        or handoff.get("race_roster") != session["race_roster"]
        or handoff.get("expected_venues") != session["expected_venues"]
        or handoff.get("record_count") != len(records)
        or handoff.get("market_blind") is not True
        or handoff.get("target_market_opened") is not False
        or handoff.get("result_opened") is not False
        or handoff.get("records_sha256") != digest(raw)
    ):
        raise ValueError("single-day Freeze seal invalid")
    for row in records:
        key = (row["venue"], int(row["race_no"]))
        entry = entries[key]
        normal = read_json(root / "reader" / entry["derived_normal_filename"])
        if (
            row.get("session_id") != session["session_id"]
            or row.get("selection_id") != session["selection_id"]
            or row.get("target_date") != session["target_date"]
            or row.get("logic_version") != LOGIC
            or row.get("reader_manifest_sha256") != session["reader_manifest_sha256"]
            or row.get("original_clean_reader_manifest_sha256") != session["clean_reader_manifest_sha256"]
            or row.get("original_clean_reader_sha256") != readers[key]["sha256"]
            or row.get("reader_sha256") != entry["derived_normal_sha256"]
            or row.get("source_semantic_sha256") != readers[key]["reader"]["source_semantic_sha256"]
            or row.get("horse_nos") != entry["horse_nos"]
            or row.get("decision_core_sha256") != digest(encoded(row["decision_core"]))
            or row["decision_core"] != authored_by_key[key]
        ):
            raise ValueError(f"frozen record binding mismatch: {key}")
        validate_core(row["decision_core"], _validator_reader(normal))
    return handoff


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="action", required=True)

    p = sub.add_parser("init")
    p.add_argument("--prep-root", type=Path, required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--base-main-sha", required=True)
    p.add_argument("--binding", type=Path, default=DEFAULT_BINDING)
    p.add_argument("--policy", type=Path, default=DEFAULT_POLICY)

    p = sub.add_parser("save")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--decisions", type=Path, required=True)

    p = sub.add_parser("freeze")
    p.add_argument("--root", type=Path, required=True)

    p = sub.add_parser("verify")
    p.add_argument("--root", type=Path, required=True)

    args = ap.parse_args()
    if args.action == "init":
        result = init_session(args.prep_root, args.root, args.base_main_sha, args.binding, args.policy)
        summary = {"status": "SESSION_SEALED", "session_id": result["session_id"], "race_count": len(result["race_roster"])}
    elif args.action == "save":
        result = save_venue(args.root, args.decisions)
        summary = {"status": "SAVED", "venue": result["venue"], "race_count": len(result["race_nos"])}
    elif args.action == "freeze":
        result = build_freeze(args.root)
        summary = {"status": result["status"], "record_count": result["record_count"]}
    else:
        result = verify_freeze(args.root)
        summary = {"status": "VERIFIED", "record_count": result["record_count"]}
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
