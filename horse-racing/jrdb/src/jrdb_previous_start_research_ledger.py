#!/usr/bin/env python3
"""All-entrant previous-start ledger. HV rules never filter the population.

Example: python jrdb_previous_start_research_ledger.py --input-dir INPUT
  --current-zip RaceReviewDB_CURRENT.zip --rule-zip frozen_rules.zip
  --output-dir OUTPUT --source-commit SHA
Input directory contains matched PACI/SED ZIPs for the ten September dates.
Features are materialized and hashed before settlement is parsed or joined.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import zipfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from jrdb_raw import Parser, ReaderAudit, iter_archive_records, race_horse_key
from jrdb_postrace_review import normalize_class_group
from jrdb_postrace_review_standard import percentile_rank
from jrdb_next_watch_reverse import _race_review_root, _relation_paths, _table_sql
from jrdb_next_watch_rules import grade_matched_rules

VERSION = "rrdb-all-runner-time-pace-v0.1"
DATES = ["2026-09-" + x for x in ("05", "06", "12", "13", "19", "20", "21", "22", "26", "27")]
CONTEXT_FIELDS = ["first3f_reference_sec", "last3f_reference_sec", "pace_balance_sec",
                  "pace_balance_percentile", "pace_shape", "pace_sample_count", "pace_scope_level"]
IDENTITY_MAP = {"race_date": "previous_race_date", "race_key": "previous_race_key",
                "race_horse_key": "previous_race_horse_key", "finish": "previous_finish",
                "surface_code": "previous_surface_code", "distance_m": "previous_distance_m",
                "field_size": "previous_field_size", "declared_class_group": "previous_declared_class_group"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str, allow_nan=False) + "\n", encoding="utf-8")


def build_features(entrants, hp, rc, rr, rules, connection):
    """Only entrants and historical facts enter this function; no target results."""
    connection.register("entrants", entrants)
    connection.execute(f"""CREATE OR REPLACE TEMP VIEW hp_valid AS
      SELECT *, -horse_adjusted_delta_per_1000m AS performance_signal,
      AVG(-horse_adjusted_delta_per_1000m) OVER (PARTITION BY horse_id
      ORDER BY race_date, race_key, horse_no ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) AS prior3_performance_mean,
      AVG(last3f_speed_percentile) OVER (PARTITION BY horse_id
      ORDER BY race_date, race_key, horse_no ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) AS prior3_last3f_pct_mean
      FROM {hp} WHERE horse_id IS NOT NULL AND TRIM(horse_id) <> ''
      AND COALESCE(finish,0)>0 AND COALESCE(time_sec,0)>0 AND surface_code IN ('1','2')
      AND venue_code IN ('01','02','03','04','05','06','07','08','09','10')""")
    hidden = [r for r in rules["frozen_rules"] if r["track"] == "hidden_value"]
    rule_select = ",".join(f"COALESCE(({r['condition']}),FALSE) AS match_{r['rule_id']}" for r in hidden)
    frame = connection.execute(f"""WITH previous AS (
      SELECT *, performance_signal-prior3_performance_mean AS performance_vs_prior3,
      last3f_speed_percentile-prior3_last3f_pct_mean AS last3f_pct_vs_prior3 FROM hp_valid),
      flagged AS (SELECT *, {rule_select} FROM previous)
      SELECT e.*, p.* EXCLUDE(horse_id,horse_name,venue_code,horse_no,pace_shape,{','.join(IDENTITY_MAP)}),
      {','.join('p.'+k+' AS '+v for k,v in IDENTITY_MAP.items())},
      {','.join('c.'+f for f in CONTEXT_FIELDS)},
      r.standard_sample_start_date,r.standard_sample_end_date,r.standard_sample_count,r.time_delta_basis
      FROM entrants e LEFT JOIN flagged p
      ON e.horse_id=p.horse_id AND p.race_date<CAST(e.target_date AS DATE)
      LEFT JOIN {rc} c ON p.race_key=c.race_key
      LEFT JOIN {rr} r ON p.race_key=r.race_key
      QUALIFY ROW_NUMBER() OVER (PARTITION BY e.target_race_horse_key
      ORDER BY p.race_date DESC,p.race_key DESC)=1
      ORDER BY e.target_date,e.target_race_horse_key""").fetchdf()
    frame["has_previous_rrdb_start"] = frame.previous_race_key.notna().astype(int)
    for name, series in {
        "front_pace_strength": frame.pace_balance_percentile / 100,
        "rear_pace_strength": (100-frame.pace_balance_percentile) / 100,
        "front_position_strength": frame.corner4_frontness,
        "rear_position_strength": 1-frame.corner4_frontness,
    }.items():
        frame[name] = series
    frame["front_pace_opposition_raw"] = frame.front_pace_strength * frame.front_position_strength
    frame["rear_pace_opposition_raw"] = frame.rear_pace_strength * frame.rear_position_strength
    frame["day_track_opposition"] = np.nan  # Deliberately deferred, not zero exposure.
    for rule in hidden:
        frame['match_'+rule['rule_id']] = frame['match_'+rule['rule_id']].fillna(False)
    matched = [[r['rule_id'] for r in hidden if row['match_'+r['rule_id']]] for _, row in frame.iterrows()]
    frame["current_hv_matched_rules"] = ["|".join(x) for x in matched]
    frame["current_hv_exact_combo"] = frame.current_hv_matched_rules
    frame["current_next_watch_grade"] = [grade_matched_rules(x) for x in matched]
    return frame


def audit_pace(frame, context, connection):
    """Recompute percentiles using strictly earlier races, with canonical tie handling."""
    hist = connection.execute(f"SELECT * FROM {context} WHERE winner_time_sec>0").fetchdf()
    groups = {key: group for key, group in hist.groupby(['surface_code','distance_m'])}
    checked = missing = mismatch = 0
    samples = []
    for _, row in frame.dropna(subset=['previous_race_key']).drop_duplicates('previous_race_key').iterrows():
        group = groups.get((row.previous_surface_code,row.previous_distance_m))
        if group is None:
            peers = pd.DataFrame()
        else:
            peers = group[(group.race_date < row.previous_race_date) & group.pace_balance_sec.notna()]
        exact = peers[peers.venue_code == row.previous_race_key[:2]] if len(peers) else peers
        use = exact if len(exact)>=10 or len(peers)==0 else peers
        scope = 1 if use is exact else 2
        pct = percentile_rank(use.pace_balance_sec.tolist() if len(use) else [], row.pace_balance_sec)
        if pd.isna(row.pace_balance_percentile):
            missing += 1
            mismatch += int(pct is not None)
        else:
            checked += 1
            valid = pct is not None and math.isclose(pct,row.pace_balance_percentile,abs_tol=1e-8)
            valid = valid and len(use)==row.pace_sample_count and scope==row.pace_scope_level
            mismatch += int(not valid)
            if not valid and len(samples)<10:
                samples.append({'race':row.previous_race_key,'observed':row.pace_balance_percentile,'recomputed':pct,'n':len(use),'stored_n':row.pace_sample_count})
    return {'checked_source_races':checked,'missing_source_races':missing,'mismatch_count':mismatch,'mismatch_examples':samples}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir',type=Path,required=True)
    parser.add_argument('--current-zip',type=Path,required=True)
    parser.add_argument('--rule-zip',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--source-commit',required=True)
    args=parser.parse_args(); out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    root=_race_review_root(args.current_zip,out/'work')
    current=json.loads((root/'current.json').read_text())
    manifest=json.loads((root/current['manifest']).read_text())
    assert manifest['validation_status']=='PASS'
    inputs={args.current_zip.name:sha(args.current_zip),args.rule_zip.name:sha(args.rule_zip)}
    with zipfile.ZipFile(args.rule_zip) as z:
        rules=json.loads(z.read('next_watch_candidate_rules_frozen.json'))
    assert rules['status']=='CANDIDATE_RULES_FROZEN'
    paths={rel:_relation_paths(root,manifest,rel) for rel in ['fact_horse_performance','fact_race_context','fact_race_review']}
    hash_errors=[]
    for rel in paths:
        for meta,p in zip(manifest['relations'][rel]['partitions'],paths[rel]):
            if sha(p)!=meta['sha256'] or p.stat().st_size!=meta['size_bytes']:hash_errors.append(str(p))
    assert not hash_errors
    con=duckdb.connect(':memory:');con.execute('SET threads=4')
    sql={rel:_table_sql(p) for rel,p in paths.items()}
    duplicates={rel:con.execute(f"SELECT COUNT(*)-COUNT(DISTINCT {manifest['relations'][rel]['canonical_key'][0]}) FROM {s}").fetchone()[0] for rel,s in sql.items()}
    assert not any(duplicates.values()),duplicates
    raw_audit=ReaderAudit();reader=Parser(raw_audit);entrants=[]
    daily=[]
    for date in DATES:
        short=date.replace('-','')[2:];paci=args.input_dir/f'PACI{short}.zip'
        inputs[paci.name]=sha(paci)
        bac=[reader.bac(r) for _,r in iter_archive_records(paci,'BAC',raw_audit)]
        assert len(bac)==len({r['race_key_raw'] for r in bac})
        by_race={r['race_key_raw']:r for r in bac}
        rows=[reader.kyi(r) for _,r in iter_archive_records(paci,'KYI',raw_audit)]
        assert len(rows)==len({r['race_horse_key'] for r in rows})
        for row in rows:
            b=by_race[row['race_key_raw']];assert b['date_raw']==date.replace('-','')
            assert row['blood_registration_no'].isdigit() and len(row['blood_registration_no'])==8
            entrants.append(dict(target_date=date,target_race_key=row['race_key_raw'],target_race_horse_key=row['race_horse_key'],
                target_venue_code=row['race_key_raw'][:2],target_race_no=int(row['race_key_raw'][-2:]),target_horse_no=row['horse_no'],
                horse_id=row['blood_registration_no'],horse_name=row['horse_name'],surface_code=b['surface_code'],
                distance_m=int(b['distance_raw']),field_size=b['field_size'],declared_class_group=normalize_class_group(b['race_class_code'],b['grade_code'])))
        daily.append({'target_date':date,'paci_entrants':len(rows),'races':len(bac)})
    features=build_features(pd.DataFrame(entrants),sql['fact_horse_performance'],sql['fact_race_context'],sql['fact_race_review'],rules,con)
    feature_path=out/'rrdb_202609_previous_start_features.parquet';features.to_parquet(feature_path,index=False,compression='zstd')
    features_hash=sha(feature_path)
    # Target results are read only after the feature artifact is complete.
    settlement=[]
    for date in DATES:
        sed=args.input_dir/f"SED{date.replace('-','')[2:]}.zip";inputs[sed.name]=sha(sed)
        for _,raw in iter_archive_records(sed,'SED',raw_audit):
            row=reader.sed(raw);assert row['date_raw']==date.replace('-','')
            settlement.append(dict(target_race_horse_key=race_horse_key(raw),settlement_horse_id=row['blood_registration_no'],
                target_finish=row['finish'],target_win_odds=row['final_win_odds'],target_popularity=row['final_popularity'],
                target_place_payout_yen=row['place_payout'],target_win_payout_yen=row['win_payout'],
                target_abnormal_code=row['abnormal_code']))
    settled=pd.DataFrame(settlement)
    assert not settled.target_race_horse_key.duplicated().any()
    ledger=features.merge(settled,on='target_race_horse_key',how='left',validate='one_to_one',indicator=True)
    missing=int((ledger._merge!='both').sum());identity_mismatch=int((ledger.horse_id!=ledger.settlement_horse_id).sum())
    assert missing==0 and identity_mismatch==0,(missing,identity_mismatch)
    ledger.drop(columns=['_merge','settlement_horse_id'],inplace=True)
    # Cancellations/exclusions are refunded; DNF is an actual losing start.
    ledger['target_started']=~ledger.target_abnormal_code.isin(['1','2'])
    actual_field=ledger.groupby('target_race_key').target_started.transform('sum')
    expected_place=ledger.target_finish.between(1,2) | (ledger.target_finish.eq(3) & actual_field.ge(8))
    assert not (expected_place & ~ledger.target_place_payout_yen.gt(0)).any()
    assert not (ledger.target_finish.eq(1) & ~ledger.target_win_payout_yen.gt(0)).any()
    for payout in ['place','win']:
        field=f'target_{payout}_payout_yen'
        ledger[field+'_raw_blank']=ledger[field].isna()
        ledger[field]=ledger[field].fillna(0).astype(int)
    ledger['target_place_hit']=ledger.target_place_payout_yen>0
    ledger['target_win_hit']=ledger.target_win_payout_yen>0
    ledger['target_flat']=ledger.surface_code.isin(['1','2'])
    previous=ledger.has_previous_rrdb_start.eq(1)
    future=int((ledger.loc[previous,'previous_race_date']>=pd.to_datetime(ledger.loc[previous,'target_date'])).sum())
    standard_future=int((ledger.loc[previous,'standard_sample_end_date']>=ledger.loc[previous,'previous_race_date']).sum())
    pace_audit=audit_pace(ledger,sql['fact_race_context'],con)
    flat=ledger.target_flat & ledger.target_started & previous
    for d in daily:
        subset=ledger[ledger.target_date==d['target_date']]
        d.update(started=int(subset.target_started.sum()),flat_started=int((subset.target_started & subset.target_flat).sum()),
                 previous_history=int(subset.has_previous_rrdb_start.sum()),no_previous_history=int(subset.has_previous_rrdb_start.eq(0).sum()))
    audit=dict(status='PASS',version=VERSION,source_commit=args.source_commit,rrdb_generation=manifest['generation_id'],rrdb_period_to=manifest['period_to'],
        target_runner_count=len(ledger),target_started_count=int(ledger.target_started.sum()),target_flat_started_count=int((ledger.target_flat & ledger.target_started).sum()),
        usable_previous_rrdb_start_count=int(previous.sum()),usable_flat_started_count=int(flat.sum()),no_previous_history_count=int((~previous).sum()),
        duplicate_count=int(ledger.target_race_horse_key.duplicated().sum()),rrdb_duplicates=duplicates,sed_join_missing_count=missing,
        settlement_identity_mismatch_count=identity_mismatch,pace_feature_missing_count=int(ledger.loc[previous,'pace_balance_percentile'].isna().sum()),
        performance_feature_missing_count=int(ledger.loc[previous,'performance_signal'].isna().sum()),corner4_feature_missing_count=int(ledger.loc[previous,'corner4_frontness'].isna().sum()),
        closing_gain_missing_count=int(ledger.loc[previous,'closing_gain_sec'].isna().sum()),previous_date_violation_count=future,
        historical_standard_date_violation_count=standard_future,pace_asof_audit=pace_audit,raw_length_errors=dict(raw_audit.record_length_errors),
        rrdb_object_hash_verified_count=sum(map(len,paths.values())),inputs_sha256=inputs,features_before_settlement_sha256=features_hash,
        rule_version=rules['rule_version'],frozen_thresholds=rules['thresholds'],daily=daily,
        features_use_target_results=False,threshold_optimization=False,formal_rule_promotion=False,
        source_modules_sha256={p.name:sha(p) for p in Path(__file__).parent.glob('jrdb*.py')},
        runtime={'python':platform.python_version(),'duckdb':duckdb.__version__,'pandas':pd.__version__})
    assert future==0 and standard_future==0 and pace_audit['mismatch_count']==0 and not raw_audit.record_length_errors,audit
    for suffix in ['parquet','csv']:
        path=out/f'rrdb_202609_all_runner_research_ledger.{suffix}'
        if suffix=='parquet':ledger.to_parquet(path,index=False,compression='zstd')
        else:ledger.to_csv(path,index=False,encoding='utf-8-sig')
    assert sha(feature_path)==features_hash
    audit['outputs_sha256']={p.name:sha(p) for p in [feature_path,
        out/'rrdb_202609_all_runner_research_ledger.parquet',out/'rrdb_202609_all_runner_research_ledger.csv']}
    write_json(out/'rrdb_202609_data_audit.json',audit)
    print(json.dumps({k:v for k,v in audit.items() if k not in ['inputs_sha256','outputs_sha256','source_modules_sha256','daily']},default=str))


if __name__=='__main__':
    main()
