#!/usr/bin/env python3
"""Reproduce D3 full-cohort statistics and two-window retrospective diagnostic.

Research-only: no scoring or modification of BRDB CURRENT, Review, RaceNote, PWA.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from brdb_d3_condition_research import analyse
from brdb_d3_temporal_validation import audit


def _dump(path:Path,data:dict)->str:
    path.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root:Path,top50:Path,out:Path)->dict:
    out.mkdir(parents=True,exist_ok=True)
    full=analyse(root,top50)
    train=analyse(root,top50,period_start='2016-01-01',cutoff_exclusive='2024-01-01')
    test=analyse(root,top50,period_start='2024-01-01',cutoff_exclusive='2026-11-02')
    temporal=audit([x for x in train['evidence_rows'] if x['scope']=='SURFACE_BAND'],
                   [x for x in test['evidence_rows'] if x['scope']=='SURFACE_BAND'])
    temporal['train_window']={'start':train['period_start'],
                              'end_exclusive':train['as_of_exclusive'],
                              'starts':train['population']['historical_starts']}
    temporal['test_window']={'start':test['period_start'],
                             'end_exclusive':test['as_of_exclusive'],
                             'starts':test['population']['historical_starts']}
    temporal['source_sha256']={'top50':full['source_sha256']['top50'],
                               'train_current':train['source_sha256']['manifest'],
                               'test_current':test['source_sha256']['manifest']}
    full_sha=_dump(out/'d3_full_condition_evidence.json',full)
    temporal_sha=_dump(out/'d3_temporal_diagnostic.json',temporal)
    return {'status':'PASS','research_only':True,'prediction_safe':False,
            'source_generation':full['source_snapshot_generation'],
            'selection_generation':full['selection_generation'],
            'historical_starts':full['population']['historical_starts'],
            'historical_distinct_horses':full['population']['historical_unique_horses'],
            'condition_evidence_by_lane':full['counts']['evidence_by_lane'],
            'pair_observed_cells':full['counts']['pair_observed_cells'],
            'temporal_counts':temporal['counts'],
            'output_sha256':{'full':full_sha,'temporal':temporal_sha},
            'as_of':'AS_OF_UNVERIFIED',
            'interpretation':'DESCRIPTIVE_ONLY_NOT_PREDICTION'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--analysis-root',type=Path,required=True)
    parser.add_argument('--top50',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    receipt=run(args.analysis_root,args.top50,args.output_dir)
    _dump(args.output_dir/'d3_run_receipt.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False,sort_keys=True))

if __name__=='__main__':main()