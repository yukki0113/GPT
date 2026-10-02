#!/usr/bin/env python3
"""Bind a market-blind, immutable Forecast input from a validated DAY PREP.

Never print raw Reader content. The lossless DAY PREP Reader is not a model input.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

RRDB = "rrdb-recommendation-signals-v0.3"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def contains_market(value: object) -> bool:
    if isinstance(value, dict):
        return "market" in value or any(contains_market(v) for v in value.values())
    if isinstance(value, list):
        return any(contains_market(v) for v in value)
    return False


def bind(prep: Path, output: Path, selection: str, target_date: str, main_sha: str) -> dict:
    if output.exists():
        raise FileExistsError(f"Forecast input already exists: {output}")
    manifest = json.loads((prep / "manifest.json").read_text(encoding="utf-8"))
    validation = json.loads((prep / "validation_report.json").read_text(encoding="utf-8"))
    assert manifest.get("status") == validation.get("status") == "PASS"
    assert manifest.get("target_date") == target_date
    assert validation.get("firewall", {}).get("target_result_exposed") is False
    assert manifest.get("sources", {}).get("rrdb_recommendation", {}).get("contract_version") == RRDB
    assert manifest.get("sources", {}).get("rrdb_recommendation", {}).get("grade_status") == "DISABLED"
    expected = int(manifest["counts"]["races_built"])
    assert expected == int(manifest["counts"]["reader_views"]) > 0

    raw_files = sorted((prep / "reader").glob("*.json"))
    assert len(raw_files) == expected
    files = {}
    removed = 0
    seen = set()
    for path in raw_files:
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw.get("race", {}).get("date") == target_date
        key = (raw["race"]["venue"], int(raw["race"]["race_no"]))
        assert key not in seen
        seen.add(key)
        reader = copy.deepcopy(raw)
        if "market" in reader["race"]:
            del reader["race"]["market"]
            removed += 1
        for horse in reader.get("horses", []):
            if "market" in horse:
                del horse["market"]
                removed += 1
        assert not contains_market(reader), f"Unstripped market field in {path.name}"
        data = (json.dumps(reader, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        files[path.name] = (data, digest(data))

    stripped_manifest = {
        "selection_id": selection, "target_date": target_date,
        "race_count": expected, "reader_sha256": {name: sha for name, (_, sha) in files.items()},
        "target_market_objects_removed": removed,
        "market_blind": True, "result_opened": False,
    }
    manifest_bytes = (json.dumps(stripped_manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    handoff = {
        "selection_id": selection, "target_date": target_date, "race_count": expected,
        "main_sha": main_sha, "rrdb_contract": RRDB,
        "market_blind": True, "stripped_at_input_bind": True,
        "result_opened": False, "target_market_opened": False,
        "reader_stripped_manifest_sha256": digest(manifest_bytes),
    }
    (output / "reader").mkdir(parents=True)
    for name, (data, _) in files.items():
        (output / "reader" / name).write_bytes(data)
    (output / "reader_stripped_manifest.json").write_bytes(manifest_bytes)
    (output / "day_prep_handoff.json").write_text(
        json.dumps(handoff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return handoff


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--day-prep-root", type=Path, required=True)
    ap.add_argument("--output-root", type=Path, required=True)
    ap.add_argument("--selection-id", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--main-sha", required=True)
    args = ap.parse_args()
    handoff = bind(args.day_prep_root, args.output_root, args.selection_id, args.date, args.main_sha)
    print(json.dumps(handoff, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
