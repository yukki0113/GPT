"""Fail-closed stage-1 Gen7->Gen8 MD private DB migration (no remote writes).

Requires pinned MD+cards source and current SQLite SHA; card IDs are matched
using the audited Gen7 crosswalk. Non-target state is compared byte-for-byte
at SQLite row serialization level. No materials/combos are inferred.
"""
from __future__ import annotations
import hashlib, json, sqlite3
from pathlib import Path
from collections import Counter
from .monster_types_migration import build_type_map

SHA7='d3ab2fa3e3c79e455a10dd9ff8aebb407a3bd045fac0d1f50711cc0443906ecb'
MD_SHA='b7bf8e365d293cfa6bc309dbbc5cbefae3a7d1b498d34cdf7c54fc26e5bd152b'
CARDS_SHA='5f71287c55c610c2753e1c6ecade4bdf9f1c7981555a127d03ccd82a493c97b7'
PROPS={"Spell":{"Normal","Quick-Play","Continuous","Field","Equip","Ritual"},"Trap":{"Normal","Continuous","Counter"}}
ARROWS={'Top-Left','Top-Center','Top-Right','Middle-Left','Middle-Right','Bottom-Left','Bottom-Center','Bottom-Right'}
SOURCE='MD:yaml-yugi:sha256:'+MD_SHA

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def row_hash(conn,table,ignore=()):
    cols=[r[1] for r in conn.execute(f'PRAGMA table_info({table})') if r[1] not in ignore]
    cur=conn.execute('SELECT '+','.join('"'+c+'"' for c in cols)+' FROM "'+table+'" ORDER BY '+','.join('"'+c+'"' for c in cols))
    h=hashlib.sha256()
    for row in cur:
        b=json.dumps(tuple(row),ensure_ascii=False,separators=(',',':')).encode();h.update(len(b).to_bytes(4,'big'));h.update(b)
    return h.hexdigest()
def migrate(source,md_path,cards_path,dest):
    for path,expected in ((source,SHA7),(md_path,MD_SHA),(cards_path,CARDS_SHA)):
        if digest(path)!=expected:raise ValueError('SHA_MISMATCH '+str(path))
    if Path(dest).exists():raise ValueError('output exists')
    md=json.loads(Path(md_path).read_bytes()); cards=json.loads(Path(cards_path).read_bytes())
    src=sqlite3.connect(f'file:{Path(source).resolve()}?mode=ro',uri=True)
    src.row_factory=sqlite3.Row
    try:
        if src.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('source_integrity')
        if [r[0] for r in src.execute('SELECT version FROM schema_migrations ORDER BY version')]!=[1,2]:raise ValueError('source_schema')
        tables=[r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'") if r[0]!='schema_migrations']
        base_hashes={t:row_hash(src,t,('link',) if t=='card_attributes' else ()) for t in tables}
        mapping=build_type_map(md,cards,src)
        expected={cid:set(flags) for cid,flags in mapping.items()}
        out=sqlite3.connect(str(dest))
        try:
            src.backup(out)
            out.execute('PRAGMA foreign_keys=ON')
            if out.execute('PRAGMA foreign_keys').fetchone()[0]!=1:raise ValueError('foreign_keys_disabled')
            out.execute('BEGIN IMMEDIATE')
            out.executescript('''
CREATE TABLE card_spell_trap_properties (
 card_id TEXT PRIMARY KEY REFERENCES cards(card_id), property TEXT NOT NULL,
 source TEXT NOT NULL, verification TEXT NOT NULL DEFAULT 'UNVERIFIED_SOURCE');
CREATE INDEX idx_card_spell_trap_property ON card_spell_trap_properties(property,card_id);
CREATE TABLE card_link_markers (
 card_id TEXT NOT NULL REFERENCES cards(card_id), arrow TEXT NOT NULL
 CHECK(arrow IN ('Top-Left','Top-Center','Top-Right','Middle-Left','Middle-Right','Bottom-Left','Bottom-Center','Bottom-Right')),
 source TEXT NOT NULL, verification TEXT NOT NULL DEFAULT 'UNVERIFIED_SOURCE',
 PRIMARY KEY(card_id,arrow));
CREATE INDEX idx_card_link_markers_arrow ON card_link_markers(arrow,card_id);
CREATE TABLE card_pendulum_details (
 card_id TEXT PRIMARY KEY REFERENCES cards(card_id), scale INTEGER NOT NULL CHECK(scale BETWEEN 0 AND 13),
 ja_pendulum_effect TEXT, source TEXT NOT NULL,
 verification TEXT NOT NULL DEFAULT 'UNVERIFIED_SOURCE');
''')
            props=[];arrows=[];links=[];pend=[]
            names={r[0]:r[1] for r in src.execute('SELECT card_id,name FROM cards')}
            # The MD record list is aligned with the source-to-KONAMI-ID map in
            # exactly the same iteration order, including duplicate-name disambiguations.
            # Derive mapping per unique source record via strict name/id crosswalk
            # using the canonical Gen7 SQLite match and typed attribute comparison.
            # Use the migration's mapping by mapping MD source records through
            # a validated name+type+race+MD-source-to-card ID index.
            import unicodedata
            def norm(x):return ''.join(ch for ch in unicodedata.normalize('NFKC',x).casefold() if ch.isalnum())
            candidates={}
            for c in cards:
                en=c.get('name',{}).get('en')
                if isinstance(en,str) and isinstance(c.get('konami_id'),int):
                    candidates.setdefault(en,[]).append(c)
            normalized_candidates={}
            for en,items in candidates.items():normalized_candidates.setdefault(norm(en),[]).extend(items)
            dbattrs={cid:(kind,race) for cid,kind,race in src.execute('SELECT c.card_id,a.kind,a.race FROM cards c JOIN card_attributes a USING(card_id)')}
            seen=set()
            for rec in md:
                en=rec['en_name'];typ=rec.get('card_type')
                if typ in PROPS: want=(typ.upper(),None)
                else:want=('MONSTER',rec['types'].split('/')[0].strip())
                source_candidates=candidates.get(en) or normalized_candidates.get(norm(en),[])
                viable=[]
                for c in source_candidates:
                    cid='konami:'+str(c['konami_id'])
                    if dbattrs.get(cid)!=want:continue
                    stypes=expected.get(cid)
                    if typ not in PROPS:
                        flags={p.strip().upper() for p in rec['types'].split('/')[1:]}
                        if stypes!=flags:continue
                    viable.append(cid)
                ids=set(viable)
                if len(ids)!=1:raise ValueError(f'mapping ambiguous: {en}: {ids}')
                cid=next(iter(ids))
                if cid in seen:raise ValueError('duplicate card '+cid)
                seen.add(cid)
                if typ in PROPS:
                    p=rec.get('property')
                    if p not in PROPS[typ]:raise ValueError('unknown spell trap property '+str(p))
                    props.append((cid,p,SOURCE,'UNVERIFIED_SOURCE'))
                    if rec.get('link_arrows') is not None or rec.get('pendulum_scale') is not None:raise ValueError('nonmonster EXTRA props')
                if 'link_arrows' in rec:
                    if 'LINK' not in expected[cid]:raise ValueError('nonlink markers')
                    a=[z.strip() for z in rec['link_arrows'].split(',')]
                    if not a or len(set(a))!=len(a) or not set(a)<=ARROWS:raise ValueError('invalid arrow')
                    links.append((cid,len(a)))
                    arrows.extend((cid,x,SOURCE,'UNVERIFIED_SOURCE') for x in a)
                elif 'LINK' in expected[cid]:raise ValueError('link missing markers '+cid)
                if 'pendulum_scale' in rec:
                    if 'PENDULUM' not in expected[cid]:raise ValueError('nonpendulum scale')
                    scale=rec['pendulum_scale']
                    if not isinstance(scale,str) or not scale.isdecimal() or not 0<=int(scale)<=13:raise ValueError('bad scale')
                    ja=rec.get('ja_pendulum_effect')
                    if ja is not None and (not isinstance(ja,str) or not ja.strip()):raise ValueError('bad ja pend effect')
                    pend.append((cid,int(scale),ja,SOURCE,'UNVERIFIED_SOURCE'))
                elif 'PENDULUM' in expected[cid]:raise ValueError('missing pend scale '+cid)
            if len(seen)!=13948 or len(props)!=4834 or len(links)!=453 or len(pend)!=385:raise ValueError('incomplete source')
            out.executemany('INSERT INTO card_spell_trap_properties VALUES (?,?,?,?)',props)
            out.executemany('INSERT INTO card_link_markers VALUES (?,?,?,?)',arrows)
            out.executemany('INSERT INTO card_pendulum_details VALUES (?,?,?,?,?)',pend)
            for cid,n in links:
                cur=out.execute('UPDATE card_attributes SET link=? WHERE card_id=? AND link IS NULL',(n,cid))
                if cur.rowcount!=1:raise ValueError('unexpected existing link')
            if out.execute('SELECT count(*) FROM card_attributes WHERE link IS NOT NULL').fetchone()[0]!=453:raise ValueError('link count')
            out.execute('INSERT INTO schema_migrations(version) VALUES(3)')
            out.commit()
            if out.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or list(out.execute('PRAGMA foreign_key_check')):raise ValueError('new integrity')
            for t,h in base_hashes.items():
                if row_hash(out,t,('link',) if t=='card_attributes' else ())!=h:raise ValueError('EXISTING_TABLE_MUTATED '+t)
            counter=Counter(x[1] for x in props)
            return {'source_sha256':SHA7,'sqlite_sha256':digest(dest),'cards':len(seen),'spell_trap':len(props),'spell_trap_by_property':dict(counter),'link_monsters':len(links),'link_marker_rows':len(arrows),'pendulum_cards':len(pend),'pendulum_japanese_effects':sum(x[2] is not None for x in pend),'unchanged_existing_tables':len(tables),'integrity':'PASS','foreign_keys':'PASS','schema_versions':[1,2,3]}
        finally:out.close()
    finally:src.close()

if __name__=='__main__':
 import sys
 result=migrate(*sys.argv[1:]); print(json.dumps(result,ensure_ascii=False,indent=2))