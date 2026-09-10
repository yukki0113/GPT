#!/usr/bin/env python3
"""Stage 1b: past-only CHA final-segment vertical comparison vs Official RunPerf.

The query hard-stops at 2023. Holdout outcome columns may exist in the database but
are neither selected nor summarized by this program.
"""
from __future__ import annotations

import argparse
import bisect
import datetime as dt
import json
import math
import sqlite3
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

VERSION = "0.1.0"
MIN_PRIOR_PERF = 3
THRESHOLDS = (2, 3, 4, 5, 6, 8, 10)


def _median(values: list[float]) -> float:
    return float(statistics.median(values))


def _mean(values: list[float]) -> float | None:
    return None if not values else float(statistics.fmean(values))


def _sd(values: list[float]) -> float | None:
    return None if len(values) < 2 else float(statistics.stdev(values))


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        rank = (cursor + 1 + end) / 2.0
        for position in range(cursor, end):
            ranks[order[position]] = rank
        cursor = end
    return ranks


def _pearson(left: list[float], right: list[float]) -> float | None:
    if len(left) < 3 or len(left) != len(right):
        return None
    lm, rm = statistics.fmean(left), statistics.fmean(right)
    numerator = sum((x-lm)*(y-rm) for x,y in zip(left,right))
    denominator = math.sqrt(sum((x-lm)**2 for x in left)*sum((y-rm)**2 for y in right))
    return None if denominator == 0 else numerator/denominator


def _spearman(left: list[float], right: list[float]) -> float | None:
    return _pearson(_ranks(left), _ranks(right))


def _summary(values: list[float]) -> dict[str, Any]:
    return {"n": len(values), "mean": _mean(values), "median": None if not values else _median(values), "sd": _sd(values)}


def _difference(high: list[float], low: list[float]) -> dict[str, Any]:
    high_mean, low_mean = _mean(high), _mean(low)
    difference = None if high_mean is None or low_mean is None else high_mean-low_mean
    pooled = None
    if len(high)>1 and len(low)>1:
        pooled = math.sqrt(((len(high)-1)*statistics.variance(high)+(len(low)-1)*statistics.variance(low))/(len(high)+len(low)-2))
    return {
        "high": _summary(high), "low": _summary(low), "mean_difference": difference,
        "standardized_mean_difference": None if not pooled or difference is None else difference/pooled,
    }


def _fixed_quintile(value: float) -> int:
    return min(5, int(value*5)+1)


def _load(db_path: Path) -> list[sqlite3.Row]:
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        rows = db.execute("""
          SELECT race_date,year,race_key,horse_no,horse_id,course_code,furlong_count,
                 final_segment_sec,official_runperf_raw,runperf_score_status
          FROM training_runner
          WHERE year BETWEEN 2010 AND 2023
          ORDER BY race_date,race_key,horse_no
        """).fetchall()
        if rows and max(int(row["year"]) for row in rows)>2023:
            raise RuntimeError("holdout guard failed")
        return rows
    finally:
        db.close()


def analyze(db_path: Path) -> dict[str, Any]:
    source_rows = _load(db_path)
    workout_history: dict[tuple[str,str,int],list[float]] = defaultdict(list)
    last_comparable: dict[tuple[str,str,int],float] = {}
    perf_history: dict[str,list[float]] = defaultdict(list)
    observations: list[dict[str, Any]] = []

    current_date = None
    pending: list[sqlite3.Row] = []

    def process_day(day_rows: list[sqlite3.Row]) -> None:
        for row in day_rows:
            horse = str(row["horse_id"] or "")
            course = str(row["course_code"] or "")
            furlong = row["furlong_count"]
            final = row["final_segment_sec"]
            runperf = row["official_runperf_raw"] if row["runperf_score_status"] == "OK" else None
            comparable = workout_history[(horse,course,int(furlong))] if horse and course and furlong is not None else []
            prior_perf = perf_history[horse] if horse else []
            if int(row["year"])>=2013 and final is not None and runperf is not None and len(comparable)>=2 and len(prior_perf)>=MIN_PRIOR_PERF:
                x=float(final)
                lower=bisect.bisect_left(comparable,x)
                upper=bisect.bisect_right(comparable,x)
                n=len(comparable)
                faster_pct=((n-upper)+0.5*(upper-lower))/n
                key=(horse,course,int(furlong))
                observations.append({
                    "year":int(row["year"]),"horse_id":horse,"prior_workout_count":n,"prior_perf_count":len(prior_perf),
                    "self_percentile":faster_pct,
                    "median_delta_sec":_median(comparable)-x,
                    "previous_delta_sec":last_comparable[key]-x,
                    "runperf_delta":float(runperf)-_median(prior_perf),
                })
        # Update only after all rows on the race date have been evaluated: strict prior-date policy.
        for row in day_rows:
            horse=str(row["horse_id"] or "")
            course=str(row["course_code"] or "")
            furlong=row["furlong_count"]
            final=row["final_segment_sec"]
            if horse and course and furlong is not None and final is not None:
                key=(horse,course,int(furlong))
                bisect.insort(workout_history[key],float(final))
                last_comparable[key]=float(final)
            if horse and row["runperf_score_status"]=="OK" and row["official_runperf_raw"] is not None:
                bisect.insort(perf_history[horse],float(row["official_runperf_raw"]))

    for row in source_rows:
        date=str(row["race_date"])
        if current_date is not None and date!=current_date:
            process_day(pending)
            pending=[]
        current_date=date
        pending.append(row)
    if pending:
        process_day(pending)

    primary=[row for row in observations if row["prior_workout_count"]>=3]
    quintiles={str(q):_summary([r["runperf_delta"] for r in primary if _fixed_quintile(r["self_percentile"])==q]) for q in range(1,6)}
    correlations={feature:_spearman([r[feature] for r in primary],[r["runperf_delta"] for r in primary])
                  for feature in ("self_percentile","median_delta_sec","previous_delta_sec")}

    sensitivity=[]
    for minimum in THRESHOLDS:
        subset=[r for r in observations if r["prior_workout_count"]>=minimum]
        high=[r["runperf_delta"] for r in subset if r["self_percentile"]>=0.8]
        low=[r["runperf_delta"] for r in subset if r["self_percentile"]<=0.2]
        sensitivity.append({"minimum_prior_workouts":minimum,"eligible_n":len(subset),**_difference(high,low)})

    yearly=[]
    for year in range(2013,2024):
        subset=[r for r in primary if r["year"]==year]
        high=[r["runperf_delta"] for r in subset if r["self_percentile"]>=0.8]
        low=[r["runperf_delta"] for r in subset if r["self_percentile"]<=0.2]
        yearly.append({"year":year,"eligible_n":len(subset),**_difference(high,low)})

    by_horse: dict[str,dict[str,list[float]]] = defaultdict(lambda:{"high":[],"low":[]})
    for row in primary:
        if row["self_percentile"]>=0.8:
            by_horse[row["horse_id"]]["high"].append(row["runperf_delta"])
        elif row["self_percentile"]<=0.2:
            by_horse[row["horse_id"]]["low"].append(row["runperf_delta"])
    paired=[statistics.fmean(v["high"])-statistics.fmean(v["low"]) for v in by_horse.values() if v["high"] and v["low"]]

    main=sensitivity[1]
    annual_diffs=[row["mean_difference"] for row in yearly if row["mean_difference"] is not None]
    positive_years=sum(value>0 for value in annual_diffs)
    if main["mean_difference"] is not None and main["mean_difference"]>=0.05 and positive_years>=9:
        classification="EFFECT_CONFIRMED"
    elif main["mean_difference"] is not None and main["mean_difference"]>0 and positive_years>=8 and (_mean(paired) or 0)>0:
        classification="WEAK_BUT_REPRODUCIBLE"
    elif main["mean_difference"] is not None and main["mean_difference"]<=0 and positive_years<=3:
        classification="NO_SIGNAL"
    else:
        classification="INCONCLUSIVE"

    return {
        "status":"success","analysis_version":VERSION,"classification":classification,
        "controller_disposition":"EVIDENCE_ONLY_PRODUCTION_NOT_AUTHORIZED",
        "protocol":{
            "period":"2013-2023","warmup":"2010-2012","holdout":"2024-2025 UNOPENED",
            "comparison":"same horse_id + CHA course_code + furlong_count + strictly prior race dates",
            "feature":"final_segment_sec; faster self percentile points toward 1.0",
            "target":"current Official RunPerf v0.1 minus strictly-prior horse median Official RunPerf",
            "minimum_prior_runperf":MIN_PRIOR_PERF,"primary_minimum_prior_workouts":3,
            "excluded_predictors":["JRDB workout indices","finish index/change","KYI training score","odds","popularity","payout"],
        },
        "population":{"source_rows_2010_2023":len(source_rows),"eligible_min2":len(observations),"primary_min3":len(primary),
                      "unique_horses_primary":len({r["horse_id"] for r in primary})},
        "quintiles":quintiles,"correlations_spearman":correlations,"history_sensitivity":sensitivity,
        "within_horse":{"paired_horses":len(paired),"mean_high_minus_low":_mean(paired),
                        "median_high_minus_low":None if not paired else _median(paired),
                        "positive_share":None if not paired else sum(v>0 for v in paired)/len(paired)},
        "yearly_stability":yearly,
        "annual_positive_years":positive_years,
        "holdout_guard":{"max_selected_year":2023,"predictive_outcomes_selected":False,"opened":False},
    }


def _fmt(value: Any, digits: int = 5) -> str:
    return "NA" if value is None else f"{value:.{digits}f}"


def render_markdown(report: dict[str, Any]) -> str:
    main=report["history_sensitivity"][1]
    lines=[
        "# JRDB Training Vertical Stage 1b — Official RunPerf evidence",
        "",f"Generated: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}","",
        f"Classification: **{report['classification']}**", "",
        "This is Controller evidence only. It does not authorize an Edge or Production formula.","",
        "## Locked protocol","",
        "- Development evaluation: 2013–2023; warmup: 2010–2012.",
        "- 2024–2025 predictive outcomes were not selected, computed, displayed, or summarized.",
        "- Same horse + same CHA course + same furlong count; strictly prior race dates only.",
        "- Target: current Official RunPerf v0.1 minus the horse's strictly-prior median RunPerf.",
        "- Primary gate: at least 3 prior comparable workouts and 3 prior scored RunPerf rows.","",
        "## Main result","",
        f"Primary eligible rows: **{report['population']['primary_min3']:,}**; unique horses: **{report['population']['unique_horses_primary']:,}**.","",
        f"Fastest 20% minus slowest 20% mean RunPerf delta: **{_fmt(main['mean_difference'])}** "
        f"(standardized difference {_fmt(main['standardized_mean_difference'])}; high n={main['high']['n']:,}, low n={main['low']['n']:,}).", "",
        "| Self-percentile quintile | n | Mean RunPerf delta | Median |", "|---:|---:|---:|---:|",
    ]
    for q, values in report["quintiles"].items():
        lines.append(f"| {q} | {values['n']:,} | {_fmt(values['mean'])} | {_fmt(values['median'])} |")
    lines += ["","## Predictor association","","| Transparent feature | Spearman vs RunPerf delta |","|---|---:|"]
    for key,value in report["correlations_spearman"].items():
        lines.append(f"| {key} | {_fmt(value)} |")
    lines += ["","## History-depth sensitivity","","| Minimum prior workouts | Eligible n | High n | Low n | High-low mean | Std. difference |","|---:|---:|---:|---:|---:|---:|"]
    for row in report["history_sensitivity"]:
        lines.append(f"| {row['minimum_prior_workouts']} | {row['eligible_n']:,} | {row['high']['n']:,} | {row['low']['n']:,} | {_fmt(row['mean_difference'])} | {_fmt(row['standardized_mean_difference'])} |")
    within=report["within_horse"]
    lines += ["","## Same-horse paired check","",
              f"Paired horses: **{within['paired_horses']:,}**; mean high-low: **{_fmt(within['mean_high_minus_low'])}**; "
              f"median: **{_fmt(within['median_high_minus_low'])}**; positive share: **{_fmt(within['positive_share'])}**.","",
              "## Annual stability","","| Year | Eligible n | High-low mean | High n | Low n |","|---:|---:|---:|---:|---:|"]
    for row in report["yearly_stability"]:
        lines.append(f"| {row['year']} | {row['eligible_n']:,} | {_fmt(row['mean_difference'])} | {row['high']['n']:,} | {row['low']['n']:,} |")
    lines += ["",f"Positive years: **{report['annual_positive_years']} / 11**.","",
              "## Holdout and Controller boundary","",
              "`2024_2025_PREDICTIVE_OUTCOMES_INSPECTED = false`","",
              "The Controller must decide whether the evidence warrants a later frozen Training Edge definition, whether any stratification is allowed, and when the temporal holdout may be opened.",""]
    return "\n".join(lines)


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--db",type=Path,required=True)
    parser.add_argument("--out-json",type=Path,required=True)
    parser.add_argument("--out-md",type=Path,required=True)
    args=parser.parse_args()
    report=analyze(args.db)
    args.out_json.parent.mkdir(parents=True,exist_ok=True)
    args.out_json.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    args.out_md.write_text(render_markdown(report),encoding="utf-8")
    print(json.dumps({"status":"success","classification":report["classification"],"n":report["population"]["primary_min3"]}))


if __name__=="__main__":
    main()
