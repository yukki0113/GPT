#!/usr/bin/env python3
"""BRDB P1-1 research-only descriptive lineage × condition statistics.

Uses a SHA-pinned P0-2 mart; NEVER treat static pedigree as as-of prediction.
The denominator is NORMAL FINISHERS, not all actual starters.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import duckdb

VERSION = "brdb-p1-1-descriptive-v0.1"
TEMPORAL_LABEL = "STATIC_LATER_SELECTED_SNAPSHOT_NOT_ASOF_VERIFIED"

def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()

def wilson(success, n, z=1.96):
    if n == 0:
        return (None, None)
    p = success / n
    center = (p + z*z/(2*n)) / (1+z*z/n)
    radius = z*((p*(1-p)/n + z*z/(4*n*n))**0.5)/(1+z*z/n)
    return round(center-radius, 6), round(center+radius, 6)

def run(mart, output, *, expected_sha, min_n=100, min_years=3):
    mart, output = Path(mart), Path(output)
    if sha(mart) != expected_sha:
        raise ValueError("P0-2 input SHA mismatch")
    c = duckdb.connect()
    try:
        escaped = str(mart).replace("'", "''")
        c.execute("CREATE VIEW mart AS SELECT * FROM read_parquet('" + escaped + "')")
        total = c.execute("SELECT count(*) FROM mart").fetchone()[0]
        if total != 481627:
            raise ValueError("unexpected P0-2 cohort size")
        bad = c.execute("""SELECT count(*) FROM mart WHERE
            pedigree_temporal_status IS DISTINCT FROM ?
            OR race_year NOT BETWEEN 2016 AND 2025
            OR normal_finisher IS NULL OR winner IS NULL OR top3 IS NULL
            OR (winner AND NOT normal_finisher) OR (top3 AND NOT normal_finisher)""",
            [TEMPORAL_LABEL]).fetchone()[0]
        if bad:
            raise ValueError("temporal/result contract violations: " + str(bad))
        duplicates = c.execute(
            "SELECT count(*)-count(DISTINCT (race_key,horse_no)) FROM mart"
        ).fetchone()[0]
        if duplicates:
            raise ValueError("duplicate race-horse keys: " + str(duplicates))
        c.execute("""CREATE VIEW classified AS SELECT *,
            CASE WHEN distance_m < 1400 THEN 'LT1400'
            WHEN distance_m < 1800 THEN '1400_1799'
            WHEN distance_m < 2200 THEN '1800_2199'
            WHEN distance_m >= 2200 THEN 'GE2200'
            ELSE 'UNKNOWN' END AS distance_band
            FROM mart""")
        c.execute("""CREATE VIEW baseline AS SELECT surface_code,distance_band,
            venue_code,race_class_code,
            count(*) FILTER (WHERE normal_finisher) AS baseline_n,
            count(*) FILTER (WHERE winner) AS baseline_wins,
            count(*) FILTER (WHERE top3) AS baseline_top3,
            count(*) AS baseline_entries
            FROM classified GROUP BY 1,2,3,4""")
        c.execute("""CREATE VIEW roles AS
            SELECT 'SIRE' AS lineage_role, sire_line_code AS lineage_code,
              surface_code,distance_band,venue_code,race_class_code,
              race_year,horse_id,normal_finisher,winner,top3
            FROM classified WHERE pedigree_status='STATIC_ONLY'
            UNION ALL
            SELECT 'BMS',broodmare_sire_line_code,
              surface_code,distance_band,venue_code,race_class_code,
              race_year,horse_id,normal_finisher,winner,top3
            FROM classified WHERE pedigree_status='STATIC_ONLY'""")
        sql = """SELECT g.*, b.baseline_n,b.baseline_wins,b.baseline_top3,
                   b.baseline_entries
            FROM (SELECT lineage_role,lineage_code,surface_code,distance_band,
                 venue_code,race_class_code,
                 count(*) AS entries,count(DISTINCT horse_id) AS unique_horses,
                 count(DISTINCT race_year) AS observed_years,
                 count(*) FILTER (WHERE normal_finisher) AS n,
                 count(*) FILTER (WHERE winner) AS wins,
                 count(*) FILTER (WHERE top3) AS top3
                 FROM roles WHERE lineage_code IS NOT NULL
                   AND trim(lineage_code)<>''
                 GROUP BY 1,2,3,4,5,6) g
            JOIN baseline b USING (surface_code,distance_band,venue_code,race_class_code)
            ORDER BY g.lineage_role,g.lineage_code,g.surface_code,
                     g.distance_band,g.venue_code,g.race_class_code"""
        result = c.execute(sql)
        columns = [d[0] for d in result.description]
        rows = result.fetchall()
        output.mkdir(parents=True, exist_ok=True)
        extra = ['win_rate','top3_rate','baseline_win_rate','baseline_top3_rate',
                 'win_lift','top3_lift','win_wilson_low','win_wilson_high',
                 'top3_wilson_low','top3_wilson_high','eligibility']
        files = [output/'lineage_conditions_all.csv',
                 output/'lineage_conditions_eligible.csv']
        good = 0
        with files[0].open('w', newline='', encoding='utf-8') as a, files[1].open(
            'w', newline='', encoding='utf-8'
        ) as b:
            writers = [csv.DictWriter(f, fieldnames=columns+extra) for f in (a,b)]
            for writer in writers: writer.writeheader()
            for row in rows:
                r = dict(zip(columns,row))
                n,w,t,bn,bw,bt = (r[k] for k in
                    ('n','wins','top3','baseline_n','baseline_wins','baseline_top3'))
                wr = w/n if n else None
                tr = t/n if n else None
                bwr = bw/bn if bn else None
                btr = bt/bn if bn else None
                lo,hi = wilson(w,n)
                lo3,hi3 = wilson(t,n)
                ok = n >= min_n and r['observed_years'] >= min_years and bn > 0
                r.update(win_rate=round(wr,6) if wr is not None else '',
                    top3_rate=round(tr,6) if tr is not None else '',
                    baseline_win_rate=round(bwr,6) if bwr is not None else '',
                    baseline_top3_rate=round(btr,6) if btr is not None else '',
                    win_lift=round(wr/bwr,6) if bwr and wr is not None else '',
                    top3_lift=round(tr/btr,6) if btr and tr is not None else '',
                    win_wilson_low=lo if lo is not None else '',
                    win_wilson_high=hi if hi is not None else '',
                    top3_wilson_low=lo3 if lo3 is not None else '',
                    top3_wilson_high=hi3 if hi3 is not None else '',
                    eligibility='DESCRIPTIVE_SAMPLE_OK' if ok else 'LOW_SAMPLE')
                writers[0].writerow(r)
                if ok:
                    writers[1].writerow(r)
                    good += 1
        base = c.execute("""SELECT surface_code,distance_band,count(*) entries,
             count(*) FILTER (WHERE normal_finisher) normal_finishers,
             count(*) FILTER (WHERE winner) wins,
             count(*) FILTER (WHERE top3) top3
             FROM classified GROUP BY 1,2 ORDER BY 1,2""")
        index = [dict(zip([x[0] for x in base.description],r)) for r in base.fetchall()]
        base_path = output/'baseline_surface_distance.json'
        base_path.write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')
        audit = {
            'status':'PASS','version':VERSION,'research_only':True,'prediction_safe':False,
            'input_sha256':expected_sha,'total_entries':total,
            'normal_finishers':c.execute('SELECT count(*) FROM mart WHERE normal_finisher').fetchone()[0],
            'baseline_surface_distance':index,
            'groups_all':len(rows),'groups_eligible':good,
            'filters':{'min_n':min_n,'min_years':min_years},
            'denominator':'NORMAL_FINISHERS_NOT_ALL_STARTERS',
            'baseline':'SAME_SURFACE_DISTANCE_BAND_VENUE_CLASS_ALL_NORMAL_FINISHERS',
            'identities':'SIRE_AND_BMS_OFFICIAL_LINEAGE_CODES_ONLY',
            'temporal_status':TEMPORAL_LABEL,
            'interval':'WILSON_95_PERCENT_DESCRIPTIVE_NOT_MULTIPLE_TEST_ADJUSTED',
            'notes':['No horse-name identity inference; no regional-root inference.',
                'Rates and lifts are descriptive historical associations, not validated predictive aptitude.',
                'Repeated starts of the same horse are not independent; Wilson ranges are indicative only.',
                'No multiple-testing correction or race-date as-of verification; do not rank for betting.',
                'Venue/race class codes retained as JRDB codes; no invented labels.'],
            'output_sha256':{p.name:sha(p) for p in files+[base_path]}}
        (output/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,
                                                    sort_keys=True,indent=2)+'\n')
        return audit
    finally:
        c.close()

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--mart',required=True)
    p.add_argument('--sha256',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--min-n',type=int,default=100)
    p.add_argument('--min-years',type=int,default=3)
    a = p.parse_args()
    print(json.dumps(run(a.mart,a.out,expected_sha=a.sha256,
                         min_n=a.min_n,min_years=a.min_years),ensure_ascii=False,indent=2))
