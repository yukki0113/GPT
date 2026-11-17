"""M6-5B stage-2: canonical, source-pinned EXTRA material screening.

Fail-closed unless an explicit, sourced *hypothetical* simultaneous material
state, a summon method, and a restriction review are all present. No game
execution is claimed, and no material state is inferred from owned cards.
"""
from __future__ import annotations
from collections import Counter
from hashlib import sha256
from pathlib import Path
import json, re, sqlite3

CID=re.compile(r'konami:[0-9]+\Z')
SHA=re.compile(r'[0-9a-f]{64}\Z')
METHODS={'FUSION','SYNCHRO','XYZ','LINK'}


def screen_structured_extra_materials(db_path, *, expected_sqlite_sha256,
                                      extra_card_ids, proposed_routes=()):
    """Produce M6-5B schema-compatible screen from explicit source evidence.

    proposed_routes elements contain EXACT keys:
      extra_card_id, summon_method, material_card_ids, evidence_ids,
      simultaneous_state_evidence_ids, summon_method_evidence_ids,
      restriction_review, material_labels, link_material_ratings

    material_labels has exact source first-line strings for FUSION only;
    link_material_ratings has each consumed material's contribution (1 or
    its actual Link rating) for LINK only; empty for other methods.

    A valid matching route results in POSSIBLE_ON_PAPER, never verified duel
    success. A source material header without explicit route evidence is
    REQUIRES_REVIEW, even when its grammar is parsed.
    """
    db=Path(db_path)
    if not SHA.fullmatch(expected_sqlite_sha256) or sha256(db.read_bytes()).hexdigest()!=expected_sqlite_sha256:
        raise ValueError('STAGE2_MASTER_SHA_MISMATCH')
    if (not isinstance(extra_card_ids,(list,tuple)) or len(extra_card_ids)>120
        or len(set(extra_card_ids))!=len(extra_card_ids) or
        not all(isinstance(c,str) and CID.fullmatch(c) for c in extra_card_ids)):
        raise ValueError('STAGE2_EXTRA_IDS_INVALID')
    if not isinstance(proposed_routes,(list,tuple)) or len(proposed_routes)>120:
        raise ValueError('STAGE2_ROUTES_INVALID')
    keys={'extra_card_id','summon_method','material_card_ids','evidence_ids',
          'simultaneous_state_evidence_ids','summon_method_evidence_ids',
          'restriction_review','material_labels','link_material_ratings'}
    by_extra={}
    for r in proposed_routes:
        if not isinstance(r,dict) or set(r)!=keys:
            raise ValueError('STAGE2_ROUTE_CONTRACT')
        eid=r['extra_card_id']
        if eid not in extra_card_ids or eid in by_extra or r['summon_method'] not in METHODS:
            raise ValueError('STAGE2_ROUTE_TARGET')
        for col in ('evidence_ids','simultaneous_state_evidence_ids','summon_method_evidence_ids'):
            if not isinstance(r[col],list) or not r[col] or not all(isinstance(x,str) and x.strip() for x in r[col]):
                raise ValueError('STAGE2_EVIDENCE_REQUIRED:'+col)
        ids=r['material_card_ids']
        if not isinstance(ids,list) or not 1<=len(ids)<=8 or not all(isinstance(x,str) and CID.fullmatch(x) for x in ids):
            raise ValueError('STAGE2_MATERIAL_IDS')
        if r['restriction_review'] not in ('REVIEWED','NOT_REVIEWED'):
            raise ValueError('STAGE2_RESTRICTION_REVIEW')
        if not isinstance(r['material_labels'],list) or not all(isinstance(x,str) for x in r['material_labels']):
            raise ValueError('STAGE2_FUSION_LABELS')
        if not isinstance(r['link_material_ratings'],list) or not all(type(x) is int and 1<=x<=8 for x in r['link_material_ratings']):
            raise ValueError('STAGE2_LINK_RATINGS')
        by_extra[eid]=r
    con=sqlite3.connect(f'file:{db.resolve().as_posix()}?mode=ro&immutable=1',uri=True)
    con.row_factory=sqlite3.Row
    try:
        con.execute('PRAGMA query_only=ON')
        if con.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('STAGE2_DB_INTEGRITY')
        if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='card_extra_material_requirements'").fetchone():
            raise ValueError('STAGE2_REQUIREMENTS_DB_MISSING')
        result=[]
        for eid in extra_card_ids:
            req=con.execute('SELECT * FROM card_extra_material_requirements WHERE card_id=?',(eid,)).fetchone()
            if not req:raise ValueError('STAGE2_EXTRA_NOT_CLASSIFIED:'+eid)
            body=con.execute("SELECT body FROM card_texts WHERE card_id=? AND language='ja'",(eid,)).fetchone()
            if not body or sha256(body[0].encode()).hexdigest()!=req['source_text_sha256']:
                raise ValueError('STAGE2_TEXT_PIN_MISMATCH:'+eid)
            reason='ROUTE_EVIDENCE_MISSING'; accepted=False
            route=by_extra.get(eid)
            if route:
                reason='REQUIRES_REVIEW'
                mat_ids=route['material_card_ids']
                mats=con.execute('SELECT a.card_id,a.kind,a.level,a.link FROM card_attributes a WHERE a.card_id IN ('+
                                 ','.join('?' for _ in mat_ids)+')',list(set(mat_ids))).fetchall()
                matmap={m['card_id']:m for m in mats}
                if len(matmap)!=len(set(mat_ids)) or not all(matmap[i]['kind']=='MONSTER' for i in mat_ids):
                    reason='MATERIAL_ID_MISSING_OR_NONMONSTER'
                elif route['summon_method']!=req['summon_method']:
                    reason='SUMMON_METHOD_MISMATCH'
                elif req['grammar']=='UNPARSED':
                    reason='MATERIAL_REQUIREMENT_UNPARSED'
                elif route['restriction_review']!='REVIEWED':
                    reason='SUMMON_RESTRICTIONS_NOT_REVIEWED'
                else:
                    n=req['min_materials']
                    expected_labels=json.loads(req['material_labels_json'])
                    if req['summon_method']=='XYZ' and req['grammar']=='GENERIC_XYZ_LEVEL':
                        accepted=len(mat_ids)==n and all(matmap[i]['level']==req['level_required'] for i in mat_ids)
                        reason='SOURCE_ALIGNED_XYZ_HYPOTHESIS' if accepted else 'XYZ_LEVEL_OR_COUNT_MISMATCH'
                    elif req['summon_method']=='SYNCHRO' and req['grammar']=='GENERIC_SYNCHRO_TUNER':
                        flags={cid:{t[0] for t in con.execute('SELECT monster_type FROM card_monster_types WHERE card_id=?',(cid,))} for cid in set(mat_ids)}
                        target=con.execute('SELECT level FROM card_attributes WHERE card_id=?',(eid,)).fetchone()[0]
                        accepted=(len(mat_ids)>=n and sum('TUNER' in flags[i] for i in mat_ids)==1
                                  and all(matmap[i]['level'] is not None for i in mat_ids)
                                  and sum(matmap[i]['level'] for i in mat_ids)==target)
                        reason='SOURCE_ALIGNED_SYNCHRO_HYPOTHESIS' if accepted else 'SYNCHRO_TUNER_LEVEL_COUNT_MISMATCH'
                    elif req['summon_method']=='LINK' and req['grammar']=='GENERIC_LINK_COUNT':
                        ratings=route['link_material_ratings']
                        target=con.execute('SELECT link FROM card_attributes WHERE card_id=?',(eid,)).fetchone()[0]
                        flags={cid:{t[0] for t in con.execute('SELECT monster_type FROM card_monster_types WHERE card_id=?',(cid,))} for cid in set(mat_ids)}
                        accepted=(len(mat_ids)>=n and len(ratings)==len(mat_ids) and target is not None
                                  and sum(ratings)==target
                                  and all(rate in (1,matmap[cid]['link']) for rate,cid in zip(ratings,mat_ids))
                                  and (req['qualifier']!='EFFECT_ONLY' or all('EFFECT' in flags[cid] for cid in mat_ids)))
                        reason='SOURCE_ALIGNED_LINK_HYPOTHESIS' if accepted else 'LINK_RATING_OR_TYPE_MISMATCH'
                    elif req['summon_method']=='FUSION' and req['grammar'] in ('FUSION_EXPLICIT_LABELS','FUSION_REPEATED_LABEL'):
                        # The label-to-card qualification is provided by the
                        # route reviewer, not inferred by this engine. Restriction
                        # review is separately mandatory; hence a paper claim only.
                        accepted=(len(mat_ids)==n and Counter(route['material_labels'])==Counter(expected_labels)
                                  and not route['link_material_ratings'])
                        reason='SOURCE_ALIGNED_FUSION_HYPOTHESIS' if accepted else 'FUSION_LABEL_OR_COUNT_MISMATCH'
                    if req['summon_method']!='FUSION' and route['material_labels']:
                        accepted=False;reason='IRRELEVANT_FUSION_LABELS'
                    if req['summon_method']!='LINK' and route['link_material_ratings']:
                        accepted=False;reason='IRRELEVANT_LINK_RATINGS'
            result.append({'card_id':eid,'first_line':req['material_header'],
                           'material_class':req['grammar'],
                           'source_text_sha256':req['source_text_sha256'],
                           'matched_capability_evidence_ids':sorted(set(route['evidence_ids'])) if accepted else [],
                           'screen':'POSSIBLE_ON_PAPER' if accepted else 'REQUIRES_REVIEW',
                           'review_reason':reason,
                           'gameplay_compatibility_verified':False,
                           'materials_simultaneously_available_verified':False,
                           'official_md_legality_verified':False})
        return {'schema':'md-m6-5b-material-screen-v1',
                'master_sqlite_sha256':expected_sqlite_sha256,'results':result,
                'gameplay_verified':False,
                'warning':'Source-aligned, explicitly reviewed material hypothesis only; neither simultaneous access nor in-game summon verified.'}
    finally:con.close()