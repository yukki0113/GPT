#!/usr/bin/env python3
"""RaceNote v0.5.5 single-day authoring / Freeze path.

This is the canonical non-A/B v0.5.5 path. It consumes one market-blind
forecast_prep and exposes one v0.5.5 Reader set, one venue-authoring surface,
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

from racenote_decision_core_v055 import (
    CONTRACT_REVISION,
    SUPPORTED_CONTRACT_REVISIONS,
    validate_core,
    validate_prose_collection,
)
from racenote_v055_authoring_quality import inspect as inspect_authoring_quality
from racenote_reader_v050 import DEFAULT_BINDING
from racenote_reader_v055 import READER_PROJECTION, VERSION as LOGIC, load_binding, transform
from racenote_save_venue_batch_v046 import load_clean

VERSION = "racenote-v055-single-day-0.1"
SESSION_VERSION = "racenote-v055-single-day-session-0.1"
MANIFEST_VERSION = "racenote-v055-single-day-reader-manifest-0.1"
AUTHORED_VERSION = "racenote-v055-single-day-authored-venue-0.1"
FROZEN_VERSION = "racenote-v055-single-day-frozen-0.1"
CONFIDENCE_REVIEW_VERSION = "racenote-v055-confidence-review-0.1"
CONFIDENCE_FROZEN_VERSION = "racenote-v055-confidence-frozen-0.1"
CONFIDENCE_MEANING = "HONMEI_WIN_CONFIDENCE"
DEFAULT_POLICY = (
    Path(__file__).resolve().parents[1]
    / "docs" / "racenote" / "research-work" / "results" / "stage_c"
    / "reader_feature_policy_v0_5_candidate.json"
)


def encoded(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def digest_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


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
    result = {
        k: session[k]
        for k in (
            "schema_version", "selection_id", "target_date", "base_main_sha",
            "clean_reader_manifest_sha256", "race_roster", "expected_venues",
            "logic_version", "binding_sha256", "policy_sha256",
        )
    }
    # r2 binds the model Reader projection; r1 sessions predate this field.
    if session.get("reader_projection") is not None:
        result["reader_projection"] = session["reader_projection"]

    if session.get("contract_revision") is not None:
        result["contract_revision"] = session["contract_revision"]
    result["evidence_bundle_sha256"] = session.get("evidence_bundle_sha256")
    result["race_lap_parquet_sha256"] = session.get("race_lap_parquet_sha256")
    return result


def expected_session_id(session: dict[str, Any]) -> str:
    return "V055-" + digest(encoded(session_identity(session)))[:20]


def _validator_reader(normal: dict[str, Any]) -> dict[str, Any]:
    horses = []
    for h in normal["horses"]:
        review = dict((h.get("other_context") or {}).get("racereview") or {})
        review["recommendation"] = h.get("rrdb_v05") or {
            "status": "UNAVAILABLE",
            "contract_version": "rrdb-recommendation-signals-v0.5",
            "signals": [],
        }
        horses.append({"basic": h["identity"], "racereview": review})
    return {"race": normal["race"], "horses": horses}


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
    contract_revision: str | None = CONTRACT_REVISION,
    evidence_bundle: Path | None = None,
    race_lap_parquet: Path | None = None,
) -> dict[str, Any]:
    if root.exists():
        raise FileExistsError(f"v0.5.5 single-day root already exists: {root}")
    if len(base_main_sha) != 40 or any(c not in "0123456789abcdef" for c in base_main_sha):
        raise ValueError("base_main_sha must be a full lowercase commit SHA")
    if contract_revision not in SUPPORTED_CONTRACT_REVISIONS:
        raise ValueError(f"unsupported v0.5.5 contract revision: {contract_revision}")

    handoff, clean_manifest, readers = load_clean(
        prep_root,
        expected_rrdb_contract="rrdb-recommendation-signals-v0.5",
    )
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
    # v0.5.5 reuses v0.5 Reader binding but adds supplemental context.
    from racenote_reader_v050 import validate_policy_binding
    validate_policy_binding(binding, policy)

    session: dict[str, Any] = {
        "schema_version": SESSION_VERSION,
        "selection_id": handoff["selection_id"],
        "target_date": handoff["target_date"],
        "base_main_sha": base_main_sha,
        "logic_version": LOGIC,
        "decision_core_version": "racenote-decision-core-0.5.5",
        "reader_projection": READER_PROJECTION,
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
    if contract_revision is not None:
        session["contract_revision"] = contract_revision

    if race_lap_parquet is None or evidence_bundle is None:
        raise ValueError("v0.5.5 requires both canonical RaceLap Parquet and a KYI evidence bundle")
    supplemental = read_json(evidence_bundle) if evidence_bundle is not None else {}
    if supplemental.get("schema_version") != "racenote-v054-kyi-supplemental-0.1":
        raise ValueError("unsupported v0.5.5 evidence bundle")
    if supplemental.get("rrdb_contract") != "rrdb-recommendation-signals-v0.5":
        raise ValueError("v0.5.5 requires RRDB v0.5 evidence contract")
    if supplemental.get("target_date") != handoff["target_date"] or supplemental.get("source_selection_id") != handoff["selection_id"]:
        raise ValueError("supplemental KYI bundle target does not match sealed forecast prep")
    if (supplemental.get("policy") or {}).get("target_result") is not False or (supplemental.get("policy") or {}).get("target_final_odds") is not False:
        raise ValueError("supplemental KYI bundle has unsafe target-result/market policy")
    bundle_rows = {}
    for item in supplemental.get("races", []):
        key = (str(item["venue"]), int(item["race_no"]))
        if key in bundle_rows:
            raise ValueError(f"duplicate v0.5.5 evidence race: {key}")
        bundle_rows[key] = item
    if set(bundle_rows) != set(readers):
        raise ValueError("supplemental evidence race roster mismatch")
    session["evidence_bundle_sha256"] = (
        digest(encoded(supplemental) + b"\n") if evidence_bundle is not None else None
    )
    session["race_lap_parquet_sha256"] = (
        digest_file(race_lap_parquet) if race_lap_parquet is not None else None
    )
    race_lap_reader = None
    if race_lap_parquet is not None:
        from jrdb_race_lap_reader import RaceLapReader
        race_lap_reader = RaceLapReader.from_parquet(race_lap_parquet)
    session["session_id"] = expected_session_id(session)

    root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{root.name}.build-", dir=root.parent) as temp:
        staging = Path(temp)
        entries = []
        for row in roster:
            source = readers[(row["venue"], row["race_no"])]["reader"]

            race_extra = bundle_rows.get((row["venue"], row["race_no"]), {})
            kyis = {}
            histories = {}
            for item in race_extra.get("horses", []):
                if set(item) - {"horse_no", "kyi", "source_race_keys", "provenance"}:
                    raise ValueError("unapproved supplemental evidence field")
                number = int(item["horse_no"])
                if number in kyis:
                    raise ValueError(f"duplicate KYI evidence for horse {number}")
                if number not in row["horse_nos"]:
                    raise ValueError(f"unknown horse in KYI evidence: {number}")
                kyis[number] = item.get("kyi") or {}
                historical = item.get("source_race_keys")
                if historical is None:
                    historical = [
                        p.get("race_key_raw") for p in kyis[number].get("previous", [])
                        if isinstance(p, dict) and p.get("race_key_raw")
                    ]
                histories[number] = historical
            candidate = transform(
                source, binding, kyi_by_horse=kyis,
                history_race_keys_by_horse=histories,
                target_date=session["target_date"], race_lap_reader=race_lap_reader,
            )
            if any(h["rrdb_v05"].get("status") == "UNAVAILABLE" for h in candidate["normal_view"]["horses"]):
                raise ValueError(
                    f"{row['venue']}{row['race_no']}R: missing canonical RRDB v0.5 enrichment"
                )
            path = staging / "reader" / row["file"]
            write_json(path, candidate["normal_view"])
            projection_meta = (candidate.get("provenance") or {}).get("v055_contract") or {}
            entries.append({
                "venue": row["venue"],
                "race_no": row["race_no"],
                "original_clean_reader_filename": row["file"],
                "original_clean_reader_sha256": original_hashes[row["file"]],
                "source_semantic_sha256": source["source_semantic_sha256"],
                "derived_normal_filename": row["file"],
                "derived_normal_sha256": digest(path.read_bytes()),
                "candidate_version": LOGIC,
                "reader_projection": READER_PROJECTION,
                "full_normal_bytes_before_projection": projection_meta.get("full_normal_bytes_before_projection"),
                "model_reader_bytes": projection_meta.get("model_reader_bytes"),
                "model_reader_reduction_pct": projection_meta.get("model_reader_reduction_pct"),
                "horse_nos": row["horse_nos"],
            })
        manifest = {
            "manifest_version": MANIFEST_VERSION,
            "session_id": session["session_id"],
            "selection_id": session["selection_id"],
            "target_date": session["target_date"],
            "clean_reader_manifest_sha256": clean_sha,
            "logic_version": LOGIC,
            "contract_revision": session.get("contract_revision"),
            "model_input": "lean_normal_view_only",
            "reader_projection": READER_PROJECTION,
            "projection_equivalent_to": "v0.5.4 evidence sources; deterministic lean field projection",
            "entries": entries,
        }

        manifest["evidence_bundle_sha256"] = session["evidence_bundle_sha256"]
        manifest["race_lap_parquet_sha256"] = session["race_lap_parquet_sha256"]
        if evidence_bundle is not None:
            write_json(staging / "input_evidence.json", supplemental)
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
        or session.get("contract_revision") not in SUPPORTED_CONTRACT_REVISIONS
        or (
            session.get("contract_revision") == CONTRACT_REVISION
            and session.get("reader_projection") != READER_PROJECTION
        )
        or session.get("market_blind") is not True
        or session.get("target_market_opened") is not False
        or session.get("result_opened") is not False
        or session.get("session_id") != expected_session_id(session)
    ):
        raise ValueError("v0.5.5 single-day session seal invalid")

    prep_root = (root / session["source_prep_root"]).resolve()
    handoff, clean_manifest, readers = load_clean(
        prep_root,
        expected_rrdb_contract="rrdb-recommendation-signals-v0.5",
    )
    if (
        handoff.get("selection_id") != session["selection_id"]
        or handoff.get("target_date") != session["target_date"]
        or handoff.get("main_sha") != session["base_main_sha"]
        or digest((prep_root / "reader_stripped_manifest.json").read_bytes())
        != session["clean_reader_manifest_sha256"]
    ):
        raise ValueError("forecast_prep changed after v0.5.5 session seal")
    if {item["file"]: item["sha256"] for item in readers.values()} != session["original_clean_reader_sha256"]:
        raise ValueError("forecast_prep Reader hashes changed")


    bundle_path = root / "input_evidence.json"
    if bundle_path.exists():
        if digest(bundle_path.read_bytes()) != session.get("evidence_bundle_sha256"):
            raise ValueError("supplemental evidence snapshot changed after seal")
    elif session.get("evidence_bundle_sha256") is not None:
        raise ValueError("supplemental evidence snapshot missing")
    manifest_path = root / "reader_manifest.json"
    if digest(manifest_path.read_bytes()) != session["reader_manifest_sha256"]:
        raise ValueError("v0.5.5 Reader manifest digest mismatch")
    manifest = read_json(manifest_path)
    if (
        session.get("contract_revision") == CONTRACT_REVISION
        and manifest.get("reader_projection") != READER_PROJECTION
    ):
        raise ValueError("v0.5.5 lean Reader projection mismatch")
    entries = {(x["venue"], int(x["race_no"])): x for x in manifest["entries"]}
    if session.get("contract_revision") == CONTRACT_REVISION:
        if any(x.get("reader_projection") != READER_PROJECTION for x in manifest["entries"]):
            raise ValueError("v0.5.5 Reader entry projection mismatch")
    if roster_from_readers(readers) != session["race_roster"] or set(entries) != set(readers):
        raise ValueError("v0.5.5 single-day race roster mismatch")
    for key, entry in entries.items():
        path = root / "reader" / entry["derived_normal_filename"]
        if digest(path.read_bytes()) != entry["derived_normal_sha256"]:
            raise ValueError(f"v0.5.5 Reader changed: {key}")
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
        validate_core(
            core,
            _validator_reader(normal),
            contract_revision=session.get("contract_revision"),
        )

    validate_prose_collection(decisions)

    payload = {
        "schema_version": AUTHORED_VERSION,
        "session_id": session["session_id"],
        "selection_id": session["selection_id"],
        "target_date": session["target_date"],
        "logic_version": LOGIC,
        "contract_revision": session.get("contract_revision"),
        "reader_projection": session.get("reader_projection"),
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
            or item.get("contract_revision") != session.get("contract_revision")
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
            validate_core(
                core,
                _validator_reader(normal),
                contract_revision=session.get("contract_revision"),
            )
        payloads.append(item)
    return payloads


def build_freeze(root: Path) -> dict[str, Any]:
    session, readers, entries = load_session(root)
    authored = _load_authored(root, session, entries)
    records = []
    all_cores = [core for payload in authored for core in payload["decisions"]]
    validate_prose_collection(all_cores)
    quality_report = None
    if session.get("contract_revision") == CONTRACT_REVISION:
        quality_report = inspect_authoring_quality(all_cores)
        write_json(root / "authoring_quality_report.json", quality_report)
        if quality_report["status"] != "PASS":
            raise ValueError(
                "pre-Freeze authoring quality gate FAIL: "
                + "; ".join(quality_report["violations"][:8])
            )
    for payload in authored:
        for core in payload["decisions"]:
            key = (payload["venue"], int(core["race_no"]))
            entry = entries[key]
            records.append({
                "session_id": session["session_id"],
                "selection_id": session["selection_id"],
                "target_date": session["target_date"],
                "logic_version": LOGIC,
                "contract_revision": session.get("contract_revision"),
                "reader_projection": session.get("reader_projection"),
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
        "status": (
            "PREDICTION_FROZEN_CLEAN_BLIND"
            if session.get("contract_revision") == CONTRACT_REVISION
            else "FROZEN_CLEAN_BLIND"
        ),
        "validator_status": "PASS",
        "validator": "racenote_decision_core_v055.validate_core + single-day session integrity",
        "session_id": session["session_id"],
        "selection_id": session["selection_id"],
        "target_date": session["target_date"],
        "logic_version": LOGIC,
        "contract_revision": session.get("contract_revision"),
        "reader_projection": session.get("reader_projection"),
        "reader_manifest_sha256": session["reader_manifest_sha256"],
        "race_roster": session["race_roster"],
        "expected_venues": session["expected_venues"],
        "record_count": len(records),
        "market_blind": True,
        "target_market_opened": False,
        "result_opened": False,
        "confidence_frozen": session.get("contract_revision") != CONTRACT_REVISION,
        "confidence_meaning": CONFIDENCE_MEANING,
        **({"confidence_pending": True} if session.get("contract_revision") == CONTRACT_REVISION else {}),
        "records_sha256": digest(encoded(records) + b"\n"),
        **({"authoring_quality_report_sha256": digest(encoded(quality_report) + b"\n")}
           if quality_report is not None else {}),
    }
    frozen = root / "frozen"
    if frozen.exists():
        raise FileExistsError(f"immutable single-day Freeze already exists: {frozen}")
    with tempfile.TemporaryDirectory(prefix=".v055.frozen-", dir=root) as temp:
        staging = Path(temp)
        if quality_report is not None:
            write_json(staging / "authoring_quality_report.json", quality_report)
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
    is_r4 = session.get("contract_revision") == CONTRACT_REVISION
    expected_status = "PREDICTION_FROZEN_CLEAN_BLIND" if is_r4 else "FROZEN_CLEAN_BLIND"
    expected_confidence_frozen = False if is_r4 else True
    if (
        handoff.get("schema_version") != FROZEN_VERSION
        or handoff.get("status") != expected_status
        or handoff.get("validator_status") != "PASS"
        or handoff.get("session_id") != session["session_id"]
        or handoff.get("selection_id") != session["selection_id"]
        or handoff.get("target_date") != session["target_date"]
        or handoff.get("logic_version") != LOGIC
        or handoff.get("contract_revision") != session.get("contract_revision")
        or handoff.get("reader_projection") != session.get("reader_projection")
        or handoff.get("reader_manifest_sha256") != session["reader_manifest_sha256"]
        or handoff.get("race_roster") != session["race_roster"]
        or handoff.get("expected_venues") != session["expected_venues"]
        or handoff.get("record_count") != len(records)
        or handoff.get("market_blind") is not True
        or handoff.get("target_market_opened") is not False
        or handoff.get("result_opened") is not False
        or handoff.get("confidence_frozen") is not expected_confidence_frozen
        or handoff.get("confidence_meaning") != CONFIDENCE_MEANING
        or (is_r4 and handoff.get("confidence_pending") is not True)
        or handoff.get("records_sha256") != digest(raw)
    ):
        raise ValueError("single-day Freeze seal invalid")
    if "authoring_quality_report_sha256" in handoff:
        quality_path = root / "frozen" / "authoring_quality_report.json"
        if (not quality_path.is_file()
            or digest(quality_path.read_bytes()) != handoff["authoring_quality_report_sha256"]
            or read_json(quality_path).get("status") != "PASS"):
            raise ValueError("frozen authoring quality report seal invalid")
    for row in records:
        key = (row["venue"], int(row["race_no"]))
        entry = entries[key]
        normal = read_json(root / "reader" / entry["derived_normal_filename"])
        if (
            row.get("session_id") != session["session_id"]
            or row.get("selection_id") != session["selection_id"]
            or row.get("target_date") != session["target_date"]
            or row.get("logic_version") != LOGIC
            or row.get("contract_revision") != session.get("contract_revision")
            or row.get("reader_projection") != session.get("reader_projection")
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
        validate_core(
            row["decision_core"],
            _validator_reader(normal),
            contract_revision=session.get("contract_revision"),
        )
    return handoff



def _prediction_records(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    handoff = verify_freeze(root)
    if handoff.get("status") != "PREDICTION_FROZEN_CLEAN_BLIND":
        raise ValueError("separate confidence review is available only for r4 prediction Freeze")
    raw = (root / "frozen" / "records.json").read_bytes()
    records = json.loads(raw)
    return handoff, records, digest(raw)


def save_confidence_review(root: Path, confidence_path: Path) -> dict[str, Any]:
    session, _, _ = load_session(root)
    if session.get("contract_revision") != CONTRACT_REVISION:
        raise ValueError("separate confidence review is only valid for current r4 sessions")
    if (root / "confidence_frozen").exists():
        raise FileExistsError("confidence is already frozen")
    prediction_handoff, prediction_records, prediction_sha = _prediction_records(root)
    incoming = (root / "incoming").resolve()
    path = confidence_path.resolve()
    if path.parent != incoming or path.suffix != ".json":
        raise ValueError("confidence input must be single-day incoming/<name>.json")
    items = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(items, list):
        raise ValueError("confidence review input must be a JSON array")

    expected = {(x["venue"], int(x["race_no"])): x for x in prediction_records}
    seen = set()
    reviewed = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {"venue", "race_no", "honmei", "confidence", "reason"}:
            raise ValueError("confidence review fields mismatch")
        key = (str(item["venue"]), int(item["race_no"]))
        if key not in expected or key in seen:
            raise ValueError(f"invalid or duplicate confidence race: {key}")
        seen.add(key)
        honmei = int(item["honmei"])
        frozen_honmei = int(expected[key]["decision_core"]["marks"][0])
        if honmei != frozen_honmei:
            raise ValueError(f"{key}: confidence honmei must equal frozen ◎ {frozen_honmei}")
        grade = str(item["confidence"])
        if grade not in {"A", "B", "C"}:
            raise ValueError(f"{key}: confidence must be A/B/C")
        reason = str(item["reason"] or "").strip()
        if len(reason) < 12:
            raise ValueError(f"{key}: confidence reason too short")
        reviewed.append({
            "venue": key[0],
            "race_no": key[1],
            "honmei": honmei,
            "confidence": grade,
            "reason": reason,
        })
    if seen != set(expected):
        raise ValueError("confidence review must cover every frozen prediction race")
    reviewed.sort(key=lambda x: (x["venue"], x["race_no"]))
    payload = {
        "schema_version": CONFIDENCE_REVIEW_VERSION,
        "status": "CONFIDENCE_REVIEW_DRAFT",
        "session_id": session["session_id"],
        "selection_id": session["selection_id"],
        "target_date": session["target_date"],
        "logic_version": LOGIC,
        "contract_revision": CONTRACT_REVISION,
        "confidence_meaning": CONFIDENCE_MEANING,
        "prediction_records_sha256": prediction_sha,
        "result_opened": False,
        "target_market_opened": False,
        "records": reviewed,
    }
    # Draft is intentionally replaceable before confidence Freeze.
    write_json(root / "confidence_review.json", payload)
    return payload


def freeze_confidence(root: Path) -> dict[str, Any]:
    session, _, _ = load_session(root)
    if session.get("contract_revision") != CONTRACT_REVISION:
        raise ValueError("separate confidence Freeze is only valid for current r4 sessions")
    if (root / "confidence_frozen").exists():
        raise FileExistsError("immutable confidence Freeze already exists")
    prediction_handoff, prediction_records, prediction_sha = _prediction_records(root)
    review = read_json(root / "confidence_review.json")
    if (
        review.get("schema_version") != CONFIDENCE_REVIEW_VERSION
        or review.get("status") != "CONFIDENCE_REVIEW_DRAFT"
        or review.get("session_id") != session["session_id"]
        or review.get("selection_id") != session["selection_id"]
        or review.get("target_date") != session["target_date"]
        or review.get("logic_version") != LOGIC
        or review.get("contract_revision") != CONTRACT_REVISION
        or review.get("confidence_meaning") != CONFIDENCE_MEANING
        or review.get("prediction_records_sha256") != prediction_sha
        or review.get("result_opened") is not False
        or review.get("target_market_opened") is not False
    ):
        raise ValueError("confidence review binding invalid")
    expected = {
        (x["venue"], int(x["race_no"])): int(x["decision_core"]["marks"][0])
        for x in prediction_records
    }
    records = review.get("records")
    if not isinstance(records, list) or len(records) != len(expected):
        raise ValueError("confidence review race count mismatch")
    seen = set()
    for item in records:
        key = (str(item.get("venue")), int(item.get("race_no")))
        if key not in expected or key in seen or int(item.get("honmei")) != expected[key]:
            raise ValueError(f"confidence review binding mismatch: {key}")
        if item.get("confidence") not in {"A", "B", "C"} or len(str(item.get("reason") or "").strip()) < 12:
            raise ValueError(f"invalid confidence review: {key}")
        seen.add(key)
    if seen != set(expected):
        raise ValueError("confidence review coverage mismatch")

    frozen_records = [dict(x) for x in records]
    handoff = {
        "schema_version": CONFIDENCE_FROZEN_VERSION,
        "status": "CONFIDENCE_FROZEN_CLEAN_BLIND",
        "session_id": session["session_id"],
        "selection_id": session["selection_id"],
        "target_date": session["target_date"],
        "logic_version": LOGIC,
        "contract_revision": CONTRACT_REVISION,
        "confidence_meaning": CONFIDENCE_MEANING,
        "confidence_frozen": True,
        "prediction_freeze_status": prediction_handoff["status"],
        "prediction_records_sha256": prediction_sha,
        "record_count": len(frozen_records),
        "confidence_records_sha256": digest(encoded(frozen_records) + b"\n"),
        "market_blind": True,
        "target_market_opened": False,
        "result_opened": False,
    }
    frozen = root / "confidence_frozen"
    with tempfile.TemporaryDirectory(prefix=".v055.confidence-", dir=root) as temp:
        staging = Path(temp)
        write_json(staging / "records.json", frozen_records)
        write_json(staging / "day_handoff.json", handoff)
        staging.rename(frozen)
    return handoff


def verify_confidence_freeze(root: Path) -> dict[str, Any]:
    session, _, _ = load_session(root)
    if session.get("contract_revision") != CONTRACT_REVISION:
        return verify_freeze(root)
    _, prediction_records, prediction_sha = _prediction_records(root)
    handoff = read_json(root / "confidence_frozen" / "day_handoff.json")
    raw = (root / "confidence_frozen" / "records.json").read_bytes()
    records = json.loads(raw)
    expected = {
        (x["venue"], int(x["race_no"])): int(x["decision_core"]["marks"][0])
        for x in prediction_records
    }
    if (
        handoff.get("schema_version") != CONFIDENCE_FROZEN_VERSION
        or handoff.get("status") != "CONFIDENCE_FROZEN_CLEAN_BLIND"
        or handoff.get("session_id") != session["session_id"]
        or handoff.get("selection_id") != session["selection_id"]
        or handoff.get("target_date") != session["target_date"]
        or handoff.get("logic_version") != LOGIC
        or handoff.get("contract_revision") != CONTRACT_REVISION
        or handoff.get("confidence_meaning") != CONFIDENCE_MEANING
        or handoff.get("confidence_frozen") is not True
        or handoff.get("prediction_records_sha256") != prediction_sha
        or handoff.get("record_count") != len(records)
        or handoff.get("confidence_records_sha256") != digest(raw)
        or handoff.get("market_blind") is not True
        or handoff.get("target_market_opened") is not False
        or handoff.get("result_opened") is not False
    ):
        raise ValueError("confidence Freeze seal invalid")
    seen = set()
    for item in records:
        key = (str(item.get("venue")), int(item.get("race_no")))
        if (
            key not in expected
            or key in seen
            or int(item.get("honmei")) != expected[key]
            or item.get("confidence") not in {"A", "B", "C"}
            or len(str(item.get("reason") or "").strip()) < 12
        ):
            raise ValueError(f"confidence frozen record invalid: {key}")
        seen.add(key)
    if seen != set(expected):
        raise ValueError("confidence frozen coverage mismatch")
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
    p.add_argument("--evidence-bundle", type=Path)
    p.add_argument("--race-lap-parquet", type=Path)

    p = sub.add_parser("save")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--decisions", type=Path, required=True)

    p = sub.add_parser("freeze")
    p.add_argument("--root", type=Path, required=True)

    p = sub.add_parser("verify-prediction")
    p.add_argument("--root", type=Path, required=True)

    p = sub.add_parser("save-confidence")
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--confidence", type=Path, required=True)

    p = sub.add_parser("freeze-confidence")
    p.add_argument("--root", type=Path, required=True)

    p = sub.add_parser("verify")
    p.add_argument("--root", type=Path, required=True)

    args = ap.parse_args()
    if args.action == "init":
        result = init_session(args.prep_root, args.root, args.base_main_sha, args.binding, args.policy, evidence_bundle=args.evidence_bundle, race_lap_parquet=args.race_lap_parquet)
        summary = {"status": "SESSION_SEALED", "session_id": result["session_id"], "race_count": len(result["race_roster"])}
    elif args.action == "save":
        result = save_venue(args.root, args.decisions)
        summary = {"status": "SAVED", "venue": result["venue"], "race_count": len(result["race_nos"])}
    elif args.action == "freeze":
        result = build_freeze(args.root)
        summary = {"status": result["status"], "record_count": result["record_count"]}
    elif args.action == "verify-prediction":
        result = verify_freeze(args.root)
        summary = {"status": "PREDICTION_VERIFIED", "record_count": result["record_count"]}
    elif args.action == "save-confidence":
        result = save_confidence_review(args.root, args.confidence)
        summary = {"status": result["status"], "record_count": len(result["records"])}
    elif args.action == "freeze-confidence":
        result = freeze_confidence(args.root)
        summary = {"status": result["status"], "record_count": result["record_count"]}
    else:
        result = verify_confidence_freeze(args.root)
        summary = {"status": "VERIFIED", "record_count": result["record_count"]}
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
