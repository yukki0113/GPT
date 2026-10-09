#!/usr/bin/env python3
"""Build a separate, result-blind v0.5 Newspaper preview from one PACI day.

This does not alter STANDARD EdgeDB Query or the published current Newspaper.
Historical first-use conditions and target going remain unknown until verified
pre-race sources are connected; their frozen candidates stay in the inventory.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import shutil
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

from build_jrdb_edge_current_facts_v0_2 import build_current_facts
from jrdb_edge_v05_2026_pre_race_match_freeze import (
    _fact_projection, build_matches, fingerprint_rows, load_cohort, validate_match_fact_schema,
)
from jrdb_newspaper_merge_edge import _sha_file, _write_day_package, _write_json

VERSION = 'edge-v05-newspaper-preview/v1'
DEFAULT_COHORT = Path(__file__).resolve().parents[1] / 'config/edgedb/v0_5/frozen/v05_positive_value_frozen_cohort.json'
DEFAULT_OOS_MANIFEST = Path(__file__).resolve().parents[1] / 'config/edgedb/v0_5/frozen/v05_2026_oos_eval_manifest.json'
DEFAULT_FREEZE_MANIFEST = Path(__file__).resolve().parents[1] / 'config/edgedb/v0_5/frozen/v05_2026_match_freeze_manifest.json'
TIERS = ('CONFIRMED', 'STILL_PLAUSIBLE', 'INSUFFICIENT_OOS', 'DECAYING', 'CONTRADICTED')
OOS_INTEGER_FIELDS = frozenset('n_2024_2025 n_2026 wins_2026 places_2026 win_return_2026 place_return_2026 place_hits_pop_5_plus place_hits_pop_8_plus place_hits_pop_10_plus max_hit_popularity max_place_payout'.split())
OOS_FLOAT_FIELDS = frozenset('place_rate_2024_2025 win_rate_2024_2025 place_roi_2024_2025 win_roi_2024_2025 win_rate_2026 place_rate_2026 win_roi_2026 place_roi_2026 delta_win_rate delta_place_rate delta_win_roi delta_place_roi top_place_return_share'.split())


class PreviewError(ValueError):
    pass


def load_sources(cohort_path: Path, oos_manifest_path: Path, freeze_manifest_path: Path,
                 oos_artifact_zip: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, Any]]:
    candidates, cohort_audit = load_cohort(cohort_path)
    oos_manifest = json.loads(oos_manifest_path.read_text(encoding='utf-8'))
    freeze_manifest = json.loads(freeze_manifest_path.read_text(encoding='utf-8'))
    if oos_manifest['cohort']['sha256'] != cohort_audit['cohort_sha256']:
        raise PreviewError('OOS cohort identity mismatch')
    expected_zip = oos_manifest['workflow_artifact']['artifact_digest'].removeprefix('sha256:')
    if _sha_file(oos_artifact_zip) != expected_zip:
        raise PreviewError('OOS artifact digest mismatch')
    with zipfile.ZipFile(oos_artifact_zip) as archive:
        with archive.open('v05_2026_oos_candidate_eval.csv') as raw:
            rows = list(csv.DictReader(io.TextIOWrapper(raw, encoding='utf-8')))
    typed_rows = []
    for row in rows:
        typed_rows.append({key: (None if value == '' else int(value) if key in OOS_INTEGER_FIELDS
                                 else float(value) if key in OOS_FLOAT_FIELDS else value)
                           for key, value in row.items()})
    expected_fingerprint = oos_manifest['fingerprints']['candidate_eval_sha256']
    if fingerprint_rows(typed_rows, ('candidate_id',)) != expected_fingerprint:
        raise PreviewError('OOS candidate evaluation fingerprint mismatch')
    oos = {}
    for row in rows:
        cid = row['candidate_id']
        if cid in oos or row['oos_label'] not in TIERS:
            raise PreviewError('duplicate candidate ID or invalid OOS tier')
        oos[cid] = row
    if len(oos) != 1620 or set(oos) != {c['candidate_id'] for c in candidates}:
        raise PreviewError('OOS candidate membership differs from frozen cohort')
    if Counter(r['oos_label'] for r in rows) != oos_manifest['oos']['labels']:
        raise PreviewError('OOS tier counts differ from frozen manifest')
    latest_evaluated = freeze_manifest['coverage']['latest_race_date']
    return {c['candidate_id']: c for c in candidates}, oos, {
        'cohort_sha256': cohort_audit['cohort_sha256'],
        'oos_manifest_sha256': _sha_file(oos_manifest_path),
        'oos_artifact_sha256': expected_zip,
        'oos_candidate_eval_fingerprint': expected_fingerprint,
        'latest_evaluated_race_date': latest_evaluated,
    }


def project_facts(raw_rows: list[Mapping[str, Any]], latest_evaluated_date: str, *, allow_evaluated_date: bool = False) -> tuple[list[dict[str, Any]], dict[str, int]]:
    projected = []
    audit = Counter()
    for row in raw_rows:
        date = str(row['race_date'])[:10]
        if date <= latest_evaluated_date and not allow_evaluated_date:
            raise PreviewError(f'preview target {date} is not after frozen OOS endpoint {latest_evaluated_date}')
        fact = _fact_projection(row, None)
        # Existing Analysis lookup resolves exactly the KYI prev1 link and enforces
        # strictly prior date. A missing or ambiguous link cannot satisfy T3.
        if row.get('previous_lookup_status') != 'RESOLVED' or not row.get('previous_race_date') or str(row['previous_race_date'])[:10] >= date:
            fact['distance_change'] = None
            fact['surface_transition'] = None
            audit['transition_unknown'] += 1
        # Complete first-use history and verified pre-race going are not part of
        # canonical daily current facts. Never substitute result SED going.
        fact['first_dirt'] = fact['first_turf'] = fact['first_blinkers'] = None
        fact['going_bucket'] = None
        audit['first_history_unknown'] += 1
        audit['going_unavailable'] += 1
        validate_match_fact_schema(fact)
        projected.append(fact)
    return projected, dict(audit)


def _number(value: str | None, *, integer: bool = False) -> int | float | None:
    if value in (None, ''):
        return None
    return int(value) if integer else float(value)


def candidate_detail(candidate: Mapping[str, Any], oos: Mapping[str, str]) -> dict[str, Any]:
    n_base = int(candidate['n_2024_2025'])
    n_oos = int(oos['n_2026'])
    return {
        'candidate_id': candidate['candidate_id'],
        'family': candidate['family'],
        'condition_text': candidate['memo'],
        'condition_fingerprint': candidate['condition_fingerprint'],
        'source_generation': 'v0.5',
        'oos_tier': oos['oos_label'],
        'discovery': {'n': n_base, 'place_rate': candidate['places_2024_2025'] / n_base if n_base else None,
                      'place_roi': candidate['place_roi_2024_2025']},
        'oos_2026': {'n': n_oos, 'place_rate': _number(oos['place_rate_2026']) if n_oos else None,
                     'place_roi': _number(oos['place_roi_2026']) if n_oos else None,
                     'payout_available': n_oos > 0},
        'longshot_place_hits_8_plus': int(oos['place_hits_pop_8_plus']),
        'longshot_place_hits_10_plus': int(oos['place_hits_pop_10_plus']),
    }


def order_ids(ids: list[str], details: Mapping[str, Mapping[str, Any]]) -> list[str]:
    def key(cid: str) -> tuple:
        item = details[cid]
        return (TIERS.index(item['oos_tier']), -item['oos_2026']['n'],
                -item['discovery']['n'],
                -int(bool(item['longshot_place_hits_8_plus'] or item['longshot_place_hits_10_plus'])), cid)
    ordered = sorted(ids, key=key)
    # Only among an equal tier, place a different family into the representative
    # pair when one exists. All other candidates remain visible in the expansion.
    if len(ordered) > 2:
        first = details[ordered[0]]
        for position in range(1, len(ordered)):
            item = details[ordered[position]]
            if item['oos_tier'] != first['oos_tier']:
                break
            if item['family'] != first['family']:
                ordered.insert(1, ordered.pop(position))
                break
    return ordered


def _set_state(day: Path, state: str, message: str) -> None:
    manifest_path = day / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    status = {'state': state, 'source_version': VERSION, 'message': message,
              'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}
    manifest.setdefault('source_status', {})['edge_v05'] = status
    for entry in manifest.get('races') or []:
        race_path = day / entry['path']
        bundle = json.loads(race_path.read_text(encoding='utf-8'))
        bundle.setdefault('metadata', {}).setdefault('source_status', {})['edge_v05'] = status
        _write_json(bundle, race_path)
        entry['sha256'] = _sha_file(race_path)
        entry['size_bytes'] = race_path.stat().st_size
    _write_json(manifest, manifest_path)


def build_preview(base_day: Path, output_dir: Path, paci: Path, analysis_root: Path | None,
                  oos_artifact_zip: Path, *, cohort_path: Path = DEFAULT_COHORT,
                  oos_manifest_path: Path = DEFAULT_OOS_MANIFEST,
                  freeze_manifest_path: Path = DEFAULT_FREEZE_MANIFEST,
                  display_smoke_test: bool = False) -> dict[str, Any]:
    if output_dir.resolve() == base_day.resolve():
        raise PreviewError('preview output must differ from base day')
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(base_day, output_dir)
    try:
        candidates, oos, provenance = load_sources(cohort_path, oos_manifest_path, freeze_manifest_path, oos_artifact_zip)
        raw_facts, fact_audit = build_current_facts(paci, analysis_root=analysis_root)
        facts, availability = project_facts(raw_facts, provenance['latest_evaluated_race_date'], allow_evaluated_date=display_smoke_test)
        matches = build_matches(list(candidates.values()), facts)
        fact_keys = [(str(f['race_key']), str(f['race_horse_key']), int(f['horse_no'])) for f in facts]
        if len(fact_keys) != len(set(fact_keys)):
            raise PreviewError('duplicate projected runner identity')
        by_key: dict[tuple[str, str, int], list[str]] = defaultdict(list)
        for row in matches:
            key = (str(row['race_key']), str(row['race_horse_key']), int(row['horse_no']))
            by_key[key].append(row['candidate_id'])
        if len(matches) != len({(str(r['race_key']), str(r['race_horse_key']), int(r['horse_no']), r['candidate_id']) for r in matches}):
            raise PreviewError('duplicate candidate match identity')
        consumed: set[tuple[str, str, int]] = set()
        horse_count = 0
        for race_path in sorted((output_dir / 'races').glob('*.json')):
            bundle = json.loads(race_path.read_text(encoding='utf-8'))
            race_key = str(bundle['race']['race_key'])
            race_dictionary = {}
            for horse in bundle.get('horses') or []:
                key_data = horse['key']
                key = (race_key, str(key_data['race_horse_key']), int(key_data['horse_no']))
                if key not in fact_keys or key in consumed:
                    raise PreviewError(f'missing or duplicate exact join: {key}')
                consumed.add(key); horse_count += 1
                ids = by_key.get(key, [])
                details = {cid: candidate_detail(candidates[cid], oos[cid]) for cid in ids}
                ordered = order_ids(ids, details)
                horse.setdefault('addons', {})['edge_v05'] = {'candidate_ids': ordered}
                race_dictionary.update(details)
            bundle['edge_v05_candidates'] = race_dictionary
            _write_json(bundle, race_path)
        if consumed != set(fact_keys):
            raise PreviewError(f'extra fact joins: {len(set(fact_keys) - consumed)}')
        state_message = ('DISPLAY SMOKE TEST: layout/merge only; target date may be inside frozen OOS window; '
                         if display_smoke_test else '') + \
                        'T1/T2 and resolved T3/T4 transition preview; first-use history and verified pre-race going unavailable'
        _set_state(output_dir, 'PARTIAL', state_message)
        package = _write_day_package(output_dir, output_dir / 'day-package.json')
        audit = {'status': 'PARTIAL', 'source_version': VERSION, 'source': provenance,
                 'paci_sha256': _sha_file(paci), 'analysis_root': str(analysis_root) if analysis_root else None,
                 'display_smoke_test': display_smoke_test,
                 'analysis_generation': (fact_audit.get('analysis_history') or {}).get('generation_id'),
                 'runner_rows': len(facts), 'matched_runner_count': len(by_key),
                 'signal_count': len(matches), 'newspaper_merged_rows': horse_count,
                 'missing_join_count': 0, 'extra_join_count': 0,
                 'family_match_counts': dict(Counter(r['family'] for r in matches)),
                 'unavailable_candidate_counts': {
                     'first_history': sum(any(k in c['conditions'] for k in ('first_dirt', 'first_turf', 'first_blinkers')) for c in candidates.values()),
                     'target_going': sum('going_bucket' in c['conditions'] for c in candidates.values()),
                 },
                 'availability': availability, 'fact_audit': fact_audit,
                 'day_package': package}
    except Exception as exc:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        shutil.copytree(base_day, output_dir)
        _set_state(output_dir, 'ERROR', f'{type(exc).__name__}: {exc}'[:500])
        package = _write_day_package(output_dir, output_dir / 'day-package.json')
        audit = {'status': 'ERROR', 'message': f'{type(exc).__name__}: {exc}'[:500],
                 'day_package': package}
    audit_path = output_dir / 'audit.json'
    saved = json.loads(audit_path.read_text(encoding='utf-8')) if audit_path.is_file() else {}
    saved['edge_v05_preview'] = audit
    _write_json(saved, audit_path)
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('base-day', 'output-dir', 'paci', 'oos-artifact-zip'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--analysis-root', type=Path)
    parser.add_argument('--display-smoke-test', action='store_true',
                        help='Allow an in-window historical date for UI/merge smoke testing only.')
    args = parser.parse_args()
    print(json.dumps(build_preview(args.base_day, args.output_dir, args.paci, args.analysis_root,
                                   args.oos_artifact_zip, display_smoke_test=args.display_smoke_test), ensure_ascii=False, sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
