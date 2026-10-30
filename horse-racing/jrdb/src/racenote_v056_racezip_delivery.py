#!/usr/bin/env python3
"""Read-only RaceNote v056 per-race ZIP delivery from committed clean-blind T1.

This module never predicts or modifies canonical Reader / Freeze records.
"""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

BASE = Path("horse-racing/jrdb/backtests")
CONTRACT = "v056-prediction-confidence-audit-newspaper-v1"

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sid = args.selection_id
    if not re.fullmatch(r"BTDAY-\d{4}", sid):
        raise SystemExit("invalid selection ID")
    selection = json.loads((BASE / sid / "selection.json").read_text(encoding="utf-8"))
    if selection.get("selection_id") != sid or selection.get("n") != 1 or len(selection.get("dates", [])) != 1:
        raise SystemExit("invalid canonical selection")
    target_date = selection["dates"][0]
    target = BASE / sid / target_date.replace("-", "")
    handoff = json.loads((target / "operation_handoff.json").read_text(encoding="utf-8"))
    if not (handoff.get("status") == "READY_FOR_V056_AUTHORING"
            and handoff.get("contract_revision") == CONTRACT
            and handoff.get("market_blind") is True
            and handoff.get("result_opened") is False
            and handoff.get("target_market_opened") is False):
        raise SystemExit("T1 not ready or not CLEAN BLIND")
    bundle = target / "v056" / "authoring_bundle"
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("selection_id") != sid or manifest.get("target_date") != target_date or manifest.get("session_id") != handoff.get("session_id"):
        raise SystemExit("bundle identity mismatch")
    if manifest.get("race_count") != handoff.get("race_count"):
        raise SystemExit("race count mismatch")
    entries = {}
    roster = set()
    for item in manifest["files"]:
        filename = item["file"]
        if filename != item["venue"] + ".json" or "/" in filename or ".." in filename:
            raise SystemExit("invalid bundle filename")
        raw = (bundle / filename).read_bytes()
        if sha(raw) != item["sha256"]:
            raise SystemExit("source SHA mismatch: " + filename)
        venue_data = json.loads(raw)
        if venue_data.get("market_blind") is not True or venue_data.get("result_opened") is not False or venue_data.get("target_market_opened") is not False:
            raise SystemExit("source not clean blind")
        if len(venue_data["races"]) != item["race_count"]:
            raise SystemExit("source race count mismatch")
        meta = {key: value for key, value in venue_data.items() if key != "races"}
        for row in venue_data["races"]:
            key = (row["venue"], int(row["race_no"]))
            if row["venue"] != item["venue"] or key in roster or not 1 <= key[1] <= 12:
                raise SystemExit("duplicate/invalid race")
            roster.add(key)
            payload = {"venue_bundle_metadata": meta, "race": row}
            encoded = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
            if json.loads(encoded)["race"] != row:
                raise SystemExit("roundtrip mismatch")
            entries[f"races/{key[0]}/{key[1]:02d}.json"] = encoded
    if len(roster) != manifest["race_count"]:
        raise SystemExit("incomplete roster")
    index = {
        "schema_version": "racenote-v056-racezip-delivery-0.1",
        "selection_id": sid, "target_date": target_date,
        "session_id": handoff["session_id"], "race_count": len(roster),
        "contract_revision": CONTRACT,
        "market_blind": True, "result_opened": False, "target_market_opened": False,
        "source_bundle_manifest_sha256": sha((bundle / "manifest.json").read_bytes()),
        "entries": [{"path": path, "sha256": sha(entries[path]), "bytes": len(entries[path])} for path in sorted(entries)],
        "note": "Transport only. LLM must review every runner in every race. Existing two-stage Freeze remains canonical."
    }
    entries["index.json"] = (json.dumps(index, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise SystemExit("output already exists")
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name in sorted(entries):
            archive.writestr(name, entries[name])
    with zipfile.ZipFile(args.output) as archive:
        assert set(archive.namelist()) == set(entries)
        for name, raw in entries.items():
            assert archive.read(name) == raw
    print(json.dumps({"status": "PASS", "selection_id": sid, "race_count": len(roster), "zip_bytes": args.output.stat().st_size, "zip_sha256": sha(args.output.read_bytes()), "file_count": len(entries)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
