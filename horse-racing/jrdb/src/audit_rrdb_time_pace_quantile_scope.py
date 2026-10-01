#!/usr/bin/env python3
"""Fixed scope sensitivity: all-entry usable quantiles vs primary flat quantiles.

Neither scope uses target outcomes to calculate thresholds. Settlement is always
on the same flat, started, usable population. Canonical ledger is read-only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import pandas as pd
from analyze_rrdb_time_pace import metrics, quantile_band
from jrdb_previous_start_research_ledger import sha, write_json

FIELDS=['performance_signal','front_pace_opposition_raw','rear_pace_opposition_raw']
QUANTILES=[.5,.7,.8,.9]

def sensitivity(ledger):
    usable=ledger.has_previous_rrdb_start.eq(1)
    primary=usable & ledger.target_flat & ledger.target_started
    base=ledger.loc[primary]
    base=base.copy()
    base['odds_band']=pd.cut(base.target_win_odds,[0,5,10,30,100,float('inf')],right=False,labels=['<5','5-9.9','10-29.9','30-99.9','>=100'])
    base['popularity_band']=pd.cut(base.target_popularity,[0,3,6,9,float('inf')],labels=['1-3','4-6','7-9','10+'])
    base['previous_finish_band']=pd.cut(base.previous_finish,[0,3,5,9,float('inf')],labels=['1-3','4-5','6-9','10+'])
    sources={'ALL_ENTRY_USABLE':ledger.loc[usable],'PRIMARY_FLAT_STARTED_USABLE':base}
    rows=[];thresholds={}
    front=base.pace_balance_percentile.ge(70)&base.corner4_frontness.ge(.6)
    rear=base.pace_balance_percentile.le(30)&base.corner4_frontness.le(.4)
    for scope,source in sources.items():
        cuts={field:{str(q):float(source[field].quantile(q)) for q in QUANTILES} for field in FIELDS}
        thresholds[scope]={'source_n':len(source),'cutoffs':cuts}
        for q,label in [(.8,'20'),(.9,'10')]:
            time=base.performance_signal.ge(cuts['performance_signal'][str(q)])
            selections={f'TIME_TOP{label}':time,
                f'FINISH_GE4_TIME_TOP{label}':time&base.previous_finish.ge(4),
                f'FINISH_GE6_TIME_TOP{label}':time&base.previous_finish.ge(6),
                f'FRONT_HIGH_TIME_TOP{label}':time&front,
                f'REAR_HIGH_TIME_TOP{label}':time&rear}
            for field in FIELDS[1:]:selections[f'{field}_TOP{label}']=base[field].ge(cuts[field][str(q)])
            for name,mask in selections.items():
                selected=base.loc[mask]
                rows.append({'family':'signal','stratum':'ALL','quantile_scope':scope,'source_n':len(source),'signal':name,**metrics(selected)})
                for column in ['odds_band','popularity_band','previous_finish_band']:
                    for band,part in selected.groupby(column,observed=True):
                        rows.append({'family':column,'stratum':str(band),'quantile_scope':scope,'source_n':len(source),'signal':name,**metrics(part)})
        for field in FIELDS:
            cutoffs=source[field].quantile([0]+QUANTILES+[1]).to_numpy()
            bands=quantile_band(base[field],cutoffs)
            for band,part in base.groupby(bands,observed=True):
                rows.append({'family':'quantile_band','stratum':str(band),'quantile_scope':scope,'source_n':len(source),'signal':field,**metrics(part)})
            if field=='performance_signal':
                for (band,finish),part in base.groupby([bands,base.previous_finish_band],observed=True):
                    rows.append({'family':'finish_quantile_cross','stratum':str(band)+'|'+str(finish),'quantile_scope':scope,'source_n':len(source),'signal':field,**metrics(part)})
    return pd.DataFrame(rows),thresholds

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ledger',type=Path,required=True)
    ap.add_argument('--output-dir',type=Path,required=True);ap.add_argument('--canonical-commit',required=True)
    ap.add_argument('--independent-ledger',type=Path)
    args=ap.parse_args();args.output_dir.mkdir(parents=True,exist_ok=True)
    ledger=pd.read_parquet(args.ledger)
    assert len(ledger)==3137 and not ledger.target_race_horse_key.duplicated().any()
    crosscheck={'status':'NOT_RUN'}
    if args.independent_ledger:
        other=pd.read_parquet(args.independent_ledger)
        columns=['horse_id','previous_race_key','previous_race_horse_key','previous_finish',
            'performance_signal','pace_balance_percentile','corner4_frontness',
            'target_place_payout_yen','target_win_odds','target_popularity']
        left=ledger.set_index('target_race_horse_key')[columns].sort_index()
        right=other.set_index('target_race_horse_key')[columns].sort_index()
        pd.testing.assert_frame_equal(left,right,check_dtype=False,check_exact=False,atol=1e-12)
        crosscheck={'status':'PASS','independent_ledger_sha256':sha(args.independent_ledger),'compared_columns':columns,'row_count':len(left)}
    table,cuts=sensitivity(ledger)
    # Demonstrate threshold independence from target results by adversarial outcome substitution.
    changed=ledger.copy()
    for col in ['target_finish','target_win_odds','target_popularity','target_place_payout_yen','target_win_payout_yen']:
        changed[col]=99999
    _,changed_cuts=sensitivity(changed)
    assert cuts==changed_cuts
    path=args.output_dir/'rrdb_202609_quantile_scope_sensitivity.csv'
    table.to_csv(path,index=False,encoding='utf-8-sig')
    write_json(args.output_dir/'rrdb_202609_quantile_scope_audit.json',dict(
        status='PASS',canonical_commit=args.canonical_commit,canonical_ledger_sha256=sha(args.ledger),
        source_script_sha256=sha(Path(__file__)),summary_sha256=sha(path),
        target_entry_count=len(ledger),primary_settlement_n=2590,thresholds=cuts,
        target_outcome_perturbation_threshold_invariance='PASS',outcome_optimized=False,
        feature_and_outcome_semantic_crosscheck=crosscheck,
        quantiles_descriptive_not_deployable_asof=True))
    print(table.loc[table.family.eq('signal'),['quantile_scope','signal','n','place_hits','place_roi_pct']].to_string(index=False))
if __name__=='__main__':main()
