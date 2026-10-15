#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import duckdb

from jrdb_race_lap_dataset import build_dataset
from jrdb_raw import Parser, canonical_members, read_fixed_records


def q(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def find_rrdb_root(root: Path) -> Path:
    hits = list(root.rglob("postrace_review/v0_1/current.json"))
    if len(hits) != 1:
        raise RuntimeError(f"unique RRDB current.json required: {hits}")
    return hits[0].parent


def rrdb_paths(rrdb_root: Path, family: str, years: tuple[int, ...]) -> list[Path]:
    out = []
    for year in years:
        hits = list(rrdb_root.glob(f"objects/{family}/year={year}/*.parquet"))
        if len(hits) != 1:
            raise RuntimeError(f"unique {family} {year} parquet required: {hits}")
        out.append(hits[0])
    return out


def distance_bucket(distance: int) -> str:
    if distance <= 1400:
        return "SPRINT"
    if distance <= 1800:
        return "MILE"
    if distance <= 2200:
        return "MIDDLE"
    return "STAYING"


def build_2026_dates(rrdb_root: Path) -> list[str]:
    con = duckdb.connect()
    try:
        hp = rrdb_paths(rrdb_root, "fact_horse_performance", (2026,))[0]
        rows = con.execute(
            f"""SELECT DISTINCT CAST(race_date AS DATE)
                FROM read_parquet({q(hp)})
                WHERE race_date>=DATE '2026-01-01'
                  AND race_date<DATE '2026-10-13'
                  AND surface_code IN ('1','2')
                ORDER BY 1"""
        ).fetchall()
        return [r[0].isoformat() for r in rows]
    finally:
        con.close()


def fetch_inputs(raw_root: Path, rrdb_root: Path) -> dict:
    src = Path(__file__).with_name("fetch_jrdb_history.py")
    common = [sys.executable, str(src), "--output-dir", str(raw_root), "--sleep-seconds", "0.2",
              "--max-retries", "5", "--retry-backoff-seconds", "2"]
    subprocess.run(common + ["--from-year", "2024", "--to-year", "2025", "--kinds", "SED", "HJC"], check=True)
    dates = build_2026_dates(rrdb_root)
    for d in dates:
        subprocess.run(common + ["--date", d, "--kinds", "SED", "HJC"], check=True)
    return {"annual_years":[2024,2025],"daily_2026_dates":dates}


def raw_archives(raw_root: Path, family: str) -> list[Path]:
    root = raw_root / family
    paths = [root / f"{family}_2024.zip", root / f"{family}_2025.zip"]
    paths += sorted(root.glob(f"{family}26*.zip"))
    missing = [p for p in paths[:2] if not p.is_file()]
    if missing:
        raise RuntimeError(f"missing annual archives: {missing}")
    return [p for p in paths if p.is_file()]


def payout_maps(hjc_archives: list[Path]) -> tuple[dict[tuple[str,int],int],dict[tuple[str,int],int]]:
    parser = Parser()
    win: dict[tuple[str,int],int] = {}
    place: dict[tuple[str,int],int] = {}
    seen_races = set()
    for archive in hjc_archives:
        with zipfile.ZipFile(archive) as zf:
            for member in canonical_members(zf, "HJC"):
                for record in read_fixed_records(zf, member, "HJC"):
                    race = parser.hjc(record)
                    key = str(race["race_key_raw"])
                    if key in seen_races:
                        raise RuntimeError(f"duplicate HJC race across archives: {key}")
                    seen_races.add(key)
                    for slot in race["win"]:
                        nums = slot["numbers"]
                        if nums and slot["payout"]:
                            win[(key,int(nums[0]))] = int(slot["payout"])
                    for slot in race["place"]:
                        nums = slot["numbers"]
                        if nums and slot["payout"]:
                            place[(key,int(nums[0]))] = int(slot["payout"])
    return win, place


def write_payout_csv(path: Path, win: dict, place: dict) -> None:
    keys = sorted(set(win)|set(place))
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f); w.writerow(["race_key","horse_no","win_payout","place_payout"])
        for key,horse_no in keys:
            w.writerow([key,horse_no,win.get((key,horse_no)),place.get((key,horse_no))])


def build_lap(raw_root: Path, out: Path) -> tuple[Path,Path]:
    sed = raw_archives(raw_root,"SED")
    lap = out/"race_lap_2024_2026.parquet"
    audit = out/"race_lap_2024_2026.audit.json"
    build_dataset(sed,lap,audit,replace=True)
    return lap,audit


RULES = [
    ("FRONT_BASE","FRONT","base"),
    ("FRONT_EL70","FRONT","el70"),
    ("FRONT_EL80","FRONT","el80"),
    ("FRONT_EL70_LASTBEST70","FRONT","el70_lastbest70"),
    ("FRONT_EL70_SLOPE70","FRONT","el70_slope70"),
    ("FRONT_EL70_DECEL70","FRONT","el70_decel70"),
    ("FRONT_RESCUE","FRONT","rescue"),
    ("REAR_BASE","REAR","base"),
    ("REAR_EL30","REAR","el30"),
    ("REAR_EL20","REAR","el20"),
    ("REAR_EL30_PACEUP30","REAR","el30_paceup30"),
    ("REAR_EL30_SLOPE30","REAR","el30_slope30"),
    ("REAR_EL30_LASTBEST30","REAR","el30_lastbest30"),
    ("REAR_RESCUE","REAR","rescue"),
]


def research(rrdb_root: Path, lap: Path, payout_csv: Path, out: Path) -> None:
    hp = rrdb_paths(rrdb_root,"fact_horse_performance",(2024,2025,2026))
    rc = rrdb_paths(rrdb_root,"fact_race_context",(2024,2025,2026))
    con=duckdb.connect()
    try:
        con.execute("SET threads=4")
        con.execute("CREATE VIEW hp AS SELECT * FROM read_parquet(["+",".join(q(x) for x in hp)+"],union_by_name=true)")
        con.execute("CREATE VIEW rc AS SELECT * FROM read_parquet(["+",".join(q(x) for x in rc)+"],union_by_name=true)")
        con.execute(f"CREATE VIEW lap AS SELECT *, CASE WHEN distance_m<=1400 THEN 'SPRINT' WHEN distance_m<=1800 THEN 'MILE' WHEN distance_m<=2200 THEN 'MIDDLE' ELSE 'STAYING' END distance_bucket FROM read_parquet({q(lap)})")
        con.execute(f"CREATE VIEW payouts AS SELECT * FROM read_csv_auto({q(payout_csv)},header=true,all_varchar=false)")
        con.execute("""
          CREATE VIEW starts0 AS
          SELECT h.*, r.pace_balance_percentile,
                 -h.horse_adjusted_delta_per_1000m performance_signal
          FROM hp h LEFT JOIN rc r USING(race_key)
          WHERE h.surface_code IN ('1','2') AND h.horse_id IS NOT NULL
            AND trim(h.horse_id)<>'' AND coalesce(h.finish,0)>0
            AND coalesce(h.time_sec,0)>0
        """)
        con.execute("""
          CREATE VIEW starts AS
          SELECT *,
            lead(race_date) over w next_race_date,
            lead(race_key) over w next_race_key,
            lead(horse_no) over w next_horse_no,
            lead(finish) over w next_finish,
            lead(performance_signal) over w next_performance_signal
          FROM starts0
          WINDOW w AS (PARTITION BY horse_id ORDER BY race_date,race_key,horse_no)
        """)
        con.execute("""
          CREATE VIEW source AS
          SELECT s.*, l.distance_bucket,l.early_late_delta_sec,l.lap_std_sec,l.lap_range_sec,
                 l.max_decel_sec,l.last_vs_best_sec,l.last3_slope_sec_per_segment,
                 l.pace_up_remaining_furlongs
          FROM starts s JOIN lap l USING(race_key)
          WHERE s.race_date>=DATE '2024-01-01' AND s.race_date<DATE '2026-10-13'
            AND s.next_race_date IS NOT NULL
            AND s.next_race_date>s.race_date
            AND s.next_race_date<=s.race_date+INTERVAL '730 days'
        """)
        # Frozen 2024-2025 race-shape reference thresholds by surface x broad distance bucket.
        con.execute("""
          CREATE VIEW thresholds AS
          SELECT surface_code,distance_bucket,count(*) n,
             quantile_cont(early_late_delta_sec,0.20) el20,
             quantile_cont(early_late_delta_sec,0.30) el30,
             quantile_cont(early_late_delta_sec,0.70) el70,
             quantile_cont(early_late_delta_sec,0.80) el80,
             quantile_cont(last_vs_best_sec,0.30) lb30,
             quantile_cont(last_vs_best_sec,0.70) lb70,
             quantile_cont(last3_slope_sec_per_segment,0.30) sl30,
             quantile_cont(last3_slope_sec_per_segment,0.70) sl70,
             quantile_cont(max_decel_sec,0.70) dec70,
             quantile_cont(pace_up_remaining_furlongs,0.30) pu30
          FROM lap
          WHERE race_date>=DATE '2024-01-01' AND race_date<DATE '2026-01-01'
            AND coverage_status='AVAILABLE'
          GROUP BY 1,2
        """)
        con.execute("""
          CREATE VIEW x AS
          SELECT s.*,t.* EXCLUDE(surface_code,distance_bucket),
             (pace_balance_percentile>=70 AND corner4_frontness>=0.60 AND winner_gap_sec<=0.50) front_base,
             (pace_balance_percentile<=30 AND corner4_frontness<=0.40 AND last3f_speed_percentile>=90) rear_base
          FROM source s JOIN thresholds t USING(surface_code,distance_bucket)
          WHERE t.n>=100
        """)
        unions=[]
        def add(name, family, cond):
            unions.append(f"SELECT *, '{name}' rule_name, '{family}' signal_family FROM x WHERE {cond}")
        add("FRONT_BASE","FRONT","front_base")
        add("FRONT_EL70","FRONT","front_base AND early_late_delta_sec>=el70")
        add("FRONT_EL80","FRONT","front_base AND early_late_delta_sec>=el80")
        add("FRONT_EL70_LASTBEST70","FRONT","front_base AND early_late_delta_sec>=el70 AND last_vs_best_sec>=lb70")
        add("FRONT_EL70_SLOPE70","FRONT","front_base AND early_late_delta_sec>=el70 AND last3_slope_sec_per_segment>=sl70")
        add("FRONT_EL70_DECEL70","FRONT","front_base AND early_late_delta_sec>=el70 AND max_decel_sec>=dec70")
        add("FRONT_RESCUE","FRONT","pace_balance_percentile>=50 AND pace_balance_percentile<70 AND corner4_frontness>=0.60 AND winner_gap_sec<=0.50 AND early_late_delta_sec>=el80 AND (last_vs_best_sec>=lb70 OR last3_slope_sec_per_segment>=sl70)")
        add("REAR_BASE","REAR","rear_base")
        add("REAR_EL30","REAR","rear_base AND early_late_delta_sec<=el30")
        add("REAR_EL20","REAR","rear_base AND early_late_delta_sec<=el20")
        add("REAR_EL30_PACEUP30","REAR","rear_base AND early_late_delta_sec<=el30 AND pace_up_remaining_furlongs<=pu30")
        add("REAR_EL30_SLOPE30","REAR","rear_base AND early_late_delta_sec<=el30 AND last3_slope_sec_per_segment<=sl30")
        add("REAR_EL30_LASTBEST30","REAR","rear_base AND early_late_delta_sec<=el30 AND last_vs_best_sec<=lb30")
        add("REAR_RESCUE","REAR","pace_balance_percentile>30 AND pace_balance_percentile<=50 AND corner4_frontness<=0.40 AND last3f_speed_percentile>=90 AND early_late_delta_sec<=el20 AND (last3_slope_sec_per_segment<=sl30 OR pace_up_remaining_furlongs<=pu30)")
        con.execute("CREATE VIEW matches AS "+" UNION ALL ".join(unions))
        con.execute("""
          CREATE VIEW settled AS
          SELECT m.*,
            CASE WHEN next_race_date<DATE '2026-01-01' THEN 'TRAIN_2024_2025' ELSE 'FORWARD_2026' END period,
            p.win_payout,p.place_payout
          FROM matches m LEFT JOIN payouts p
            ON m.next_race_key=p.race_key AND m.next_horse_no=p.horse_no
          WHERE (m.next_race_date>=DATE '2024-01-01' AND m.next_race_date<DATE '2026-01-01')
             OR (m.next_race_date>=DATE '2026-01-01' AND m.next_race_date<DATE '2026-10-13')
        """)
        con.execute(f"""COPY (
          SELECT period,signal_family,rule_name,count(*) n,count(distinct horse_id) horses,
            avg((next_finish=1)::int)::double win_rate,
            avg((next_finish<=3)::int)::double top3_rate,
            avg(next_performance_signal) mean_next_performance,
            sum(coalesce(win_payout,0))::double/(count(*)*100) win_roi,
            sum(coalesce(place_payout,0))::double/(count(*)*100) place_roi
          FROM settled GROUP BY 1,2,3 ORDER BY 1,2,3
        ) TO {q(out/'rule_summary.csv')} (HEADER,DELIMITER ',')""")
        con.execute(f"""COPY (
          SELECT period,signal_family,rule_name,surface_code,distance_bucket,count(*) n,
            avg((next_finish=1)::int)::double win_rate,
            avg((next_finish<=3)::int)::double top3_rate,
            sum(coalesce(win_payout,0))::double/(count(*)*100) win_roi,
            sum(coalesce(place_payout,0))::double/(count(*)*100) place_roi
          FROM settled GROUP BY 1,2,3,4,5 ORDER BY 1,2,3,4,5
        ) TO {q(out/'rule_by_surface_distance.csv')} (HEADER,DELIMITER ',')""")
        con.execute(f"""COPY (
          SELECT period,rule_name,race_date,race_key,horse_no,horse_id,
            pace_balance_percentile,corner4_frontness,winner_gap_sec,last3f_speed_percentile,
            early_late_delta_sec,last_vs_best_sec,last3_slope_sec_per_segment,max_decel_sec,
            pace_up_remaining_furlongs,next_race_date,next_race_key,next_horse_no,next_finish,
            win_payout,place_payout
          FROM settled ORDER BY period,rule_name,race_date,race_key,horse_no
        ) TO {q(out/'matched_details.csv')} (HEADER,DELIMITER ',')""")
        # baseline-relative lift within period/family.
        con.execute(f"""COPY (
          WITH a AS (
            SELECT period,signal_family,rule_name,count(*) n,
              avg((next_finish=1)::int)::double win_rate,
              avg((next_finish<=3)::int)::double top3_rate,
              avg(next_performance_signal) perf,
              sum(coalesce(win_payout,0))::double/(count(*)*100) win_roi,
              sum(coalesce(place_payout,0))::double/(count(*)*100) place_roi
            FROM settled GROUP BY 1,2,3
          ), b AS (
            SELECT period,signal_family,win_rate base_win,top3_rate base_top3,perf base_perf,
                   win_roi base_win_roi,place_roi base_place_roi
            FROM a WHERE rule_name IN ('FRONT_BASE','REAR_BASE')
          )
          SELECT a.*,a.win_rate-b.base_win win_lift,a.top3_rate-b.base_top3 top3_lift,
            a.perf-b.base_perf perf_lift,a.win_roi-b.base_win_roi win_roi_delta,
            a.place_roi-b.base_place_roi place_roi_delta
          FROM a JOIN b USING(period,signal_family)
          ORDER BY period,signal_family,rule_name
        ) TO {q(out/'rule_lift_vs_current.csv')} (HEADER,DELIMITER ',')""")
        con.execute(f"""COPY (
          SELECT * FROM thresholds ORDER BY surface_code,distance_bucket
        ) TO {q(out/'frozen_thresholds_2024_2025.csv')} (HEADER,DELIMITER ',')""")
        meta={
          "status":"PASS",
          "train_outcome_period":["2024-01-01","2025-12-31"],
          "forward_outcome_period":["2026-01-01","2026-10-12"],
          "threshold_reference":["2024-01-01","2025-12-31"],
          "normalization":"surface_code x distance_bucket",
          "distance_buckets":{"SPRINT":"<=1400","MILE":"1500-1800","MIDDLE":"1900-2200","STAYING":">=2300"},
          "minimum_reference_races_per_group":100,
          "rules":[r[0] for r in RULES],
          "settled_rows":con.execute("SELECT count(*) FROM settled").fetchone()[0],
          "source_rows":con.execute("SELECT count(*) FROM source").fetchone()[0],
          "race_lap_rows":con.execute("SELECT count(*) FROM lap").fetchone()[0],
        }
        (out/"summary.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2)+"\n")
    finally:
        con.close()


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--rrdb-zip",type=Path,required=True)
    ap.add_argument("--work-root",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--skip-fetch",action="store_true")
    ap.add_argument("--prebuilt-lap",type=Path)
    ap.add_argument("--prebuilt-payouts",type=Path)
    ap.add_argument("--prebuilt-lap-audit",type=Path)
    a=ap.parse_args()
    a.work_root.mkdir(parents=True,exist_ok=True); a.out.mkdir(parents=True,exist_ok=True)
    rr=a.work_root/"rrdb"
    if rr.exists():
        import shutil; shutil.rmtree(rr)
    rr.mkdir()
    with zipfile.ZipFile(a.rrdb_zip) as zf: zf.extractall(rr)
    rrdb_root=find_rrdb_root(rr)
    raw=a.work_root/"raw"
    if a.prebuilt_lap and a.prebuilt_payouts:
        if not a.prebuilt_lap.is_file() or not a.prebuilt_payouts.is_file():
            raise RuntimeError("prebuilt lap/payout inputs missing")
        fetch_meta={"skipped":True,"source":"prebuilt_artifact"}
        lap=a.prebuilt_lap
        payout_csv=a.prebuilt_payouts
        audit=a.prebuilt_lap_audit
    else:
        fetch_meta = {"skipped":True} if a.skip_fetch else fetch_inputs(raw,rrdb_root)
        lap,audit=build_lap(raw,a.out)
        win,place=payout_maps(raw_archives(raw,"HJC"))
        payout_csv=a.out/"payouts.csv"; write_payout_csv(payout_csv,win,place)
    research(rrdb_root,lap,payout_csv,a.out)
    meta=json.loads((a.out/"summary.json").read_text())
    meta["fetch"]=fetch_meta
    if audit and Path(audit).is_file():
        meta["race_lap_audit"]=json.loads(Path(audit).read_text())
    (a.out/"summary.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(meta,ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
