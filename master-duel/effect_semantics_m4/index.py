"""M4 private read-only extraction -> immutable, separately versioned SQLite index.

The production SQLite is always opened read-only; no schema changes to it.
Derived index may contain copyrighted text excerpts and is PRIVATE Drive-only.
"""
from __future__ import annotations

from collections import Counter
from contextlib import closing
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import sqlite3
import tempfile
from urllib.parse import quote

from .extraction import ACTIONS, EXTRACTOR_VERSION, extract_effect_facets

SCHEMA = '''
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE cards(card_id TEXT PRIMARY KEY,name TEXT NOT NULL,kind TEXT,rarity TEXT,
                   text_version TEXT,text_sha256 TEXT,text_source TEXT,
                   facet_count INTEGER NOT NULL);
CREATE TABLE facets(card_id TEXT NOT NULL REFERENCES cards(card_id),facet TEXT NOT NULL,
                   role TEXT NOT NULL,confidence TEXT NOT NULL,verification TEXT NOT NULL,
                   start INTEGER NOT NULL,end INTEGER NOT NULL,evidence TEXT NOT NULL,
                   text_sha256 TEXT NOT NULL,text_version TEXT NOT NULL,
                   text_source TEXT NOT NULL,extractor_version TEXT NOT NULL,
                   PRIMARY KEY(card_id,facet,role,start,end));
CREATE INDEX idx_facets_action ON facets(facet,role,card_id);
CREATE INDEX idx_cards_rarity ON cards(rarity,kind);
'''


def _sha_file(path):
    digest = sha256()
    with open(path,'rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()


def _read_only(path):
    p = Path(path).resolve()
    if not p.is_file():
        raise ValueError('file does not exist')
    uri = 'file:' + quote(str(p),safe='/') + '?mode=ro'
    db = sqlite3.connect(uri,uri=True)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA query_only=ON')
    return db


def build_private_index(source_db, dest, *, expected_source_sha256, replace=False):
    """Hash-pin private input, build into a temporary file, then atomic replace.

    Metadata and all output excerpts are private. Return only aggregate counts.
    """
    source_db, dest = Path(source_db).resolve(), Path(dest).resolve()
    if source_db == dest:
        raise ValueError('cannot overwrite the source database')
    if not isinstance(expected_source_sha256,str) or not re.fullmatch(r'[0-9a-f]{64}',expected_source_sha256):
        raise ValueError('pinned source SHA-256 required')
    if _sha_file(source_db) != expected_source_sha256:
        raise ValueError('source SQLite SHA-256 mismatch')
    if dest.exists() and not replace:
        raise ValueError('derived index exists; explicit replace required')
    dest.parent.mkdir(parents=True,exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.m4-private-',suffix='.sqlite',dir=dest.parent)
    os.close(fd)
    try:
        with closing(_read_only(source_db)) as src:
            if src.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('source SQLite integrity_check failed')
            if src.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('source SQLite foreign keys invalid')
            if [r[0] for r in src.execute('SELECT version FROM schema_migrations')] != [1]:
                raise ValueError('unsupported source schema version')
            cards_count = 0
            tagged_cards = 0
            counts = Counter()
            with closing(sqlite3.connect(temp)) as out:
                out.executescript('PRAGMA foreign_keys=ON;'+SCHEMA)
                # Text versions are multiple by design: choose the most recent
                # acquired_at/version in deterministic order for each card.
                sql = '''WITH newest AS (
                    SELECT card_id,body,source,version,
                       ROW_NUMBER() OVER (PARTITION BY card_id
                          ORDER BY COALESCE(acquired_at,'' ) DESC,version DESC) AS rn
                    FROM card_texts WHERE language='ja'
                ) SELECT c.card_id,c.name,a.kind,m.rarity,
                           n.body,n.source AS text_source,n.version AS text_version
                    FROM cards c
                    LEFT JOIN card_attributes a ON a.card_id=c.card_id
                    LEFT JOIN md_catalog m ON m.card_id=c.card_id
                    LEFT JOIN newest n ON n.card_id=c.card_id AND n.rn=1
                    ORDER BY c.card_id'''
                for row in src.execute(sql):
                    cards_count += 1
                    body = row['body']
                    facets = (extract_effect_facets(row['card_id'],body,
                               text_version=row['text_version'],
                               text_source=row['text_source']) if body else [])
                    if facets:tagged_cards += 1
                    digest = sha256(body.encode('utf-8')).hexdigest() if body else None
                    out.execute('INSERT INTO cards VALUES (?,?,?,?,?,?,?,?)',(
                        row['card_id'],row['name'],row['kind'],row['rarity'],
                        row['text_version'],digest,row['text_source'],len(facets)))
                    for f in facets:
                        counts[f['facet']+':'+f['role']] += 1
                        out.execute('INSERT INTO facets VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',(
                            f['card_id'],f['facet'],f['role'],f['confidence'],f['verification'],
                            f['start'],f['end'],f['evidence'],f['text_sha256'],
                            f['text_version'],f['text_source'],f['extractor_version']))
                meta = {
                    'schema_version':'1','source_sqlite_sha256':expected_source_sha256,
                    'extractor_version':EXTRACTOR_VERSION,
                    'cards':str(cards_count), 'tagged_cards':str(tagged_cards),
                    'facets':str(sum(counts.values())),
                }
                out.executemany('INSERT INTO metadata VALUES (?,?)',sorted(meta.items()))
                out.commit()
                if out.execute('PRAGMA foreign_key_check').fetchall():
                    raise ValueError('invalid derived foreign keys')
        # Protect against source replacement between initial digest and commit.
        if _sha_file(source_db) != expected_source_sha256:
            raise ValueError('source modified during extraction')
        if dest.exists() and not replace:
            raise ValueError('derived index appeared concurrently')
        os.replace(temp,dest)
        return {'source_sha256':expected_source_sha256,'index_sha256':_sha_file(dest),
                'cards':cards_count,'tagged_cards':tagged_cards,
                'facets':sum(counts.values()),'by_facet_role':dict(sorted(counts.items())),
                'extractor_version':EXTRACTOR_VERSION}
    finally:
        if os.path.exists(temp):os.unlink(temp)


def search_private_index(index_path, *, facets, roles=('ACTION',),
                         rarity=None,kind=None,limit=50,expected_source_sha256=None):
    """Search materialized candidates without scanning source or claiming rulings.

    Multiple facets implement ANY semantics. Return matching evidence only.
    """
    if not isinstance(facets,(list,tuple)) or not facets or len(facets)>12 or any(x not in ACTIONS for x in facets):
        raise ValueError('unsupported facet search')
    if not isinstance(roles,(list,tuple)) or not roles or any(x not in ('ACTION','CONDITION','REFERENCED','RESTRICTION','METADATA') for x in roles):
        raise ValueError('unsupported role search')
    if type(limit) is not int or not 1<=limit<=1000:raise ValueError('invalid limit')
    if rarity is not None and rarity not in ('N','R','SR','UR'):raise ValueError('invalid rarity')
    if kind is not None and kind not in ('MONSTER','SPELL','TRAP'):raise ValueError('invalid kind')
    with closing(_read_only(index_path)) as db:
        meta=dict(db.execute('SELECT key,value FROM metadata'))
        if meta.get('extractor_version') != EXTRACTOR_VERSION:
            raise ValueError('incompatible extractor version')
        if expected_source_sha256 is not None and meta.get('source_sqlite_sha256') != expected_source_sha256:
            raise ValueError('stale facet index source')
        sql = ('''SELECT c.card_id,c.name,c.kind,c.rarity,
                         f.facet,f.role,f.confidence,f.verification,
                         f.start,f.end,f.evidence,f.text_sha256,f.text_version,
                         f.text_source,f.extractor_version
                  FROM facets f JOIN cards c ON c.card_id=f.card_id WHERE f.facet IN ('''
               + ','.join('?' for _ in facets) + ') AND f.role IN ('
               + ','.join('?' for _ in roles) + ')')
        params=list(facets)+list(roles)
        for column,value in [('c.rarity',rarity),('c.kind',kind)]:
            if value is not None:sql+=' AND '+column+'=?';params.append(value)
        sql+=' ORDER BY c.card_id,f.start,f.facet LIMIT ?';params.append(limit)
        return {'source_sha256':meta['source_sqlite_sha256'],
                'extractor_version':EXTRACTOR_VERSION,
                'results':[dict(r) for r in db.execute(sql,params)]}
