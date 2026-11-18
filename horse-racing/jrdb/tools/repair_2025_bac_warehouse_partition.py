#!/usr/bin/env python3
"""Strict single-partition BAC repair using only JRDB official sources and shared Warehouse builder.

Does not publish to Drive or modify existing Warehouse CURRENT.
Only run with immutable annual and 2025-12-13/14 daily source artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "horse-racing/jrdb/src"))
from jrdb_raw import Parser, read_fixed_records
from build_jrdb_normalized_warehouse import ArchiveSpec, build_generation

EXPECTED = {
    "annual": "aeab5d807c12640b908152eb24249c872b4aaafcfc7e97baaafda440994c5491",
    "BAC251213.zip": "f159c63f89889bd4a1151e63584055ba43306806f3383da3dd72de492cca41ff",
    "BAC251214.zip": "3610a3d09161d9da57a2c50916ead3c337195fe1caa66e1cb15e0edd4afea160",
}

def ensure(ok, msg):
    if not ok:
        raise ValueError(msg)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def member_keys(blob):
    class ZF:
        def read(self, name):
            return blob
    rows = read_fixed_records(ZF(), "BAC", "BAC")
    ensure(rows, "missing or invalid BAC records")
    keys = [Parser().bac(row)["race_key_raw"] for row in rows]
    ensure(len(keys) == len(set(keys)), "BAC daily duplicated race key")
    return set(keys)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--annual", type=Path, required=True)
    p.add_argument("--daily13", type=Path, required=True)
    p.add_argument("--daily14", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    p.add_argument("--source-git-commit", required=True)
    p.add_argument("--generation-id", required=True)
    args = p.parse_args()
    original = args.annual.read_bytes()
    ensure(sha(original) == EXPECTED["annual"], "annual BAC has changed; do not rebuild from a different original")
    overrides = {}
    for day, path in [("BAC251213",args.daily13),("BAC251214",args.daily14)]:
        zipbytes = path.read_bytes()
        ensure(sha(zipbytes) == EXPECTED[path.name], f"daily source SHA changed: {path.name}")
        with zipfile.ZipFile(path) as zf:
            ensure(zf.testzip() is None, "corrupt source daily BAC")
            names = zf.namelist()
            ensure(names == [day+".txt"], f"unexpected source members: {names}")
            overrides[day+".txt"] = zf.read(names[0])
            ensure(len(member_keys(overrides[day+".txt"])) == 36, "daily must have 36 races")
    out = args.output_root
    out.mkdir(parents=True, exist_ok=False)
    candidate = out / "BAC_2025_REPAIRED.zip"
    with zipfile.ZipFile(args.annual) as orig:
        ensure(orig.testzip() is None, "corrupt original")
        srcnames = orig.namelist()
        ensure(len(srcnames) == 109 and set(overrides).issubset(srcnames), "unexpected annual member inventory")
        original_keys = set()
        for member in srcnames:
            original_keys |= member_keys(orig.read(member))
        changed_old = {n:orig.read(n) for n in overrides}
        ensure(all(member_keys(b) <= member_keys(overrides[n]) for n,b in changed_old.items()),"old races lost")
        with zipfile.ZipFile(candidate, mode="w") as rebuilt:
            for info in orig.infolist():
                body = overrides.get(info.filename)
                if body is None:
                    body = orig.read(info.filename)
                rebuilt.writestr(info, body)
    with zipfile.ZipFile(candidate) as repaired:
        ensure(repaired.testzip() is None, "repaired archive corrupt")
        keys = set()
        rows = 0
        for name in repaired.namelist():
            new = member_keys(repaired.read(name))
            ensure(not keys.intersection(new), "repaired annual duplicate race key")
            keys |= new
            rows += len(new)
        ensure(rows==3455 and len(keys)==3455, f"unexpected repaired BAC count: {rows}")
        ensure(len(keys-original_keys)==53, "expected exactly 53 newly recovered race keys")
    built = build_generation(
        [ArchiveSpec(family="BAC",year=2025,path=candidate)],
        output_root=out/"warehouse",
        generation_id=args.generation_id,
        source_git_commit=args.source_git_commit
    )
    entries=built["manifest"]["assets"]
    ensure(len(entries)==1 and entries[0]["family"]=="bac","unexpected outputs")
    asset=entries[0]
    ensure(asset["row_count"]==3455,"normalized row count mismatch")
    ensure(asset["source_record_count"]==3455,"normalized source count mismatch")
    receipt={
        "status":"PASS",
        "source_annual_sha256":EXPECTED["annual"],
        "source_daily_sha256":{k:EXPECTED[k] for k in ("BAC251213.zip","BAC251214.zip")},
        "repaired_annual_sha256":sha(candidate.read_bytes()),
        "repaired_annual_size":candidate.stat().st_size,
        "old_races":len(original_keys),
        "added_races":len(keys-original_keys),
        "repaired_races":len(keys),
        "untouched_member_count":107,
        "updated_member_count":2,
        "warehouse_generation_id":args.generation_id,
        "warehouse_parquet_asset":asset,
        "warehouse_audit_status":built["audit"]["status"],
        "source_git_commit":args.source_git_commit,
        "production_current_changed":False,
    }
    (out/"repair_receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
if __name__=="__main__":
    main()
