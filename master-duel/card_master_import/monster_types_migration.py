"""Offline, fail-closed Gen6 monster type classification migration (no Drive writes).

Uses exact pinned source snapshots and the existing KONAMI IDs. Preserves every
other DB row and can only be run against a known original DB SHA.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path
import json
import sqlite3
import unicodedata

TYPES = frozenset('NORMAL EFFECT FUSION SYNCHRO XYZ LINK RITUAL PENDULUM TUNER FLIP GEMINI SPIRIT UNION TOON'.split())
DDL = """CREATE TABLE card_monster_types (
    card_id TEXT NOT NULL REFERENCES cards(card_id),
    monster_type TEXT NOT NULL CHECK(monster_type IN
      ('NORMAL','EFFECT','FUSION','SYNCHRO','XYZ','LINK','RITUAL',
       'PENDULUM','TUNER','FLIP','GEMINI','SPIRIT','UNION','TOON')),
    source TEXT NOT NULL, verification TEXT NOT NULL DEFAULT 'UNVERIFIED_SOURCE',
    PRIMARY KEY(card_id,monster_type)
);
CREATE INDEX idx_card_monster_types_type ON card_monster_types(monster_type,card_id);
"""

def normalized_name(name):
    return ''.join(c for c in unicodedata.normalize('NFKC',name).casefold() if c.isalnum())

def build_type_map(md_source, card_source, db):
    mapping=defaultdict(list)
    exact=defaultdict(list)
    for c in card_source:
        en=c.get('name',{}).get('en')
        if isinstance(en,str) and en:
            exact[en].append(c)
            mapping[normalized_name(en)].append(c)
    db_cards={r['card_id']:(r['kind'],r['race']) for r in db.execute(
        'SELECT c.card_id,a.kind,a.race FROM cards c JOIN card_attributes a USING(card_id)')}
    selections={}
    for record in md_source:
        name=record.get('en_name')
        if not isinstance(name,str) or not name:
            raise ValueError('unrecognized MD source name')
        rawtypes=record.get('types')
        if isinstance(rawtypes,str) and rawtypes.strip():
            parts=[part.strip() for part in rawtypes.split('/')]
            if len(parts)<2 or not parts[0] or not all(x.upper() in TYPES for x in parts[1:]):
                raise ValueError('unknown or malformed monster types: '+name)
            expected=('MONSTER',parts[0]); category=tuple(x.upper() for x in parts[1:])
            if len(set(category))!=len(category):raise ValueError('duplicate source type')
        elif record.get('card_type') in ('Spell','Trap'):
            expected=(record['card_type'].upper(),None);category=()
        else:
            raise ValueError('unknown card source type: '+name)
        candidates=exact.get(name) or mapping[normalized_name(name)]
        valid=[]
        for c in candidates:
            konami=c.get('konami_id')
            if type(konami) is not int:continue
            cid='konami:'+str(konami)
            if db_cards.get(cid)!=expected:continue
            orig=c.get('monster_type_line')
            if len({v.get("konami_id") for v in candidates})>1 and category:
                cp=[part.strip().upper() for part in (orig or "").split("/")][1:]
                if ("RITUAL" in category)!=("RITUAL" in cp) or ("NORMAL" in category)!=("NORMAL" in cp):
                    continue
            valid.append(cid)
        unique=set(valid)
        if len(unique)!=1:
            raise ValueError(f'ambiguous or missing source mapping: {name} {unique}')
        cid=next(iter(unique))
        if cid in selections:raise ValueError('duplicate mapped card id: '+cid)
        selections[cid]=category
    if set(selections)!=set(db_cards):
        raise ValueError(f'full source/card-master coverage mismatch: {len(selections)} != {len(db_cards)}')
    return selections

def migrate(base_path, md_path, cards_path, output_path, *, expected_db_sha, expected_md_sha, expected_cards_sha):
    for p,expected in ((base_path,expected_db_sha),(md_path,expected_md_sha),(cards_path,expected_cards_sha)):
        if sha256(Path(p).read_bytes()).hexdigest()!=expected:
            raise ValueError('SOURCE_SHA_MISMATCH: '+str(p))
    if Path(output_path).exists():raise ValueError('output already exists')
    md=json.loads(Path(md_path).read_text(encoding='utf-8'))
    cards=json.loads(Path(cards_path).read_text(encoding='utf-8'))
    source=sqlite3.connect('file:'+str(Path(base_path).resolve())+'?mode=ro',uri=True)
    source.row_factory=sqlite3.Row
    try:
        if source.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('source corrupt')
        if source.execute('SELECT group_concat(version) FROM schema_migrations ORDER BY version').fetchone()[0]!='1':
            raise ValueError('unexpected schema version')
        before={table:source.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in
                ('cards','card_attributes','card_texts','md_catalog','inventory','inventory_history','inventory_batches',
                 'banlist_entries','banlist_snapshots','decks','deck_cards')}
        mapping=build_type_map(md,cards,source)
        out=sqlite3.connect(str(output_path));out.row_factory=sqlite3.Row
        try:
            source.backup(out)
            out.execute('PRAGMA foreign_keys=ON')
            out.execute('BEGIN IMMEDIATE')
            try:
                for line in DDL.split(';'):
                    if line.strip():out.execute(line)
                records=[(cid,t,'MD:yaml-yugi:sha256:'+expected_md_sha,'UNVERIFIED_SOURCE')
                         for cid,types in mapping.items() for t in types]
                out.executemany('INSERT INTO card_monster_types(card_id,monster_type,source,verification) VALUES (?,?,?,?)',records)
                out.execute('INSERT INTO schema_migrations(version) VALUES (2)')
                out.commit()
            except Exception:
                out.rollback();raise
            after={table:out.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in before}
            if before!=after:raise ValueError('CARD_OR_INVENTORY_COUNTS_CHANGED')
            if out.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('integrity failure')
            if out.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('foreign keys failure')
            for cid in mapping:
                actual={r[0] for r in out.execute('SELECT monster_type FROM card_monster_types WHERE card_id=?',(cid,))}
                if actual!=set(mapping[cid]):raise ValueError('type mismatch: '+cid)
            if out.execute('SELECT count(*) FROM card_monster_types').fetchone()[0]!=len(records):raise ValueError('types count mismatch')
            if out.execute('SELECT count(*) FROM card_monster_types WHERE monster_type IN (\'FUSION\',\'SYNCHRO\',\'XYZ\',\'LINK\')').fetchone()[0]==0:raise ValueError('no EXTRA types')
            distribution=dict(out.execute('SELECT monster_type,count(*) FROM card_monster_types GROUP BY monster_type').fetchall())
        finally:out.close()
    finally:source.close()
    return {'source_db_sha256':expected_db_sha,'new_db_sha256':sha256(Path(output_path).read_bytes()).hexdigest(),
            'source_md_sha256':expected_md_sha,'source_cards_sha256':expected_cards_sha,
            'original_table_rows_unchanged':before,'covered_card_count':len(mapping),
            'type_rows':len(records),'type_distribution':distribution,'schema_versions':[1,2]}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    for x in ('base','md','cards','output','expected_db_sha','expected_md_sha','expected_cards_sha'):
        p.add_argument('--'+x.replace('_','-'),required=True)
    a=vars(p.parse_args())
    print(json.dumps(migrate(a['base'],a['md'],a['cards'],a['output'],
        expected_db_sha=a['expected_db_sha'],expected_md_sha=a['expected_md_sha'],expected_cards_sha=a['expected_cards_sha']),ensure_ascii=False,indent=2))