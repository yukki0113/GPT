#!/usr/bin/env python3
"""Research-only year stratification of already eligible P1-1 lineage cells.

No predictive use, no as-of proof, no inferential ranking. All row-level
outputs stay in the caller's private output directory.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import duckdb

VERSION = 'brdb-p1-2-annual-stability-v0.1'
TEMPORAL = 'STATIC_LATER_SELECTED_SNAPSHOT_NOT_ASOF_VERIFIED'
KEYS = ('lineage_role','lineage_code','surface_code','distance_band','venue_code','race_class_code')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as fp:
        for b in iter(lambda: fp.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def run(mart, eligible, out, *, mart_sha, eligible_sha, min_annual_n=10, min_baseline_n=50):
    mart, eligible, out = Path(mart), Path(eligible), Path(out)
    if min_annual_n < 1 or min_baseline_n < 1:
        raise ValueError('support thresholds must be positive')
    if sha(mart) != mart_sha or sha(eligible) != eligible_sha:
        raise ValueError('input SHA-256 mismatch')
    with eligible.open(newline='', encoding='utf-8') as fp:
        reader = csv.DictReader(fp)
        if not reader.fieldnames or any(k not in reader.fieldnames for k in KEYS):
            raise ValueError('P1-1 eligible CSV key contract missing')
        selected = list(reader)
    if len(selected) != 1935 or any(row.get('eligibility') != 'DESCRIPTIVE_SAMPLE_OK' for row in selected):
        raise ValueError('wrong P1-1 eligible cohort')
    keys = [tuple(row[k] for k in KEYS) for row in selected]
    if len(set(keys)) != len(keys) or any(not all(key) for key in keys):
        raise ValueError('duplicate or empty P1-1 eligible keys')
    con = duckdb.connect()
    try:
        con.execute("CREATE VIEW mart AS SELECT * FROM read_parquet('" + str(mart).replace("'","''") + "')")
        n = con.execute('SELECT count(*) FROM mart').fetchone()[0]
        if n != 481627:
            raise ValueError('wrong P0-2 cohort')
        violations = con.execute('''SELECT count(*) FROM mart WHERE
            pedigree_temporal_status IS DISTINCT FROM ?
            OR race_year NOT BETWEEN 2016 AND 2025
            OR normal_finisher IS NULL OR winner IS NULL OR top3 IS NULL
            OR (winner AND NOT normal_finisher) OR (top3 AND NOT normal_finisher)
            OR race_key IS NULL OR horse_no IS NULL''', [TEMPORAL]).fetchone()[0]
        if violations:
            raise ValueError('temporal/result contract violations')
        duplicates = con.execute('SELECT count(*) - count(DISTINCT (race_key, horse_no)) FROM mart').fetchone()[0]
        if duplicates:
            raise ValueError('duplicate race-horse keys')
        con.execute('CREATE TEMP TABLE eligible (' + ','.join(k+' VARCHAR' for k in KEYS) + ')')
        con.executemany('INSERT INTO eligible VALUES (?,?,?,?,?,?)', keys)
        con.execute('''CREATE TEMP VIEW classified AS SELECT *, CASE
            WHEN distance_m < 1400 THEN 'LT1400'
            WHEN distance_m < 1800 THEN '1400_1799'
            WHEN distance_m < 2200 THEN '1800_2199'
            WHEN distance_m >= 2200 THEN 'GE2200'
            ELSE 'UNKNOWN' END AS distance_band FROM mart''')
        con.execute('''CREATE TEMP VIEW baseline_year AS SELECT
            race_year, surface_code, distance_band, venue_code, race_class_code,
            count(*) FILTER(WHERE normal_finisher) baseline_n,
            count(*) FILTER(WHERE winner) baseline_wins,
            count(*) FILTER(WHERE top3) baseline_top3
            FROM classified GROUP BY 1,2,3,4,5''')
        con.execute('''CREATE TEMP VIEW roles_year AS
            SELECT race_year,'SIRE' AS lineage_role,sire_line_code lineage_code,
            surface_code,distance_band,venue_code,race_class_code,
            normal_finisher,winner,top3
            FROM classified WHERE pedigree_status='STATIC_ONLY'
            UNION ALL
            SELECT race_year,'BMS',broodmare_sire_line_code,
            surface_code,distance_band,venue_code,race_class_code,
            normal_finisher,winner,top3
            FROM classified WHERE pedigree_status='STATIC_ONLY' ''')
        con.execute('''CREATE TEMP VIEW group_year AS SELECT
            race_year,lineage_role,lineage_code,surface_code,distance_band,
            venue_code,race_class_code,
            count(*) entries,
            count(*) FILTER(WHERE normal_finisher) n,
            count(*) FILTER(WHERE winner) wins,
            count(*) FILTER(WHERE top3) top3
            FROM roles_year WHERE lineage_code IS NOT NULL AND trim(lineage_code)<>''
            GROUP BY 1,2,3,4,5,6,7''')
        results = con.execute('''SELECT e.lineage_role,e.lineage_code,e.surface_code,
            e.distance_band,e.venue_code,e.race_class_code,y.year,
            coalesce(g.entries,0) entries,coalesce(g.n,0) n,
            coalesce(g.wins,0) wins,coalesce(g.top3,0) top3,
            coalesce(b.baseline_n,0) baseline_n,
            coalesce(b.baseline_wins,0) baseline_wins,
            coalesce(b.baseline_top3,0) baseline_top3
            FROM eligible e CROSS JOIN range(2016,2026) y(year)
            LEFT JOIN group_year g ON g.race_year=y.year
              AND g.lineage_role=e.lineage_role AND g.lineage_code=e.lineage_code
              AND g.surface_code=e.surface_code AND g.distance_band=e.distance_band
              AND g.venue_code=e.venue_code AND g.race_class_code=e.race_class_code
            LEFT JOIN baseline_year b ON b.race_year=y.year
              AND b.surface_code=e.surface_code AND b.distance_band=e.distance_band
              AND b.venue_code=e.venue_code AND b.race_class_code=e.race_class_code
            ORDER BY e.lineage_role,e.lineage_code,e.surface_code,
              e.distance_band,e.venue_code,e.race_class_code,y.year''')
        names = [d[0] for d in results.description]
        observations = results.fetchall()
        if len(observations) != 19350:
            raise ValueError('unexpected eligible x year count')
        out.mkdir(parents=True, exist_ok=True)
        years_path = out / 'eligible_group_years.csv'
        output_fields = names + ['win_rate','baseline_win_rate','top3_rate',
                                 'baseline_top3_rate','annual_support','win_direction','top3_direction']
        stats = {key:{'supported':0,'win_above':0,'win_below':0,'top3_above':0,'top3_below':0,'observed':0} for key in keys}
        with years_path.open('w',encoding='utf-8',newline='') as fp:
            writer = csv.DictWriter(fp,fieldnames=output_fields)
            writer.writeheader()
            for value in observations:
                row = dict(zip(names,value))
                key = tuple(row[k] for k in KEYS)
                n,w,t,bn,bw,bt = [row[k] for k in ('n','wins','top3','baseline_n','baseline_wins','baseline_top3')]
                if any(v < 0 for v in (n,w,t,bn,bw,bt)) or w > t or t > n or bw > bt or bt > bn:
                    raise ValueError('invalid winner/top3 bounds')
                supported = n >= min_annual_n and bn >= min_baseline_n
                wr, tr = w/n if n else None, t/n if n else None
                bwr, btr = bw/bn if bn else None, bt/bn if bn else None
                def direction(x,y):
                    if x is None or y is None:
                        return 'INSUFFICIENT_YEAR_SAMPLE'
                    return 'ABOVE' if x>y else ('BELOW' if x<y else 'EQUAL')
                wd = direction(wr,bwr) if supported else 'INSUFFICIENT_YEAR_SAMPLE'
                td = direction(tr,btr) if supported else 'INSUFFICIENT_YEAR_SAMPLE'
                row.update(win_rate=round(wr,6) if wr is not None else '',
                           baseline_win_rate=round(bwr,6) if bwr is not None else '',
                           top3_rate=round(tr,6) if tr is not None else '',
                           baseline_top3_rate=round(btr,6) if btr is not None else '',
                           annual_support='SUFFICIENT_FOR_DESCRIPTION' if supported else 'LOW_SAMPLE',
                           win_direction=wd,top3_direction=td)
                writer.writerow(row)
                st = stats[key]
                if n:
                    st['observed'] += 1
                if supported:
                    st['supported'] += 1
                    st['win_above'] += (wd == 'ABOVE')
                    st['win_below'] += (wd == 'BELOW')
                    st['top3_above'] += (td == 'ABOVE')
                    st['top3_below'] += (td == 'BELOW')
        # Summary deliberately contains no role/code/year group or horse-level rows.
        support_hist = {str(n):sum(s['supported']==n for s in stats.values()) for n in range(11)}
        summary = {
            'status':'PASS','version':VERSION,'research_only':True,'prediction_safe':False,
            'temporal_status':TEMPORAL,'denominator':'NORMAL_FINISHERS_NOT_ACTUAL_STARTERS',
            'baseline':'SAME_YEAR_SURFACE_DISTANCE_BAND_VENUE_CLASS_ALL_NORMAL_FINISHERS',
            'p0_sha256':mart_sha,'p1_eligible_sha256':eligible_sha,
            'years':[2016,2025],'cohort_entries':481627,
            'eligible_groups':len(keys),'annual_rows':len(observations),
            'annual_thresholds':{'min_n':min_annual_n,'min_baseline_n':min_baseline_n},
            'supported_years_histogram':support_hist,
            'groups_with_3plus_supported_years':sum(s['supported']>=3 for s in stats.values()),
            'groups_with_5plus_supported_years':sum(s['supported']>=5 for s in stats.values()),
            'annual_rows_supported':sum(s['supported'] for s in stats.values()),
            'annual_rows_win_above_baseline':sum(s['win_above'] for s in stats.values()),
            'annual_rows_win_below_baseline':sum(s['win_below'] for s in stats.values()),
            'annual_rows_top3_above_baseline':sum(s['top3_above'] for s in stats.values()),
            'annual_rows_top3_below_baseline':sum(s['top3_below'] for s in stats.values()),
            'private_annual_csv_sha256':sha(years_path),
            'notes':['Yearly direction is descriptive and is not evidence of independent predictive stability.',
                     'Eligibility selected using the same 2016–2025 period: in-sample selection bias.',
                     'Repeated starts and multiple comparisons remain unadjusted.',
                     'Static later-selected pedigree snapshot is NOT as-of verified.',
                     'No score, ranking, betting signal, CURRENT or consumer output is produced.']
        }
        (out/'annual_stability_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        return summary
    finally:
        con.close()

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--mart',required=True)
    p.add_argument('--mart-sha256',required=True)
    p.add_argument('--eligible',required=True)
    p.add_argument('--eligible-sha256',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--min-annual-n',type=int,default=10)
    p.add_argument('--min-baseline-n',type=int,default=50)
    a=p.parse_args()
    print(json.dumps(run(a.mart,a.eligible,a.out,mart_sha=a.mart_sha256,
                         eligible_sha=a.eligible_sha256,min_annual_n=a.min_annual_n,
                         min_baseline_n=a.min_baseline_n),ensure_ascii=False,indent=2))
