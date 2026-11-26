"""U1 event observations. No network, text import, or DB writes."""
from collections import Counter
from copy import deepcopy
from datetime import date, datetime
import re
import json
from html.parser import HTMLParser
import unicodedata
from urllib.parse import urlsplit
from discovery import validate, RARITIES


def name_key(name):
    return ''.join(unicodedata.normalize('NFKC', name or '').casefold().split()).replace('−', '-').replace('‐', '-')


def evidence(items):
    if not items:
        raise ValueError('missing evidence')
    for item in items:
        u = urlsplit(item['url'])
        if u.scheme != 'https' or not u.netloc or datetime.fromisoformat(item['observed_at']).utcoffset() is None:
            raise ValueError('invalid evidence')


def from_legacy(batch):
    """Preserve pack observations and independent same-day leads, without joining aliases."""
    validate(batch)
    day = date.fromisoformat(batch['effective_on']).isoformat()
    if day != batch['pack']['available_from']:
        raise ValueError('event/pack date mismatch')
    result = []
    for row in batch['cards']:
        result.append(dict(deepcopy(row), channel='PACK', pack_id=batch['pack']['pack_id'], effective_on=day))
    for row in batch.get('other_md_release_leads', []):
        evidence(row['sources'])
        if not name_key(row.get('name_en')) or row.get('rarity') not in RARITIES | {None}:
            raise ValueError('invalid independent lead')
        result.append(dict(deepcopy(row), channel='OTHER_RELEASE_LEAD', pack_id=None, effective_on=day))
    return result


class _Ruby(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hide = 0
        self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag in {'rt', 'rp'}:
            self.hide += 1
    def handle_endtag(self, tag):
        if tag in {'rt', 'rp'}:
            self.hide -= 1
    def handle_data(self, data):
        if not self.hide:
            self.parts.append(data)


def project_record(obj):
    """Discard card prose; retain only U1 metadata."""
    names = obj.get('name') or {}
    parser = _Ruby()
    parser.feed(names.get('ja') or '')
    parser.close()
    return {'cid': obj.get('konami_id'), 'name_ja': ''.join(parser.parts) or None,
            'name_en': names.get('en'), 'rarity': obj.get('master_duel_rarity'),
            'ja_text_present': bool((obj.get('text') or {}).get('ja'))}


def project_commit_files(files):
    """Parse one-line JSON patches; truncated/multiline patches stay unresolved.

    Caller fetches all pages, or supplies pinned individual before/after
    records using project_record for missing projections. No HTTP here.
    """
    rows = []
    for f in files:
        path = f['filename']
        if not re.fullmatch(r'data/cards/[^/]+\.json', path):
            continue
        parts = (f.get('patch') or '').splitlines()
        result = {'path': path, 'status': f['status'], 'before': None, 'after': None}
        for prefix, side in (('-{', 'before'), ('+{', 'after')):
            lines = [line for line in parts if line.startswith(prefix)]
            if len(lines) == 1:
                try:
                    result[side] = project_record(json.loads(lines[0][1:]))
                except (ValueError, TypeError, AttributeError):
                    pass
        rows.append(result)
    return rows


def extract_delta(records, *, revision, parent_revision, observed_at, pages_complete=False):
    """Consume before/after metadata projections of pinned JSON records.

    Record = path, status, before/after (CID, ja/en names, MD rarity,
    Japanese text presence). Missing projections stay unresolved.
    A rarity field appearance is not proof of the game release date.
    """
    if not all(re.fullmatch(r'[0-9a-f]{40}', x) for x in (revision, parent_revision)) or revision == parent_revision:
        raise ValueError('invalid revision pair')
    source = {'url': 'https://github.com/DawnbrandBots/yaml-yugi/commit/' + revision, 'observed_at': observed_at, 'role': 'MD_RARITY_DELTA'}
    evidence([source])
    changes, unresolved, seen, paths = [], [], set(), set()
    for record in records:
        path = record['path']
        if not re.fullmatch(r'data/cards/[^/]+\.json', path) or path in paths:
            raise ValueError('invalid/duplicate path')
        paths.add(path)
        old, new = record.get('before'), record.get('after')
        status = record['status']
        if status not in {'modified', 'added', 'removed', 'renamed'} or (old is None and status != 'added') or (new is None and status != 'removed') or (old is None and new is None):
            unresolved.append({'path': path, 'reason': 'MISSING_PROJECTION'})
            continue
        if old and new and old['cid'] != new['cid']:
            unresolved.append({'path': path, 'reason': 'IDENTITY_CHANGED'})
            continue
        obj = new or old
        cid = obj['cid']
        if type(cid) is not int or cid <= 0 or cid in seen:
            raise ValueError('invalid/duplicate CID')
        seen.add(cid)
        before = old['rarity'] if old else None
        after = new['rarity'] if new else None
        if before not in RARITIES | {None} or after not in RARITIES | {None}:
            unresolved.append({'path': path, 'reason': 'INVALID_RARITY'})
            continue
        if before == after:
            continue
        if not name_key(obj.get('name_ja')) and not name_key(obj.get('name_en')):
            unresolved.append({'path': path, 'reason': 'MISSING_NAME'})
            continue
        change = 'MD_RARITY_ADDED' if before is None else 'MD_RARITY_REMOVED' if after is None else 'MD_RARITY_CHANGED'
        changes.append(dict(obj, path=path, change=change, previous_rarity=before, sources=[source], source_revision=revision, parent_revision=parent_revision))
    return {'changes': changes, 'unresolved': unresolved, 'records': len(paths), 'source_coverage': 'FULL' if pages_complete and not unresolved else 'PARTIAL'}


def build_event(legacy, delta, base, pack_rows, *, pack_source, observed_at):
    """Reconcile CID first; exact source name observations only for event association.

    base maps canonical integer CID to current MD rarity. Never infer initial
    release from absence alone. Pack completeness is independent of event coverage.
    """
    evidence([pack_source])
    observations = from_legacy(legacy)
    pack_index = {}
    for row in pack_rows:
        pack_index.setdefault(name_key(row['name_ja']), []).append(row)
    other_index = {}
    for row in observations:
        if row['channel'] == 'PACK' and row.get('membership') == 'ANNOUNCED_PICKUP':
            k = name_key(row['name_ja'])
            if k not in pack_index:
                pack_index[k] = [{'name_ja': row['name_ja'], 'reported_rarity': row['rarity'], 'sources': row['sources']}]
        if row['channel'] == 'OTHER_RELEASE_LEAD':
            other_index.setdefault(name_key(row['name_en']), []).append(row)
    rows, pending = [], list(delta['unresolved'])
    for row in delta['changes']:
        cid = row['cid']
        matches = pack_index.get(name_key(row.get('name_ja')), [])
        leads = other_index.get(name_key(row.get('name_en')), [])
        pack_ok = len(matches) == 1 and matches[0]['reported_rarity'] == row['rarity']
        other_ok = len(leads) == 1 and leads[0]['rarity'] in (None, row['rarity'])
        conflict = bool(matches) and not pack_ok or bool(leads) and not other_ok
        sources = list(row['sources'])
        channels = []
        if pack_ok:
            channels.append('PACK_REPORTED'); sources.extend(matches[0].get('sources', [pack_source]))
        if other_ok:
            channels.append('OTHER_RELEASE_REPORTED'); sources.extend(leads[0]['sources'])
        if row['change'] == 'MD_RARITY_REMOVED':
            disposition = 'REVIEW_SOURCE_REMOVAL'
        elif conflict or not channels:
            disposition = 'PENDING_EVENT_EVIDENCE'
        elif cid not in base:
            disposition = 'U2_CANDIDATE'
        elif base[cid] != row['rarity']:
            disposition = 'U2_EXISTING_RARITY_REVIEW'
        else:
            disposition = 'EXISTING_NO_RARITY_CHANGE'
        rows.append(dict(row, card_id=f'konami:{cid}', effective_on=legacy['effective_on'] if channels and not conflict else None, channels=channels, pack_id=legacy['pack']['pack_id'] if pack_ok else None, disposition=disposition, base_present=cid in base, base_rarity=base.get(cid), sources=sources))
    return {'schema': 'md-implementation-event-discovery-v1', 'batch_id': legacy['batch_id'] + '-event-v1', 'effective_on': legacy['effective_on'], 'observed_at': observed_at, 'base_generation': legacy['base_generation'], 'base_sqlite_sha256': legacy['base_sqlite_sha256'], 'event_coverage': 'PARTIAL', 'pack_coverage': legacy['pack']['coverage'], 'source_delta_coverage': delta['source_coverage'], 'pack': deepcopy(legacy['pack']), 'legacy_observations': observations, 'cards': rows, 'unresolved': pending, 'counts': dict(Counter(r['disposition'] for r in rows))}
