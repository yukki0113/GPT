"""U3: pinned private batch -> transactional schema-v4 candidate.
No Drive writes. Private diff includes old text; publish only aggregate audit.
"""
from collections import Counter
from datetime import datetime, date
from hashlib import sha256
from pathlib import Path
import json, shutil, sqlite3
from card_master_import.importer import MONSTER_TYPES, SPELL_PROPS, TRAP_PROPS, LINK_ARROWS
from card_master_import.stage2_gen9_migration import extract_material_requirement
from card_master_import.incremental.normalize import ATTRIBUTES, RACES, EX, evidence

TABLES = ('cards','card_attributes','md_catalog','card_texts','card_monster_types',
          'card_spell_trap_properties','card_link_markers','card_pendulum_details',
          'card_extra_material_requirements')
ATTR = ('kind','attribute','race','level','rank','link','atk','def')
VERIFY = 'UNVERIFIED_SOURCE'

def digest(raw): return sha256(raw).hexdigest()
def encode(obj): return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',',':'))
def source(obj): return encode(obj)
def require(ok, msg):
    if not ok: raise ValueError(msg)

def material(c):
    methods = EX.intersection(c['monster_types'])
    if not methods: return None
    method = next(iter(methods))
    head, pre, parsed = extract_material_requirement(method,c['ja_text'])
    return dict(summon_method=method,material_header=head,material_header_sha256=digest(head.encode()),
                pre_effect_restrictions=pre,source_text_sha256=digest(c['ja_text'].encode()),
                **parsed,material_verification='SOURCE_TEXT_ONLY',simultaneous_materials_verified=0,summon_route_verified=0)

def validate(c):
    cid=c['card_id']; require(type(c['konami_id']) is int and c['konami_id']>0 and cid==f"konami:{c['konami_id']}",'CID')
    require(all(isinstance(c[k],str) and c[k].strip() for k in ('name_ja','ja_text')),'NAME_TEXT')
    date.fromisoformat(c['effective_on']); require(bool(c['channels']),'EVENT')
    require(c['verification']==VERIFY,'VERIFICATION')
    require(c['rarity'] in (None,'N','R','SR','UR') and c['craftable'] in ('YES','NO','UNKNOWN'),'CATALOG')
    s=c['sources'];
    for k in ('identity','attributes','ja_text'):
        evidence([s[k]]); require(s[k].get('konami_id')==c['konami_id'],'SOURCE_CID')
        require(s[k].get('verification')=='OCG_SHARED','UNSUPPORTED_SOURCE_CLASS')
    evidence(s['md_implementation']);
    if c['rarity'] is not None: evidence(s['md_rarity'])
    if c['craftable']!='UNKNOWN': evidence([s['craftable']])
    flags=c['monster_types']; arrows=c['link_markers']; k=c['kind'];
    require(len(flags)==len(set(flags)) and set(flags)<=MONSTER_TYPES and len(EX.intersection(flags))<=1,'FLAGS')
    require(len(arrows)==len(set(arrows)) and set(arrows)<=LINK_ARROWS,'ARROWS')
    for key in ('level','rank','link','atk','def'):
        require(c[key] is None or type(c[key]) is int and c[key]>=0,'STAT')
    if k=='MONSTER':
        require(bool(flags) and c['attribute'] in ATTRIBUTES and c['race'] in RACES and c['spell_trap_property'] is None,'MONSTER')
        if 'LINK' in flags: require(c['link']==len(arrows) and 1<=c['link']<=8 and all(c[x] is None for x in ('level','rank','def')),'LINK')
        elif 'XYZ' in flags: require(c['rank'] in range(14) and c['level'] is None and c['link'] is None and not arrows,'XYZ')
        else: require(c['level'] in range(14) and c['rank'] is None and c['link'] is None and not arrows,'LEVEL')
    else:
        require(k in ('SPELL','TRAP') and not flags and not arrows and all(c[x] is None for x in ATTR[1:]),'NONMONSTER')
        require(c['spell_trap_property'] in (SPELL_PROPS if k=='SPELL' else TRAP_PROPS),'PROPERTY')
    if 'PENDULUM' in flags:
        require(type(c['pendulum_scale']) is int and 0<=c['pendulum_scale']<=13 and isinstance(c['ja_pendulum_effect'],str) and c['ja_pendulum_effect'].strip(),'PENDULUM')
        evidence([s['ja_pendulum_effect']]); require(s['ja_pendulum_effect'].get('konami_id')==c['konami_id'],'P_SOURCE')
    else: require(c['pendulum_scale'] is None and c['ja_pendulum_effect'] is None,'NONPENDULUM')
    require(c['extra_material_requirement']==material(c),'MATERIAL_ANCHOR')

def rows(db,table,cid):
    return [dict(x) for x in db.execute(f'SELECT * FROM {table} WHERE card_id=? ORDER BY 1,2',(cid,))]

def desired(c,stamp):
    cid=c['card_id']; s=c['sources']; os='OCG_SHARED:'+source(s['attributes']); ts='OCG_SHARED:'+source(s['ja_text']); ms='MD:'+source(s['md_implementation']); rs='MD:'+source(s['md_rarity']) if c['rarity'] is not None else None
    common={'card_id':cid,'verification':VERIFY}; timed={**common,'acquired_at':stamp}
    m=c['extra_material_requirement']; mat=[]
    if m:
        mat=[{'card_id':cid,**{k:v for k,v in m.items() if k!='material_labels'},'material_labels_json':json.dumps(m['material_labels'],ensure_ascii=False),'source':ts}]
    return {'cards':[{**timed,'konami_id':c['konami_id'],'name':c['name_ja'],'source':'OCG_SHARED:'+source(s['identity'])}],
      'card_attributes':[{**timed,**{k:c[k] for k in ATTR},'source':os}],
      'md_catalog':[{**timed,'rarity':c['rarity'],'rarity_source':rs,'craftable':c['craftable'],'source':ms}],
      'card_texts':[{**timed,'language':'ja','version':'OCG_SHARED_'+digest(c['ja_text'].encode()),'body':c['ja_text'],'source':ts}],
      'card_monster_types':[{**common,'monster_type':x,'source':os} for x in c['monster_types']],
      'card_spell_trap_properties':[{**common,'property':c['spell_trap_property'],'source':os}] if c['spell_trap_property'] is not None else [],
      'card_link_markers':[{**common,'arrow':x,'source':os} for x in c['link_markers']],
      'card_pendulum_details':[{**common,'scale':c['pendulum_scale'],'ja_pendulum_effect':c['ja_pendulum_effect'],'source':'OCG_SHARED:'+source(s['ja_pendulum_effect'])}] if c['pendulum_scale'] is not None else [],
      'card_extra_material_requirements':mat}

# Evidence-only differences do not trigger writes. Preserve existing provenance on no-op.
META={'source','acquired_at','verification','rarity_source','version'}
def semantic(rs): return sorted(encode({k:v for k,v in x.items() if k not in META}) for x in rs)

def plan(db,batch):
    require(batch['schema']=='md-card-incremental-update-v1','SCHEMA')
    stamp=batch['observed_at']; require(datetime.fromisoformat(stamp).utcoffset() is not None,'TIMESTAMP')
    ids=[c['card_id'] for c in batch['cards']]; require(len(set(ids))==len(ids),'DUPLICATE')
    require(not set(ids)&{x.get('card_id') for x in batch['unresolved']},'PENDING_OVERLAP')
    changes=[]
    for c in batch['cards']:
        validate(c); cid=c['card_id']; before={t:rows(db,t,cid) for t in TABLES}; after=desired(c,stamp)
        require(not db.execute('SELECT 1 FROM cards WHERE konami_id=? AND card_id<>?',(c['konami_id'],cid)).fetchone(),'CID_CONFLICT')
        if before['cards']:
            require(before['cards'][0]['konami_id']==c['konami_id'],'CID_CONFLICT')
            require(all(len(before[t])==1 for t in ('card_attributes','md_catalog')),'BASE_INCOMPLETE')
            # Non-Japanese texts are outside this batch. Preserve them exactly.
            ja=[r for r in before['card_texts'] if r['language']=='ja']; require(len(ja)==1,'CURRENT_JA_NOT_UNIQUE')
            after['card_texts'] += [r for r in before['card_texts'] if r['language']!='ja']
            a=after['card_attributes'][0]; old=before['card_attributes'][0]
            # Null ATK/DEF is unknown where applicable; non-applicable structural fields can clear.
            if a['kind']=='MONSTER' and old['kind']=='MONSTER':
                retained={}
                if a['atk'] is None and old['atk'] is not None: a['atk']=old['atk']; retained['atk']=old['source']
                if 'LINK' not in c['monster_types'] and a['def'] is None and old['def'] is not None: a['def']=old['def']; retained['def']=old['source']
                if retained: a['source']='OCG_SHARED:'+source({'incoming':c['sources']['attributes'],'retained':retained})
            new=after['md_catalog'][0]; old=before['md_catalog'][0]
            if new['rarity'] is None: new['rarity'],new['rarity_source']=old['rarity'],old['rarity_source']
            if new['craftable']=='UNKNOWN' and old['craftable']!='UNKNOWN':
                new['craftable']=old['craftable']; new['source']='MD:'+source({'implementation':c['sources']['md_implementation'],'retained_craftable_source':old['source']})
            elif new['craftable']!='UNKNOWN': new['source']='MD:'+source({'implementation':c['sources']['md_implementation'],'craftable':c['sources']['craftable']})
        changed=[]
        for t in TABLES:
            if semantic(before[t])==semantic(after[t]): after[t]=before[t]; continue
            # Do not downgrade a game-verified row through unverified OCG evidence.
            require(not any(r.get('verification')=='GAME_VERIFIED' for r in before[t]),'GAME_VERIFIED_CONFLICT')
            changed.append(t)
        if not before['cards']: actions=['INSERT']
        elif not changed: actions=['NO_CHANGE']
        else:
            actions=[]
            if 'card_texts' in changed: actions.append('UPDATE_TEXT')
            if 'md_catalog' in changed: actions.append('UPDATE_RARITY')
            if set(changed)-{'md_catalog','card_texts'}: actions.append('UPDATE_ATTRIBUTES')
        changes.append({'card_id':cid,'actions':actions,'tables':changed,'before':{t:before[t] for t in changed},'after':{t:after[t] for t in changed},'sources':c['sources']})
    return changes

def write_plan(db,changes,*,fail_after=None):
    for n,c in enumerate(changes,1):
        cid=c['card_id']
        for t in c['tables']:
            old,new=c['before'][t],c['after'][t]
            require(rows(db,t,cid)==old,'PLAN_STALE')
            if t=='cards' and old:
                r=new[0]; keys=[k for k in r if k!='card_id']; db.execute('UPDATE cards SET '+','.join(k+'=?' for k in keys)+' WHERE card_id=?',[r[k] for k in keys]+[cid]); continue
            if t=='card_texts': db.execute("DELETE FROM card_texts WHERE card_id=? AND language='ja'",(cid,)); new=[r for r in new if r['language']=='ja']
            else: db.execute(f'DELETE FROM {t} WHERE card_id=?',(cid,))
            for r in new:
                keys=list(r); db.execute(f'INSERT INTO {t} ('+','.join(keys)+') VALUES ('+','.join('?' for _ in keys)+')',[r[k] for k in keys])
        if fail_after==n: raise RuntimeError('INJECTED_FAILURE')

def table_hashes(db, excluded=()):
    result={}
    for t, in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        cols=[r[1] for r in db.execute(f'PRAGMA table_info({t})')]; q=f'SELECT * FROM {t}'; params=[]
        if t in TABLES and excluded: q+=' WHERE card_id NOT IN ('+','.join('?' for _ in excluded)+')'; params=list(excluded)
        q+=' ORDER BY '+','.join(str(i+1) for i in range(len(cols))); h=sha256(); count=0
        for r in db.execute(q,params): h.update((encode(list(r))+'\n').encode()); count+=1
        result[t]={'count':count,'sha256':h.hexdigest()}
    return result

def integrity(db):
    require([tuple(r) for r in db.execute('PRAGMA integrity_check')]==[('ok',)] and not db.execute('PRAGMA foreign_key_check').fetchone(),'INTEGRITY')
    require([x[0] for x in db.execute('SELECT version FROM schema_migrations ORDER BY version')]==[1,2,3,4],'SCHEMA_VERSION')

def apply(base,batch_path,dest,diff_path,*,expected_batch_sha,expected_generation,expected_base_sha,fail_after=None):
    """Write private diff before commit; candidate and diff are never production.
    Existing destination refused; exact base SHA required. Rebase is a new U2 batch.
    """
    base,batch_path,dest,diff_path=map(Path,(base,batch_path,dest,diff_path))
    require(not dest.exists() and not diff_path.exists() and dest.resolve()!=diff_path.resolve(),'OUTPUT_EXISTS')
    raw=batch_path.read_bytes(); require(digest(raw)==expected_batch_sha,'BATCH_SHA'); batch=json.loads(raw)
    require(digest(base.read_bytes())==expected_base_sha and batch['base_sqlite_sha256']==expected_base_sha and batch['base_generation']==expected_generation,'BASE_SHA_OR_GENERATION')
    shutil.copy2(base,dest); db=sqlite3.connect(dest); db.row_factory=sqlite3.Row; db.execute('PRAGMA foreign_keys=ON')
    try:
        integrity(db); db.execute('BEGIN IMMEDIATE'); changes=plan(db,batch); ids=[c['card_id'] for c in changes]; before=table_hashes(db,ids)
        diff={'schema':'md-card-incremental-diff-v1','batch_id':batch['batch_id'],'batch_sha256':expected_batch_sha,'base_sqlite_sha256':expected_base_sha,'base_generation':expected_generation,'changes':changes,'unresolved':batch['unresolved'],'pending_count':len(batch['unresolved']),'non_target_hashes':before}
        # Persist old text/evidence before modifying the candidate. Never use a public path.
        with diff_path.open('x',encoding='utf-8') as f: json.dump(diff,f,ensure_ascii=False,indent=2); f.write('\n')
        write_plan(db,changes,fail_after=fail_after); integrity(db)
        require(table_hashes(db,ids)==before,'NON_TARGET_CHANGED')
        for c in batch['cards']:
            cid=c['card_id']; require(db.execute("SELECT count(*) FROM card_texts WHERE card_id=? AND language='ja'",(cid,)).fetchone()[0]==1,'JA_UNIQUE')
            m=db.execute('SELECT source_text_sha256 FROM card_extra_material_requirements WHERE card_id=?',(cid,)).fetchone()
            if m: require(m[0]==digest(c['ja_text'].encode()),'MATERIAL_SHA')
        replay=plan(db,batch); require(all(x['actions']==['NO_CHANGE'] for x in replay),'REPLAY_NOT_NOOP')
        db.commit(); integrity(db)
        return {'actions':dict(Counter(a for x in changes for a in x['actions'])),'table_counts':{t:v['count'] for t,v in table_hashes(db).items()},'non_target_hashes_equal':True,'replay_noop':len(replay),'pending':len(batch['unresolved']),'integrity':'PASS','foreign_keys':'PASS'}
    except Exception:
        db.rollback(); raise
    finally: db.close()
