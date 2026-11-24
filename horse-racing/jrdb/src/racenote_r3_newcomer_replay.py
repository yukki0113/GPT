"""Orchestrate per-field M7/R3 newcomer research replay, not BRDB debut research.

Use only independently pinned prior details and per-field manifests. Reuse the
canonical R3 builder and audit; do not promote either database to production.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

BASE = {'jpdb_r1', 'jpdb_r2', 'paci', 'jpdb_r1_receipt', 'jpdb_r2_receipt'}
BLOOD = {'brdb_v03', 'brdb_relatives_detail', 'brdb_sire_bms', 'brdb_m7_receipt', 'brdb_detail_receipt'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def pinned(path, expected):
    require(re.fullmatch(r'[0-9a-f]{64}', expected) is not None and sha(path) == expected,
            'input SHA mismatch')
    return json.loads(Path(path).read_bytes())


def safe(d):
    return (d['research_only'] is True and d['prediction_safe'] is False
            and d['production_authorized'] is False and d['target_date'] == d['as_of_exclusive'])


def plan(previous):
    targets = {}
    for path, digest in previous:
        d = pinned(path, digest)
        require(d['contract_version'] == 'racenote-independent-evidence-v0.1-candidate' and safe(d),
                'wrong previous detail contract')
        sources = {k: d['source_assets'][k]['sha256'] for k in BASE}
        require(sources['paci'] == d['target_paci_sha256'], 'prior PACI mismatch')
        for r in d['races']:
            require(r['is_newcomer_race'] == (r['race_class_code'] == 'A1'), 'cohort mismatch')
            if not r['is_newcomer_race']:
                continue
            key = r['race_key_raw']
            require(re.fullmatch(r'[0-9]{8}', key) and key not in targets, 'duplicate/invalid target')
            roster = sorted((h['horse_no'], h['horse_id'], h['scheduled_jockey_code'],
                             h['entry_cancel_flag_raw']) for h in r['horses'])
            require(len(roster) == r['entry_count'] > 0 and len({x[0] for x in roster}) == len(roster)
                    and len({x[1] for x in roster}) == len(roster), 'prior roster mismatch')
            targets[key] = {'target_date': d['target_date'], 'field_size': len(roster),
                            'prior_detail_sha256': digest, 'sources': sources, 'roster': roster}
    require(bool(targets), 'no newcomer targets')
    return targets


def validate_job(key, path, digest, target):
    m = pinned(path, digest)
    require(m['schema_version'] == 'racenote-r3-private-input-manifest-v1', 'wrong manifest version')
    assets = m['assets']
    require(set(assets) == BASE | BLOOD, 'incomplete dual-source assets')
    require(all(assets[k]['sha256'] == target['sources'][k] for k in BASE), 'prior source changed')
    for a in assets.values():
        require(sha(a['path']) == a['sha256'], 'asset SHA mismatch')
    b = pinned(assets['brdb_v03']['path'], assets['brdb_v03']['sha256'])
    require(b['race']['race_key'] == key and b['as_of_exclusive'] == target['target_date'],
            'wrong BRDB race/date')
    require(sorted((h['horse_no'], h['horse_id']) for h in b['horses']) ==
            [(h[0], h[1]) for h in target['roster']], 'wrong BRDB roster')


def run_job(key, path, digest, target, root, python, audit_python):
    validate_job(key, path, digest, target)
    src = Path(__file__).resolve().parent
    hashes = []
    for attempt in ('first', 'second'):
        dest = root / key / attempt
        dest.mkdir(parents=True, exist_ok=False)
        detail, previews, receipt = dest / 'detail.json', dest / 'preview', dest / 'audit.json'
        args = ['--manifest', str(Path(path).resolve()), '--manifest-sha256', digest]
        subprocess.run([python, str(src / 'racenote_r3_independent_evidence.py'), *args,
                        '--output', str(detail), '--preview-dir', str(previews)], check=True)
        subprocess.run([audit_python, str(src / 'racenote_r3_independent_evidence_audit.py'), *args,
                        '--detail', str(detail), '--preview-dir', str(previews), '--schema-dir',
                        str(src.parent / 'schema'), '--output', str(receipt)], check=True)
        d = json.loads(detail.read_bytes())
        require(safe(d) and d['target_date'] == target['target_date'], 'unsafe replay')
        matches = [r for r in d['races'] if r['race_key_raw'] == key]
        require(len(matches) == 1 and matches[0]['is_newcomer_race'] is True and
                matches[0]['coverage_status'] == 'DUAL_SOURCE_RESEARCH', 'target not dual-source')
        require(sorted((h['horse_no'], h['horse_id'], h['scheduled_jockey_code'], h['entry_cancel_flag_raw'])
                       for h in matches[0]['horses']) == target['roster'], 'replay roster changed')
        audit = json.loads(receipt.read_bytes())
        require(audit['status'] == 'PASS_FIXED_SOURCE_PROJECTION_ONLY' and audit['detail_sha256'] == sha(detail),
                'canonical audit did not pass')
        hashes.append({'detail': sha(detail), 'audit': sha(receipt),
                       'previews': {p.name: sha(p) for p in sorted(previews.glob('*.json'))}})
    require(hashes[0] == hashes[1], 'replay bytes differ')
    return {'status': 'PASS_M7_COMPOSITION_ONLY', 'hashes': hashes[0]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--previous-detail', nargs=2, action='append', required=True, metavar=('PATH', 'SHA256'))
    p.add_argument('--job', nargs=3, action='append', default=[], metavar=('RACE_KEY', 'MANIFEST', 'SHA256'))
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--python', default=sys.executable)
    p.add_argument('--audit-python', default=sys.executable)
    a = p.parse_args()
    targets = plan(a.previous_detail)
    jobs = {k: (path, digest) for k, path, digest in a.job}
    require(len(jobs) == len(a.job) and set(jobs) <= set(targets), 'duplicate/unknown job')
    root = a.output_dir.resolve()
    root.mkdir(parents=True, exist_ok=False)
    rows = []
    for key, target in sorted(targets.items()):
        row = {'race_key_raw': key, **{k: target[k] for k in ('target_date', 'field_size', 'prior_detail_sha256', 'sources')}}
        row['status'] = 'PENDING_BRDB_ACCEPTED_INPUT'
        if key in jobs:
            row.update(run_job(key, *jobs[key], target, root, a.python, a.audit_python))
        rows.append(row)
    summary = {'status': 'PASS_M7_COMPOSITION_ONLY' if all(r['status'] == 'PASS_M7_COMPOSITION_ONLY' for r in rows)
               else 'PENDING_BRDB_ACCEPTED_INPUT', 'targets': rows, 'target_races': len(rows),
               'target_horses': sum(r['field_size'] for r in rows),
               'accepted_races': sum(r['status'] == 'PASS_M7_COMPOSITION_ONLY' for r in rows),
               'debut_specific_evidence': 'NOT_CERTIFIED_BY_THIS_RUN', 'r4_authorized': False,
               'prediction_safe': False, 'production_authorized': False}
    (root / 'summary.json').write_text(json.dumps(summary, sort_keys=True, indent=2) + '\n')


if __name__ == '__main__':
    main()
