#!/usr/bin/env python3
"""JPDB P0 read-only retrospective cutoff audit; NOT an as-of-certified Reader.

A target date restricts prior SED race outcomes. Annual finalized Warehouse
cannot attest that exact records/revisions were available at target prediction time.
No licensed rider rows or prediction features are exported by this audit.
"""
from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import re
from datetime import date
from pathlib import Path

import duckdb

SOURCE_GENERATION = "jrdb_normalized_warehouse_v1_2010_2025_g20261118_bacfix"
MIN_DATE = date(2023, 1, 1)
EXPECTED_SED_COUNTS = {2023: 47672, 2024: 47181, 2025: 47884}


def parse_target(value: str) -> date:
    if not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("target date must be YYYY-MM-DD")
    d = date.fromisoformat(value)
    if not MIN_DATE <= d <= date(2025,12,31):
        raise ValueError("P0 accepted cohort permits only 2023-01-01..2025-12-31")
    return d


def years_before(d: date, count: int) -> date:
    y = d.year-count
    return date(y,d.month,min(d.day,calendar.monthrange(y,d.month)[1]))


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):
            h.update(b)
    return h.hexdigest()


def prepare(db, root: Path, manifest: Path):
    cfg=json.loads(manifest.read_text(encoding="utf-8"))
    indexed={(row["artifact_id"]):row for row in cfg["artifacts"]}
    paths=[]
    for y in (2023,2024,2025):
        key=f"sed_{y}"
        spec=indexed[key]
        asset=root/key/spec["expected_name"]
        if not asset.is_file() or sha256(asset)!=spec["sha256"] or asset.stat().st_size!=spec["expected_size"]:
            raise RuntimeError(f"SED {y} immutable source hash/size mismatch")
        paths.append(str(asset))
    db.execute("CREATE VIEW sed_all AS SELECT * FROM read_parquet(?, union_by_name=true)",[paths]) if False else None
    quoted=",".join("'" + p.replace("'","''") + "'" for p in paths)
    db.execute(f"CREATE VIEW sed_all AS SELECT * FROM read_parquet([{quoted}], union_by_name=true)")
    annual={int(y):int(n) for y,n in db.execute(
        "SELECT YEAR(CAST(race_date AS DATE)),COUNT(*) FROM sed_all GROUP BY 1 ORDER BY 1").fetchall()}
    if annual!=EXPECTED_SED_COUNTS:
        raise RuntimeError(f"annual SED cohort mismatch: {annual}")
    if db.execute("""SELECT COUNT(*) FROM sed_all WHERE
        race_date IS NULL OR jockey_code IS NULL OR TRIM(jockey_code) IN ('','00000')
        OR race_key_raw IS NULL OR horse_no IS NULL""").fetchone()[0]:
        raise RuntimeError("null historical SED identity")
    return [{"year":y,"sha256":indexed[f"sed_{y}"]["sha256"],
             "size_bytes":indexed[f"sed_{y}"]["expected_size"]} for y in (2023,2024,2025)]


def audit_cutoff(db, target_date: date, *, lookback_years: int=3):
    if lookback_years!=3:
        raise ValueError("only approved 3 calendar year research window")
    lower=max(MIN_DATE,years_before(target_date,lookback_years))
    cutoff=target_date.isoformat()
    low=lower.isoformat()
    # Never ingest the target day, even when its race results are already in finalized SED.
    sql="""SELECT jockey_code,COUNT(*) AS prior_entries,
      COUNT(*) FILTER (WHERE abnormal_code IN ('0','')) AS normal_finishes,
      COUNT(*) FILTER (WHERE abnormal_code IN ('1','2')) AS nonstarters,
      COUNT(*) FILTER (WHERE abnormal_code='3') AS dnf,
      COUNT(*) FILTER (WHERE abnormal_code='5') AS demoted,
      COUNT(*) FILTER (WHERE abnormal_code IN ('0','') AND finish=1) AS wins,
      COUNT(*) FILTER (WHERE abnormal_code IN ('0','') AND finish BETWEEN 1 AND 3) AS top3
      FROM sed_all WHERE CAST(race_date AS DATE)>=CAST(? AS DATE)
       AND CAST(race_date AS DATE)<CAST(? AS DATE)
       AND surface_code IN ('1','2')
      GROUP BY jockey_code"""
    rows=db.execute(sql,[low,cutoff]).fetchall()
    vals=[tuple(int(x) for x in row[1:]) for row in rows]
    total=[sum(row[i] for row in vals) for i in range(7)]
    (entries,normals,nonstarters,dnf,demoted,wins,top3)=total
    invalid=sum(1 for row in vals if row[5]>row[1] or row[6]>row[1]
                or row[5]>row[6] or row[1]+row[2]+row[3]+row[4]>row[0])
    if invalid:
        raise RuntimeError(f"inconsistent per-jockey historical aggregates: {invalid}")
    eligible=db.execute("""SELECT COUNT(*),MIN(race_date),MAX(race_date)
       FROM sed_all WHERE CAST(race_date AS DATE)>=CAST(? AS DATE)
        AND CAST(race_date AS DATE)<CAST(? AS DATE) AND surface_code IN ('1','2')""",[low,cutoff]).fetchone()
    if int(eligible[0])!=entries or eligible[2] is not None and str(eligible[2])>=cutoff:
        raise RuntimeError("cutoff leakage / aggregate disagreement")
    excluded=db.execute("""SELECT COUNT(*) FROM sed_all WHERE
       CAST(race_date AS DATE)>=CAST(? AS DATE) AND surface_code IN ('1','2')""",[cutoff]).fetchone()[0]
    return {
      "target_date":cutoff,"history_from_inclusive":low,
      "history_to_exclusive":cutoff,"lookback_calendar_years":3,
      "window_clamped_to_2023":years_before(target_date,3)<MIN_DATE,
      "historic_flat_race_entries":entries,
      "historic_unique_jockey_codes":len(rows),
      "historic_normal_finishes":normals,
      "historic_nonstarters_codes_1_2":nonstarters,
      "historic_dnf_code_3":dnf,
      "historic_demotion_code_5":demoted,
      "historic_wins_normal_only":wins,"historic_top3_normal_only":top3,
      "observed_min_history_date":str(eligible[1]) if eligible[1] else None,
      "observed_max_history_date":str(eligible[2]) if eligible[2] else None,
      "flat_future_or_same_day_entries_excluded":int(excluded),
      "same_day_target_results_as_features":False,
      "observational_population_only":True,
      "official_ride_start_denominator_approved":False,
      "source_available_by_target_verified":False,
      "prediction_safe":False,
      "status":"PASS_RETROSPECTIVE_CUTOFF_ONLY"
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input-root",type=Path,required=True)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--target-date",action="append",required=True)
    args=p.parse_args()
    targets=[parse_target(x) for x in args.target_date]
    if len(targets)!=len(set(targets)) or len(targets)>20:
        raise ValueError("target dates must be unique and at most 20")
    db=duckdb.connect(":memory:")
    db.execute("SET threads=1")
    sources=prepare(db,args.input_root,args.manifest)
    checks=[audit_cutoff(db,t) for t in sorted(targets)]
    result={
      "status":"PASS_RETROSPECTIVE_CUTOFF_ONLY",
      "prediction_safe":False,
      "as_of_certified":False,
      "usage":"P0 research verification only; not a RaceNote feature API",
      "source_generation":SOURCE_GENERATION,
      "source_mode":"annual_finalized_sed_not_historical_release_snapshot",
      "input_sed_assets":sources,
      "target_date_is_exclusive":True,
      "actual_release_time_attested":False,
      "late_sed_revision_asof_attested":False,
      "population_filter_id":"JPDB_P0_FLAT_RETROSPECTIVE_DIAGNOSTIC_V0",
      "target_checks":checks
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    db.close()


if __name__=="__main__":
    main()
