#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Append-only one-race checkpoint for RaceNote v0.4.5 authoring.

This module validates identities and structural invariants only. It never
selects marks, challengers, verdicts, or prose.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

LOGIC = "RaceNote-Human-Context-Reader-0.4.5-candidate"
VERSION = "racenote-checkpoint-authored-0.4.5"
LABELS = {"CHALLENGER_STRONGER","DELTA2_STRONGER","ROUGHLY_EQUAL","UNCLEAR"}
ROLES = {
    "UPGRADE_RECENT_FORM","DOWNGRADE_APPARENT_FORM","SUPPORT_REPEATABILITY",
    "SUPPORT_COUNTERARGUMENT","CONTEXT_ONLY",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def required(obj: dict, key: str):
    if key not in obj or obj[key] is None:
        raise ValueError(f"model-authored field missing: {key}")
    return obj[key]


def load_reader(prep: Path, venue: str, race_no: int) -> tuple[dict, str, dict]:
    handoff = json.loads((prep / "day_prep_handoff.json").read_text(encoding="utf-8"))
    raw_manifest = (prep / "reader_stripped_manifest.json").read_bytes()
    manifest = json.loads(raw_manifest)
    if digest(raw_manifest) != handoff.get("reader_stripped_manifest_sha256"):
        raise ValueError("clean Reader manifest digest mismatch")
    if handoff.get("market_blind") is not True or handoff.get("result_opened") is not False:
        raise ValueError("checkpoint requires market-blind pre-result Reader")
    for path in sorted((prep / "reader").glob("*.json")):
        raw = path.read_bytes()
        if digest(raw) != (manifest.get("reader_sha256") or {}).get(path.name):
            raise ValueError(f"Reader digest mismatch: {path.name}")
        reader = json.loads(raw)
        race = reader.get("race") or {}
        if str(race.get("venue")) == venue and int(race.get("race_no")) == race_no:
            return reader, path.name, handoff
    raise ValueError(f"clean Reader not found: {venue}{race_no}R")


def verify_chunks(chunks_root: Path, reader: dict, reader_file: str, reader_sha: str, venue: str, race_no: int) -> str:
    top_raw = (chunks_root / "manifest.json").read_bytes()
    top = json.loads(top_raw)
    if top.get("status") != "PASS" or top.get("market_blind") is not True:
        raise ValueError("Reader chunks manifest is not PASS")
    item = next((x for x in top.get("races", []) if x.get("venue") == venue and int(x.get("race_no")) == race_no), None)
    if not item:
        raise ValueError(f"Reader chunks missing race: {venue}{race_no}R")
    race_dir = chunks_root / item["directory"]
    mraw = (race_dir / "manifest.json").read_bytes()
    if digest(mraw) != item.get("manifest_sha256"):
        raise ValueError("race chunk manifest digest mismatch")
    rm = json.loads(mraw)
    if rm.get("source_reader_file") != reader_file or rm.get("source_reader_sha256") != reader_sha:
        raise ValueError("chunk source Reader identity mismatch")
    source_semantic = digest(canonical(reader))
    if rm.get("source_reader_semantic_sha256") != source_semantic or rm.get("reassembled_semantic_sha256") != source_semantic:
        raise ValueError("chunk semantic reconstruction mismatch")
    return digest(top_raw)


def validate_decision(d: dict, reader: dict, venue: str, race_no: int) -> None:
    horses = {int(h["basic"]["horse_no"]): h for h in reader.get("horses", [])}
    horse_nos = set(horses)

    if str(required(d, "venue")) != venue or int(required(d, "race_no")) != race_no:
        raise ValueError("decision identity mismatch")
    if len(str(required(d, "race_model")).strip()) < 30:
        raise ValueError("race_model too short")

    boundary = required(d, "boundary_marks")
    final = required(d, "final_marks")
    for name, marks in (("boundary_marks", boundary), ("final_marks", final)):
        if not isinstance(marks, list) or len(marks) != 5:
            raise ValueError(f"{name} must contain exactly five horse numbers")
        vals = [int(x) for x in marks]
        if len(set(vals)) != 5 or not set(vals) <= horse_nos:
            raise ValueError(f"{name} must be five unique Reader horses")

    mainline = required(d, "mainline_cases")
    if not isinstance(mainline, list) or len(mainline) != 4:
        raise ValueError("four substantive mainline_cases required")
    for item in mainline:
        if int(required(item, "horse_no")) not in horse_nos or not str(required(item, "case")).strip():
            raise ValueError("invalid mainline case")

    single = required(d, "single_shot_case")
    if int(required(single, "horse_no")) not in horse_nos or not str(required(single, "case")).strip():
        raise ValueError("invalid single_shot_case")
    if int(single["horse_no"]) != int(boundary[2]) or int(final[2]) != int(boundary[2]):
        raise ValueError("independent ▲ must remain the third mark through Coverage")

    if len(str(required(d, "mark_reason")).strip()) < 20:
        raise ValueError("mark_reason too short")
    if len(str(required(d, "reader_facing_reason")).strip()) < 45:
        raise ValueError("reader_facing_reason too short")
    if "\n" in d["reader_facing_reason"]:
        raise ValueError("reader_facing_reason must be one paragraph")

    hierarchy = required(d, "hierarchy")
    if not isinstance(required(hierarchy, "changed"), bool):
        raise ValueError("hierarchy.changed must be boolean")
    if hierarchy["changed"] and not str(hierarchy.get("reason") or "").strip():
        raise ValueError("hierarchy change requires reason")

    promotion = required(d, "single_shot_promotion")
    if not isinstance(required(promotion, "promoted"), bool):
        raise ValueError("single_shot_promotion.promoted must be boolean")
    if promotion["promoted"] and not str(promotion.get("reason") or "").strip():
        raise ValueError("single-shot promotion requires reason")

    rr = required(d, "rrdb_evidence")
    if required(rr, "reviewed") is not True or not isinstance(required(rr, "available"), bool):
        raise ValueError("RRDB review fields invalid")
    used = required(rr, "used_in_decision")
    if not isinstance(used, bool):
        raise ValueError("rrdb_evidence.used_in_decision must be boolean")
    refs = required(rr, "horse_refs")
    if not isinstance(refs, list):
        raise ValueError("rrdb_evidence.horse_refs must be array")
    for ref in refs:
        if int(required(ref, "horse_no")) not in horse_nos or required(ref, "decision_role") not in ROLES:
            raise ValueError("invalid RRDB horse reference")
    if used and not refs:
        raise ValueError("used RRDB requires horse_refs")
    if not used and len(str(rr.get("reason_not_used") or "").strip()) < 8:
        raise ValueError("unused RRDB requires reason_not_used")

    cov = required(d, "coverage")
    shortlist = required(cov, "shortlist")
    if not isinstance(shortlist, list) or any(not isinstance(x, int) for x in shortlist) or len(shortlist) != len(set(shortlist)):
        raise ValueError("coverage.shortlist must be unique integer horse numbers")
    if not set(shortlist) <= (horse_nos - set(int(x) for x in boundary)):
        raise ValueError("coverage.shortlist must contain unmarked Reader horses only")
    verdict = required(cov, "verdict")
    if verdict not in {"KEEP","SWAP","NO_ELIGIBLE_CHALLENGER"}:
        raise ValueError("invalid Coverage verdict")
    if len(str(required(cov, "reason")).strip()) < 8:
        raise ValueError("Coverage reason too short")

    challenger = cov.get("challenger")
    comparisons = (cov.get("direct_condition"), cov.get("ability"), cov.get("race_model"))
    if verdict == "NO_ELIGIBLE_CHALLENGER":
        if shortlist or challenger is not None or any(x is not None for x in comparisons):
            raise ValueError("NO_ELIGIBLE requires empty shortlist, null challenger and null comparisons")
    else:
        if challenger is None or int(challenger) not in shortlist:
            raise ValueError(f"{verdict} requires challenger in shortlist")
        if any(x not in LABELS for x in comparisons):
            raise ValueError("Coverage comparisons must use controlled labels")

    b = [int(x) for x in boundary]
    f = [int(x) for x in final]
    if f[:4] != b[:4]:
        raise ValueError("Coverage may modify only the fifth mark")
    if verdict == "SWAP":
        if cov.get("direct_condition") != "CHALLENGER_STRONGER":
            raise ValueError("SWAP requires challenger stronger on direct condition")
        if cov.get("ability") not in {"CHALLENGER_STRONGER","ROUGHLY_EQUAL"}:
            raise ValueError("SWAP requires no material ability gap")
        if cov.get("race_model") not in {"CHALLENGER_STRONGER","ROUGHLY_EQUAL"}:
            raise ValueError("SWAP requires race-model fit at least equal")
        if f[4] != int(challenger) or b[4] in f:
            raise ValueError("SWAP fifth-mark invariant failed")
    else:
        if f != b:
            raise ValueError(f"{verdict} must keep all boundary marks")
        if verdict == "KEEP" and int(challenger) in f:
            raise ValueError("KEEP challenger must remain unmarked")


def write_manifest(output_root: Path, handoff: dict, chunks_manifest_sha: str) -> dict:
    authored = sorted(output_root.glob("*.json"))
    entries = []
    for path in authored:
        if path.name == "checkpoint_manifest.json":
            continue
        raw = path.read_bytes()
        d = json.loads(raw)
        entries.append({
            "venue": d["venue"],
            "race_no": int(d["race_no"]),
            "file": path.name,
            "sha256": digest(raw),
            "decision_core_sha256": digest(canonical(d)),
        })
    expected = int(handoff["race_count"])
    complete = len(entries)
    status = "COMPLETE_READY_TO_FREEZE" if complete == expected else "IN_PROGRESS_CHECKPOINTED"
    manifest = {
        "checkpoint_version": VERSION,
        "logic_version": LOGIC,
        "selection_id": handoff["selection_id"],
        "target_date": handoff["target_date"],
        "clean_reader_manifest_sha256": handoff["reader_stripped_manifest_sha256"],
        "reader_chunks_manifest_sha256": chunks_manifest_sha,
        "expected_race_count": expected,
        "completed_race_count": complete,
        "remaining_race_count": expected - complete,
        "status": status,
        "entries": sorted(entries, key=lambda x: (x["venue"], x["race_no"])),
    }
    data = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    (output_root / "checkpoint_manifest.json").write_bytes(data)
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prep-root", type=Path, required=True)
    ap.add_argument("--chunks-root", type=Path, required=True)
    ap.add_argument("--decision", type=Path, required=True)
    ap.add_argument("--output-root", type=Path, required=True)
    args = ap.parse_args()

    d = json.loads(args.decision.read_text(encoding="utf-8"))
    venue, race_no = str(required(d, "venue")), int(required(d, "race_no"))
    reader, reader_file, handoff = load_reader(args.prep_root, venue, race_no)
    reader_sha = json.loads((args.prep_root / "reader_stripped_manifest.json").read_text(encoding="utf-8"))["reader_sha256"][reader_file]
    chunks_sha = verify_chunks(args.chunks_root, reader, reader_file, reader_sha, venue, race_no)
    validate_decision(d, reader, venue, race_no)

    args.output_root.mkdir(parents=True, exist_ok=True)
    out = args.output_root / f"{venue}{race_no:02d}R.json"
    if out.exists():
        raise FileExistsError(f"checkpoint already exists and is immutable: {out}")
    payload = dict(d)
    payload["checkpoint"] = {
        "version": VERSION,
        "logic_version": LOGIC,
        "source_reader_file": reader_file,
        "source_reader_sha256": reader_sha,
        "source_reader_semantic_sha256": digest(canonical(reader)),
        "reader_chunks_manifest_sha256": chunks_sha,
    }
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    out.write_bytes(data)
    manifest = write_manifest(args.output_root, handoff, chunks_sha)
    print(json.dumps({
        "status": manifest["status"],
        "checkpoint": str(out),
        "completed_race_count": manifest["completed_race_count"],
        "remaining_race_count": manifest["remaining_race_count"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
