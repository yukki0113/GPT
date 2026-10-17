#!/usr/bin/env python3
"""Promote a validated immutable RaceLap candidate into a current delivery bundle.

Publication to durable Drive and current-pointer update are separate atomic
operations. This tool never acquires historical data or modifies a candidate.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
from pathlib import Path

from jrdb_race_lap_forward_current import validate


def promote(candidate: Path, destination: Path, target_date: str,
            expected_period_to: str) -> dict:
    if destination.exists():
        raise FileExistsError(f"current bundle exists: {destination}")
    m = candidate / "manifest.json"
    p = candidate / "race_lap.parquet"
    a = candidate / "audit.json"
    obj = json.loads(m.read_text(encoding="utf-8"))
    if obj.get("status") != "CANDIDATE_PASS" or obj.get("validation_status") != "PASS":
        raise ValueError("candidate is not PASS")
    if obj.get("period_to") != expected_period_to or not expected_period_to < target_date:
        raise ValueError("RaceLap expected cutoff mismatch")
    if obj["parquet_sha256"] != hashlib.sha256(p.read_bytes()).hexdigest():
        raise ValueError("candidate parquet SHA mismatch")
    import tempfile
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent,prefix=".racelap-promote-") as temporary:
        stage=Path(temporary)/"bundle"
        stage.mkdir()
        shutil.copy2(p,stage/"race_lap.parquet")
        shutil.copy2(a,stage/"audit.json")
        current=dict(obj)
        current["status"]="CURRENT"
        (stage/"manifest.json").write_text(json.dumps(current,sort_keys=True,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        receipt=validate(stage/"race_lap.parquet",stage/"manifest.json",target_date,expected_period_to)
        stage.rename(destination)
        return receipt


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate",required=True,type=Path)
    parser.add_argument("--destination",required=True,type=Path)
    parser.add_argument("--target-date",required=True)
    parser.add_argument("--expected-period-to",required=True)
    args=parser.parse_args()
    print(json.dumps(promote(args.candidate,args.destination,args.target_date,args.expected_period_to),sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
