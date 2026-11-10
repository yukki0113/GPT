"""Versioned *candidate* M5 theme/engine/generic registry validation.

No user inventory, private card text or rulings are baked into public code.
The private seed contains evidence and is never a source of GAME_VERIFIED.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
import json
import re
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit

_SHA = re.compile(r'[a-f0-9]{64}\Z')
_ID = re.compile(r'konami:[1-9][0-9]*\Z')
_KEY = re.compile(r'[A-Z][A-Z0-9_]{1,63}\Z')
_ROLES = {'STARTER','EXTENDER','BRIDGE','PAYOFF','TECH','FLEX','HAND_TRAP','NEGATE',
          'DRAW','REMOVAL','PROTECTION','SEARCH','GRAVE_HATE'}
_STATUS = {'SECONDARY_SOURCE_CANDIDATE','PERSON_REVIEWED'}


def _assert(condition, message):
    if not condition: raise ValueError(message)


def _object(obj, expected, label):
    _assert(isinstance(obj,dict) and set(obj) == set(expected), 'invalid '+label+' fields')


def _key(text, label):
    _assert(isinstance(text,str) and _KEY.fullmatch(text), 'invalid '+label)


def _cid(text):
    _assert(isinstance(text,str) and _ID.fullmatch(text), 'invalid card ID')


def _text(text,label):
    _assert(isinstance(text,str) and 0 < len(text.strip()) <= 500,'invalid '+label)


def _url(text):
    _assert(isinstance(text,str), 'missing source URL')
    u=urlsplit(text)
    _assert(u.scheme=='https' and bool(u.netloc) and not u.username and not u.password,
            'HTTPS source URL required')


def validate_seed(seed):
    _object(seed, ('schema_version','as_of','source_db_sha256','m4_index_sha256',
                   'themes','generic_cards','engines'), 'seed')
    _assert(type(seed['schema_version']) is int and seed['schema_version']==1,'bad seed schema')
    _assert(isinstance(seed['as_of'],str),'as_of required')
    date.fromisoformat(seed['as_of'])
    for field in ('source_db_sha256','m4_index_sha256'):
        _assert(isinstance(seed[field],str) and _SHA.fullmatch(seed[field]),'bad '+field)
    for name in ('themes','generic_cards','engines'):
        _assert(isinstance(seed[name],list),'invalid '+name)
    _assert(1 <= len(seed['themes']) <= 50,'themes out of bounds')
    themes=set()
    for t in seed['themes']:
        _object(t,('theme_id','name','name_patterns','quoted_targets'),'theme')
        _key(t['theme_id'],'theme_id');_text(t['name'],'theme name')
        _assert(t['theme_id'] not in themes,'duplicate theme');themes.add(t['theme_id'])
        _assert(isinstance(t['name_patterns'],list) and t['name_patterns'], 'missing patterns')
        for pat in t['name_patterns']:
            _object(pat,('text','mode'),'name pattern');_text(pat['text'],'name pattern')
            _assert(pat['mode'] in ('PREFIX','CONTAINS'),'invalid name match mode')
        _assert(isinstance(t['quoted_targets'],list),'quoted target list required')
        for token in t['quoted_targets']: _text(token,'quoted target')
    gkeys=set()
    for g in seed['generic_cards']:
        _object(g,('card_id','role','source_url','verification'),'generic card')
        _cid(g['card_id']);_key(g['role'],'generic role')
        _assert(g['role'] in _ROLES,'unsupported generic role')
        _url(g['source_url']);_assert(g['verification'] in _STATUS,'invalid generic status')
        pair=(g['card_id'],g['role']);_assert(pair not in gkeys,'duplicate generic role');gkeys.add(pair)
    engines=set()
    for e in seed['engines']:
        _object(e,('engine_id','name','theme_id','model_kind','verification',
                   'source_url','notes','cards','choice_groups','constraints'),'engine')
        _key(e['engine_id'],'engine_id');_text(e['name'],'engine name')
        _assert(e['engine_id'] not in engines,'duplicate engine');engines.add(e['engine_id'])
        _assert(e['theme_id'] in themes,'unknown engine theme')
        _assert(e['model_kind'] in ('PACKAGE','SINGLETON'),'unsupported engine type')
        _assert(e['verification'] in _STATUS,'unsupported engine verification')
        _url(e['source_url']);_text(e['notes'],'engine notes')
        _assert(isinstance(e['cards'],list) and isinstance(e['choice_groups'],list)
                and isinstance(e['constraints'],list),'bad engine lists')
        present=set()
        for c in e['cards']:
            _validate_part(c)
            _assert(c['card_id'] not in present,'duplicate engine card')
            present.add(c['card_id'])
        choiceids=set()
        for group in e['choice_groups']:
            _object(group,('group_id','min_choices','options'),'choice group')
            _key(group['group_id'],'group_id')
            _assert(group['group_id'] not in choiceids,'duplicate choice group')
            choiceids.add(group['group_id'])
            _assert(isinstance(group['options'],list) and group['options'],'empty choices')
            _assert(type(group['min_choices']) is int and
                    1 <= group['min_choices'] <= len(group['options']), 'invalid min_choices')
            for c in group['options']:
                _validate_part(c)
                _assert(c['card_id'] not in present,'card repeated in engine options')
                present.add(c['card_id'])
        _assert(present,'empty engine')
        if e['model_kind']=='SINGLETON':
            _assert(not e['cards'] and len(e['choice_groups'])==1 and
                    e['choice_groups'][0]['min_choices']==1, 'singleton must be one choice')
        for c in e['constraints']:
            _object(c,('code','scope','source_url','verification','note'),'constraint')
            _key(c['code'],'constraint code')
            _assert(c['scope'] in ('WHOLE_PACKAGE','OPTIONAL_LINE','ENTRY_LINE','EXTRA_DECK'),
                    'unsupported constraint scope')
            _url(c['source_url']);_assert(c['verification'] in _STATUS,'bad constraint status')
            _text(c['note'],'constraint note')
    return deepcopy(seed)


def _validate_part(part):
    _object(part,('card_id','section','min_copies','max_copies','role'),'engine part')
    _cid(part['card_id']);_assert(part['section'] in ('MAIN','EXTRA'),'invalid section')
    _assert(type(part['min_copies']) is int and 1<=part['min_copies']<=3,'bad min_copies')
    _assert(type(part['max_copies']) is int and
            part['min_copies']<=part['max_copies']<=3, 'bad max_copies')
    _assert(part['role'] in _ROLES,'unsupported part role')


def load_seed(path, *, expected_sha256):
    _assert(isinstance(expected_sha256,str) and _SHA.fullmatch(expected_sha256),
            'seed SHA-256 required')
    raw=Path(path).read_bytes()
    _assert(sha256(raw).hexdigest()==expected_sha256, 'seed SHA-256 mismatch')
    try:
        obj=json.loads(raw.decode('utf-8-sig'))
    except (ValueError,UnicodeDecodeError) as exc:
        raise ValueError('invalid seed JSON') from exc
    return validate_seed(obj)
