#!/usr/bin/env python3
"""M6 P1-4d: freeze a 2026 pre-day PACI cohort against canonical JRDB SED outcomes.

Research only: no inferred pre-race distribution, scoring or CURRENT writes.
Rows and private source IDs never enter the public GitHub repository.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from zipfile import BadZipFile, ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "jrdb" / "src"))
from jrdb_raw import Parser, split_fixed_records
from jrdb_ukc import parse_ukc_record
from audit_brdb_paci_pre_day_inventory import DATES, body_records, parse_provider_time

VERSION = "brdb-m6-p1-4d-2026-outcome-freeze-v0.1"
JST = timezone(timedelta(hours=9))
STATUS = {"0": "NORMAL", "1": "CANCELLED", "2": "EXCLUDED",
          "3": "DID_NOT_FINISH", "4": "DISQUALIFIED",
          "5": "DEMOTED", "6": "REMOUNTED"}
FIELDS = ("date","race_key","horse_no","horse_id","finish","abnormal_code",
          "actual_starter","normal_finisher","paci_sha256","sed_sha256")

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()

def validated_file(root: Path, name: str, expected_sha: str, size: int):
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha or ""):
        raise ValueError("invalid SHA")
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("missing or escaped source path")
    if path.stat().st_size != size or digest(path) != expected_sha:
        raise ValueError("source SHA or size mismatch")
    return path

def read_results(path: Path, member: str, kind: str, parser):
    try:
        with ZipFile(path) as z:
            names = z.namelist()
            if len(set(names)) != len(names) or member not in names:
                raise ValueError("missing or duplicated member")
            if z.testzip() is not None:
                raise ValueError("ZIP CRC mismatch")
            rows = split_fixed_records(z.read(member), kind)
            if not rows:
                raise ValueError("missing/malformed fixed-length records")
            return [parser(row) for row in rows]
    except BadZipFile as exc:
        raise ValueError("invalid ZIP") from exc

def key(row):
    horse_no = row.get("horse_no")
    hid = row.get("blood_registration_no")
    race = row.get("race_key_raw")
    if (not isinstance(horse_no, int) or horse_no < 1
            or not isinstance(hid,str) or not re.fullmatch(r"[0-9]{8}",hid)
            or not isinstance(race,str) or not re.fullmatch(r"[0-9A-Za-z]{8}",race)):
        raise ValueError("invalid canonical race/horse identity")
    return race,horse_no,hid

def index(rows):
    result = {}
    for row in rows:
        ident = key(row)
        if ident in result:
            raise ValueError("duplicate canonical race+horse+registration key")
        result[ident] = row
    return result

def audit(root, manifest, out):
    root, out = Path(root), Path(out)
    if manifest.get("schema_version") != 1 or manifest.get("prediction_safe") is not False:
        raise ValueError("private input contract must explicitly be research-only")
    entries = manifest.get("archives")
    if not isinstance(entries,list) or tuple(x.get("date") for x in entries) != DATES:
        raise ValueError("require exactly 14 ordered P1-4c dates")
    parser = Parser()
    all_horses = Counter()
    races = set()
    totals = Counter()
    annual = []
    detailed = []
    duplicate_summary = []
    for record in entries:
        day = record["date"]
        compact = day[2:]
        midnight = datetime.strptime(day,"%Y%m%d").replace(tzinfo=JST)
        created = parse_provider_time(record.get("paci_created_utc"))
        modified = parse_provider_time(record.get("paci_modified_utc"))
        if created >= midnight or modified >= midnight or modified < created:
            raise ValueError("Drive storage cutoff not satisfied")
        if record.get("paci_revision_count") != 1:
            raise ValueError("ambiguous Drive revisions")
        paci = validated_file(root, "PACI"+compact+".zip",record.get("paci_sha256"),record.get("paci_size"))
        sed = validated_file(root, "SED"+compact+".zip",record.get("sed_sha256"),record.get("sed_size"))
        kyi = index(read_results(paci, "KYI"+compact+".txt", "KYI", parser.kyi))
        sed_rows = index(read_results(sed,"SED"+compact+".txt", "SED",parser.sed))
        if kyi.keys() != sed_rows.keys():
            raise ValueError("KYI/SED canonical entry keys differ")
        # Independent, in-archive UKC identity/date crosscheck, reusing canonical parsers.
        with ZipFile(paci) as z:
            raw = z.read("UKC"+compact+".txt")
        ukc = [parse_ukc_record(x) for x in body_records(raw,"UKC",290)]
        if len(ukc) != len(kyi):
            raise ValueError("UKC/KYI counts differ")
        if [x.horse_id for x in ukc] != [x["blood_registration_no"] for x in kyi.values()]:
            raise ValueError("UKC/KYI identity sequence differs")
        if any(x.data_date != day for x in ukc):
            raise ValueError("UKC profile data date differs from target")
        other = record.get("alternate_sed",[])
        if not isinstance(other,list) or len(other)>1:
            raise ValueError("unexpected SED alternatives")
        if other:
            alt = other[0]
            filename = alt.get("path")
            if filename != "SED"+compact+"_later.zip":
                raise ValueError("unapproved alternate name")
            alt_path = validated_file(root,filename,alt.get("sha256"),alt.get("size"))
            alternative = index(read_results(alt_path,"SED"+compact+".txt","SED",parser.sed))
            if sed_rows.keys()!=alternative.keys():
                raise ValueError("SED alternate identities conflict")
            if any((r["finish"],r["abnormal_code"],r["date_raw"]) !=
                   (alternative[k]["finish"],alternative[k]["abnormal_code"],alternative[k]["date_raw"])
                   for k,r in sed_rows.items()):
                raise ValueError("SED alternate results conflict")
            revised = sum(sed_rows[k] != alternative[k] for k in sed_rows)
            duplicate_summary.append({"date":day,"alternate_present":True,
                                      "results_identical":True,"other_fields_revised_rows":revised})
        counters = Counter()
        for ident, r in sed_rows.items():
            if r.get("date_raw")!=day:
                raise ValueError("SED date differs from target")
            status = r["abnormal_code"]
            if status not in STATUS:
                raise ValueError("unknown SED abnormal code")
            fin = r["finish"]
            normal = status=="0"
            if normal and (not isinstance(fin,int) or fin<1):
                raise ValueError("normal finisher lacks valid placing")
            starter = status not in ("1","2")
            counters[status]+=1
            totals[status]+=1
            races.add((day,ident[0]))
            all_horses[ident[2]]+=1
            detailed.append(dict(zip(FIELDS,(
                day,ident[0],ident[1],ident[2],fin,status,starter,normal,
                record["paci_sha256"],record["sed_sha256"]))))
        annual.append({"date":day,"declarations":len(kyi),
            "matched":len(sed_rows),"actual_starters":len(kyi)-counters["1"]-counters["2"],
            "normal_finishers":counters["0"],"abnormal_codes":dict(sorted(counters.items())),
            "race_count":len({k[0] for k in kyi})})
    out.mkdir(parents=True,exist_ok=True)
    with (out/"private_outcome_cohort.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(detailed)
    n = len(detailed)
    result={
        "version":VERSION,"status":"PASS_RESEARCH_ONLY",
        "source_manifest_sha256":None,
        "days":len(annual),"race_declarations":n,"matched_kyi_sed":n,
        "actual_starters":n-totals["1"]-totals["2"],
        "normal_finishers":totals["0"],
        "abnormal_codes":dict(sorted(totals.items())),
        "abnormal_code_labels":STATUS,
        "race_count":len(races),"unique_horses":len(all_horses),
        "horses_with_repeated_declarations":sum(x>1 for x in all_horses.values()),
        "extra_declarations_of_repeated_horses":sum(x-1 for x in all_horses.values()),
        "duplicate_sed_versions":duplicate_summary,
        "daily":annual,"prediction_safe":False,
        "asof_provider_release_proven":False,"historical_2016_2025_asof_proven":0,
        "per_horse_rows_private":True,"forecasting_promotion":"HOLD",
    }
    (out/"outcome_aggregate_audit.json").write_text(
        json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source-root",type=Path,required=True)
    p.add_argument("--private-manifest",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    manifest_path=args.private_manifest
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    report=audit(args.source_root,manifest,args.out)
    report["source_manifest_sha256"]=digest(manifest_path)
    (args.out/"outcome_aggregate_audit.json").write_text(
        json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":report["status"],"entries":report["race_declarations"],
                      "actual_starters":report["actual_starters"]},sort_keys=True))

if __name__=="__main__":
    main()
