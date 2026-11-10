"""Private SQLite read-only Japanese card and literal effect-text search.

This is a lexical search only, not card-effect semantics/ruling inference.
Matches are derived from the current immutable SQLite snapshot, without
indexing private card prose in public artifacts or writing back to the DB.
"""
from __future__ import annotations

import sqlite3
import unicodedata
from pathlib import Path
from contextlib import closing
from urllib.parse import quote

RARITIES = ('N', 'R', 'SR', 'UR')
KINDS = ('MONSTER', 'SPELL', 'TRAP')


def _norm(value: str) -> str:
    return ''.join(unicodedata.normalize('NFKC', value).casefold().split())


def _open(path: str | Path):
    uri = 'file:' + quote(str(Path(path).resolve()), safe='/') + '?mode=ro'
    db = sqlite3.connect(uri, uri=True)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA query_only=ON')
    versions = [row[0] for row in db.execute('SELECT version FROM schema_migrations')]
    if versions != [1]:
        db.close()
        raise ValueError('unsupported schema version')
    return db


def _query(db, *, kind=None, rarity=None, attribute=None):
    if kind is not None and kind not in KINDS:
        raise ValueError('unknown kind')
    if rarity is not None and rarity not in RARITIES:
        raise ValueError('unknown rarity')
    if attribute is not None and not isinstance(attribute, str):
        raise TypeError('attribute must be string')
    sql = '''SELECT c.card_id, c.konami_id, c.name, c.verification,
                    a.kind, a.attribute, a.race, a.level, a.rank, a.link,
                    m.rarity, m.craftable, t.body, t.source AS text_source,
                    t.version AS text_version
             FROM cards c
             JOIN card_attributes a ON a.card_id = c.card_id
             JOIN md_catalog m ON m.card_id = c.card_id
             LEFT JOIN card_texts t ON t.card_id = c.card_id AND t.language = 'ja'
             WHERE 1=1'''
    args = []
    for column, value in [('a.kind', kind), ('m.rarity',rarity), ('a.attribute',attribute)]:
        if value is not None:
            sql += ' AND ' + column + '=?'
            args.append(value)
    return db.execute(sql + ' ORDER BY c.card_id', args)


def _format(row, *, include_text=False):
    result = {k:row[k] for k in ('card_id','konami_id','name','kind','attribute','race','level','rank','link','rarity','craftable','verification')}
    if include_text:
        result.update(effect_text=row['body'], text_source=row['text_source'], text_version=row['text_version'])
    return result


def search_cards(db_path, *, name=None, kind=None, rarity=None, attribute=None, limit=50):
    """Search with normalized substring name matches and exact structured filters."""
    if name is not None and not isinstance(name, str):
        raise TypeError('name must be string')
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError('limit out of bounds')
    needle = _norm(name or '')
    with closing(_open(db_path)) as db:
        result = []
        for row in _query(db, kind=kind, rarity=rarity, attribute=attribute):
            if needle in _norm(row['name']):
                result.append(_format(row))
                if len(result) >= limit: break
        return result


def search_effects(db_path, *, phrases, kind=None, rarity=None, attribute=None, limit=50):
    """All phrases must literally occur in one Japanese effect; no LLM inference.

    Distinguish the search text from any interpretation: searching 'ドロー' does
    not establish that a card draws from the deck under the desired conditions.
    """
    if not isinstance(phrases, (list,tuple)) or not phrases or any(not isinstance(p,str) or not p.strip() for p in phrases):
        raise ValueError('phrases must be nonempty strings')
    if len(phrases) > 10:
        raise ValueError('too many phrases')
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError('limit out of bounds')
    terms = [_norm(x) for x in phrases]
    with closing(_open(db_path)) as db:
        result = []
        for row in _query(db, kind=kind, rarity=rarity, attribute=attribute):
            if row['body'] is not None and all(t in _norm(row['body']) for t in terms):
                result.append(_format(row, include_text=True))
                if len(result) >= limit: break
        return result


def resolve_names(db_path, names):
    """Never guess IDs: ambiguous normalized names preserve all candidates."""
    if not isinstance(names, (list, tuple)) or any(not isinstance(n,str) or not n.strip() for n in names):
        raise ValueError('names must be nonempty strings')
    normalized = {_norm(name): [] for name in names}
    with closing(_open(db_path)) as db:
        for row in _query(db):
            key = _norm(row['name'])
            if key in normalized:
                normalized[key].append(_format(row))
    return [{'input':name,
             'status':'UNRESOLVED' if not normalized[_norm(name)] else ('RESOLVED' if len(normalized[_norm(name)]) == 1 else 'AMBIGUOUS'),
             'candidates':normalized[_norm(name)]} for name in names]
