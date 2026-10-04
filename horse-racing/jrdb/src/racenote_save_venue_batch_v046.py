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
        race = reader.get("race") or {}
        key = (str(race.get("venue")), int(race.get("race_no")))
        readers[key] = {
            "reader": reader,
            "file": path.name,
            "sha256": expected[path.name],
        }
    return handoff, manifest, readers


def validate_core(core: dict, reader: dict) -> None:
    race = reader["race"]
    venue = str(race["venue"])
    race_no = int(race["race_no"])
    if str(core.get("venue")) != venue or int(core.get("race_no")) != race_no:
        raise ValueError(f"{venue}{race_no}R: Decision Core identity mismatch")

    horses = {int(h["basic"]["horse_no"]): h for h in reader.get("horses", [])}
    roster = set(horses)
    marks = core.get("marks")
    if not isinstance(marks, list) or len(marks) != 5:
        raise ValueError(f"{venue}{race_no}R: exactly five marks required")
    marks = [int(x) for x in marks]
    if len(set(marks)) != 5 or not set(marks) <= roster:
        raise ValueError(f"{venue}{race_no}R: marks must be five unique Reader horses")

    if len(str(core.get("race_model") or "").strip()) < 30:
        raise ValueError(f"{venue}{race_no}R: race_model too short")

    mainline = core.get("mainline_cases")
    if not isinstance(mainline, list) or len(mainline) != 4:
        raise ValueError(f"{venue}{race_no}R: four mainline cases required")
    mainline_nos = []
    for item in mainline:
        n = int(item.get("horse_no"))
        if n not in roster or len(str(item.get("case") or "").strip()) < 8:
            raise ValueError(f"{venue}{race_no}R: invalid mainline case")
        mainline_nos.append(n)
    expected_mainline = {marks[0], marks[1], marks[3], marks[4]}
    if set(mainline_nos) != expected_mainline or len(set(mainline_nos)) != 4:
        raise ValueError(f"{venue}{race_no}R: mainline cases must match ◎ ○ △1 △2")

    single = core.get("single_shot_case") or {}
    if int(single.get("horse_no")) != marks[2]:
        raise ValueError(f"{venue}{race_no}R: single-shot case must match ▲")
    if len(str(single.get("case") or "").strip()) < 8:
        raise ValueError(f"{venue}{race_no}R: single-shot case too short")

    boundary = core.get("boundary_review")
    if not isinstance(boundary, dict):
        raise ValueError(f"{venue}{race_no}R: boundary_review required")
    alt = boundary.get("alternative_horse_no")
    if alt is not None:
        alt = int(alt)
        if alt not in roster or alt in marks:
            raise ValueError(f"{venue}{race_no}R: boundary alternative must be an excluded Reader horse")
    if len(str(boundary.get("reason") or "").strip()) < 8:
        raise ValueError(f"{venue}{race_no}R: boundary reason too short")

    refs = core.get("rrdb_refs")
    if not isinstance(refs, list):
        raise ValueError(f"{venue}{race_no}R: rrdb_refs must be array")
    seen = set()
    for ref in refs:
        n = int(ref.get("horse_no"))
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
    entries = []
    for path in sorted(output_root.glob("*.json")):
        if path.name == "batch_manifest.json":
            continue
        raw = path.read_bytes()
        value = json.loads(raw)
        venue = str(value["venue"])
        rows = value["decisions"]
        entries.append({
            "venue": venue,
            "file": path.name,
            "sha256": digest(raw),
            "race_nos": [int(x["race_no"]) for x in rows],
            "race_count": len(rows),
        })

    expected_by_venue = {}
    for venue, race_no in readers:
        expected_by_venue.setdefault(venue, []).append(race_no)
    for venue in expected_by_venue:
        expected_by_venue[venue].sort()

    completed_venues = sorted(x["venue"] for x in entries)
    all_venues = sorted(expected_by_venue)
    remaining = [v for v in all_venues if v not in completed_venues]
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
        "entries": entries,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prep-root", type=Path, required=True)
    ap.add_argument("--decisions", type=Path, required=True,
                    help="JSON array containing one venue's complete Decision Cores")
    ap.add_argument("--output-root", type=Path, required=True)
    args = ap.parse_args()

    handoff, _, readers = load_clean(args.prep_root)
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

    args.output_root.mkdir(parents=True, exist_ok=True)
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
    (args.output_root / "batch_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
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
