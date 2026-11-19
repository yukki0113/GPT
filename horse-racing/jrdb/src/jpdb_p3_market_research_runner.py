#!/usr/bin/env python3
"""JPDB P3 real SED market/peer retrospective diagnostic runner.

All historical odds are FINAL archived observations. This is NOT a pre-race
prediction, a causal jockey ability score, or authorization for RaceNote.
Requires private exact SHA-pinned P1.2 inputs and canonical JRDB Parser.
Output is aggregate-only, no source runner rows or jockey rankings.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import tempfile
import zipfile
from datetime import date, timedelta
from pathlib import Path
from statistics import mean

from jpdb_history_reader import JPDBHistoryReaderError, POLICY, sha256
from jpdb_performance_reader_v12 import validate_extended_target
from jpdb_p2_condition_reader import JPDBConditionReader2026
from jpdb_p3_market_baselines import SCHEMA, prepare, validate
from jpdb_p3_condition_robustness import evaluate as evaluate_condition_robustness
from jrdb_raw import Parser, ymd

def quote(path) -> str:
    return "'" + str(path).replace("'", "''") + "'"

def convert_daily_odds(reader, daily_root: Path) -> None:
    db=reader.db
    db.execute("""CREATE TEMP TABLE p3_2026_market (
      race_key_raw VARCHAR,horse_no INTEGER,
      final_win_odds DOUBLE,final_popularity BIGINT)""")
    parser=Parser()
    seen=set()
    with tempfile.TemporaryDirectory(prefix="jpdb-p3-market-") as td:
        path=Path(td)/"daily_market.csv"
        with path.open("w",encoding="utf-8",newline="") as out:
            writer=csv.writer(out)
            writer.writerow(("race_key_raw","horse_no",
                             "final_win_odds","final_popularity"))
            for spec in reader.daily_sources:
                source=Path(daily_root)/spec["name"]
                if source.stat().st_size!=spec["size"] or sha256(source)!=spec["zip_sha256"]:
                    raise JPDBHistoryReaderError("2026 SED byte drift before P3")
                with zipfile.ZipFile(source) as archive:
                    member=spec["name"].replace(".zip",".txt")
                    raw=archive.read(member)
                    if hashlib.sha256(raw).hexdigest()!=spec["sed_member_sha256"] or len(raw)%376:
                        raise JPDBHistoryReaderError("P3 SED member changed")
                    for offset in range(0,len(raw),376):
                        parsed=parser.sed(raw[offset:offset+374])
                        key=(parsed["race_key_raw"],parsed["horse_no"])
                        if not key[0] or key[1] is None or key in seen or ymd(parsed["date_raw"])!=spec["race_date"]:
                            raise JPDBHistoryReaderError("P3 daily SED identity/date mismatch")
                        seen.add(key)
                        values=[*key,parsed["final_win_odds"],parsed["final_popularity"]]
                        writer.writerow(["\\N" if x is None else x for x in values])
        db.execute("COPY p3_2026_market FROM "+quote(path)+
                   " (HEADER TRUE, DELIMITER ',', NULL '\\N')")
    count=db.execute("SELECT COUNT(*) FROM p3_2026_market").fetchone()[0]
    if count!=reader.daily_rows:
        raise JPDBHistoryReaderError("P3 daily odds rows differ from P1.2")
    issues=db.execute("""SELECT
      (SELECT COUNT(*) FROM p3_2026_market m LEFT JOIN sed_2026 s
        USING(race_key_raw,horse_no) WHERE s.race_key_raw IS NULL),
      (SELECT COUNT(*) FROM sed_2026 s LEFT JOIN p3_2026_market m
        USING(race_key_raw,horse_no) WHERE m.race_key_raw IS NULL),
      (SELECT COUNT(*) FROM (SELECT race_key_raw,horse_no
         FROM p3_2026_market GROUP BY 1,2 HAVING COUNT(*)<>1))""").fetchone()
    if any(issues):
        raise JPDBHistoryReaderError("P3 2026 odds join missing/duplicate runners")

def construct_view(reader, input_root: Path, manifest: Path) -> None:
    spec=json.loads(Path(manifest).read_text(encoding="utf-8"))
    paths=[]
    for year in (2023,2024,2025):
        asset=next(x for x in spec["artifacts"] if x["artifact_id"]==f"sed_{year}")
        path=Path(input_root)/f"sed_{year}"/asset["expected_name"]
        if path.stat().st_size!=asset["expected_size"] or sha256(path)!=asset["sha256"]:
            raise JPDBHistoryReaderError("P3 historical immutable SED hash differs")
        paths.append(str(path.resolve()))
    literals=",".join(quote(path) for path in paths)
    reader.db.execute("""CREATE TEMP VIEW p3_all AS
      SELECT race_date,race_key_raw,horse_no,jockey_code,surface_code,
        abnormal_code,finish,field_size,final_win_odds,final_popularity,
        SUBSTR(race_key_raw,1,2) AS venue_code
      FROM read_parquet(["""+literals+"""],union_by_name=true)
      UNION ALL BY NAME
      SELECT s.race_date,s.race_key_raw,s.horse_no,s.jockey_code,s.surface_code,
        s.abnormal_code,s.finish,s.field_size,
        m.final_win_odds,m.final_popularity,
        SUBSTR(s.race_key_raw,1,2) AS venue_code
      FROM sed_2026 s JOIN p3_2026_market m USING(race_key_raw,horse_no)""")

def val(x):
    return None if x is None else round(float(x),6)

def compare_years(db):
    rows=db.execute("""SELECT event_year,jockey_code,surface_code,
        COUNT(*) AS n,100*(SUM(win)-SUM(market_p))/COUNT(*) AS residual_100
      FROM p3_eval WHERE event_year IN ('2024','2025','2026')
      GROUP BY 1,2,3 HAVING COUNT(*)>=100""").fetchall()
    keyed={(year,code,surface):float(residual)
           for year,code,surface,n,residual in rows}
    result=[]
    for previous,current in (("2024","2025"),("2025","2026")):
        pairs=[(value,keyed[(current,code,surface)])
          for (year,code,surface),value in keyed.items()
          if year==previous and (current,code,surface) in keyed]
        corr=None
        if len(pairs)>1:
            a,b=zip(*pairs)
            am,bm=mean(a),mean(b)
            av=sum((v-am)**2 for v in a)
            bv=sum((v-bm)**2 for v in b)
            if av>0 and bv>0:
                corr=sum((x-am)*(y-bm) for x,y in pairs)/math.sqrt(av*bv)
        result.append({
            "prior_year":previous,"next_year":current,
            "paired_rider_surface_groups":len(pairs),
            "min_rides_per_year":100,
            "pearson_market_residual_per100":val(corr),
            "sign_persistent":sum(x*y>0 for x,y in pairs),
            "sign_reversed":sum(x*y<0 for x,y in pairs),
        })
    return result

def inspect(db):
    source=db.execute("""SELECT COUNT(*),COUNT(DISTINCT race_key_raw)
      FROM p3_source""").fetchone()
    yearly=[]
    for year,n,races,w,expect,brier,trained,loo_brier,market_same,top3_brier in db.execute("""
      SELECT event_year,COUNT(*),COUNT(DISTINCT race_key_raw),
        SUM(win),SUM(market_p),
        AVG((win-market_p)*(win-market_p)),
        COUNT(*) FILTER (WHERE empirical_prior_p IS NOT NULL),
        AVG((win-empirical_prior_p)*(win-empirical_prior_p))
          FILTER (WHERE empirical_prior_p IS NOT NULL),
        AVG((win-market_p)*(win-market_p))
          FILTER (WHERE empirical_prior_p IS NOT NULL),
        AVG((top3-empirical_prior_top3_p)*(top3-empirical_prior_top3_p))
          FILTER (WHERE empirical_prior_top3_p IS NOT NULL)
      FROM p3_eval GROUP BY 1 ORDER BY 1""").fetchall():
        yearly.append({
            "year":year,"eligible_starts":n,"eligible_races":races,
            "observed_wins":int(w),"market_expected_wins":val(expect),
            "market_brier":val(brier),
            "earlier_year_leave_rider_out_covered":trained,
            "earlier_year_leave_rider_out_win_brier":val(loo_brier),
            "market_win_brier_same_subset":val(market_same),
            "earlier_year_leave_rider_out_top3_brier":val(top3_brier),
        })
    rejects=db.execute("""SELECT COUNT(*),
        COUNT(*) FILTER(WHERE starts<2),
        COUNT(*) FILTER(WHERE winners<>1),
        COUNT(*) FILTER(WHERE bad_statuses>0),
        COUNT(*) FILTER(WHERE bad_market>0),
        COUNT(*) FILTER(WHERE distinct_dates<>1)
      FROM p3_race""").fetchone()
    popularity=[]
    for y,surface,bucket,n,wins,expected in db.execute("""
      SELECT event_year,surface_code,popularity_bucket,COUNT(*),
        SUM(win),SUM(market_p)
      FROM p3_eval GROUP BY 1,2,3 ORDER BY 1,2,3""").fetchall():
        popularity.append(dict(year=y,surface=surface,bucket=bucket,n=n,
            wins=int(wins),market_expected=val(expected),
            market_residual_per100=val(100*(wins-expected)/n)))
    multiple=db.execute("""SELECT COUNT(*) FROM (
        SELECT event_year,jockey_code,surface_code,venue_code
        FROM p3_eval GROUP BY 1,2,3,4 HAVING COUNT(*)>=30
      )""").fetchone()[0]
    trained=db.execute("""SELECT COUNT(*) FROM p3_eval
      WHERE empirical_prior_p IS NOT NULL""").fetchone()[0]
    return dict(
      flat_population_before_cutoff=int(source[0]),
      flat_races_before_cutoff=int(source[1]),
      earlier_year_empirical_covered_starts=int(trained),
      yearly_diagnostics=yearly,
      population_rejections=dict(zip(
          ("all_flat_races","fewer_than_two_starters","nonunique_winner",
           "status_or_finish_review","incomplete_market","multiple_race_dates"),
          map(int,rejects))),
      popularity_surface_cohort=popularity,
      year_pair_stability=compare_years(db),
      exploratory_rider_venue_surface_cells_n_ge30=int(multiple),
      ability_significance_or_multiple_testing_approved=False,
    )

def run(args):
    if args.output.exists():
        raise FileExistsError("refusing to overwrite immutable research receipt")
    with JPDBConditionReader2026(
        input_root=args.input_root,manifest=args.manifest,
        daily_root=args.daily_root,daily_manifest=args.daily_manifest,
        expected_daily_manifest_sha256=args.expected_daily_manifest_sha256
    ) as reader:
        target=validate_extended_target(args.target_date,
                                        fresh_through=reader.daily_coverage_to)
        convert_daily_odds(reader,args.daily_root)
        construct_view(reader,args.input_root,args.manifest)
        prepare(reader.db,target.isoformat())
        receipt=validate(reader.db,target.isoformat())
        receipt.update(inspect(reader.db))
        receipt['condition_robustness']=evaluate_condition_robustness(reader.db)
        receipt.update({
            "schema_version":SCHEMA,
            "source_generation":"jrdb_normalized_warehouse_v1_2010_2025_g20261118_bacfix",
            "historical_manifest_sha256":reader.manifest_sha256,
            "daily_manifest_sha256":reader.daily_manifest_sha256,
            "asof_policy":POLICY,
            "market_observation_basis":"HISTORICAL_FINAL_ODDS_ARCHIVE; NOT_PRE_RACE_ATTESTED",
            "market_baseline":"normalized 1/final_win_odds per eligible race",
            "empirical_baseline":"prior whole calendar years, popularity bucket x surface, leave evaluated jockey out, min peer_n 100",
            "population":"race-complete, normal/DNF starters, unique winner; review flags exclude whole race",
            "not_authorized":["causal jockey skill","predictive weights","RaceNote P4","PWA","Freeze"],
            "source_rows_exported":False
        })
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(receipt,ensure_ascii=False,
        sort_keys=True,indent=2)+"\n",encoding="utf-8")
    return {key:receipt[key] for key in ("status","source_rows",
        "market_eligible_rows","market_eligible_races",
        "earlier_year_empirical_covered_starts")}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("input-root","manifest","daily-root","daily-manifest","output"):
        parser.add_argument("--"+name,required=True,type=Path)
    parser.add_argument("--expected-daily-manifest-sha256")
    parser.add_argument("--target-date",default="2026-11-16")
    args=parser.parse_args()
    print(json.dumps(run(args),ensure_ascii=False,sort_keys=True))

if __name__=="__main__":
    main()
