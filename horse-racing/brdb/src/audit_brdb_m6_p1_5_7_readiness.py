#!/usr/bin/env python3
"""M6 P1-5..P1-7 fail-closed readiness and frozen walk-forward design.

This DOES NOT estimate pedigree effects, train models, calculate betting ROI,
or attest pre-race source delivery. It uses aggregate provenance audits only.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

VERSION = 'brdb-m6-p1-5-7-readiness-v0.1'
COHORT_2016_2025 = 481627
MART_SHA256 = '8b41f4b7132bc268428133535cce9c4aff79ac5b7b4c0dca5a5cdd5c1df13b63'

def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def load_pinned(path, expected):
    if not isinstance(expected, str) or len(expected) != 64 or sha256(path) != expected:
        raise ValueError('source SHA-256 mismatch')
    return json.loads(Path(path).read_text(encoding='utf-8'))

def folds():
    return [{'fold_id': f'year_{year}', 'train_years': list(range(2016, year)),
             'test_year': year, 'training_end': year - 1,
             'selection_boundary': 'train_only', 'horse_reentry_across_periods': 'NOT_YET_GUARDED'}
            for year in range(2021, 2026)]

def assess(asof: dict, outcome: dict, dependence: dict) -> dict:
    if asof.get('status') != 'PASS_AS_AUDIT_ONLY' or asof.get('source_mart_sha256') != MART_SHA256:
        raise ValueError('unexpected P1-4 accepted provenance audit')
    if (asof.get('total_entries') != COHORT_2016_2025 or
            asof.get('static_unverified_entries') != 481623 or
            asof.get('missing_pedigree_entries') != 4 or
            asof.get('asof_proven_entries') != 0 or
            asof.get('prediction_safe') is not False):
        raise ValueError('historical temporal cohort diverged; require independent re-audit')
    if (outcome.get('status') != 'PASS_RESEARCH_ONLY' or
            outcome.get('race_declarations') != 4945 or
            outcome.get('actual_starters') != 4932 or
            outcome.get('normal_finishers') != 4919 or
            outcome.get('days') != 14 or
            outcome.get('prediction_safe') is not False or
            outcome.get('historical_2016_2025_asof_proven') != 0):
        raise ValueError('2026 outcome cohort diverged from accepted evidence')
    scope = dependence.get('scope', {})
    if (dependence.get('status') != 'PASS_DESCRIPTIVE_UNCERTAINTY_ONLY' or
            dependence.get('prediction_safe') is not False or
            dependence.get('forecasting_promotion') != 'HOLD' or
            scope.get('dates') != 14 or scope.get('declarations') != 4945 or
            scope.get('races') != 372 or scope.get('distinct_horses') != 3970 or
            scope.get('horses_with_repeated_declarations') != 906 or
            scope.get('extra_repeated_declarations') != 975):
        raise ValueError('P1-5 cluster-audit reference diverged')
    for metric, numer, denom in [('starter_rate',4932,4945),('dnf_among_starters',13,4932)]:
        v=dependence.get('metrics',{}).get(metric,{})
        if (v.get('numerator'),v.get('denominator')) != (numer,denom):
            raise ValueError('P1-5 endpoint changed')
        for dimension, clusters in [('date',14),('race',372),('horse',3970)]:
            if v.get('cluster_bootstrap',{}).get(dimension,{}).get('n_clusters') != clusters:
                raise ValueError('P1-5 cluster dimension changed')
    return {
        'version': VERSION,
        'status': 'PASS_READINESS_AUDIT_HOLD_PREDICTION',
        'prediction_safe': False,
        'historical_asof_attested_entries': 0,
        'research_basis': {'historical_rows': COHORT_2016_2025,
                           'retrospective_2026_declarations': 4945,
                           'retrospective_2026_days': 14,
                           'dependency_2026_races': 372,
                           'dependency_2026_horses': 3970},
        'p1_5': {
            'engineering': 'DESCRIPTIVE_BOOTSTRAP_DONE',
            'predictive_evaluation': 'HOLD',
            'missing': ['independently attested pre-race blood feature snapshots',
                        'horse/race/date/year multiway dependence analysis on an as-of cohort',
                        'predeclared blood-specific estimand and adequately sized independent sample']},
        'p1_6': {
            'engineering': 'CHRONOLOGICAL_WINDOW_PLAN_FROZEN',
            'predictive_evaluation': 'HOLD',
            'proposed_folds': folds(),
            'eligible_historical_entries': 0,
            'missing': ['independently authenticated 2016-2025 as-of blood features',
                        'frozen train-only discovery and tuning results',
                        'horse identity reentry policy with independent temporal evaluation']},
        'p1_7': {
            'engineering': 'INCREMENTAL_VALUE_CONTRACT_FROZEN',
            'predictive_evaluation': 'HOLD',
            'comparison': {
                'same_test_entries': True,
                'target': 'win among actual starters; nonstarters excluded; DNF retained as non-winning',
                'baseline': 'pre-race available non-blood model, frozen per training fold',
                'challenger': 'same baseline plus independently as-of-attested blood features',
                'primary_metric': 'held-out binary log_loss',
                'secondary_metrics': ['Brier score','race-level discrimination','calibration'],
                'uncertainty': 'race/horse/time-clustered paired uncertainty; no naive row IID',
                'multiple_comparisons': 'pre-specified hypotheses and correction',
                'minimum_publication_evidence': 'positive incremental effect in independent temporal folds with uncertainty'},
            'matched_predictions_available': False,
            'missing': ['pre-race non-blood baseline predictions with feature provenance',
                        'frozen challenger predictions from a time-safe model',
                        'independent held-out years and paired evaluation']},
        'no_promotions': ['BRDB CURRENT','Blood Score','RaceNote','PWA','Newspaper','betting logic'],
        'note': 'An executable readiness audit is not an executed predictive study. Do not claim P1-5/6/7 predictive completion.',
    }

def run(asof_path, outcome_path, dependence_path, output, *, asof_sha, outcome_sha, dependence_sha, require_predictive=False):
    sources = [load_pinned(path, digest) for path,digest in
               [(asof_path,asof_sha),(outcome_path,outcome_sha),(dependence_path,dependence_sha)]]
    report = assess(*sources)
    report['inputs_sha256'] = {'p1_4_asof':asof_sha,'p1_4d_outcome':outcome_sha,'p1_5_dependence':dependence_sha}
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    (output/'m6_p1_5_7_readiness.json').write_text(json.dumps(report,indent=2,ensure_ascii=False,sort_keys=True)+'\n',encoding='utf-8')
    if require_predictive:
        raise ValueError('P1-5 through P1-7 predictive evaluation is HOLD: zero historical as-of-attested features')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ['asof','outcome','dependence']:
        p.add_argument('--'+key,required=True,type=Path)
        p.add_argument('--'+key+'-sha',required=True)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--require-predictive',action='store_true')
    a=p.parse_args()
    r=run(a.asof,a.outcome,a.dependence,a.out,asof_sha=a.asof_sha,outcome_sha=a.outcome_sha,dependence_sha=a.dependence_sha,require_predictive=a.require_predictive)
    print(json.dumps({'status':r['status'],'p1_5':r['p1_5']['predictive_evaluation'],'p1_6':r['p1_6']['predictive_evaluation'],'p1_7':r['p1_7']['predictive_evaluation']}))
