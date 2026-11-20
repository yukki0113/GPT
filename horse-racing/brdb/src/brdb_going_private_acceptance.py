#!/usr/bin/env python3
"""Private-input acceptance for BRDB v0.6 multi-lane going discovery.

Consumes the real private M7 relatives-detail candidate plus the same SHA-verified
Analysis/PACI inputs used by the public source-real replay. Horse-level output is
private by contract; a separate aggregate receipt contains no horse identifiers,
names or individual statistics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
JRDB_SRC = HERE.parents[1] / 'jrdb' / 'src'
if str(JRDB_SRC) not in sys.path:
    sys.path.insert(0, str(JRDB_SRC))

REL_SCOPES = ('VENUE_COURSE_EXACT','VENUE_DISTANCE','VENUE_BAND','ALL_VENUES_DISTANCE','ALL_VENUES_BAND')
RELATIONS = ('FULL_SIBLING','MATERNAL_HALF_SIBLING','MATERNAL_AUNT_UNCLE','SAME_DAM_SAME_SIRE_NAME_UNVERIFIED')
from brdb_going_multilane_discovery import build_from_aggregated, VERSION as DISCOVERY_VERSION  # noqa: E402

VERSION = 'brdb-going-private-acceptance-v0.1-candidate'


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()




def _convert_relatives(row: dict) -> dict:
    rels=row['relatives']; by_scope=defaultdict(list); individual=[]; seen=set()
    for rel in rels:
        rid=rel['horse_id']; relation=rel['relationship']
        require(isinstance(rid,str) and len(rid)==8 and rid.isdigit(),'relative id invalid')
        require(rid not in seen,'duplicate relative id'); seen.add(rid)
        require(relation in RELATIONS,'unknown kinship')
        require(set(rel['scope_stats'])==set(REL_SCOPES),'relative scope set mismatch')
        obs=[]
        for scope in REL_SCOPES:
            st=rel['scope_stats'][scope]; n,w,t,rate=st['starts'],st['wins'],st['top3'],st['top3_rate']
            require(all(type(x) is int for x in (n,w,t)) and 0<=w<=t<=n,'relative counts invalid')
            require((rate is None and n==0) or (n>0 and rate is not None and abs(rate-t/n)<0.00011),'relative rate mismatch')
            counts={'starts':n,'wins':w,'top3':t,'top3_rate':rate}
            by_scope[(scope,relation)].append((rid,counts)); obs.append({'scope_key':scope,'counts':counts})
        individual.append({'relative_horse_id':rid,'relative_name':rel.get('horse_name'),'relation':relation,'scope_observations':obs,'historical_asof_status':'AS_OF_UNVERIFIED'})
    grouped=[]
    for scope in REL_SCOPES:
        for relation in RELATIONS:
            rows=by_scope[(scope,relation)]
            if not rows: continue
            n=sum(x['starts'] for _,x in rows); w=sum(x['wins'] for _,x in rows); t=sum(x['top3'] for _,x in rows)
            grouped.append({'scope_key':scope,'relation':relation,'relative_count':len(rows),'relatives_with_starts':sum(x['starts']>0 for _,x in rows),'counts':{'starts':n,'wins':w,'top3':t,'top3_rate':t/n if n else None},'source':'M7_RELATIVES_DETAIL','interpretation_status':'OBSERVATION_ONLY','historical_asof_status':'AS_OF_UNVERIFIED','prediction_eligible':False,'display_eligible':False})
    return {'status':row['status'],'individual':individual,'grouped_scopes':grouped,'pending':[] if rels else [{'kind':'RELATIVES_CONDITION','reason':'NO_CONFIRMED_RELATIVES'}],'overlapping_scopes':True,'historical_asof_status':'AS_OF_UNVERIFIED'}

def load_relatives_detail(path: Path, race: dict, horses: list[dict]) -> tuple[dict[str, dict], dict]:
    raw = json.loads(path.read_text(encoding='utf-8'))
    require(raw.get('contract_version') == 'brdb-m7-relatives-detail-v0.1-candidate', 'relative detail contract')
    require(raw.get('research_only') is True and raw.get('prediction_safe') is False, 'relative detail authorization')
    require(raw.get('historical_asof_status') == 'AS_OF_UNVERIFIED', 'relative historical as-of status')
    meta = raw.get('source_metadata') or {}
    require(meta.get('as_of_exclusive') == race['target_date'], 'relative as-of mismatch')
    cov = raw.get('aggregate_coverage') or {}
    require(cov.get('field_size') == race['field_size'] == len(horses), 'relative field size mismatch')
    rows = raw.get('horses')
    require(isinstance(rows, list) and len(rows) == race['field_size'], 'relative cohort incomplete')

    target = {(h['horse_no'], h['horse_id']) for h in horses}
    seen = set()
    mapped = {}
    relative_records = 0
    scope_cells = 0
    zero_cells = 0
    with_starts = 0
    for row in rows:
        key = (row.get('horse_no'), row.get('horse_id'))
        require(key in target, 'relative cohort identity mismatch')
        require(key not in seen, 'duplicate relative target identity')
        seen.add(key)
        rels = row.get('relatives')
        require(isinstance(rels, list), 'relative list missing')
        for rel in rels:
            require(set(rel.get('scope_stats', {})) == set(REL_SCOPES), 'relative scope set mismatch')
            relative_records += 1
            for scope in REL_SCOPES:
                st = rel['scope_stats'][scope]
                n, w, t, rate = st['starts'], st['wins'], st['top3'], st['top3_rate']
                require(all(type(x) is int for x in (n, w, t)) and 0 <= w <= t <= n, 'relative counts invalid')
                require((rate is None and n == 0) or (n > 0 and rate is not None and abs(rate - t / n) < 0.00011), 'relative rate mismatch')
                scope_cells += 1
                zero_cells += int(n == 0)
        converted = _convert_relatives(row)
        if any(x['counts']['starts'] > 0 for x in converted['grouped_scopes']):
            with_starts += 1
        mapped[row['horse_id']] = converted

    require(seen == target, 'relative cohort mismatch')
    require(relative_records == cov.get('relative_records'), 'relative record total mismatch')
    require(scope_cells == cov.get('scope_observations'), 'relative scope cell total mismatch')
    require(zero_cells == cov.get('zero_start_cells'), 'relative zero cell total mismatch')
    receipt = {
        'relative_detail_sha256': sha256(path),
        'relative_records': relative_records,
        'scope_observations': scope_cells,
        'zero_start_cells': zero_cells,
        'horses_with_relative_starts': with_starts,
        'historical_asof_status': raw['historical_asof_status'],
    }
    return mapped, receipt


def aggregate_receipt(result: dict, relative_receipt: dict) -> dict:
    summary = result['summary']
    rel_links = summary['relative_condition_links']
    return {
        'acceptance_version': VERSION,
        'status': 'PASS_RESEARCH_ONLY',
        'discovery_contract': DISCOVERY_VERSION,
        'race_key': result['race']['race_key'],
        'target_date': result['race']['target_date'],
        'horse_count': len(result['horses']),
        'relative_input': relative_receipt,
        'selected_observation_count': sum(x['count'] for x in summary['selected_observations']),
        'primary_observation_count': sum(x['count'] for x in summary['primary_observations']),
        'cross_lane_alignment_count': sum(x['count'] for x in summary['cross_lane_alignments']),
        'relative_condition_link_count': sum(x['count'] for x in rel_links),
        'relative_condition_links_by_state_lane': rel_links,
        'horses_with_selected_signal_by_state': summary['horses_with_selected_signal_by_state'],
        'private_horse_level_output_written': True,
        'aggregate_contains_horse_identity': False,
        'nested_and_related_samples_not_independent': True,
        'relative_going_state_known': False,
        'prediction_eligible': False,
        'display_eligible': False,
        'production_authorized': False,
    }


def run(manifest: Path, objects_root: Path, paci: Path, race_key: str, target_date: str,
        relative_detail: Path, private_output: Path, aggregate_output: Path) -> tuple[dict, dict]:
    from brdb_going_multilane_real_replay import cohort, aggregate_lane_counts
    race, horses = cohort(paci, target_date, race_key)
    relative_map, relative_receipt = load_relatives_detail(relative_detail, race, horses)
    lane_counts, source = aggregate_lane_counts(manifest, objects_root, race, horses)
    result = build_from_aggregated(race, horses, lane_counts, relative_map, source=source)
    require(len(result['horses']) == race['field_size'], 'output cohort mismatch')
    # All private target horses must be represented exactly once.
    ids = [h['horse_id'] for h in result['horses']]
    require(len(ids) == len(set(ids)) == race['field_size'], 'output identity duplication')
    private_output.parent.mkdir(parents=True, exist_ok=True)
    aggregate_output.parent.mkdir(parents=True, exist_ok=True)
    private_output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    receipt = aggregate_receipt(result, relative_receipt)
    aggregate_output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return result, receipt


def cli():
    ap = argparse.ArgumentParser()
    for name in ('manifest', 'objects-root', 'paci', 'race-key', 'target-date', 'relative-detail', 'private-output', 'aggregate-output'):
        ap.add_argument('--' + name, required=True)
    a = ap.parse_args()
    _, receipt = run(Path(a.manifest), Path(a.objects_root), Path(a.paci), a.race_key, a.target_date,
                     Path(a.relative_detail), Path(a.private_output), Path(a.aggregate_output))
    print(json.dumps({
        'status': receipt['status'],
        'horse_count': receipt['horse_count'],
        'relative_condition_link_count': receipt['relative_condition_link_count'],
        'private_output': 'WRITTEN_NOT_FOR_PUBLICATION',
    }, ensure_ascii=False))


if __name__ == '__main__':
    cli()
