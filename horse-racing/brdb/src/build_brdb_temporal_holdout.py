#!/usr/bin/env python3
"""BRDB research-only chronological holdout audit; NOT a prediction backtest.

Discovery uses only 2016-2020 records. 2021-2022 gates direction/support.
2023-2025 is read only after discovery and validation decisions are frozen.
Horse-cluster sandwich uncertainty; BH FDR for discovery and final holdout.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import duckdb

VERSION = 'brdb-p1-3-temporal-holdout-v0.1'
TEMPORAL = 'STATIC_LATER_SELECTED_SNAPSHOT_NOT_ASOF_VERIFIED'
KEYS = ('lineage_role', 'lineage_code', 'surface_code', 'distance_band', 'venue_code', 'race_class_code')
PERIODS = {'train': (2016, 2020), 'validation': (2021, 2022), 'test': (2023, 2025)}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def bh(pvalues):
    """Stable monotone Benjamini-Hochberg q-values without optional deps."""
    if not pvalues:
        return []
    n=len(pvalues)
    if any(not math.isfinite(x) or x<0 or x>1 for x in pvalues):
        raise ValueError('invalid p-value')
    order=sorted(range(n), key=lambda i:(pvalues[i],i))
    out=[1.0]*n
    running=1.0
    for rank_index in range(n-1,-1,-1):
        i=order[rank_index]
        running=min(running,pvalues[i]*n/(rank_index+1))
        out[i]=running
    return out


def p_two_sided(z):
    return math.erfc(abs(z)/math.sqrt(2))


def p_one_sided_signed(z):
    return 0.5*math.erfc(z/math.sqrt(2))


def independent_years_and_horses(con, period):
    """Year and unique-horse counts independent of fitted model/other periods."""
    return con.execute('''SELECT r.lineage_role,r.lineage_code,r.surface_code,r.distance_band,
       r.venue_code,r.race_class_code,count(DISTINCT r.race_year) AS years,
       count(DISTINCT r.horse_id) AS horses
       FROM roles r WHERE period=? GROUP BY 1,2,3,4,5,6''', [period]).fetchall()


def run(mart, out, *, expected_sha, min_train_n=100, min_train_years=3,
        min_valid_n=30, min_test_n=50, min_baseline_n=150, alpha=0.05):
    mart, out = Path(mart), Path(out)
    if sha(mart) != expected_sha:
        raise ValueError('P0-2 mart SHA mismatch')
    if min_train_n < 1 or min_train_years not in range(1,6) or min_valid_n < 1 or min_test_n < 1 or min_baseline_n < 1:
        raise ValueError('invalid support threshold')
    if not 0 < alpha < 1:
        raise ValueError('invalid alpha')
    out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute('SET threads=1')  # fixed reduction order for audit reproducibility
    try:
        con.execute("CREATE VIEW mart AS SELECT * FROM read_parquet('" + str(mart).replace("'", "''") + "')")
        if con.execute('SELECT count(*) FROM mart').fetchone()[0] != 481627:
            raise ValueError('wrong cohort total')
        bad = con.execute('''SELECT count(*) FROM mart WHERE
           race_year NOT BETWEEN 2016 AND 2025 OR
           pedigree_temporal_status IS DISTINCT FROM ? OR
           horse_id IS NULL OR trim(horse_id)='' OR
           race_key IS NULL OR horse_no IS NULL OR
           normal_finisher IS NULL OR winner IS NULL OR top3 IS NULL OR
           (winner AND NOT top3) OR (winner AND NOT normal_finisher) OR (top3 AND NOT normal_finisher)''', [TEMPORAL]).fetchone()[0]
        if bad or con.execute('SELECT count(*) - count(DISTINCT (race_key,horse_no)) FROM mart').fetchone()[0]:
            raise ValueError('bad temporal, key, lineage or result guard')
        con.execute('''CREATE TEMP TABLE base AS SELECT *, CASE
           WHEN distance_m < 1400 THEN 'LT1400'
           WHEN distance_m < 1800 THEN '1400_1799'
           WHEN distance_m < 2200 THEN '1800_2199'
           WHEN distance_m >= 2200 THEN 'GE2200' ELSE 'UNKNOWN' END distance_band,
           CASE WHEN race_year <= 2020 THEN 'train'
                WHEN race_year <= 2022 THEN 'validation' ELSE 'test' END period
           FROM mart''')
        con.execute('''CREATE TEMP VIEW roles AS
          SELECT period, race_year,'SIRE' lineage_role, sire_line_code lineage_code,
             surface_code,distance_band,venue_code,race_class_code,horse_id,
             normal_finisher, winner,top3 FROM base WHERE pedigree_status='STATIC_ONLY'
          UNION ALL
          SELECT period,race_year,'BMS',broodmare_sire_line_code,
             surface_code,distance_band,venue_code,race_class_code,horse_id,
             normal_finisher,winner,top3 FROM base WHERE pedigree_status='STATIC_ONLY' ''')
        # Conditions include all normal finishers whether a pedigree lineage is available.
        context = ('period', 'surface_code', 'distance_band', 'venue_code', 'race_class_code')
        group = ('period',) + KEYS
        keys_sql = ','.join(group)
        ctx_sql = ','.join(context)
        con.execute('''CREATE TEMP TABLE condition_horse AS SELECT ''' + ctx_sql + ''',horse_id,
           count(*) FILTER (WHERE normal_finisher) n,
           count(*) FILTER (WHERE winner) wins,
           count(*) FILTER (WHERE top3) top3
           FROM base GROUP BY ''' + ctx_sql + ''',horse_id''')
        con.execute('''CREATE TEMP TABLE role_horse AS SELECT ''' + keys_sql + ''',horse_id,
           count(*) FILTER (WHERE normal_finisher) n,
           count(*) FILTER (WHERE winner) wins,
           count(*) FILTER (WHERE top3) top3
           FROM roles WHERE lineage_code IS NOT NULL AND trim(lineage_code)<>''
           GROUP BY ''' + keys_sql + ''',horse_id''')
        con.execute('''CREATE TEMP TABLE condition_stats AS SELECT ''' + ctx_sql + ''',
           sum(n)::DOUBLE bn,sum(wins)::DOUBLE bw,sum(top3)::DOUBLE bt
           FROM condition_horse GROUP BY ''' + ctx_sql)
        con.execute('''CREATE TEMP TABLE group_stats AS SELECT ''' + keys_sql + ''',
           sum(n)::DOUBLE n,sum(wins)::DOUBLE wins,sum(top3)::DOUBLE top3,
           count(*)::BIGINT horses
           FROM role_horse GROUP BY ''' + keys_sql)
        con.execute('''CREATE TEMP TABLE joined_stats AS SELECT g.*,b.bn,b.bw,b.bt,
           g.wins/nullif(g.n,0) AS pgw,g.top3/nullif(g.n,0) AS pgt,
           b.bw/nullif(b.bn,0) AS pbw,b.bt/nullif(b.bn,0) AS pbt
           FROM group_stats g JOIN condition_stats b USING (''' + ctx_sql + ''')''')
        # Horse-level cluster covariance adjusts repeated horse starts. The baseline
        # includes the lineage, so the cross-covariance term is mandatory.
        con.execute('''CREATE TEMP TABLE baseline_var AS SELECT s.period,s.surface_code,
           s.distance_band,s.venue_code,s.race_class_code,
           sum(pow(h.wins - s.bw/nullif(s.bn,0)*h.n,2)) / nullif(pow(s.bn,2),0) AS vw,
           sum(pow(h.top3 - s.bt/nullif(s.bn,0)*h.n,2)) / nullif(pow(s.bn,2),0) AS vt
           FROM condition_horse h JOIN condition_stats s USING (''' + ctx_sql + ''')
           GROUP BY s.period,s.surface_code,s.distance_band,s.venue_code,s.race_class_code,
                    s.bn,s.bw,s.bt''')
        con.execute('''CREATE TEMP TABLE group_var AS SELECT ''' + ','.join('s.' + k for k in group) + ''',
           sum(pow(h.wins - s.pgw*h.n,2))/nullif(pow(s.n,2),0) AS vw,
           sum(pow(h.top3 - s.pgt*h.n,2))/nullif(pow(s.n,2),0) AS vt,
           sum((h.wins-s.pgw*h.n)*(b.wins-s.pbw*b.n))/nullif(s.n*s.bn,0) AS cw,
           sum((h.top3-s.pgt*h.n)*(b.top3-s.pbt*b.n))/nullif(s.n*s.bn,0) AS ct
           FROM role_horse h JOIN joined_stats s USING (''' + keys_sql + ''')
           JOIN condition_horse b USING (''' + ','.join(context+('horse_id',)) + ''')
           WHERE s.n>0 AND s.bn>0
           GROUP BY ''' + ','.join('s.' + k for k in group) + ''',s.n,s.bn''')
        result = con.execute('''SELECT s.*,v.vw + b.vw - 2*v.cw AS variance_win,
           v.vt + b.vt - 2*v.ct AS variance_top3
           FROM joined_stats s
           LEFT JOIN group_var v USING (''' + keys_sql + ''')
           JOIN baseline_var b USING (''' + ctx_sql + ''')
           ORDER BY s.lineage_role,s.lineage_code,s.surface_code,s.distance_band,
             s.venue_code,s.race_class_code,s.period''')
        cols = [x[0] for x in result.description]
        rows = [dict(zip(cols, r)) for r in result.fetchall()]
        yrs = {}
        for period in PERIODS:
            for r in independent_years_and_horses(con,period):
                yrs[(period,) + tuple(r[:6])] = (r[6],r[7])
        by_key = {}
        for r in rows:
            key = tuple(r[k] for k in KEYS)
            r['observed_years'],r['unique_horses'] = yrs.get((r['period'],)+key, (0,0))
            by_key.setdefault(key,{})[r['period']] = r
        # Train-only support selection. No P1-1 10-year eligible list may be read.
        candidates = []
        for key,p in by_key.items():
            r=p.get('train')
            if r and r['n'] >= min_train_n and r['observed_years']>= min_train_years and r['bn']>=min_baseline_n:
                candidates.append((key,p))
        # p-values: 2 endpoints x all train support candidates, BH within one family.
        tests = []
        for key,p in candidates:
            for outcome in ('win','top3'):
                r=p['train']
                d = float(r['pgw']-r['pbw']) if outcome=='win' else float(r['pgt']-r['pbt'])
                v = r['variance_win' if outcome=='win' else 'variance_top3']
                if v is None or not math.isfinite(v) or v <= 0:
                    z, pv = None, 1.0
                else:
                    z=d / math.sqrt(max(v,0))
                    pv=p_two_sided(z)
                tests.append({'key':key,'outcome':outcome,'train_effect':d,
                              'train_p':pv,'train_z':z,'periods':p})
        q = bh([t['train_p'] for t in tests])
        for t,adj in zip(tests,q):
            t['train_q']=adj
            t['discovered']=(adj<=0.10 and t['train_effect']!=0)
            v=t['periods'].get('validation')
            s=t['outcome']
            effect_key=('pgw','pbw') if s=='win' else ('pgt','pbt')
            t['validation_effect']=float(v[effect_key[0]]-v[effect_key[1]]) if v and v['n'] else None
            t['validation_pass']=bool(t['discovered'] and v and v['n']>=min_valid_n and
               v['bn']>=min_baseline_n and t['validation_effect'] is not None and
               t['validation_effect']*t['train_effect']>0)
        frozen=[t for t in tests if t['validation_pass']]
        # Test-set data are consulted only for frozen hypotheses.
        for t in frozen:
            r=t['periods'].get('test')
            s=t['outcome']
            a,b=('pgw','pbw') if s=='win' else ('pgt','pbt')
            t['test_n']=int(r['n']) if r else 0
            t['test_baseline_n']=int(r['bn']) if r else 0
            eligible = bool(r and r['n']>=min_test_n and r['bn']>=min_baseline_n)
            t['test_supported']=eligible
            if eligible:
                eff=float(r[a]-r[b]);v=r['variance_win' if s=='win' else 'variance_top3']
                se=math.sqrt(max(float(v),0)) if v is not None and math.isfinite(v) and v>0 else None
                t['test_effect']=eff;t['test_se']=se
                t['test_ci95']=(eff-1.96*se,eff+1.96*se) if se is not None else None
                # Directional replication is a pre-specified one-sided test.
                t['test_p_one_sided']=p_one_sided_signed(math.copysign(eff/se,t['train_effect'])) if se else 1.0
            else:
                t['test_effect']=None;t['test_se']=None;t['test_ci95']=None;t['test_p_one_sided']=1.0
        # Each retained hypothesis enters family, including failed support (p=1).
        test_q=bh([t['test_p_one_sided'] for t in frozen])
        for t,qv in zip(frozen,test_q):
            t['test_q']=qv
            t['test_pass']=(t['test_supported'] and qv<=alpha and
                t['test_effect'] is not None and t['test_effect']*t['train_effect']>0)
        # No horse/lineage identifiers in public aggregate summary.
        private=out/'hypotheses_private.csv'
        fields=list(KEYS)+['endpoint','train_n','train_years','train_effect','train_p','train_q',
           'discovered','validation_n','validation_effect','validation_pass','test_n',
           'test_supported','test_effect','test_se','test_ci_low','test_ci_high',
           'test_p_one_sided','test_q','test_pass']
        with private.open('w',newline='',encoding='utf-8') as fp:
            w=csv.DictWriter(fp,fieldnames=fields);w.writeheader()
            for t in tests:
                p=t['periods'];v=p.get('validation');r=p.get('test');ci=t.get('test_ci95')
                row=dict(zip(KEYS,t['key']))
                row.update(endpoint=t['outcome'],train_n=int(p['train']['n']),
                   train_years=p['train']['observed_years'],train_effect=t['train_effect'],
                   train_p=t['train_p'],train_q=t['train_q'],discovered=t['discovered'],
                   validation_n=int(v['n']) if v else 0,
                   validation_effect=t['validation_effect'],validation_pass=t['validation_pass'],
                   test_n=int(r['n']) if r else 0,test_supported=t.get('test_supported','NOT_OPENED'),
                   test_effect=t.get('test_effect'),test_se=t.get('test_se'),
                   test_ci_low=ci[0] if ci else None,test_ci_high=ci[1] if ci else None,
                   test_p_one_sided=t.get('test_p_one_sided'),test_q=t.get('test_q'),
                   test_pass=t.get('test_pass','NOT_OPENED'))
                w.writerow(row)
        summary={'status':'PASS','version':VERSION,'research_only':True,'prediction_safe':False,
          'temporal_status':TEMPORAL,'outcome_denominator':'NORMAL_FINISHERS_NOT_ACTUAL_STARTERS',
          'mart_sha256':expected_sha,'cohort_entries':481627,'splits':PERIODS,
          'baseline':'SAME_PERIOD_CONDITION_ALL_NORMAL_FINISHERS_INCLUDES_GROUP',
          'train_eligibility':{'min_n':min_train_n,'min_years':min_train_years,'min_baseline_n':min_baseline_n},
          'validation_eligibility':{'min_n':min_valid_n,'min_baseline_n':min_baseline_n},
          'test_eligibility':{'min_n':min_test_n,'min_baseline_n':min_baseline_n},
          'all_period_groups':len(by_key),'train_support_groups':len(candidates),
          'train_tests':len(tests),'train_bh_q_threshold':0.10,
          'train_discoveries':sum(t['discovered'] for t in tests),
          'validation_direction_supported':len(frozen),
          'test_supported':sum(t.get('test_supported',False)==True for t in frozen),
          'test_bh_q_threshold':alpha,
          'test_confirmed':sum(t.get('test_pass',False)==True for t in frozen),
          'private_hypotheses_sha256':sha(private),
          'multiple_comparisons':'BH over both outcomes and all train eligible tests; separately over frozen validation-passing test family, unsupported test assigned p=1',
          'uncertainty':'horse-level cluster sandwich; normal approximation, unadjusted race cluster dependence',
          'limitations':['Chronological holdout uses retrospective static later-selected pedigree. This is not a leakage-free pre-race backtest.',
            'Horse-cluster SE handles repeated starts, not race-level common shocks, multi-year drift, or all cross-horse dependencies.',
            'Repeated horses can appear across years and across train/validation/test; temporal evaluation is not independent-horse holdout.',
            'Train discovery and validation gate use historical outcomes; only 2023-2025 holdout is outcome-sequestered until gate.',
            'A BH-positive association is descriptive, not proven practical or causal predictive value.',
            'No automatic scoring, ranking, betting, CURRENT, RaceNote or PWA integration.']}
        (out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False,sort_keys=True)+'\n')
        return summary
    finally:
        con.close()


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--mart',required=True)
    p.add_argument('--mart-sha256',required=True)
    p.add_argument('--out',required=True)
    a=p.parse_args()
    print(json.dumps(run(a.mart,a.out,expected_sha=a.mart_sha256),indent=2,ensure_ascii=False))
