"""U2 deterministic normalization, no network or database writes.

Inputs: U1 event JSON and SHA-pinned OCG cards.json. Foreign-first cards
without Japanese source remain unresolved. U3 must recheck the base SHA.
"""
from collections import Counter
from datetime import date, datetime
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlsplit
from card_master_import.importer import kind, numeric, subtype_flags, extra_properties
from card_master_import.stage2_gen9_migration import extract_material_requirement
from card_master_import.incremental.resolver import index_records, resolve

RARITIES = {'N', 'R', 'SR', 'UR'}
EX = {'FUSION', 'SYNCHRO', 'XYZ', 'LINK'}
ARROWS = {'↖':'Top-Left','⬆':'Top-Center','↗':'Top-Right',
          '⬅':'Middle-Left','➡':'Middle-Right','↙':'Bottom-Left',
          '⬇':'Bottom-Center','↘':'Bottom-Right'}
ATTRIBUTES = {'DARK','LIGHT','EARTH','WATER','FIRE','WIND','DIVINE'}
RACES = {'Aqua','Beast','Beast-Warrior','Cyberse','Dinosaur','Divine-Beast',
         'Dragon','Fairy','Fiend','Fish','Illusion','Insect','Machine','Plant',
         'Psychic','Pyro','Reptile','Rock','Sea Serpent','Spellcaster','Thunder',
         'Warrior','Winged Beast','Wyrm','Zombie','Creator God'}


def digest(raw):
    return sha256(raw).hexdigest()


def evidence(items):
    if not items:
        raise ValueError('MISSING_EVIDENCE')
    for item in items:
        url = urlsplit(item['url'])
        if url.scheme != 'https' or not url.netloc:
            raise ValueError('INVALID_EVIDENCE_URL')
        if datetime.fromisoformat(item['observed_at']).utcoffset() is None:
            raise ValueError('INVALID_EVIDENCE_TIMESTAMP')
    return items


def read_pinned(path, expected):
    raw = Path(path).read_bytes()
    if digest(raw) != expected:
        raise ValueError('INPUT_SHA_MISMATCH')
    return json.loads(raw)


def stat(record, key, required=False, question=False):
    raw = record.get(key)
    val = numeric(raw)
    if required and val is None and not (question and raw == '?'):
        raise ValueError('MISSING_' + key.upper())
    if val is not None and val < 0:
        raise ValueError('INVALID_' + key.upper())
    return val


def normalize_card(obs, record, name, ocg_source):
    """OCG_SHARED is an evidence class, not MD game verification."""
    if obs.get('disposition') != 'U2_CANDIDATE' or not obs.get('channels') or not obs.get('effective_on'):
        raise ValueError('PENDING_EVENT_EVIDENCE')
    date.fromisoformat(obs['effective_on'])
    md_sources = evidence(obs.get('sources'))
    event_sources = [s for s in md_sources if s.get('role') != 'MD_RARITY_DELTA']
    if not event_sources:
        raise ValueError('MISSING_EVENT_EVIDENCE')
    rarity = obs.get('rarity')
    rarity_sources = [s for s in md_sources if s.get('role') == 'MD_RARITY_DELTA']
    if rarity is not None and (rarity not in RARITIES or not rarity_sources):
        raise ValueError('INVALID_OR_UNSOURCED_MD_RARITY')
    body = record.get('text', {}).get('ja')
    if not isinstance(body, str) or not body.strip():
        raise ValueError('MISSING_JAPANESE_EFFECT')
    if not record.get('sets', {}).get('ja'):
        raise ValueError('OCG_SHARED_NOT_ESTABLISHED')
    unofficial = record.get('is_translation_unofficial') or {}
    if any((unofficial.get(k) or {}).get('ja') for k in ('name','text','pendulum_effect')):
        raise ValueError('UNOFFICIAL_JAPANESE_SOURCE')
    card_kind = kind(record)
    if card_kind not in {'MONSTER','SPELL','TRAP'}:
        raise ValueError('INVALID_KIND')
    adapted = dict(record)
    if card_kind == 'MONSTER':
        adapted['types'] = record.get('monster_type_line')
    if isinstance(record.get('link_arrows'), list):
        try:
            adapted['link_arrows'] = ','.join(ARROWS.get(a, a) for a in record['link_arrows'])
        except TypeError as exc:
            raise ValueError('INVALID_LINK_ARROW') from exc
    adapted['ja_pendulum_effect'] = (record.get('pendulum_effect') or {}).get('ja')
    flags = subtype_flags(adapted)
    if flags is None:
        raise ValueError('INVALID_MONSTER_TYPES')
    flags = list(flags)
    prop, arrows, scale, pend = extra_properties(adapted, card_kind, flags)
    race = attribute = level = rank = link = atk = defense = None
    if card_kind == 'MONSTER':
        race = adapted['types'].split('/')[0].strip()
        attribute = record.get('attribute')
        if race not in RACES or attribute not in ATTRIBUTES:
            raise ValueError('MISSING_OR_INVALID_RACE_ATTRIBUTE')
        if len(EX.intersection(flags)) > 1:
            raise ValueError('MULTIPLE_EXTRA_METHODS')
        if 'LINK' in flags:
            link = len(arrows)
            if record.get('level') is not None or record.get('rank') is not None or record.get('def') is not None:
                raise ValueError('UNEXPECTED_LINK_STAT')
        elif 'XYZ' in flags:
            rank = stat(record, 'rank', required=True)
            if record.get('level') is not None or rank not in range(0, 14):
                raise ValueError('INVALID_XYZ_RANK')
        else:
            level = stat(record, 'level', required=True)
            if record.get('rank') is not None or level not in range(0, 14):
                raise ValueError('INVALID_LEVEL')
        atk = stat(record, 'atk', required=True, question=True)
        if 'LINK' not in flags:
            defense = stat(record, 'def', required=True, question=True)
        if 'PENDULUM' in flags and not pend:
            raise ValueError('MISSING_JAPANESE_PENDULUM_EFFECT')
    elif any(record.get(k) is not None for k in ('monster_type_line','attribute','level','rank','atk','def','link_arrows','pendulum_scale')):
        raise ValueError('UNEXPECTED_NONMONSTER_STAT')
    ocg = {**ocg_source,'verification':'OCG_SHARED','konami_id':obs['cid']}
    evidence([ocg])
    out = {'card_id':obs['card_id'],'konami_id':obs['cid'],'name_ja':name,
           'name_en':record.get('name', {}).get('en'), 'kind':card_kind,
           'attribute':attribute,'race':race,'level':level,'rank':rank,'link':link,
           'atk':atk,'def':defense,'rarity':rarity,'craftable':'UNKNOWN',
           'ja_text':body,'monster_types':flags,'spell_trap_property':prop,
           'link_markers':list(arrows),'pendulum_scale':scale,'ja_pendulum_effect':pend,
           'effective_on':obs['effective_on'],'channels':obs['channels'],'pack_id':obs.get('pack_id'),
           'series_en':record.get('series') or [],
           'sources':{'identity':ocg,'attributes':ocg,'ja_text':ocg,
                      'ja_pendulum_effect':ocg if pend is not None else None,
                      'series':ocg,'md_implementation':event_sources,
                      'md_rarity':rarity_sources,'craftable':None},
           'verification':'UNVERIFIED_SOURCE'}
    methods = EX.intersection(flags)
    out['extra_material_requirement'] = None
    if methods:
        method = next(iter(methods))
        head, preamble, grammar = extract_material_requirement(method, body)
        out['extra_material_requirement'] = {'summon_method':method,'material_header':head,
            'material_header_sha256':digest(head.encode()),'pre_effect_restrictions':preamble,
            'source_text_sha256':digest(body.encode()),**grammar,
            'material_verification':'SOURCE_TEXT_ONLY','simultaneous_materials_verified':0,
            'summon_route_verified':0}
    return out


def build_batch(event, records, ocg_source, *, expected_base, input_sha, observed_at,
                event_resolutions=None):
    """Partial success; failed rows are retained, never silently dropped."""
    if event.get('schema') != 'md-implementation-event-discovery-v1':
        raise ValueError('INVALID_EVENT_SCHEMA')
    if (event['base_generation'],event['base_sqlite_sha256']) != expected_base:
        raise ValueError('BASE_MISMATCH')
    if datetime.fromisoformat(observed_at).utcoffset() is None:
        raise ValueError('INVALID_OBSERVATION_TIME')
    if not isinstance(records, list):
        raise ValueError('INVALID_OCG_INPUT')
    ids = [r.get('cid') for r in event['cards']]
    duplicates = {cid for cid,n in Counter(ids).items() if n > 1}
    index = index_records(records)
    cards, unresolved = [], []
    resolutions = event_resolutions or {}
    for original in event['cards']:
        obs = dict(original)
        cid = obs.get('cid')
        correction = resolutions.get(cid)
        try:
            if cid in duplicates:
                raise ValueError('DUPLICATE_EVENT_CID')
            if correction:
                # Explicit, independently acquired event evidence only. Do not
                # override canonical identity or text using a fuzzy name match.
                if correction.get('card_id') != obs.get('card_id') or not correction.get('channels'):
                    raise ValueError('INVALID_EVENT_RESOLUTION')
                obs.update(disposition='U2_CANDIDATE',effective_on=correction['effective_on'],
                           channels=correction['channels'],pack_id=correction.get('pack_id'),
                           sources=obs['sources']+evidence(correction['sources']))
            if obs.get('disposition') != 'U2_CANDIDATE':
                raise ValueError(obs.get('disposition') or 'PENDING_EVENT_EVIDENCE')
            # Report missing Japanese source explicitly before name resolution.
            candidates = index.get(cid, [])
            if len(candidates)==1 and not (candidates[0].get('text') or {}).get('ja'):
                raise ValueError('MISSING_JAPANESE_EFFECT')
            record, name = resolve(obs,index)
            cards.append(normalize_card(obs,record,name,ocg_source))
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            unresolved.append({'card_id':obs.get('card_id'),'cid':cid,'name_ja':obs.get('name_ja'),
                'name_en':obs.get('name_en'),'rarity':obs.get('rarity'),'reason':str(exc),
                'event_disposition':obs.get('disposition'),'effective_on':obs.get('effective_on'),
                'sources':obs.get('sources',[]),'source_path':obs.get('path'),
                'event_resolution':correction})
    return {'schema':'md-card-incremental-update-v1','batch_id':event['batch_id']+'-u2',
        'effective_on':event['effective_on'],'base_generation':expected_base[0],
        'base_sqlite_sha256':expected_base[1],'pack':event.get('pack'),
        'event_coverage':event['event_coverage'],'pack_coverage':event['pack_coverage'],
        'observed_at':observed_at,'input_sha256':input_sha,'ocg_source':ocg_source,
        'cards':cards,'unresolved':unresolved,'upstream_unresolved':event.get('unresolved',[])}
