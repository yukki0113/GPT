"""Validate acquired pack observations, never infer completeness or MD rarity."""
from collections import Counter
from datetime import date, datetime
import unicodedata
from urllib.parse import urlsplit

RARITIES = {'N', 'R', 'SR', 'UR'}

def key(name):
    return unicodedata.normalize('NFKC', name).casefold().replace(' ', '')

def validate(batch):
    pack = batch['pack']
    date.fromisoformat(pack['available_from'])
    if pack.get('available_until'):
        if date.fromisoformat(pack['available_until']) < date.fromisoformat(pack['available_from']):
            raise ValueError('end before start')
    if not pack['name_ja'] or not pack['pack_type']:
        raise ValueError('missing pack metadata')
    def evidence(sources):
        if not sources:
            raise ValueError('missing evidence')
        for item in sources:
            if urlsplit(item['url']).scheme != 'https' or not urlsplit(item['url']).netloc:
                raise ValueError('invalid source URL')
            if datetime.fromisoformat(item['observed_at']).utcoffset() is None:
                raise ValueError('timestamp must include timezone')
    evidence(pack['sources'])
    seen = set()
    for row in batch['cards']:
        k = (key(row['name_ja']), row.get('variant', 'UNSPECIFIED'))
        if not k[0] or k in seen:
            raise ValueError('empty/duplicate observation')
        seen.add(k)
        if row['rarity'] is not None and row['rarity'] not in RARITIES:
            raise ValueError('invalid rarity')
        evidence(row['sources'])
        if row['rarity'] is not None:
            evidence(row['rarity_sources'])
    counts = Counter(row['rarity'] or 'UNKNOWN' for row in batch['cards'])
    coverage = pack['coverage']
    if coverage not in {'FULL', 'PARTIAL', 'UNKNOWN'}:
        raise ValueError('invalid coverage')
    total = pack.get('reported_slots')
    if total is not None and (not isinstance(total, int) or total < len(seen)):
        raise ValueError('invalid reported slots')
    if coverage == 'FULL' and (total != len(seen) or not pack.get('full_list_evidence')):
        raise ValueError('full coverage not demonstrated')
    return {'coverage': coverage, 'observations': len(seen), 'rarities': dict(counts), 'reported_slots': total}
