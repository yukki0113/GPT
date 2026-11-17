"""Identity-dependent EX material source claims, never summon authorization.

Evidence is a *reviewer-supplied claim*, even when marked REVIEWED. A source
hash binds a document but does not prove the document's authority or that a
live token/board state is true. Every material occurrence is independently
bound, including two copies of the same card ID.
"""
from __future__ import annotations
import re
import unicodedata
from hashlib import sha256

CID = re.compile(r'konami:[0-9]+\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
XYZ_THEME = re.compile(r'レベル(?P<level>[1-9][0-9]?)「(?P<label>[^「」\n]{1,60})」モンスター×(?P<count>[1-5])\Z')
LINK_THEME = re.compile(r'「(?P<label>[^「」\n]{1,60})」モンスター(?P<count>[1-5])体(?P<more>以上)?\Z')
LINK_TOKEN = re.compile(r'トークン以外のモンスター(?P<count>[1-5])体(?P<more>以上)?\Z')
CLAIM_KEYS = {'card_id','predicate','label','claim','source_ref','source_document_sha256','review_status'}
EVIDENCE_KEYS = {'master_sqlite_sha256','extra_card_id','material_header_sha256','occurrences'}


def observe_identity_header(method, header):
    """Unambiguous whole-header patterns, with opaque archetype label."""
    if method not in ('XYZ','LINK') or not isinstance(header,str):
        return None
    h=unicodedata.normalize('NFKC',header.strip())
    m=(XYZ_THEME.fullmatch(h) if method=='XYZ' else LINK_THEME.fullmatch(h))
    if m:
        return {'predicate':'ARCHETYPE_MEMBERSHIP', 'label':m.group('label'),
                'level':int(m.group('level')) if method=='XYZ' else None,
                'min_materials':int(m.group('count')),
                'max_materials':None if m.groupdict().get('more') else int(m.group('count')),
                'qualification_verified':False, 'route_verified':False}
    m=LINK_TOKEN.fullmatch(h) if method=='LINK' else None
    if m:
        return {'predicate':'NOT_TOKEN', 'label':None, 'level':None,
                'min_materials':int(m.group('count')),
                'max_materials':None if m.group('more') else int(m.group('count')),
                'qualification_verified':False, 'route_verified':False}
    return None


def diagnose_identity_claims(con, *, method, header, extra_card_id,
                             material_card_ids, expected_sqlite_sha256,
                             evidence, link_material_ratings=(), target_link=None):
    """Return (UNKNOWN|MISMATCH|CLAIM_ALIGNED, reason), never a verified MATCH.

    Evidence must be a complete, source-pinned *per-occurrence* claim bundle.
    Absence or incomplete review never yields a positive result. Mismatch
    is a contradiction of supplied claims, not a certified game judgment.
    """
    spec=observe_identity_header(method,header)
    if spec is None:
        return 'UNKNOWN','IDENTITY_SOURCE_GRAMMAR_UNSUPPORTED'
    if not isinstance(evidence,dict) or set(evidence)!=EVIDENCE_KEYS:
        return 'UNKNOWN','IDENTITY_EVIDENCE_MISSING_OR_MALFORMED'
    if (not isinstance(expected_sqlite_sha256,str) or
        not SHA.fullmatch(expected_sqlite_sha256) or
        evidence['master_sqlite_sha256']!=expected_sqlite_sha256 or
        evidence['extra_card_id']!=extra_card_id or
        evidence['material_header_sha256']!=sha256(header.encode()).hexdigest()):
        return 'UNKNOWN','IDENTITY_EVIDENCE_SOURCE_PIN_MISMATCH'
    ids=material_card_ids
    if not isinstance(ids,(list,tuple)) or not ids or not all(isinstance(x,str) and CID.fullmatch(x) for x in ids):
        return 'UNKNOWN','IDENTITY_MATERIAL_IDS_INVALID'
    n=len(ids)
    if n<spec['min_materials'] or (spec['max_materials'] is not None and n>spec['max_materials']):
        return 'MISMATCH','IDENTITY_MATERIAL_COUNT_MISMATCH'
    claims=evidence['occurrences']
    if not isinstance(claims,list) or len(claims)!=n:
        return 'UNKNOWN','IDENTITY_OCCURRENCE_EVIDENCE_INCOMPLETE'
    for cid,item in zip(ids,claims):
        if not isinstance(item,dict) or set(item)!=CLAIM_KEYS or item['card_id']!=cid:
            return 'UNKNOWN','IDENTITY_OCCURRENCE_BINDING_INVALID'
        if (item['predicate'] != spec['predicate'] or item['label'] != spec['label'] or
            type(item['claim']) is not bool or
            not isinstance(item['source_ref'],str) or not item['source_ref'].strip() or
            not isinstance(item['source_document_sha256'],str) or
            not SHA.fullmatch(item['source_document_sha256']) or
            item['review_status'] not in ('REVIEWED','NOT_REVIEWED')):
            return 'UNKNOWN','IDENTITY_OCCURRENCE_CLAIM_INVALID'
    if any(c['review_status']!='REVIEWED' for c in claims):
        return 'UNKNOWN','IDENTITY_CLAIMS_NOT_REVIEWED'
    unique=list(dict.fromkeys(ids))
    rows=con.execute('SELECT card_id,kind,level,link FROM card_attributes WHERE card_id IN ('+
                     ','.join('?' for _ in unique)+')',unique).fetchall()
    byid={r['card_id']:r for r in rows}
    if len(byid)!=len(unique) or any(byid[i]['kind']!='MONSTER' for i in ids):
        return 'UNKNOWN','IDENTITY_MATERIAL_ROW_MISSING'
    if method=='XYZ':
        if any(byid[i]['level'] is None for i in ids):
            return 'UNKNOWN','IDENTITY_LEVEL_MISSING'
        if any(byid[i]['level']!=spec['level'] for i in ids):
            return 'MISMATCH','IDENTITY_LEVEL_MISMATCH'
    if method=='LINK':
        ratings=link_material_ratings
        if (not isinstance(ratings,(list,tuple)) or len(ratings)!=n or
            type(target_link) is not int or target_link<1 or
            any(type(v) is not int or v<1 for v in ratings)):
            return 'UNKNOWN','IDENTITY_LINK_RATINGS_MISSING'
        if sum(ratings)!=target_link or any(rate not in (1,byid[i]['link']) for rate,i in zip(ratings,ids)):
            return 'MISMATCH','IDENTITY_LINK_RATING_MISMATCH'
    expected=(spec['predicate']=='ARCHETYPE_MEMBERSHIP')
    if any(c['claim']!=expected for c in claims):
        return 'MISMATCH','IDENTITY_REVIEWED_CLAIM_CONTRADICTS_REQUIREMENT'
    return 'CLAIM_ALIGNED','IDENTITY_REVIEWED_SOURCE_CLAIMS_ONLY'
