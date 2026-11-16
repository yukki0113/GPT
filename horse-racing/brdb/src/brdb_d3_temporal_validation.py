"""Descriptive temporal stability audit of D3 condition buckets (not predictive)."""
from __future__ import annotations

from collections import defaultdict


def audit(evidence_train: list[dict], evidence_test: list[dict]) -> dict:
    """Compare independent-period within-condition deviations, never pool starts.

    Only >=30 starts AND >=10 horses in both windows is comparable;
    same-sign deviation is a descriptive diagnostic, *not* proof of aptitude.
    """
    def indexed(rows):
        index = {}
        for x in rows:
            key = (x['lane'], x['name'], x['scope'],
                   tuple(sorted(x['dimensions'].items())))
            if key in index:
                raise ValueError('duplicate temporal evidence bucket')
            index[key] = x
        return index
    a, b = indexed(evidence_train), indexed(evidence_test)
    keys = sorted(set(a) | set(b))
    out = []
    counts = defaultdict(int)
    for key in keys:
        old, new = a.get(key), b.get(key)
        if old is None or new is None:
            verdict = 'PERIOD_MISSING'
        elif old['sample_status'] != 'DESCRIPTIVE' or new['sample_status'] != 'DESCRIPTIVE':
            verdict = 'INSUFFICIENT_WINDOW_SAMPLE'
        else:
            x, y = old['top3_delta_percentage_points'], new['top3_delta_percentage_points']
            if x is None or y is None:
                verdict = 'INSUFFICIENT_BASELINE'
            elif x == 0 or y == 0:
                verdict = 'NO_DIRECTION'
            elif (x > 0) == (y > 0):
                verdict = 'SAME_SIGN_DESCRIPTIVE_ONLY'
            else:
                verdict = 'DIRECTION_CHANGED'
        counts[verdict] += 1
        out.append({'lane': key[0], 'name': key[1], 'scope': key[2],
                    'dimensions': dict(key[3]),
                    'train_starts': old['starts'] if old else 0,
                    'test_starts': new['starts'] if new else 0,
                    'train_delta_pp': old['top3_delta_percentage_points'] if old else None,
                    'test_delta_pp': new['top3_delta_percentage_points'] if new else None,
                    'stability_status': verdict})
    return {'schema_version':'brdb-d3-temporal-diagnostic-v0.1',
            'research_only': True, 'prediction_safe': False,
            'interpretation': 'SAME_SIGN_IS_NOT_CAUSAL_EVIDENCE_OR_RACE_DAY_AVAILABILITY',
            'counts': dict(sorted(counts.items())), 'rows': out}