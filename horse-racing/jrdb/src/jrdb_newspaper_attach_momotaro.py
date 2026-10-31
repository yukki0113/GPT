#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Attach already-validated public Momotaro member entries to the personal day.

The authoritative matching, source validation and public allowlist projection
are handled by build_momotaro_newspaper_projection.py. This adapter copies
ONLY that validated member namespace and race comments back onto the complete
private newspaper without modifying existing JRDB, Edge or other addons.
"""
from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path

from build_momotaro_newspaper_projection import sha_file, write_json


def _horse_key(bundle, horse):
    race = bundle["race"]
    key = horse["key"]
    return (
        str(race["date"]),
        str(race["venue_code"]).zfill(2),
        int(race["race_no"]),
        int(key["horse_no"]),
        str(horse["basic"]["horse_name"]),
    )


def attach(personal_dir: Path, public_dir: Path) -> dict:
    personal_manifest = json.loads((personal_dir / "manifest.json").read_text(encoding="utf-8"))
    public_manifest = json.loads((public_dir / "manifest.json").read_text(encoding="utf-8"))
    if personal_manifest["date"] != public_manifest["date"]:
        raise ValueError("personal/public date mismatch")
    if len(personal_manifest["races"]) != len(public_manifest["races"]):
        raise ValueError("personal/public race count mismatch")
    expected = json.loads((public_dir / "audit.json").read_text(encoding="utf-8"))
    if expected.get("status") != "PASS":
        raise ValueError("public projection audit not PASS")

    count = Counter()
    for private_entry, public_entry in zip(personal_manifest["races"], public_manifest["races"]):
        if private_entry["path"] != public_entry["path"]:
            raise ValueError("race path mismatch")
        private_path = personal_dir / private_entry["path"]
        public_path = public_dir / public_entry["path"]
        if sha_file(private_path) != private_entry["sha256"]:
            raise ValueError("private source SHA mismatch")
        if sha_file(public_path) != public_entry["sha256"]:
            raise ValueError("public source SHA mismatch")
        private = json.loads(private_path.read_text(encoding="utf-8"))
        public = json.loads(public_path.read_text(encoding="utf-8"))
        priv_horses = private.get("horses") or []
        pub_horses = public.get("horses") or []
        if len(priv_horses) != len(pub_horses):
            raise ValueError("race horse count mismatch")
        public_index = {_horse_key(public, horse): horse for horse in pub_horses}
        if len(public_index) != len(pub_horses):
            raise ValueError("duplicate public horse identity")
        for horse in priv_horses:
            key = _horse_key(private, horse)
            matched = public_index.pop(key, None)
            if matched is None:
                raise ValueError(f"public horse identity missing: {key}")
            member_data = (matched.get("addons") or {}).get("momotaro")
            if member_data:
                if not isinstance(member_data, dict):
                    raise ValueError("invalid public Momotaro member data")
                horse.setdefault("addons", {})["momotaro"] = copy.deepcopy(member_data)
                for member in member_data:
                    count[member] += 1
        if public_index:
            raise ValueError("extra public horse identities")
        public_comments = (public.get("race_notes") or {}).get("momotaro_comments")
        if public_comments:
            private.setdefault("race_notes", {})["momotaro_comments"] = copy.deepcopy(public_comments)
            count["race_comments"] += len(public_comments)

        member_status = (public.get("metadata") or {}).get("source_status", {}).get("momotaro")
        if member_status:
            private.setdefault("metadata", {}).setdefault("source_status", {})["momotaro"] = copy.deepcopy(member_status)
        write_json(private, private_path)
        private_entry["sha256"] = sha_file(private_path)
        private_entry["size_bytes"] = private_path.stat().st_size

    source_status = (public_manifest.get("source_status") or {}).get("momotaro")
    if not source_status or source_status.get("state") != "READY":
        raise ValueError("public Momotaro source not READY")
    personal_manifest.setdefault("source_status", {})["momotaro"] = copy.deepcopy(source_status)
    write_json(personal_manifest, personal_dir / "manifest.json")
    expected_rows = int(((expected.get("momotaro_predictions") or {}).get("merged")) or -1)
    # The projection audit's merged count represents explicitly supplied
    # shared-member rows only. Automatic Kenshow rows are derived from the
    # already-validated private RaceNote/RRDB addons and must not inflate that
    # explicit-row comparison.
    explicit = count["ryota"] + count["oji"]
    # For partial member replacement, the projection may preserve existing
    # validated Ryota/Oji rows in addition to the explicitly supplied rows.
    # The projection builder has already fail-closed validated every supplied
    # row, so require only that the public projection contains at least that
    # many explicit shared-member rows.
    if expected_rows > explicit:
        raise ValueError(f"member count mismatch: projected={expected_rows}, personal={explicit}")
    return {"status": "PASS", "date":personal_manifest["date"], "revision":personal_manifest["revision"],
            "explicit_rows":explicit, "ryota":count["ryota"], "oji":count["oji"],
            "kenshow":count["kenshow"], "race_comments":count["race_comments"],
            "personal_manifest_sha256":sha_file(personal_dir / "manifest.json")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--personal-dir", required=True, type=Path)
    parser.add_argument("--public-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(attach(args.personal_dir, args.public_dir), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
