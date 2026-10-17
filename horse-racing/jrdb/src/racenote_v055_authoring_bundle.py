#!/usr/bin/env python3
"""Build lossless LLM authoring bundles from a sealed RaceNote v0.5.5 Reader.

This module is deliberately non-predictive:
- no scoring;
- no ranking;
- no candidate filtering;
- no mark/confidence generation.

It only validates the sealed session and groups the complete lean Reader payloads
by venue so an LLM can read 12 races at a time instead of fetching 36 files.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from racenote_v055_single_day import digest, load_session, write_json

VERSION = "racenote-v055-authoring-bundle-0.1"


def build(root: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"immutable authoring bundle already exists: {output}")

    session, _, entries = load_session(root)
    by_venue: dict[str, list[dict[str, Any]]] = {}

    for row in session["race_roster"]:
        key = (str(row["venue"]), int(row["race_no"]))
        entry = entries[key]
        path = root / "reader" / entry["derived_normal_filename"]
        raw = path.read_bytes()
        reader = json.loads(raw)
        by_venue.setdefault(key[0], []).append({
            "venue": key[0],
            "race_no": key[1],
            "reader_filename": entry["derived_normal_filename"],
            "reader_sha256": digest(raw),
            "reader": reader,
        })

    output.mkdir(parents=True)
    files: list[dict[str, Any]] = []
    for venue, races in sorted(by_venue.items()):
        races.sort(key=lambda x: x["race_no"])
        payload = {
            "schema_version": VERSION,
            "status": "READY_FOR_LLM_RACE_BY_RACE_REVIEW",
            "session_id": session["session_id"],
            "selection_id": session["selection_id"],
            "target_date": session["target_date"],
            "venue": venue,
            "race_count": len(races),
            "reader_projection": session.get("reader_projection"),
            "market_blind": True,
            "result_opened": False,
            "target_market_opened": False,
            "prediction_policy": "LLM_RACE_BY_RACE_ONLY",
            "automated_scoring": False,
            "automated_ranking": False,
            "automated_marks": False,
            "reader_semantics": "FULL_SEALED_LEAN_READER_NO_OMISSION",
            "races": races,
        }
        path = output / f"{venue}.json"
        write_json(path, payload)
        files.append({
            "venue": venue,
            "file": path.name,
            "race_count": len(races),
            "sha256": digest(path.read_bytes()),
        })

    manifest = {
        "schema_version": VERSION,
        "status": "READY_FOR_LLM_RACE_BY_RACE_REVIEW",
        "session_id": session["session_id"],
        "selection_id": session["selection_id"],
        "target_date": session["target_date"],
        "race_count": len(session["race_roster"]),
        "expected_venues": session["expected_venues"],
        "reader_manifest_sha256": session["reader_manifest_sha256"],
        "prediction_policy": "LLM_RACE_BY_RACE_ONLY",
        "automated_scoring": False,
        "automated_ranking": False,
        "automated_marks": False,
        "confidence_generation": False,
        "files": files,
    }
    write_json(output / "manifest.json", manifest)
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    output = args.output or (args.root / "authoring_bundle")
    result = build(args.root, output)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
