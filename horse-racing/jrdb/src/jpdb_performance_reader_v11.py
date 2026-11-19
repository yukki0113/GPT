#!/usr/bin/env python3
"""JPDB P1.1 read-only batched descriptive rider history.

Shares the SHA-verified existing JPDBHistoryReader source. Strict D-exclusive
event cutoff. This is a candidate denominator, not production skill scoring.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from jpdb_history_reader import (
    JPDBHistoryReader, JPDBHistoryReaderError, POLICY, SOURCE_GENERATION,
    lower_bound, validate_jockey, validate_target,
)

VERSION = "jpdb-performance-reader-v1.1-candidate"
POPULATION = "JPDB_FLAT_RIDE_START_V1_CANDIDATE"
MAX_CODES = 64
# A normal finished outcome must also have an ordinal finish within the field size.
NORMAL = "abnormal_code IN ('0','') AND finish BETWEEN 1 AND field_size AND field_size >= 1"


def _checked_codes(jockey_codes: Sequence[str]) -> list[str]:
    if isinstance(jockey_codes, (str, bytes)) or not isinstance(jockey_codes, (list, tuple)):
        raise JPDBHistoryReaderError("jockey_codes must be a list/tuple of five-digit strings")
    if not 1 <= len(jockey_codes) <= MAX_CODES:
        raise JPDBHistoryReaderError(f"jockey_codes length must be 1..{MAX_CODES}")
    if len(set(jockey_codes)) != len(jockey_codes):
        raise JPDBHistoryReaderError("duplicate jockey codes forbidden")
    return [validate_jockey(code) for code in jockey_codes]


def _windows(day):
    lower = lower_bound(day)
    # Date-relative windows have a single strict target date bound. The shorter
    # windows are clipped to the approved 2023 historical start.
    from datetime import timedelta
    return {
        "ROLLING_3Y": lower.isoformat(),
        "RECENT_365D": max(lower, day - timedelta(days=365)).isoformat(),
        "RECENT_90D": max(lower, day - timedelta(days=90)).isoformat(),
    }


def _grouped(db, target_date: str, jockey_codes: Sequence[str], *, target_validator=validate_target) -> dict:
    day = target_validator(target_date)
    codes = _checked_codes(jockey_codes)
    windows = _windows(day)
    markers = ",".join("?" for _ in codes)
    # Single prepared query per window for the *entire* target rider roster,
    # not one scan per jockey. All numerator/denominator cases are explicit.
    sql = f"""SELECT jockey_code, surface_code,
      COUNT(*) AS entries,
      COUNT(*) FILTER (WHERE {NORMAL}) AS normal_finishers,
      COUNT(*) FILTER (WHERE abnormal_code='1') AS cancellations,
      COUNT(*) FILTER (WHERE abnormal_code='2') AS exclusions,
      COUNT(*) FILTER (WHERE abnormal_code='3') AS dnf,
      COUNT(*) FILTER (WHERE abnormal_code='5') AS demotion_review,
      COUNT(*) FILTER (WHERE abnormal_code IS NULL
        OR abnormal_code NOT IN ('0','','1','2','3','5')) AS unknown_codes,
      COUNT(*) FILTER (WHERE abnormal_code IN ('0','')
        AND (finish IS NULL OR field_size IS NULL
             OR field_size < 1 OR finish NOT BETWEEN 1 AND field_size))
           AS invalid_normal_finish,
      COUNT(*) FILTER (WHERE {NORMAL} AND finish=1) AS wins,
      COUNT(*) FILTER (WHERE {NORMAL} AND finish<=2) AS top2,
      COUNT(*) FILTER (WHERE {NORMAL} AND finish<=3) AS top3,
      MIN(race_date) AS first_observed,
      MAX(race_date) AS last_observed
      FROM sed_all
      WHERE race_date >= ? AND race_date < ?
        AND jockey_code IN ({markers})
        AND surface_code IN ('1','2')
      GROUP BY jockey_code, surface_code"""
    fields = ("entries","normal_finishers","cancellations","exclusions",
              "dnf","demotion_review","unknown_codes","invalid_normal_finish",
              "wins","top2","top3","first_observed","last_observed")
    output = {}
    for name, lower in windows.items():
        result = db.execute(sql,[lower,day.isoformat(),*codes]).fetchall()
        by_code = {}
        for code,surface,*values in result:
            if surface not in ("1","2"):
                raise JPDBHistoryReaderError("bad surface in aggregate")
            row=dict(zip(fields,values))
            by_code.setdefault(code,{})[surface]=row
        output[name] = by_code
    responses={}
    for code in codes:
        window_out = {}
        for name, lower in windows.items():
            by_surface={}
            for surface,label in (("1","turf"),("2","dirt")):
                row=output[name].get(code,{}).get(surface,{})
                by_surface[label]=_metrics({k:row.get(k,0) for k in fields[:11]},
                                           row.get("first_observed"),row.get("last_observed"),
                                           day.isoformat())
            nums={k:sum(by_surface[s][k] for s in ("turf","dirt")) for k in fields[:11]}
            observed=[by_surface[s]["first_observed"] for s in ("turf","dirt")
                      if by_surface[s]["first_observed"]]
            latest=[by_surface[s]["last_observed"] for s in ("turf","dirt")
                    if by_surface[s]["last_observed"]]
            all_flat=_metrics(nums,min(observed) if observed else None,
                              max(latest) if latest else None,day.isoformat())
            if all_flat["entries"] != sum(by_surface[s]["entries"] for s in ("turf","dirt")):
                raise JPDBHistoryReaderError("surface aggregation mismatch")
            window_out[name] = {
                "period_from_inclusive":lower,
                "period_to_exclusive":day.isoformat(),
                "all_flat":all_flat,
                "by_surface":by_surface,
            }
        responses[code]={
            "schema_version":VERSION,
            "target_date":day.isoformat(),
            "jockey_code":code,
            "source_generation":SOURCE_GENERATION,
            "asof_policy":POLICY,
            "availability_basis":"ASSUMED_PREVIOUS_DAY",
            "historical_release_attested":False,
            "population_filter_id":POPULATION,
            "source_jockey_role":"HISTORICAL_SED_ACTUAL",
            "target_entry_source":"NOT_RESOLVED_BY_THIS_READER",
            "sample_status":"HAS_HISTORY" if window_out["ROLLING_3Y"]["all_flat"]["entries"] else "NO_HISTORY",
            "windows":window_out,
            "strict_asof_certified":False,
            "assumption_based_backtest_eligible":True,
        }
    return {"schema_version":VERSION,"target_date":day.isoformat(),
            "population_filter_id":POPULATION,"asof_policy":POLICY,
            "jockey_histories":responses}


def _metrics(row, first, last, cutoff):
    n = {k:int(v) for k,v in row.items()}
    n["first_observed"] = str(first) if first is not None else None
    n["last_observed"] = str(last) if last is not None else None
    if n["last_observed"] is not None and n["last_observed"] >= cutoff:
        raise JPDBHistoryReaderError("target-date SED leakage")
    if not (0 <= n["wins"] <= n["top2"] <= n["top3"] <= n["normal_finishers"]):
        raise JPDBHistoryReaderError("invalid result counts")
    classified = (n["normal_finishers"]+n["cancellations"]+n["exclusions"]+n["dnf"]
                  +n["demotion_review"]+n["unknown_codes"]+n["invalid_normal_finish"])
    if classified != n["entries"]:
        raise JPDBHistoryReaderError("incomplete mutually exclusive outcome classification")
    n["nonstarters"]=n["cancellations"]+n["exclusions"]
    n["actual_starts_candidate"]=n["normal_finishers"]+n["dnf"]+n["demotion_review"]
    n["unresolved_count"]=n["unknown_codes"]+n["invalid_normal_finish"]+n["demotion_review"]
    normal_n=n["normal_finishers"]
    n["normal_win_rate"]=n["wins"]/normal_n if normal_n else None
    n["normal_top2_rate"]=n["top2"]/normal_n if normal_n else None
    n["normal_top3_rate"]=n["top3"]/normal_n if normal_n else None
    # Code 5 (demotion) has not yet been reviewed for official finish/result
    # contribution, and unknown/invalid facts make a ride-start rate unsafe.
    safe_starts=n["actual_starts_candidate"]
    approved_for_rate = (n["unresolved_count"]==0 and safe_starts>0)
    n["start_basis_win_rate_candidate"]=n["wins"]/safe_starts if approved_for_rate else None
    n["start_basis_top3_rate_candidate"]=n["top3"]/safe_starts if approved_for_rate else None
    n["start_rate_status"]=(
        "REVIEW_REQUIRED" if n["unresolved_count"] else
        ("NO_STARTS" if safe_starts==0 else "CANDIDATE_ONLY")
    )
    n["sample_support_status"]=(
        "REVIEW_REQUIRED" if n["unresolved_count"] else
        "NO_HISTORY" if n["entries"]==0 else
        "INSUFFICIENT" if safe_starts<30 else "DESCRIPTIVE_ONLY"
    )
    return n


class JPDBPerformanceReader(JPDBHistoryReader):
    """New separate API; the inherited v0.1 rider_history remains unchanged."""

    def rider_histories(self, *, target_date: str, jockey_codes: Sequence[str]) -> dict:
        result = _grouped(self.db, target_date, jockey_codes)
        result["source_generation"] = SOURCE_GENERATION
        result["source_manifest_sha256"] = self.manifest_sha256
        result["source_assets"] = self.asset_receipts
        return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input-root",type=Path,required=True)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--expected-manifest-sha256")
    p.add_argument("--target-date",required=True)
    p.add_argument("--jockey-code",action="append",required=True)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    with JPDBPerformanceReader(input_root=a.input_root,manifest=a.manifest,
                               expected_manifest_sha256=a.expected_manifest_sha256) as reader:
        result=reader.rider_histories(target_date=a.target_date,jockey_codes=a.jockey_code)
    if a.output.exists():
        raise FileExistsError("refusing to overwrite output")
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")


if __name__=="__main__":
    main()
