#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RaceNote Portfolio v0.1 five-price query over an explicit odds snapshot.

The source adapter is deliberately independent of Prediction, Confidence and
JRDB payout settlement. PACI KYI contains base WIN estimates, *not* the
five closing market odds; HJC lists payouts for winners only. Neither may be
misrepresented as a complete closing-odds board.

Input snapshot contract:
{"schema_version":"racenote-odds-snapshot-v0.1",
 "source":{"provider":"...", "as_of":"...", "kind":"closing_or_latest"},
 "races":[{"race_key":"20250426-京都-10",
           "win":{"8":3.4},
           "quinella":{"5-8":12.8,"6-8":21.6},
           "exacta":{"8>5":18.2,"8>6":27.5}}]}
"""
from __future__ import annotations
import argparse
import json
import math
import re
from pathlib import Path

SCHEMA_VERSION = "racenote-portfolio-odds-v0.1"
KEY_PATTERN = re.compile(r"^([0-9]{8})-([^\\-]+)-([1-9]|1[0-2])$")

def _price(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number >= 1.0 else None

def _result(key, horses, status, odds=None, missing=None, source=None):
    return {
        "schema_version": SCHEMA_VERSION, "status": status,
        "race_key": key, "horse_no_1": horses[0],
        "horse_no_2": horses[1], "horse_no_3": horses[2],
        "odds": odds or {"win_1":None,"quinella_1_2":None,"quinella_1_3":None,
                         "exacta_1_2":None,"exacta_1_3":None},
        "missing": missing or [], "source": source,
    }

def query(snapshot, race_key, horse1, horse2, horse3):
    horses = (horse1, horse2, horse3)
    if not KEY_PATTERN.fullmatch(race_key):
        raise ValueError("race_key must be YYYYMMDD-venue-race_no")
    if any(type(h) is not int or not 1 <= h <= 18 for h in horses) or len(set(horses)) != 3:
        raise ValueError("horses must be three distinct integer horse numbers (1-18)")
    if snapshot.get("schema_version") != "racenote-odds-snapshot-v0.1":
        raise ValueError("unsupported snapshot schema_version")
    source = snapshot.get("source")
    if not isinstance(source, dict) or not all(source.get(k) for k in ("provider","as_of","kind")):
        raise ValueError("snapshot must provide source provider/as_of/kind")
    if source["kind"] not in ("closing_or_latest","confirmed_closing"):
        raise ValueError("unsupported odds source kind (PACI base estimates are excluded)")
    races = snapshot.get("races")
    if not isinstance(races, list):
        raise ValueError("snapshot races must be a list")
    matches = [x for x in races if isinstance(x, dict) and x.get("race_key") == race_key]
    if len(matches) > 1:
        raise ValueError("ambiguous duplicate race_key")
    if not matches:
        return _result(race_key, horses, "not_found", source=source)
    race = matches[0]
    keys = {
        "win_1": ("win", str(horse1)),
        "quinella_1_2": ("quinella", "-".join(map(str,sorted((horse1,horse2))))),
        "quinella_1_3": ("quinella", "-".join(map(str,sorted((horse1,horse3))))),
        "exacta_1_2": ("exacta", f"{horse1}>{horse2}"),
        "exacta_1_3": ("exacta", f"{horse1}>{horse3}"),
    }
    odds = {}
    for output, (group,key) in keys.items():
        table = race.get(group, {})
        if not isinstance(table,dict):
            raise ValueError(f"{group} odds must be a map")
        odds[output] = _price(table.get(key))
    missing = [key for key,value in odds.items() if value is None]
    status = "success" if not missing else "partial"
    return _result(race_key,horses,status,odds,missing,source)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--odds-json", type=Path, required=True, help="verified complete/partial odds snapshot JSON")
    ap.add_argument("--race-key",required=True)
    ap.add_argument("--horse1",type=int,required=True)
    ap.add_argument("--horse2",type=int,required=True)
    ap.add_argument("--horse3",type=int,required=True)
    ap.add_argument("--pretty",action="store_true")
    ap.add_argument("--output",type=Path)
    args = ap.parse_args()
    try:
        snapshot=json.loads(args.odds_json.read_text(encoding="utf-8"))
        result=query(snapshot,args.race_key,args.horse1,args.horse2,args.horse3)
        rc={"success":0,"partial":3,"not_found":4}[result["status"]]
    except (ValueError,OSError,json.JSONDecodeError) as exc:
        result={"schema_version":SCHEMA_VERSION,"status":"error","error":str(exc)}
        rc=2
    data=json.dumps(result,ensure_ascii=False,indent=2 if args.pretty else None)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(data,encoding="utf-8")
    print(data,end="")
    return rc

if __name__=="__main__":
    raise SystemExit(main())
