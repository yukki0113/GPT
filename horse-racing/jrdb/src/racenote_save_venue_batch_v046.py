#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Save one immutable venue batch of RaceNote v0.4.6 Decision Cores.

Normal operation calls this once per venue, not once per race. The module
validates model-authored decisions against the clean Reader roster and writes
one immutable batch plus a small recovery manifest. It never selects horses or
writes prediction prose.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from racenote_freeze_prepared_forecast import contains_key

LOGIC = "RaceNote-Human-Context-Reader-0.4.6-candidate"
VERSION = "racenote-save-venue-batch-0.4.6"
RRDB = "rrdb-recommendation-signals-v0.3"
ROLES = {
    "UPGRADE_RECENT_FORM",
    "DOWNGRADE_APPARENT_FORM",
    "SUPPORT_REPEATABILITY",
    "SUPPORT_COUNTERARGUMENT",
    "CONTEXT_ONLY",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def load_clean(prep: Path) -> tuple[dict, dict, dict]:
    handoff = json.loads((prep / "day_prep_handoff.json").read_text(encoding="utf-8"))
    raw_manifest = (prep / "reader_stripped_manifest.json").read_bytes()
    manifest = json.loads(raw_manifest)
    if digest(raw_manifest) != handoff.get("reader_stripped_manifest_sha256"):
        raise ValueError("clean Reader manifest digest mismatch")
    if handoff.get("market_blind") is not True or handoff.get("result_opened") is not False:
        raise ValueError("venue batch requires clean market-blind pre-result input")
    if handoff.get("target_market_opened") is not False:
        raise ValueError("target market was opened")
    if manifest.get("market_blind") is not True or manifest.get("result_opened") is not False:
        raise ValueError("clean Reader manifest is not market-blind pre-result")
    if (
        manifest.get("selection_id") != handoff.get("selection_id")
        or manifest.get("target_date") != handoff.get("target_date")
        or manifest.get("race_count") != handoff.get("race_count")
    ):
        raise ValueError("clean Reader manifest identity/count mismatch")
    if handoff.get("rrdb_contract") != RRDB:
        raise ValueError("RRDB contract mismatch")

    readers = {}
    expected = manifest.get("reader_sha256") or {}
    paths = sorted((prep / "reader").glob("*.json"))
    if set(expected) != {p.name for p in paths}:
        raise ValueError("clean Reader file set mismatch")
    for path in paths:
        raw = path.read_bytes()
        if digest(raw) != expected[path.name]:
            raise ValueError(f"Reader digest mismatch: {path.name}")
        reader = json.loads(raw)
        if contains_key(reader, "market"):
            raise ValueError(f"market field in clean Reader: {path.name}")
        race = reader.get("race") or {}
        if race.get("date") != handoff.get("target_date"):
            raise ValueError(f"Reader target date mismatch: {path.name}")
        key = (str(race.get("venue")), int(race.get("race_no")))
        if key in readers:
            raise ValueError(f"duplicate clean Reader race: {key}")
        readers[key] = {
            "reader": reader,
            "file": path.name,
            "sha256": expected[path.name],
        }
    if len(readers) != int(handoff["race_count"]):
        raise ValueError("clean Reader race count mismatch")
    return handoff, manifest, readers


def validate_core(core: dict, reader: dict) -> None:
    race = reader["race"]
    venue = str(race["venue"])
    race_no = int(race["race_no"])
    expected_fields = {
        "venue", "race_no", "race_model", "marks", "mainline_cases",
        "single_shot_case", "boundary_review", "rrdb_refs", "reader_facing_reason",
    }
    if set(core) != expected_fields:
        raise ValueError(f"{venue}{race_no}R: Decision Core fields must match the v0.4.6 schema")
    if not isinstance(core.get("race_no"), int) or isinstance(core.get("race_no"), bool):
        raise ValueError(f"{venue}{race_no}R: race_no must be an integer")
    if str(core.get("venue")) != venue or core["race_no"] != race_no:
        raise ValueError(f"{venue}{race_no}R: Decision Core identity mismatch")

    horses = {int(h["basic"]["horse_no"]): h for h in reader.get("horses", [])}
    roster = set(horses)
    marks = core.get("marks")
    if (
        not isinstance(marks, list)
        or len(marks) != 5
        or any(not isinstance(x, int) or isinstance(x, bool) for x in marks)
    ):
        raise ValueError(f"{venue}{race_no}R: exactly five integer marks required")
    if len(set(marks)) != 5 or not set(marks) <= roster:
        raise ValueError(f"{venue}{race_no}R: marks must be five unique Reader horses")

    if len(str(core.get("race_model") or "").strip()) < 30:
        raise ValueError(f"{venue}{race_no}R: race_model too short")

    mainline = core.get("mainline_cases")
    if not isinstance(mainline, list) or len(mainline) != 4:
        raise ValueError(f"{venue}{race_no}R: four mainline cases required")
    mainline_nos = []
    for item in mainline:
        if not isinstance(item, dict) or set(item) != {"horse_no", "case"}:
            raise ValueError(f"{venue}{race_no}R: mainline case fields must match the v0.4.6 schema")
        if not isinstance(item["horse_no"], int) or isinstance(item["horse_no"], bool):
            raise ValueError(f"{venue}{race_no}R: mainline horse_no must be an integer")
        n = item["horse_no"]
        if n not in roster or len(str(item.get("case") or "").strip()) < 8:
            raise ValueError(f"{venue}{race_no}R: invalid mainline case")
        mainline_nos.append(n)
    expected_mainline = {marks[0], marks[1], marks[3], marks[4]}
    if set(mainline_nos) != expected_mainline or len(set(mainline_nos)) != 4:
        raise ValueError(f"{venue}{race_no}R: mainline cases must match ◎ ○ △1 △2")

    single = core.get("single_shot_case") or {}
    if not isinstance(single, dict) or set(single) != {"horse_no", "case"}:
        raise ValueError(f"{venue}{race_no}R: single-shot fields must match the v0.4.6 schema")
    if not isinstance(single.get("horse_no"), int) or isinstance(single.get("horse_no"), bool):
        raise ValueError(f"{venue}{race_no}R: single-shot horse_no must be an integer")
    if single.get("horse_no") != marks[2]:
        raise ValueError(f"{venue}{race_no}R: single-shot case must match ▲")
    if len(str(single.get("case") or "").strip()) < 8:
        raise ValueError(f"{venue}{race_no}R: single-shot case too short")

    boundary = core.get("boundary_review")
    if not isinstance(boundary, dict) or set(boundary) != {"alternative_horse_no", "reason"}:
        raise ValueError(f"{venue}{race_no}R: boundary_review fields must match the v0.4.6 schema")
    alt = boundary.get("alternative_horse_no")
    if alt is not None:
        if not isinstance(alt, int) or isinstance(alt, bool):
            raise ValueError(f"{venue}{race_no}R: boundary alternative horse_no must be an integer or null")
        if alt not in roster or alt in marks:
            raise ValueError(f"{venue}{race_no}R: boundary alternative must be an excluded Reader horse")
    if len(str(boundary.get("reason") or "").strip()) < 8:
        raise ValueError(f"{venue}{race_no}R: boundary reason too short")

    refs = core.get("rrdb_refs")
    if not isinstance(refs, list):
        raise ValueError(f"{venue}{race_no}R: rrdb_refs must be array")
    seen = set()
    for ref in refs:
        if not isinstance(ref, dict) or set(ref) != {"horse_no", "decision_role"}:
            raise ValueError(f"{venue}{race_no}R: RRDB ref fields must match the v0.4.6 schema")
        if not isinstance(ref.get("horse_no"), int) or isinstance(ref.get("horse_no"), bool):
            raise ValueError(f"{venue}{race_no}R: RRDB horse_no must be an integer")
        n = ref["horse_no"]
        if n not in roster:
            raise ValueError(f"{venue}{race_no}R: RRDB ref horse absent")
        if n in seen:
            raise ValueError(f"{venue}{race_no}R: duplicate RRDB ref")
        seen.add(n)
        if ref.get("decision_role") not in ROLES:
            raise ValueError(f"{venue}{race_no}R: invalid RRDB decision role")
        recommendation = (horses[n].get("racereview") or {}).get("recommendation") or {}
        if recommendation.get("contract_version") != RRDB:
            raise ValueError(f"{venue}{race_no}R: cited RRDB horse lacks v0.3 evidence")

    prose = str(core.get("reader_facing_reason") or "").strip()
    if len(prose) < 45 or "\n" in prose:
        raise ValueError(f"{venue}{race_no}R: reader-facing reason must be one substantial paragraph")


def manifest_for(output_root: Path, handoff: dict, readers: dict) -> dict:
    expected_by_venue = {}
    for venue, race_no in readers:
        expected_by_venue.setdefault(venue, []).append(race_no)
    for venue in expected_by_venue:
        expected_by_venue[venue].sort()

    entries = []
    seen_venues = set()
    paths = sorted(
        p for p in output_root.glob("*.json") if p.name != "batch_manifest.json"
    )
    expected_files = {f"{venue}.json" for venue in expected_by_venue}
    actual_files = {p.name for p in paths}
    if not actual_files <= expected_files:
        raise ValueError(f"unexpected venue batch files: {sorted(actual_files - expected_files)}")

    for path in paths:
        raw = path.read_bytes()
        payload = json.loads(raw)
        venue = str(payload.get("venue") or "")
        if venue not in expected_by_venue or path.name != f"{venue}.json":
            raise ValueError(f"invalid venue batch identity: {path.name}")
        if venue in seen_venues:
            raise ValueError(f"duplicate venue batch: {venue}")
        seen_venues.add(venue)
        if payload.get("batch_version") != VERSION or payload.get("logic_version") != LOGIC:
            raise ValueError(f"venue batch version mismatch: {path.name}")
        if payload.get("selection_id") != handoff.get("selection_id"):
            raise ValueError(f"venue batch selection mismatch: {path.name}")
        if payload.get("target_date") != handoff.get("target_date"):
            raise ValueError(f"venue batch target date mismatch: {path.name}")

        rows = payload.get("decisions")
        hashes = payload.get("decision_core_sha256")
        if not isinstance(rows, list) or not isinstance(hashes, list) or len(rows) != len(hashes):
            raise ValueError(f"venue batch decisions/hash mismatch: {path.name}")
        race_nos = [int(x.get("race_no")) for x in rows]
        if sorted(race_nos) != expected_by_venue[venue] or len(set(race_nos)) != len(race_nos):
            raise ValueError(f"venue batch must cover the complete venue card: {path.name}")
        for core, expected_hash in zip(rows, hashes):
            if str(core.get("venue")) != venue or digest(canonical(core)) != expected_hash:
                raise ValueError(f"venue batch Decision Core identity/hash mismatch: {path.name}")
            validate_core(core, readers[(venue, int(core["race_no"]))]["reader"])

        entries.append({
            "venue": venue,
            "file": path.name,
            "sha256": digest(raw),
            "race_nos": race_nos,
            "race_count": len(rows),
        })

    completed_venues = sorted(seen_venues)
    all_venues = sorted(expected_by_venue)
    remaining = [v for v in all_venues if v not in seen_venues]
    status = "COMPLETE_READY_TO_BIND" if not remaining else "IN_PROGRESS_BATCHED"

    return {
        "batch_version": VERSION,
        "logic_version": LOGIC,
        "selection_id": handoff["selection_id"],
        "target_date": handoff["target_date"],
        "clean_reader_manifest_sha256": handoff["reader_stripped_manifest_sha256"],
        "expected_venues": all_venues,
        "expected_races_by_venue": expected_by_venue,
        "completed_venues": completed_venues,
        "remaining_venues": remaining,
        "status": status,
        "entries": sorted(entries, key=lambda x: x["venue"]),
    }


def write_manifest(output_root: Path, manifest: dict) -> None:
    path = output_root / "batch_manifest.json"
    temporary = output_root / "batch_manifest.json.tmp"
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prep-root", type=Path, required=True)
    ap.add_argument("--decisions", type=Path,
                    help="JSON array containing one venue's complete Decision Cores")
    ap.add_argument("--output-root", type=Path, required=True)
    ap.add_argument(
        "--reconcile-only",
        action="store_true",
        help="Rebuild batch_manifest.json from validated immutable venue files after interruption",
    )
    args = ap.parse_args()

    handoff, _, readers = load_clean(args.prep_root)
    args.output_root.mkdir(parents=True, exist_ok=True)
    if args.reconcile_only:
        manifest = manifest_for(args.output_root, handoff, readers)
        write_manifest(args.output_root, manifest)
        print(json.dumps({
            "status": manifest["status"],
            "reconciled": True,
            "completed_venues": manifest["completed_venues"],
            "remaining_venues": manifest["remaining_venues"],
        }, ensure_ascii=False, indent=2))
        return 0
    if args.decisions is None:
        raise ValueError("--decisions is required unless --reconcile-only is set")
    decisions = json.loads(args.decisions.read_text(encoding="utf-8"))
    if not isinstance(decisions, list) or not decisions:
        raise ValueError("decisions must be a non-empty JSON array")
    venues = {str(x.get("venue")) for x in decisions}
    if len(venues) != 1:
        raise ValueError("one venue batch must contain exactly one venue")
    venue = next(iter(venues))

    expected_keys = sorted(k for k in readers if k[0] == venue)
    got_keys = sorted((str(x.get("venue")), int(x.get("race_no"))) for x in decisions)
    if got_keys != expected_keys:
        raise ValueError(f"{venue}: venue batch must contain the complete venue card: expected={expected_keys}, got={got_keys}")

    for core in decisions:
        key = (venue, int(core["race_no"]))
        validate_core(core, readers[key]["reader"])

    out = args.output_root / f"{venue}.json"
    if out.exists():
        raise FileExistsError(f"immutable venue batch already exists: {out}")

    payload = {
        "batch_version": VERSION,
        "logic_version": LOGIC,
        "selection_id": handoff["selection_id"],
        "target_date": handoff["target_date"],
        "venue": venue,
        "decisions": decisions,
        "decision_core_sha256": [digest(canonical(x)) for x in decisions],
    }
    raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    out.write_bytes(raw)

    manifest = manifest_for(args.output_root, handoff, readers)
    write_manifest(args.output_root, manifest)
    print(json.dumps({
        "status": manifest["status"],
        "saved_venue": venue,
        "completed_venues": manifest["completed_venues"],
        "remaining_venues": manifest["remaining_venues"],
        "batch_file": str(out),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
