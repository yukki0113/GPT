"""M5 private sidecar: archetype evidence, generic roles and engine variants.

All real names, card ids, M4-derived quotations and source snapshots live only
in a separate private SQLite. Production MD SQLite and M4 index are read-only.
"""
from __future__ import annotations

from collections import Counter
from contextlib import closing
from hashlib import sha256
from pathlib import Path
import os
import re
import sqlite3
import tempfile
from urllib.parse import quote
from .catalog import load_seed

SCHEMA='''
PRAGMA foreign_keys=ON;
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE cards(card_id TEXT PRIMARY KEY,name TEXT NOT NULL,kind TEXT,rarity TEXT,
                   attribute TEXT,race TEXT,level INTEGER,rank INTEGER,link INTEGER);
CREATE TABLE themes(theme_id TEXT PRIMARY KEY,name TEXT NOT NULL);
CREATE TABLE theme_relations(theme_id TEXT NOT NULL REFERENCES themes(theme_id),
                   card_id TEXT NOT NULL REFERENCES cards(card_id),
                   relation TEXT NOT NULL, evidence TEXT NOT NULL,
                   source_version TEXT,source_sha256 TEXT,
                   start INTEGER,end INTEGER,verification TEXT NOT NULL,
                   PRIMARY KEY(theme_id,card_id,relation,evidence));
CREATE INDEX idx_relation_card ON theme_relations(card_id,relation);
CREATE TABLE generic_roles(card_id TEXT NOT NULL REFERENCES cards(card_id),
                   role TEXT NOT NULL,source_url TEXT NOT NULL,verification TEXT NOT NULL,
                   PRIMARY KEY(card_id,role));
CREATE TABLE engines(engine_id TEXT PRIMARY KEY,name TEXT NOT NULL,
                   theme_id TEXT NOT NULL REFERENCES themes(theme_id),
                   model_kind TEXT NOT NULL,verification TEXT NOT NULL,
                   source_url TEXT NOT NULL,notes TEXT NOT NULL);
CREATE TABLE choice_groups(engine_id TEXT NOT NULL REFERENCES engines(engine_id),
                   group_id TEXT NOT NULL,min_choices INTEGER NOT NULL,
                   PRIMARY KEY(engine_id,group_id));
CREATE TABLE engine_parts(engine_id TEXT NOT NULL REFERENCES engines(engine_id),
                   group_id TEXT NOT NULL DEFAULT '',
                   card_id TEXT NOT NULL REFERENCES cards(card_id),
                   section TEXT NOT NULL,min_copies INTEGER NOT NULL,
                   max_copies INTEGER NOT NULL,role TEXT NOT NULL,
                   PRIMARY KEY(engine_id,group_id,card_id));
CREATE INDEX idx_engine_parts_card ON engine_parts(card_id);
CREATE TABLE engine_constraints(engine_id TEXT NOT NULL REFERENCES engines(engine_id),
                   code TEXT NOT NULL,scope TEXT NOT NULL,
                   source_url TEXT NOT NULL,verification TEXT NOT NULL,
                   note TEXT NOT NULL,PRIMARY KEY(engine_id,code,scope));
'''


def file_sha256(path):
    h=sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def _open_ro(path):
    p=Path(path).resolve()
    if not p.is_file():raise ValueError('source file not found')
    db=sqlite3.connect('file:'+quote(str(p),safe='/')+'?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA query_only=ON')
    return db


def _verify_source(db, expected_sha, m4):
    if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():
        raise ValueError('source SQLite corruption')
    if m4:
        meta=dict(db.execute('SELECT key,value FROM metadata'))
        if meta.get('source_sqlite_sha256')!=expected_sha:
            raise ValueError('M4 index references other source SQLite')
        if not meta.get('extractor_version'):
            raise ValueError('M4 missing extractor version')
        return meta['extractor_version']
    versions=[r[0] for r in db.execute('SELECT version FROM schema_migrations')]
    if versions!=[1]:raise ValueError('unsupported production schema')
    return None


def _quoted_match(evidence, terms):
    # A quoted *target* is a candidate, never an asserted archetype membership.
    quotations=re.findall('「([^」]{1,100})」',evidence)
    return any(term in q for term in terms for q in quotations)


def build_private_m5_index(source_db,m4_index,seed_path,dest,*,
                            expected_source_sha256,expected_m4_sha256,
                            expected_seed_sha256,replace=False):
    source_db,m4_index,seed_path,dest=map(lambda p:Path(p).resolve(),
                                          (source_db,m4_index,seed_path,dest))
    if len({source_db,m4_index,seed_path,dest})!=4:raise ValueError('paths must be distinct')
    if dest.exists() and not replace:raise ValueError('M5 index exists; explicit replace required')
    seed=load_seed(seed_path,expected_sha256=expected_seed_sha256)
    if seed['source_db_sha256']!=expected_source_sha256 or seed['m4_index_sha256']!=expected_m4_sha256:
        raise ValueError('seed source hash mismatch')
    if file_sha256(source_db)!=expected_source_sha256:
        raise ValueError('production source SHA mismatch')
    if file_sha256(m4_index)!=expected_m4_sha256:
        raise ValueError('M4 index SHA mismatch')
    dest.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix='.m5-',suffix='.sqlite',dir=dest.parent)
    os.close(fd)
    try:
        with closing(_open_ro(source_db)) as src,closing(_open_ro(m4_index)) as m4:
            _verify_source(src,expected_source_sha256,False)
            extractor_version=_verify_source(m4,expected_source_sha256,True)
            with closing(sqlite3.connect(temp)) as out:
                out.executescript(SCHEMA)
                cards=src.execute('''SELECT c.card_id,c.name,a.kind,m.rarity,
                                           a.attribute,a.race,a.level,a.rank,a.link
                                    FROM cards c
                                    LEFT JOIN card_attributes a ON a.card_id=c.card_id
                                    LEFT JOIN md_catalog m ON m.card_id=c.card_id
                                    ORDER BY c.card_id''').fetchall()
                out.executemany('INSERT INTO cards VALUES(?,?,?,?,?,?,?,?,?)',
                                (tuple(r) for r in cards))
                card_ids={r['card_id'] for r in cards}
                out.executemany('INSERT INTO themes VALUES (?,?)',
                                ((t['theme_id'],t['name']) for t in seed['themes']))
                relation_counts=Counter()
                for row in cards:
                    for theme in seed['themes']:
                        if any((row['name'].startswith(p['text']) if p['mode']=='PREFIX'
                                else p['text'] in row['name']) for p in theme['name_patterns']):
                            out.execute('INSERT INTO theme_relations VALUES (?,?,?,?,?,?,?,?,?)',(
                                theme['theme_id'],row['card_id'],'NAME_MATCH_CANDIDATE',
                                row['name'],None,None,None,None,'LEXICAL_CANDIDATE'))
                            relation_counts['NAME_MATCH_CANDIDATE']+=1
                # M4 NAMED_TARGET is not necessarily an actual relationship:
                # retain the evidence as a tentative *quoted* reference only.
                for f in m4.execute("SELECT card_id,evidence,start,end,text_sha256,text_version "
                                    "FROM facets WHERE facet='NAMED_TARGET' ORDER BY card_id,start"):
                    for t in seed['themes']:
                        if t['quoted_targets'] and _quoted_match(f['evidence'],t['quoted_targets']):
                            out.execute('INSERT OR IGNORE INTO theme_relations VALUES (?,?,?,?,?,?,?,?,?)',(
                                t['theme_id'],f['card_id'],'QUOTED_TARGET_CANDIDATE',
                                f['evidence'],f['text_version'],f['text_sha256'],
                                f['start'],f['end'],'UNVERIFIED_INTERPRETATION'))
                            if out.execute('SELECT changes()').fetchone()[0]:
                                relation_counts['QUOTED_TARGET_CANDIDATE']+=1
                for g in seed['generic_cards']:
                    if g['card_id'] not in card_ids:raise ValueError('missing generic card id')
                    out.execute('INSERT INTO generic_roles VALUES(?,?,?,?)',
                                (g['card_id'],g['role'],g['source_url'],g['verification']))
                for engine in seed['engines']:
                    out.execute('INSERT INTO engines VALUES(?,?,?,?,?,?,?)',(
                        engine['engine_id'],engine['name'],engine['theme_id'],
                        engine['model_kind'],engine['verification'],engine['source_url'],engine['notes']))
                    for group in engine['choice_groups']:
                        out.execute('INSERT INTO choice_groups VALUES(?,?,?)',(
                            engine['engine_id'],group['group_id'],group['min_choices']))
                    for group_id,items in [('',engine['cards'])]+[
                        (g['group_id'],g['options']) for g in engine['choice_groups']]:
                        for part in items:
                            if part['card_id'] not in card_ids:
                                raise ValueError('missing engine card id')
                            # EX section is always a Monster. This is a type guard,
                            # not a guarantee that it is actually a legal EX card.
                            if part['section']=='EXTRA':
                                kind=next(r['kind'] for r in cards if r['card_id']==part['card_id'])
                                if kind!='MONSTER':raise ValueError('non-monster in EXTRA')
                            out.execute('INSERT INTO engine_parts VALUES (?,?,?,?,?,?,?)',(
                                engine['engine_id'],group_id,part['card_id'],
                                part['section'],part['min_copies'],part['max_copies'],part['role']))
                    for c in engine['constraints']:
                        out.execute('INSERT INTO engine_constraints VALUES (?,?,?,?,?,?)',(
                            engine['engine_id'],c['code'],c['scope'],c['source_url'],
                            c['verification'],c['note']))
                totals={name:out.execute('SELECT COUNT(*) FROM '+name).fetchone()[0]
                        for name in ('cards','themes','theme_relations','generic_roles',
                                     'engines','choice_groups','engine_parts','engine_constraints')}
                metadata={
                    'schema_version':'1','source_db_sha256':expected_source_sha256,
                    'm4_index_sha256':expected_m4_sha256,
                    'm4_extractor_version':extractor_version,
                    'seed_sha256':expected_seed_sha256,'as_of':seed['as_of'],
                    'classification':'PRIVATE_CANDIDATES_NOT_GAME_VERIFIED',
                }
                out.executemany('INSERT INTO metadata VALUES(?,?)',sorted(metadata.items()))
                out.commit()
                if out.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or out.execute('PRAGMA foreign_key_check').fetchall():
                    raise ValueError('invalid M5 index integrity')
        # Detect source/seed replacement while producing the sidecar.
        if (file_sha256(source_db)!=expected_source_sha256 or
            file_sha256(m4_index)!=expected_m4_sha256 or
            file_sha256(seed_path)!=expected_seed_sha256):
            raise ValueError('input changed during M5 build')
        if dest.exists() and not replace:raise ValueError('M5 index appeared concurrently')
        os.replace(temp,dest)
        return {'index_sha256':file_sha256(dest), 'seed_sha256':expected_seed_sha256,
                'source_db_sha256':expected_source_sha256,
                'm4_index_sha256':expected_m4_sha256,
                'counts':totals, 'relation_counts':dict(relation_counts),
                'verification':'PRIVATE_CANDIDATES_NOT_GAME_VERIFIED'}
    finally:
        if os.path.exists(temp):os.unlink(temp)


def _check_index(db,*,expected_source_sha256,expected_m4_sha256,expected_seed_sha256):
    meta=dict(db.execute('SELECT key,value FROM metadata'))
    for key,value in (('source_db_sha256',expected_source_sha256),
                      ('m4_index_sha256',expected_m4_sha256),
                      ('seed_sha256',expected_seed_sha256)):
        if value is not None and meta.get(key)!=value:
            raise ValueError('M5 stale '+key)
    if meta.get('schema_version')!='1' or meta.get('classification')!='PRIVATE_CANDIDATES_NOT_GAME_VERIFIED':
        raise ValueError('invalid M5 index metadata')
    return meta


def search_theme(index_path,theme_id,*,relations=None,limit=100,
                 expected_source_sha256=None,expected_m4_sha256=None,
                 expected_seed_sha256=None):
    if not isinstance(theme_id,str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{1,63}',theme_id):
        raise ValueError('invalid theme id')
    if relations is not None and (not isinstance(relations,(list,tuple)) or not relations or
       any(x not in ('NAME_MATCH_CANDIDATE','QUOTED_TARGET_CANDIDATE') for x in relations)):
        raise ValueError('invalid relation filter')
    if type(limit)is not int or not 1<=limit<=1000:raise ValueError('invalid limit')
    with closing(_open_ro(index_path)) as db:
        meta=_check_index(db,expected_source_sha256=expected_source_sha256,
                          expected_m4_sha256=expected_m4_sha256,expected_seed_sha256=expected_seed_sha256)
        where='r.theme_id=?';params=[theme_id]
        if relations:
            where+=' AND r.relation IN ('+','.join('?' for _ in relations)+')'
            params.extend(relations)
        rows=db.execute('''SELECT r.theme_id,r.card_id,c.name,c.rarity,c.kind,r.relation,
                                  r.verification,r.evidence,r.start,r.end,
                                  r.source_sha256,r.source_version
                           FROM theme_relations r JOIN cards c ON c.card_id=r.card_id
                           WHERE '''+where+' ORDER BY r.card_id,r.relation,r.start LIMIT ?',
                           params+[limit]).fetchall()
        return {'as_of':meta['as_of'],'theme_id':theme_id,
                'classification':meta['classification'],
                'results':[dict(r) for r in rows]}


def list_engine_variants(index_path,*,expected_source_sha256=None,
                         expected_m4_sha256=None,expected_seed_sha256=None):
    with closing(_open_ro(index_path)) as db:
        meta=_check_index(db,expected_source_sha256=expected_source_sha256,
                          expected_m4_sha256=expected_m4_sha256,expected_seed_sha256=expected_seed_sha256)
        return {'as_of':meta['as_of'],'results':[dict(r) for r in db.execute(
            'SELECT engine_id,name,theme_id,model_kind,verification,source_url FROM engines ORDER BY engine_id')]}


def get_engine(index_path,engine_id,*,expected_seed_sha256=None):
    with closing(_open_ro(index_path)) as db:
        meta=_check_index(db,expected_source_sha256=None,expected_m4_sha256=None,
                          expected_seed_sha256=expected_seed_sha256)
        e=db.execute('SELECT * FROM engines WHERE engine_id=?',(engine_id,)).fetchone()
        if e is None:raise ValueError('unknown engine')
        parts=[dict(r) for r in db.execute('''SELECT p.*,c.name,c.kind,c.rarity
            FROM engine_parts p JOIN cards c ON c.card_id=p.card_id
            WHERE engine_id=? ORDER BY group_id,section,card_id''',(engine_id,))]
        return {'as_of':meta['as_of'],'engine':dict(e),'parts':parts,
                'choice_groups':[dict(r) for r in db.execute(
                    'SELECT * FROM choice_groups WHERE engine_id=?',(engine_id,))],
                'constraints':[dict(r) for r in db.execute(
                    'SELECT * FROM engine_constraints WHERE engine_id=?',(engine_id,))],
                'classification':meta['classification']}


def search_generic_roles(index_path,*,role=None,limit=100):
    if role is not None and (not isinstance(role,str) or not re.fullmatch('[A-Z_]+',role)):
        raise ValueError('bad role')
    if type(limit)is not int or not 1<=limit<=1000:raise ValueError('bad limit')
    with closing(_open_ro(index_path)) as db:
        _check_index(db,expected_source_sha256=None,expected_m4_sha256=None,expected_seed_sha256=None)
        sql=('SELECT g.card_id,c.name,c.kind,c.rarity,g.role,g.verification,g.source_url '
             'FROM generic_roles g JOIN cards c ON g.card_id=c.card_id')
        vals=[]
        if role is not None:sql+=' WHERE g.role=?';vals.append(role)
        sql+=' ORDER BY g.card_id,g.role LIMIT ?';vals.append(limit)
        return [dict(r) for r in db.execute(sql,vals)]
