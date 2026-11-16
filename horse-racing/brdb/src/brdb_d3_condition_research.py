#!/usr/bin/env python3
"""BRDB D3: retrospective sire/BMS condition evidence (research-only).

Consumes an immutable JRDB Analysis v1.4 CURRENT manifest and the exact
Stage3-B frozen 50-subject master. Historical starts are outcomes, *never*
race-day source-availability proof or a production prediction signal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import duckdb

SCHEMA = 'brdb-d3-condition-research-v0.1'
TOP50_SHA = '89d01e2c05af27a929c8398ef9e94660f5f1e442362d458383db6e6a9bd7bdc0'
SOURCE_GENERATION = '5279af0bd8226cde'
STARTERS = ('0', '3', '4', '5', '6')
SURFACES = ('1', '2')
# Encoded surface and going codes are preserved, not interpreted as suitability.
SCOPES = {
    'SURFACE': ('track_type',),
    'SURFACE_BAND': ('track_type', 'distance_band'),
    'SURFACE_DISTANCE': ('track_type', 'distance'),
    'VENUE_SURFACE_BAND': ('venue_code', 'track_type', 'distance_band'),
    'SURFACE_GOING_CODE': ('track_type', 'track_condition_code'),
    'VENUE_SURFACE_GOING_CODE': ('venue_code', 'track_type', 'track_condition_code'),
}


class D3ResearchError(ValueError):
    """Invalid input, duplicate source result, or unsupported interpretation."""


def require(condition: bool, explanation: str) -> None:
    if not condition:
        raise D3ResearchError(explanation)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _quote(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def verified_history(root: Path) -> tuple[str, list[Path], dict[str, str]]:
    """Validate every referenced partition by exact bytes before SQL reads."""
    root = root.resolve()
    pointer_file = root / 'current.json'
    pointer = json.loads(pointer_file.read_text(encoding='utf-8'))
    require(pointer.get('status') == 'CURRENT', 'analysis CURRENT marker invalid')
    relative = pointer.get('manifest')
    require(isinstance(relative, str) and relative.endswith('.json'), 'bad manifest path')
    manifest_path = (root / relative).resolve()
    require(manifest_path.is_relative_to(root), 'manifest escaped analysis root')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    generation = pointer.get('generation_id')
    require(generation == manifest.get('generation_id') and
            manifest.get('schema_version') == 'v1.4' and
            manifest.get('validation_status') is not None,
            'unsupported or drifted Analysis generation')
    partitions = manifest.get('fact_table', {}).get('partitions')
    require(isinstance(partitions, list) and len(partitions) >= 1, 'no fact partitions')
    files = []
    hashes = {}
    for item in partitions:
        relative = item.get('relative_path')
        require(isinstance(relative, str), 'bad partition path')
        file = (root / relative).resolve()
        require(file.is_relative_to(root) and file.is_file(), 'missing/escaped partition')
        actual = sha256(file)
        require(actual == item.get('sha256'), 'partition checksum mismatch')
        require(relative not in hashes, 'duplicate manifest partition')
        hashes[relative] = actual
        files.append(file)
    require(len(files) == len(set(files)), 'duplicate partition source')
    return generation, files, hashes


def verified_subjects(path: Path) -> list[dict]:
    require(sha256(path) == TOP50_SHA, 'Stage3-B top50 SHA drift')
    top = json.loads(path.read_text(encoding='utf-8'))
    require(top.get('source_generation') == SOURCE_GENERATION and
            top.get('research_only') is True and
            top.get('prediction_safe') is False, 'wrong Stage3-B research population')
    subjects = top.get('subjects')
    require(isinstance(subjects, list) and len(subjects) == 50,
            'expected exactly 50 ranked sources')
    require(set(s['rank'] for s in subjects) == set(range(1, 51)) and
            len({s['name'] for s in subjects}) == 50 and
            all(type(s['name']) is str and s['name'].strip() for s in subjects),
            'ranking name/identity duplicates or missing')
    return sorted(subjects, key=lambda s: s['rank'])


def wilson95(hits: int, total: int) -> list[float] | None:
    if total == 0:
        return None
    p = hits / total
    z = 1.959963984540054
    denom = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denom
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total**2)) / denom
    return [round(max(0.0, center - radius), 6),
            round(min(1.0, center + radius), 6)]


def _summary(starts: int, horses: int, wins: int, top3: int,
             base_starts: int, base_top3: int) -> dict:
    require(0 <= wins <= top3 <= starts and 0 <= base_top3 <= base_starts,
            'inconsistent official placement counts')
    measured = top3 / starts if starts else None
    baseline = base_top3 / base_starts if base_starts else None
    return {
        'starts': starts, 'distinct_horses': horses, 'wins': wins,
        'top3': top3, 'win_rate': round(wins/starts, 6) if starts else None,
        'top3_rate': round(measured, 6) if measured is not None else None,
        'wilson95_top3': wilson95(top3, starts),
        'baseline_starts': base_starts,
        'baseline_top3': base_top3,
        'baseline_top3_rate': round(baseline, 6) if baseline is not None else None,
        'top3_delta_percentage_points': round(100*(measured-baseline), 3)
        if measured is not None and baseline is not None else None,
        'sample_status': 'NO_SAMPLE' if not starts else
        ('LOW_SAMPLE' if starts < 30 or horses < 10 else 'DESCRIPTIVE'),
        'interpretation': 'OBSERVED_ONLY_NOT_CAUSAL_NOT_PREDICTION',
    }


def _where_scope(cols: tuple[str, ...]) -> str:
    return ', '.join(cols)


def _extract(conn: duckdb.DuckDBPyConnection, scope: str,
             cols: tuple[str, ...], names: set[str]) -> list[dict]:
    """Match exact strings, no fuzzy seed or official-person-ID coercion."""
    coltext = _where_scope(cols)
    # Descriptive source stats; a result can occur in the sire and BMS lanes,
    # hence no cross-lane summing of starts is ever allowed.
    measures = (
        "COUNT(*) AS starts, COUNT(DISTINCT horse_id) AS horses, "
        "COUNT(*) FILTER (WHERE abnormal_code IN ('0','5') AND finish=1) AS wins, "
        "COUNT(*) FILTER (WHERE abnormal_code IN ('0','5') AND finish BETWEEN 1 AND 3) AS top3"
    )
    base_rows = conn.execute(
        f'SELECT {coltext}, {measures} FROM starts GROUP BY {coltext}'
    ).fetchall()
    baseline = {tuple(row[:len(cols)]): row[len(cols):] for row in base_rows}
    results = []
    for lane, source_column in (('SIRE', 'sire_name'), ('BMS', 'broodmare_sire_name')):
        raw = conn.execute(
            f'SELECT {source_column}, {coltext}, {measures} FROM starts '
            f'WHERE {source_column} IS NOT NULL AND {source_column} <> \'\' '
            f'GROUP BY {source_column}, {coltext}'
        ).fetchall()
        for row in raw:
            name = row[0]
            if name not in names:
                continue
            dimension_values = tuple(row[1:1+len(cols)])
            # Baselines are aggregated from the same field and same scoped rows.
            b = baseline[dimension_values]
            stats = _summary(*(int(k) for k in row[1+len(cols):]),
                             int(b[0]), int(b[3]))
            results.append({
                'lane': lane, 'name': name, 'scope': scope,
                'dimensions': dict(zip(cols, dimension_values)),
                **stats,
            })
    return results


def analyse(analysis_root: Path, top50_file: Path, *,
            cutoff_exclusive: str = '2026-11-02') -> dict:
    """Compute conditional retrospective evidence over pinned Analysis facts."""
    require(cutoff_exclusive == '2026-11-02',
            'D3 initial cohort is pinned to the 2026-11-01 completed snapshot')
    subjects = verified_subjects(top50_file)
    generation, files, hashes = verified_history(analysis_root)
    names = {s['name'] for s in subjects}
    conn = duckdb.connect(':memory:')
    try:
        literal_list = '[' + ','.join(_quote(p) for p in files) + ']'
        conn.execute(f'''CREATE TEMP TABLE starts AS SELECT
            race_key, race_date, horse_id, venue_code, track_type,
            track_condition_code, distance,
            CASE WHEN distance < 1400 THEN 'SHORT'
                 WHEN distance < 1800 THEN 'MILE'
                 WHEN distance < 2400 THEN 'MIDDLE'
                 ELSE 'LONG' END AS distance_band,
            sire_name, broodmare_sire_name, abnormal_code, finish
            FROM read_parquet({literal_list})
            WHERE race_date < ? AND race_date >= '2016-01-01'
              AND track_type IN ('1','2')
              AND abnormal_code IN ('0','3','4','5','6')
              AND horse_id IS NOT NULL AND race_key IS NOT NULL
              AND distance > 0''', [cutoff_exclusive])
        quality = conn.execute('''SELECT count(*) AS starts,
            count(distinct (race_key,horse_id)) AS unique_starts,
            count(distinct horse_id) AS unique_horses,
            count(*) FILTER (WHERE sire_name IS NULL OR sire_name='') AS missing_sire,
            count(*) FILTER (WHERE broodmare_sire_name IS NULL OR broodmare_sire_name='') AS missing_bms,
            min(race_date),max(race_date)
            FROM starts''').fetchone()
        require(quality[0] == quality[1], 'duplicate official starter race/horse identity')
        require(quality[0] > 0, 'empty certified race history')
        require(quality[5] < cutoff_exclusive, 'future result leakage')
        evidence = []
        for scope, cols in SCOPES.items():
            evidence.extend(_extract(conn, scope, cols, names))
        evidence.sort(key=lambda x: (x['lane'], x['name'], x['scope'],
                                     json.dumps(x['dimensions'], sort_keys=True)))
        # Exact observed sire+BMS pairing. Same-start pair only, no pooled
        # summation with separate sire/BMS lanes and no inferred ancestor ID.
        pairs = []
        pair_measures = (
            "COUNT(*) AS starts, COUNT(DISTINCT horse_id) AS horses, "
            "COUNT(*) FILTER (WHERE abnormal_code IN ('0','5') AND finish=1) AS wins, "
            "COUNT(*) FILTER (WHERE abnormal_code IN ('0','5') AND finish BETWEEN 1 AND 3) AS top3"
        )
        b = conn.execute(f'SELECT track_type,distance_band,{pair_measures} '
                         'FROM starts GROUP BY 1,2').fetchall()
        base = {(r[0], r[1]): r[2:] for r in b}
        p_rows = conn.execute(
            f'SELECT sire_name,broodmare_sire_name,track_type,distance_band,{pair_measures} '
            'FROM starts GROUP BY 1,2,3,4').fetchall()
        for sire, bms, surface, band, starts, horses, wins, top3 in p_rows:
            if sire not in names or bms not in names:
                continue
            baseline = base[surface,band]
            pairs.append({
                'sire_name': sire, 'bms_name': bms,
                'dimensions': {'track_type': surface,'distance_band': band},
                **_summary(starts, horses, wins, top3, baseline[0], baseline[3]),
            })
        pairs.sort(key=lambda x: (x['sire_name'], x['bms_name'],
                                  x['dimensions']['track_type'],
                                  x['dimensions']['distance_band']))
        lane_counts = Counter(row['lane'] for row in evidence)
        return {
            'schema_version': SCHEMA,
            'research_only': True, 'prediction_safe': False,
            'historical_asof_status': 'AS_OF_UNVERIFIED',
            'source_snapshot_generation': generation,
            'selection_generation': SOURCE_GENERATION,
            'as_of_exclusive': cutoff_exclusive,
            'population': {
                'source_subject_count': len(subjects),
                'source_subjects': [{'rank': s['rank'], 'name': s['name']} for s in subjects],
                'historical_starts': quality[0],
                'historical_unique_horses': quality[2],
                'missing_sire_labels': quality[3],
                'missing_bms_labels': quality[4],
                'history_first_date': quality[5],
                'history_last_date': quality[6],
            },
            'source_sha256': {
                'top50': sha256(top50_file),
                'manifest': sha256((analysis_root / 'current.json').resolve()),
                'parquet_partitions': hashes,
            },
            'policy': {
                'starter_codes': list(STARTERS),
                'winning_codes': ['0','5'],
                'surface_codes': list(SURFACES),
                'distance_bands': {'SHORT':'0-1399m', 'MILE':'1400-1799m',
                                   'MIDDLE':'1800-2399m','LONG':'2400+m'},
                'sample_descriptive_only': 'starts>=30 AND distinct_horses>=10',
                'baseline': 'all starters in the identical condition bucket',
                'label_match': 'exact historical sire/BMS label',
                'going_code_policy': 'raw source code; no interpretation of wet/dry effects',
                'overlap_policy': 'sire, BMS, and pair lanes overlap; do not sum across lanes',
                'historical_source_timing': 'not independently verified for race-day use',
                'asof_outcome_guard': 'completed history before 2026-11-02; retrospective only',
                'unverified_ancestor_ids': 'no ancestral identity join and no suitability claims',
                'score_or_rank_production': False,
            },
            'evidence_rows': evidence,
            'pair_rows': pairs,
            'counts': {'evidence_by_lane': dict(sorted(lane_counts.items())),
                       'pair_observed_cells': len(pairs)},
        }
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--analysis-root', type=Path, required=True)
    ap.add_argument('--top50', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    payload = analyse(args.analysis_root, args.top50)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False,
                                      sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({**payload['counts'], 'historical_starts':payload['population']['historical_starts']},
                     ensure_ascii=False,sort_keys=True))

if __name__ == '__main__':
    main()