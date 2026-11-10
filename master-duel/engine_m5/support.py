"""M5-B private, conservative cross-attribute/race/theme support discovery.

Builds a *separate* sidecar from the pinned production catalog and M4 evidence.
It does not infer official theme membership, rulings, legal targets or combos.
Quoted terms are candidate group identifiers; target compatibility is a broad
attribute/race catalog match that must be checked against full effect text.
"""
from __future__ import annotations

from contextlib import closing
from hashlib import sha256
from pathlib import Path
from urllib.parse import quote
import os
import re
import sqlite3
import tempfile

ATTRIBUTES = {'光':'LIGHT','闇':'DARK','地':'EARTH','水':'WATER',
              '炎':'FIRE','風':'WIND','神':'DIVINE'}
RACES = {
'戦士':'Warrior','魔法使い':'Spellcaster','ドラゴン':'Dragon',
'悪魔':'Fiend','機械':'Machine','天使':'Fairy','獣戦士':'Beast-Warrior',
'鳥獣':'Winged Beast','獣':'Beast','アンデット':'Zombie','サイバース':'Cyberse',
'水':'Aqua','海竜':'Sea Serpent','魚':'Fish','雷':'Thunder','炎':'Pyro',
'岩石':'Rock','昆虫':'Insect','植物':'Plant','サイキック':'Psychic',
'恐竜':'Dinosaur','爬虫類':'Reptile','幻竜':'Wyrm','幻神獣':'Divine-Beast',
'幻想魔':'Illusion',
}
# All lexical observations are candidates; never rewrite official card metadata.
ATTR_RE = re.compile(r'('+'|'.join(map(re.escape,ATTRIBUTES))+r')属性')
RACE_RE = re.compile('('+'|'.join(map(re.escape,sorted(RACES,key=len,reverse=True)))+r')族')
QUOTED = re.compile('「([^」\n]{2,30})」')
ACTION_FACETS = ('SEARCH_FROM_DECK','RECOVER_FROM_GRAVE','SPECIAL_SUMMON',
                 'RETURN_TO_HAND','NEGATE','DESTROY','BANISH')
SCHEMA = '''
PRAGMA foreign_keys=ON;
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE cards(card_id TEXT PRIMARY KEY,name TEXT NOT NULL,kind TEXT,rarity TEXT,
                   attribute TEXT,race TEXT,level INTEGER,rank INTEGER);
CREATE TABLE property_support(id INTEGER PRIMARY KEY,source_card_id TEXT NOT NULL REFERENCES cards(card_id),
    target_type TEXT NOT NULL CHECK(target_type IN ('ATTRIBUTE','RACE')),
    target_value TEXT NOT NULL,action TEXT NOT NULL,role TEXT NOT NULL,
    start INTEGER NOT NULL,end INTEGER NOT NULL,evidence TEXT NOT NULL,
    text_sha256 TEXT NOT NULL,text_version TEXT NOT NULL,
    verification TEXT NOT NULL DEFAULT 'UNVERIFIED_INTERPRETATION',
    UNIQUE(source_card_id,target_type,target_value,action,role,start,end));
CREATE INDEX property_support_filter ON property_support(target_type,target_value,action,role);
CREATE TABLE name_groups(group_key TEXT PRIMARY KEY,member_count INTEGER NOT NULL,
                         reference_count INTEGER NOT NULL);
CREATE TABLE name_group_members(group_key TEXT NOT NULL REFERENCES name_groups(group_key),
    card_id TEXT NOT NULL REFERENCES cards(card_id),PRIMARY KEY(group_key,card_id));
CREATE INDEX name_members_card ON name_group_members(card_id);
CREATE TABLE name_group_refs(group_key TEXT NOT NULL REFERENCES name_groups(group_key),
    source_card_id TEXT NOT NULL REFERENCES cards(card_id),start INTEGER NOT NULL,
    end INTEGER NOT NULL,evidence TEXT NOT NULL,text_sha256 TEXT NOT NULL,
    text_version TEXT NOT NULL,role TEXT NOT NULL,
    PRIMARY KEY(group_key,source_card_id,start,end));
'''


def _sha(path):
    h=sha256()
    with open(path,'rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''): h.update(part)
    return h.hexdigest()


def _ro(path):
    path=Path(path).resolve()
    if not path.is_file(): raise ValueError('input does not exist')
    con=sqlite3.connect('file:'+quote(str(path),safe='/')+'?mode=ro',uri=True)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA query_only=ON')
    return con


def _check_pin(path,sha):
    if not isinstance(sha,str) or re.fullmatch('[a-f0-9]{64}',sha) is None:
        raise ValueError('expected SHA256 required')
    if _sha(path)!=sha: raise ValueError('input SHA256 mismatch')


def extract_property_support(evidence,*,action,role):
    """Use M4 ACTION clauses only; detect broad property context, not verified target.

    Only a positive action and explicit property mention within the SAME M4
    sentence can produce a candidate; cost/condition/referenced clauses do not.
    Inferences about which part of a multi-part effect is supported remain
    unverified. Return distinct (type,value) pairs.
    """
    if action not in ACTION_FACETS or role!='ACTION' or not isinstance(evidence,str):
        return []
    if re.search(r'できない|できず|無効にされる|発動を無効',evidence):
        return []
    found={('ATTRIBUTE',ATTRIBUTES[m.group(1)]) for m in ATTR_RE.finditer(evidence)}
    found.update(('RACE',RACES[m.group(1)]) for m in RACE_RE.finditer(evidence))
    return sorted(found)


def build_private_support_index(source_db,m4_db,dest,*,expected_source_sha256,
                                expected_m4_sha256,replace=False,min_group_members=2):
    """Read-only inputs; atomically publish *derived private* source excerpts."""
    source_db,m4_db,dest=map(lambda p:Path(p).resolve(),(source_db,m4_db,dest))
    if len({source_db,m4_db,dest})!=3:raise ValueError('paths must differ')
    if type(min_group_members) is not int or not 2<=min_group_members<=10:
        raise ValueError('invalid minimum group member count')
    _check_pin(source_db,expected_source_sha256)
    _check_pin(m4_db,expected_m4_sha256)
    if dest.exists() and not replace:raise ValueError('index exists; explicit replace required')
    dest.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.m5-support-',suffix='.sqlite',dir=dest.parent)
    os.close(fd)
    try:
        with closing(_ro(source_db)) as source,closing(_ro(m4_db)) as m4:
            for con in (source,m4):
                if con.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                    raise ValueError('input integrity mismatch')
                if con.execute('PRAGMA foreign_key_check').fetchall():
                    raise ValueError('input foreign keys invalid')
            ver=dict(m4.execute('SELECT key,value FROM metadata'))
            if ver.get('source_sqlite_sha256')!=expected_source_sha256:
                raise ValueError('stale M4 source')
            cards=list(source.execute('''SELECT c.card_id,c.name,a.kind,m.rarity,
                     a.attribute,a.race,a.level,a.rank,a.link FROM cards c
                     LEFT JOIN card_attributes a ON a.card_id=c.card_id
                     LEFT JOIN md_catalog m ON m.card_id=c.card_id'''))
            with closing(sqlite3.connect(tmp)) as out:
                out.executescript(SCHEMA)
                out.executemany('INSERT INTO cards VALUES (?,?,?,?,?,?,?,?)',
                                (tuple(row)[:8] for row in cards))
                for facet in m4.execute('''SELECT card_id,facet,role,start,end,evidence,
                     text_sha256,text_version FROM facets WHERE role='ACTION' AND
                     facet IN ('SEARCH_FROM_DECK','RECOVER_FROM_GRAVE','SPECIAL_SUMMON',
                               'RETURN_TO_HAND','NEGATE','DESTROY','BANISH')
                     ORDER BY card_id,start'''):
                    for kind,val in extract_property_support(
                          facet['evidence'],action=facet['facet'],role=facet['role']):
                        out.execute('''INSERT OR IGNORE INTO property_support
                            (source_card_id,target_type,target_value,action,role,start,end,
                            evidence,text_sha256,text_version)
                            VALUES(?,?,?,?,?,?,?,?,?,?)''',
                            (facet['card_id'],kind,val,facet['facet'],facet['role'],
                             facet['start'],facet['end'],facet['evidence'],
                             facet['text_sha256'],facet['text_version']))
                # Candidate theme keys are discovered from exact quoted terms,
                # but only when >=2 cards have that token in the actual name.
                names={}
                for row in cards:
                    for facet in m4.execute('''SELECT evidence,start,end,text_sha256,
                                          text_version,role FROM facets
                         WHERE card_id=? AND facet='NAMED_TARGET' ''',(row['card_id'],)):
                        for hit in QUOTED.finditer(facet['evidence']):
                            token=hit.group(1)
                            if not 3<=len(token)<=24 or token in names:continue
                            names[token]=None
                for token in sorted(names):
                    members=[c['card_id'] for c in cards if token in c['name']]
                    if len(members)<min_group_members:continue
                    refs=list(m4.execute('''SELECT card_id,evidence,start,end,text_sha256,
                                             text_version,role FROM facets
                              WHERE facet='NAMED_TARGET' AND evidence LIKE ?''',
                              ('%「'+token+'」%',)))
                    refs=[r for r in refs if token in QUOTED.findall(r['evidence'])]
                    if not refs:continue
                    out.execute('INSERT INTO name_groups VALUES(?,?,?)',
                                (token,len(members),len(refs)))
                    out.executemany('INSERT INTO name_group_members VALUES (?,?)',
                                    ((token,cid) for cid in members))
                    out.executemany('''INSERT OR IGNORE INTO name_group_refs
                         VALUES (?,?,?,?,?,?,?,?)''',((token,r['card_id'],r['start'],
                         r['end'],r['evidence'],r['text_sha256'],r['text_version'],
                         r['role']) for r in refs))
                metrics={n:out.execute('SELECT COUNT(*) FROM '+n).fetchone()[0]
                         for n in ('cards','property_support','name_groups',
                                   'name_group_members','name_group_refs')}
                meta={'schema_version':'1','source_sha256':expected_source_sha256,
                      'm4_sha256':expected_m4_sha256,
                      'classification':'UNVERIFIED_SUPPORT_CANDIDATES',
                      'minimum_group_members':str(min_group_members)}
                out.executemany('INSERT INTO metadata VALUES (?,?)',sorted(meta.items()))
                out.commit()
                if out.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                    raise ValueError('sidecar integrity failed')
                if out.execute('PRAGMA foreign_key_check').fetchall():
                    raise ValueError('sidecar foreign key failure')
        _check_pin(source_db,expected_source_sha256)
        _check_pin(m4_db,expected_m4_sha256)
        if dest.exists() and not replace:raise ValueError('index appeared concurrently')
        os.replace(tmp,dest)
        return {'metrics':metrics,'index_sha256':_sha(dest),
                'source_sha256':expected_source_sha256,
                'm4_sha256':expected_m4_sha256,
                'verification':'UNVERIFIED_SUPPORT_CANDIDATES'}
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def search_property_support(index_path,*,attribute=None,race=None,action=None,
                            target_card_id=None,match_mode='ANY',limit=50,expected_source_sha256=None):
    """Exact property filter; never conflate a card's properties with its support."""
    if attribute is not None and attribute not in ATTRIBUTES.values():
        raise ValueError('invalid attribute')
    if race is not None and race not in RACES.values():
        raise ValueError('invalid race')
    if action is not None and action not in ACTION_FACETS:
        raise ValueError('invalid action')
    if match_mode not in ('ANY','ALL'):
        raise ValueError('invalid match mode')
    if type(limit) is not int or not 1<=limit<=1000:
        raise ValueError('invalid limit')
    with closing(_ro(index_path)) as con:
        meta=dict(con.execute('SELECT key,value FROM metadata'))
        if meta.get('classification')!='UNVERIFIED_SUPPORT_CANDIDATES':
            raise ValueError('invalid M5 support index')
        if expected_source_sha256 is not None and meta.get('source_sha256')!=expected_source_sha256:
            raise ValueError('stale M5 support index')
        where=[];params=[]
        if target_card_id is not None:
            if not isinstance(target_card_id,str):raise ValueError('invalid target card')
            target=con.execute('SELECT attribute,race FROM cards WHERE card_id=?',
                               (target_card_id,)).fetchone()
            if target is None:raise ValueError('unknown target card')
            attribute,race=target['attribute'],target['race']
        if attribute is None and race is None:
            raise ValueError('attribute, race or target card required')
        if attribute is not None:
            where.append("(p.target_type='ATTRIBUTE' AND p.target_value=?)");params.append(attribute)
        if race is not None:
            where.append("(p.target_type='RACE' AND p.target_value=?)");params.append(race)
        sql=('''SELECT p.source_card_id,c.name AS source_name,p.target_type,p.target_value,
                      p.action,p.role,p.evidence,p.start,p.end,p.text_sha256,
                      p.text_version,p.verification FROM property_support p
                      JOIN cards c ON c.card_id=p.source_card_id
                      WHERE ('''+ ' OR '.join(where)+')')
        if attribute is not None and race is not None and match_mode=='ALL':
            # Require both attributes in the SAME source evidence span;
            # unrelated effects cannot be accidentally conjoined.
            sql+=(''' AND EXISTS (SELECT 1 FROM property_support q WHERE
                     q.source_card_id=p.source_card_id AND q.start=p.start
                     AND q.end=p.end AND q.action=p.action AND
                     q.target_type='ATTRIBUTE' AND q.target_value=?)
                     AND EXISTS (SELECT 1 FROM property_support q WHERE
                     q.source_card_id=p.source_card_id AND q.start=p.start
                     AND q.end=p.end AND q.action=p.action AND
                     q.target_type='RACE' AND q.target_value=?)''')
            params.extend([attribute,race])
        if action: sql+=' AND p.action=?';params.append(action)
        sql+=' ORDER BY p.source_card_id,p.target_type,p.action LIMIT ?';params.append(limit)
        return {'verification':meta['classification'],'results':[dict(r) for r in con.execute(sql,params)]}


def search_name_groups(index_path,*,query=None,min_members=2,limit=50):
    if query is not None and (not isinstance(query,str) or not query.strip()):
        raise ValueError('invalid query')
    if type(min_members)is not int or min_members<2 or type(limit)is not int or not 1<=limit<=1000:
        raise ValueError('invalid search bounds')
    with closing(_ro(index_path)) as con:
        sql='''SELECT group_key,member_count,reference_count FROM name_groups
               WHERE member_count>=?''';args=[min_members]
        if query is not None:
            sql+=' AND instr(group_key,?)>0';args.append(query)
        sql+=' ORDER BY reference_count DESC,group_key LIMIT ?';args.append(limit)
        return {'verification':'NAME_GROUP_CANDIDATE_NOT_OFFICIAL_ARCHETYPE',
                'results':[dict(r) for r in con.execute(sql,args)]}


def search_name_group_support(index_path, group_key, *, include_members=False,
                              limit=50,expected_source_sha256=None):
    """Find named group references outside/inside group; never certify searchability.

    A quoted group name may describe a cost, restriction or negated effect.
    Callers must inspect source evidence before adopting it as engine support.
    """
    if not isinstance(group_key,str) or not group_key or len(group_key)>30:
        raise ValueError('invalid group key')
    if type(limit) is not int or not 1<=limit<=1000:
        raise ValueError('invalid limit')
    with closing(_ro(index_path)) as db:
        meta=dict(db.execute('SELECT key,value FROM metadata'))
        if (meta.get('classification')!='UNVERIFIED_SUPPORT_CANDIDATES' or
            (expected_source_sha256 is not None and meta.get('source_sha256')!=expected_source_sha256)):
            raise ValueError('stale or invalid M5 support index')
        if db.execute('SELECT 1 FROM name_groups WHERE group_key=?',(group_key,)).fetchone() is None:
            raise ValueError('unknown candidate group')
        sql='''SELECT r.source_card_id,c.name AS source_name,r.evidence,r.start,
                      r.end,r.text_sha256,r.text_version,r.role,
                      CASE WHEN m.card_id IS NULL THEN 0 ELSE 1 END AS same_group_name
               FROM name_group_refs r JOIN cards c ON c.card_id=r.source_card_id
               LEFT JOIN name_group_members m ON m.group_key=r.group_key
                                             AND m.card_id=r.source_card_id
               WHERE r.group_key=?'''
        if not include_members:sql+=' AND m.card_id IS NULL'
        sql+=' ORDER BY r.source_card_id,r.start LIMIT ?'
        return {'group_key':group_key,'verification':'QUOTED_REFERENCE_CANDIDATE_NOT_VERIFIED_SUPPORT',
                'results':[dict(x) for x in db.execute(sql,(group_key,limit))]}
