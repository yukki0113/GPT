#!/usr/bin/env python3
"""Formal RaceNote logical-bundle Raw-versus-Warehouse audit."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

from jrdb_raw import iter_archive_records, race_key
from jrdb_racenote_raw_adapter import build_paci_equivalent
from jrdb_racenote_warehouse_reader import WarehouseRaceNoteReader
from racenote_archive import semantic_sha256
from racenote_jrdb import Audit, BundleBuilder, parse_zip

def _canon(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",",":")).encode()).hexdigest()

def _keys(root: Path, day: dt.date) -> set[str]:
    path = root / "BAC" / f"BAC_{day.year}.zip"
    return {race_key(row) for _, row in iter_archive_records(path, "BAC") if row[8:16].decode("ascii", errors="ignore") == day.strftime("%Y%m%d")}

def _raw(root: Path, day: dt.date, keys: set[str]) -> tuple[dict[str,dict[str,Any]],dict[str,Any]]:
    with tempfile.TemporaryDirectory() as tmp:
        destination = Path(tmp) / "raw.zip"
        def ensure(year: int, kinds: list[str]) -> None:
            missing = [kind for kind in kinds if not (root / kind / f"{kind}_{year}.zip").is_file()]
            if missing:
                raise RuntimeError(f"missing Raw boundary archive year={year}: {missing}")
        provenance = build_paci_equivalent(root, day.year, day.strftime("%y%m%d"), keys, destination, ensure)
        audit = Audit(); parsed = parse_zip(destination, audit); builder = BundleBuilder(parsed, audit)
        grouped: dict[str,list[dict[str,Any]]] = {}
        for row in parsed["KYI"]: grouped.setdefault(str(row["race_key_raw"]), []).append(row)
        bundles = {str(row["race_key_raw"]):builder.build(row, grouped.get(str(row["race_key_raw"]),[])) for row in parsed["BAC"]}
        if audit.bundle_errors: raise RuntimeError("; ".join(audit.bundle_errors))
        return bundles, {"provenance":provenance,"record_counts":{k:len(v) for k,v in parsed.items()}}

def _compare(raw: dict[str,dict[str,Any]], warehouse: dict[str,dict[str,Any]]) -> dict[str,Any]:
    records = []
    for key in sorted(set(raw)|set(warehouse)):
        left,right=raw.get(key),warehouse.get(key)
        records.append({"race_key":key,"raw_present":left is not None,"warehouse_present":right is not None,
            "raw_schema":sorted(left) if left else None,"warehouse_schema":sorted(right) if right else None,
            "raw_semantic_sha256":semantic_sha256(left) if left else None,
            "warehouse_semantic_sha256":semantic_sha256(right) if right else None,
            "equal":left is not None and right is not None and semantic_sha256(left)==semantic_sha256(right)})
    hashes=lambda bundles:{k:semantic_sha256(v) for k,v in sorted(bundles.items())}
    logical=all(x["equal"] for x in records)
    return {"row_count":len(raw)==len(warehouse),"primary_keys":sorted(raw)==sorted(warehouse),
        "schema":all(x["raw_schema"]==x["warehouse_schema"] for x in records),
        "null_blank_semantics":logical,"all_logical_values":logical,"logical_bundle":logical,
        "canonical_bundle_hash":_canon(hashes(raw))==_canon(hashes(warehouse)),"bundles":records}

def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--date",required=True);parser.add_argument("--raw-root",required=True,type=Path)
    parser.add_argument("--warehouse-current",required=True,type=Path);parser.add_argument("--asset-root",action="append",required=True)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args(); day=dt.date.fromisoformat(args.date.replace("/","-"))
    roots={item.split("=",1)[0].upper():Path(item.split("=",1)[1]) for item in args.asset_root}
    keys=_keys(args.raw_root,day);raw,raw_meta=_raw(args.raw_root,day,keys)
    reader=WarehouseRaceNoteReader(args.warehouse_current,asset_roots=roots)
    warehouse,warehouse_meta=reader.build(day,race_keys=keys,source_member_date=day)
    comparison=_compare(raw,warehouse); reread,_=reader.build(day,race_keys=keys,source_member_date=day)
    # Archive's semantic contract deliberately excludes runtime generated_at.
    comparison["repeated_read_determinism"]=_canon({k:semantic_sha256(v) for k,v in warehouse.items()})==_canon({k:semantic_sha256(v) for k,v in reread.items()})
    comparison["idempotence"]=comparison["repeated_read_determinism"]
    gates=("row_count","primary_keys","schema","null_blank_semantics","all_logical_values","canonical_bundle_hash","repeated_read_determinism","idempotence")
    result={"date":day.isoformat(),"status":"PASS" if all(comparison[x] for x in gates) else "FAIL","comparison":comparison,"raw":raw_meta,"warehouse":warehouse_meta}
    args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return 0 if result["status"]=="PASS" else 2
if __name__=="__main__": raise SystemExit(main())
