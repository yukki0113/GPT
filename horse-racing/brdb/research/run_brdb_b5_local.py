"""B5: private, non-scoring debut review from canonical pre-race PACI.
Use B1/B3 setup and B4 paths/results unchanged; historical results frozen through 2025.
No target outcome inputs, no CURRENT changes, no persistent relation updates.
"""
from pathlib import Path
from datetime import date,datetime
from collections import Counter
from dataclasses import asdict
import argparse,hashlib,json,re,sys,zipfile

ROOT=Path(__file__).resolve().parent
BRDB_SRC=ROOT.parent/'src'
JRDB_SRC=ROOT.parent.parent/'jrdb'/'src'
for p in (BRDB_SRC,JRDB_SRC):
    if p.is_dir():sys.path.insert(0,str(p))
from jrdb_raw import Parser,ReaderAudit,iter_archive_records,VERSION as RAW_VERSION
from brdb_parent_relation import HorseMasterIndex,resolve_first_generation
from run_brdb_b3_local import setup,cohort_sql,B2_ROOT,validate as validate_b3
from run_brdb_b4_local import build as build_b4,audit as audit_b4
from run_brdb_b1_b2_local import require,rows,sha,ANALYSIS_SHA,WAREHOUSE_SHA,PEDIGREE_SHAS
import run_brdb_b3_local as b3
import run_brdb_b4_local as b4

CUTOFF='2026-01-01'
COHORTS=('A1_RACE_ACTUAL_STARTERS','FIRST_OBSERVED_JRA_START_CANDIDATE')
LANES=('SIRE_ID','BMS_ID','PARENT_ID_PAIR','LINEAGE_CODE_PAIR')
SCOPES=('ALL','SURFACE','SURFACE_DISTANCE','SURFACE_MONTH','SURFACE_AGE')
TEMPORAL='AS_OF_UNVERIFIED'
PARENT='e2ff7dbc468ce4cd2282590d3cf92674d14f07a5'
MAIN='f757c45380813dcbee2a3f24e0376b5e45191205'
HIST_SOURCE_SHA={'run_brdb_b3_local.py':'d0cf57fc967a1ab98436a339ca10cc32c97bcbbfd2e202724fe6e67005d866b6','brdb_b3_debut_statistics_v0_1.sql':'eee017a885d66949efc7466efb28d99959426a97debf8e57a38a766687c587b1','run_brdb_b4_local.py':'dc1817610aedfb72b94990c5c33949da45aa331bd8d1fae919d020540fe951a3','brdb_b4_relative_paths_v0_1.sql':'e7a878add05326aab2a7232adb0fec84b61836ef5534f7cb7e512533cd1153ee','brdb_b4_relative_early_results_v0_1.sql':'d0348aaa888d0c131805d20c3abc85cb354da4effc217b20bcb50bcbb4ac1783'}

def iso(s):
    try:
        if re.fullmatch(r'[0-9]{8}',s or ''):return datetime.strptime(s,'%Y%m%d').date().isoformat()
    except ValueError:pass
    return None

def valid_id(s):return isinstance(s,str) and bool(re.fullmatch(r'[0-9]{8}',s)) and s!='00000000'

def read_field(paci,expected_sha,race_keys):
    require(sha(paci)==expected_sha,'PACI SHA mismatch')
    audit=ReaderAudit();parser=Parser(audit)
    bacs=[parser.bac(raw) for _,raw in iter_archive_records(paci,'BAC',audit)]
    selected=[r for r in bacs if r['race_key_raw'] in race_keys]
    require(len(selected)==len(race_keys) and len({r['race_key_raw'] for r in selected})==len(race_keys),'BAC missing/duplicate')
    dates={iso(r['date_raw']) for r in selected};require(len(dates)==1 and None not in dates,'invalid/mixed BAC date')
    target_date=dates.pop();require(CUTOFF<=target_date<'2027-01-01','frozen research supports 2026 only')
    require(paci.name.upper()=='PACI'+target_date[2:].replace('-','')+'.ZIP','archive date mismatch')
    for r in selected:
        require(r['race_class_code']=='A1' and r['surface_code'] in ('1','2') and r['distance_raw'].isdigit() and int(r['distance_raw'])>0,'non-A1/invalid race condition')
        require(re.fullmatch(r'[0-9a-fA-F]{8}',r['race_key_raw']) is not None,'invalid race key')
    entries=[parser.kyi(raw) for _,raw in iter_archive_records(paci,'KYI',audit)]
    entries=[e for e in entries if e['race_key_raw'] in race_keys]
    require(all(valid_id(e['blood_registration_no']) and type(e['horse_no']) is int and 1<=e['horse_no']<=18 for e in entries),'invalid KYI identity')
    require(len({(e['race_key_raw'],e['horse_no']) for e in entries})==len(entries) and len({e['blood_registration_no'] for e in entries})==len(entries),'duplicate KYI identity')
    for r in selected:require(sum(e['race_key_raw']==r['race_key_raw'] for e in entries)==r['field_size'] and r['field_size']>0,'BAC/KYI field count mismatch')
    # UKC is exact-ID joined; conflicts/missing are per-target unavailable, not dropped.
    profiles={};conflicts=set();invalid=set()
    for member,raw in iter_archive_records(paci,'UKC',audit):
        u=parser.ukc(raw);hid=u['horse_id'];obs=iso(u['data_date']);birth=iso(u['birth_date'])
        if not valid_id(hid) or obs is None or birth is None or obs>target_date or birth>obs:
            invalid.add(hid);continue
        if hid in profiles and u!=profiles[hid]:conflicts.add(hid)
        profiles[hid]=u
    require(not audit.record_length_errors,'canonical reader record-length errors')
    for hid in conflicts|invalid:profiles.pop(hid,None)
    return selected,sorted(entries,key=lambda e:(e['race_key_raw'],e['horse_no'])),profiles,conflicts|invalid,target_date

def individual_status(e,history,age,target_date):
    hid=e['blood_registration_no'];prior=e['previous'];known=any(h['start_status'] in ('STARTED_NORMAL','STARTED_ABNORMAL') for h in history)
    links=[]
    for k in prior:
        pr=k['result_key'].strip();pk=k['race_key_raw'].strip()
        if not pr and not pk:continue
        d=iso(pr[8:]) if re.fullmatch(r'[0-9]{16}',pr) and pr[:8]==hid else None
        if d is None or d>=target_date or not re.fullmatch(r'[0-9a-fA-F]{8}',pk):status='INVALID_OR_NONPRIOR_REFERENCE'
        else:
            h=next((x for x in history if x['race_key']==pk and x['race_date']==d),None)
            status='UNCONFIRMED_PRIOR_REFERENCE' if h is None else h['start_status']
            if status in ('STARTED_NORMAL','STARTED_ABNORMAL'):known=True
        links.append(dict(result_key=pr,race_key=pk,status=status))
    if known:status='KNOWN_PRIOR_JRA_START'
    elif any(x['status']!='NON_STARTER' for x in links) or any(h['start_status']=='UNKNOWN' for h in history):status='PRIOR_HISTORY_UNRESOLVED'
    elif age not in (2,3):status='AGE_OR_HISTORY_UNCERTAIN'
    else:status='NO_PRIOR_START_OBSERVED_HISTORY_INCOMPLETE'
    return dict(status=status,prior_references=links,observed_prior_starts=sum(h['start_status'] in ('STARTED_NORMAL','STARTED_ABNORMAL') for h in history),lifetime_first_start_certified=False)

def sample_cell(stat,base,available):
    if not available:status='SOURCE_UNAVAILABLE';n=None
    elif stat is None:status='NO_SAMPLE';n=0
    else:n=stat['starts'];status='LOW_SAMPLE' if n<30 else 'DESCRIPTIVE'
    return dict(status=status,starts=n,horses=None if n is None else stat['horses'] if stat else 0,races=None if n is None else stat['races'] if stat else 0,wins=None if n is None else stat['wins'] if stat else 0,top3=None if n is None else stat['top3'] if stat else 0,top3_rate=stat['top3_rate'] if stat else None,max_history_date=stat['max_history_date'] if stat else None,baseline_starts=base['baseline_starts'] if base else 0,baseline_top3=base['baseline_top3'] if base else 0,resolved_starts=base['resolved_starts'] if base else 0,resolved_top3=base['resolved_top3'] if base else 0,left_marginal_starts=stat['left_marginal_starts'] if stat else None,left_marginal_top3=stat['left_marginal_top3'] if stat else None,right_marginal_starts=stat['right_marginal_starts'] if stat else None,right_marginal_top3=stat['right_marginal_top3'] if stat else None)

def generate(input_root,paci,expected_sha,race_keys):
    for path in (Path(b3.__file__),Path(b3.ROOT/'brdb_b3_debut_statistics_v0_1.sql'),Path(b4.__file__),Path(b4.ROOT/'brdb_b4_relative_paths_v0_1.sql'),Path(b4.ROOT/'brdb_b4_relative_early_results_v0_1.sql')):require(sha(path)==HIST_SOURCE_SHA[path.name],'upstream source mismatch: '+path.name)
    races,entries,profiles,bad_profiles,target_date=read_field(paci,expected_sha,race_keys)
    c=setup(input_root);c.execute('INSERT INTO cutoff VALUES (?)',[CUTOFF])
    c.execute('CREATE TEMP TABLE cohort AS '+cohort_sql((B2_ROOT/'brdb_b2_sire_debut_statistics_v0_1.sql').read_text()))
    require(c.execute('SELECT count(*) FROM cohort').fetchone()[0]==78184,'historical cohort mismatch')
    c.execute('CREATE TEMP TABLE stats AS '+(b3.ROOT/'brdb_b3_debut_statistics_v0_1.sql').read_text());validate_b3(c,CUTOFF)
    require(c.execute('SELECT count(*) FILTER(WHERE race_date>=?)=0 FROM classified',[CUTOFF]).fetchone()[0],'history cutoff violation')
    # Canonical dated master index: same priority rule as B4. PACI observations are appended
    # in memory, not written into immutable warehouse/master. Only exact alias-free resolution.
    c.execute('CREATE TEMP TABLE paci_profiles AS SELECT * FROM dated_ukc WHERE false')
    cols=['horse_id','horse_name','sex_code','coat_color_code','horse_symbol_code','sire_name','dam_name','broodmare_sire_name','birth_date','sire_birth_year','dam_birth_year','broodmare_sire_birth_year','owner_name','owner_group_code','breeder_name','breeding_place','deregistered_flag','data_date','sire_line_code','broodmare_sire_line_code','semantic_hash','birth_date_iso','data_date_iso']
    if profiles:c.executemany('INSERT INTO paci_profiles('+','.join(cols)+') VALUES ('+','.join('?' for _ in cols)+')',[[u.get(k) if k not in ('birth_date_iso','data_date_iso') else iso(u['birth_date' if k=='birth_date_iso' else 'data_date']) for k in cols] for _,u in sorted(profiles.items())])
    c.execute('CREATE TEMP TABLE historical_ukc AS SELECT * FROM dated_ukc');c.execute('DROP VIEW dated_ukc')
    c.execute('''CREATE TEMP VIEW dated_ukc AS SELECT * FROM (SELECT *,1 AS priority FROM paci_profiles UNION ALL SELECT *,2 AS priority FROM historical_ukc) QUALIFY row_number() OVER(PARTITION BY horse_id,data_date_iso ORDER BY priority)=1''')
    # Index considers latest date-qualified observation of every canonical individual.
    fields='horse_id,horse_name,sex_code,birth_date,sire_name,sire_birth_year,dam_name,dam_birth_year,broodmare_sire_name,broodmare_sire_birth_year,sire_line_code,broodmare_sire_line_code'
    master=rows(c,f'''SELECT {fields},obs FROM (SELECT {fields},data_date_iso AS obs,1 AS priority FROM dated_ukc UNION ALL SELECT {fields},strftime(try_strptime(profile_data_date,'%Y%m%d'),'%Y-%m-%d') AS obs,2 AS priority FROM pedigree_master) WHERE obs IS NOT NULL AND obs<='{target_date}' AND regexp_full_match(horse_id,'[0-9]{{8}}') AND horse_id<>'00000000' QUALIFY row_number() OVER(PARTITION BY horse_id ORDER BY obs DESC,priority)=1 ORDER BY horse_id''')
    by_id={x['horse_id']:x for x in master};idx=HorseMasterIndex(master)
    official={x[0] for x in c.execute('SELECT lineage_code FROM lineage_master').fetchall()}
    c.execute('CREATE TEMP TABLE overlay_edges AS SELECT * FROM parent_master WHERE false')
    c.execute('CREATE TEMP TABLE field_targets(cohort VARCHAR,race_key VARCHAR,horse_no BIGINT,horse_id VARCHAR,race_date VARCHAR,track_type VARCHAR,distance BIGINT,age BIGINT,ukc_date VARCHAR,sire_id VARCHAR)')
    rd={r['race_key_raw']:r for r in races};target_meta={}
    for e in entries:
        hid=e['blood_registration_no'];rk=e['race_key_raw'];no=e['horse_no'];u=profiles.get(hid);r=rd[rk]
        age=int(target_date[:4])-int(u['birth_date'][:4]) if u else None
        resolution={}
        if u:
            for role,z in resolve_first_generation(u,master=idx).items():
                z=asdict(z);pid=z['resolved_horse_id'];parent=by_id.get(pid)
                # Canonical resolver enforces uniqueness, sex and lineage/BMS guard;
                # additionally require valid distinct ID, older birth and official code.
                if z['status']=='RESOLVED_EXACT' and (not valid_id(pid) or pid==hid or parent is None or not iso(parent['birth_date']) or parent['birth_date']>=u['birth_date'] or z['requested_lineage_code'] not in official):
                    z['status']='TARGET_GUARD_REJECTED';z['resolved_horse_id']=None;pid=None
                if z['status']!='RESOLVED_EXACT':z['resolved_horse_id']=None;pid=None
                resolution[role]=dict(status=z['status'],parent_id=pid,guard=z['guard'],candidate_count=z['candidate_count'],profile_date=parent['obs'] if pid else None)
                if pid:c.execute('INSERT INTO overlay_edges VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',[hid,role,z['requested_name'],z['requested_birth_year'],z['requested_lineage_code'],pid,z['status'],z['resolution_method'],z['candidate_count'],z['guard'],'B5_CANONICAL_RESOLVER_EPHEMERAL','PACI_TARGET_ONLY'])
        else:
            resolution={role:dict(status='SOURCE_UNAVAILABLE',parent_id=None,guard=None,candidate_count=0,profile_date=None) for role in ('sire','dam','broodmare_sire')}
        sire=resolution['sire']['parent_id'];bms=resolution['broodmare_sire']['parent_id']
        keys={'SIRE_ID':(sire,''),'BMS_ID':(bms,''),'PARENT_ID_PAIR':(sire,bms),'LINEAGE_CODE_PAIR':(u['sire_line_code'] if u and u['sire_line_code'] in official else None,u['broodmare_sire_line_code'] if u and u['broodmare_sire_line_code'] in official else None)}
        dates={'ALL':'ALL','SURFACE':r['surface_code'],'SURFACE_DISTANCE':r['surface_code']+':'+str(int(r['distance_raw'])),'SURFACE_MONTH':r['surface_code']+':'+target_date[5:7],'SURFACE_AGE':r['surface_code']+':'+str(age) if age is not None else None}
        hist=c.execute('SELECT race_key,race_date,start_status FROM classified WHERE horse_id=? AND race_date<? ORDER BY race_date,race_key',[hid,target_date]);hh=[dict(zip([x[0] for x in hist.description],v)) for v in hist.fetchall()]
        target_meta[rk,no]=dict(race_key=rk,horse_no=no,horse_id=hid,age=age,race_class_code='A1',profile_status='DATED_PACI_UKC' if u else 'INVALID_OR_CONFLICTING_UKC' if hid in bad_profiles else 'MISSING_UKC',profile_date=iso(u['data_date']) if u else None,individual_eligibility=individual_status(e,hh,age,target_date),parent_resolution=resolution,keys=keys,dimensions=dates,paci_cancel_flag=e['cancel_flag'])
        c.execute('INSERT INTO field_targets VALUES (?,?,?,?,?,?,?,?,?,?)',['PRE_RACE_FIELD',rk,no,hid,target_date,r['surface_code'],int(r['distance_raw']),age,iso(u['data_date']) if u else None,sire])
    # Overlay only the target child edges. Never change historical stats or static file bytes.
    c.execute('CREATE TEMP TABLE saved_parent_master AS SELECT * FROM parent_master');c.execute('DROP VIEW parent_master')
    c.execute('CREATE TEMP VIEW parent_master AS SELECT * FROM saved_parent_master WHERE child_horse_id NOT IN (SELECT horse_id FROM field_targets) UNION ALL SELECT * FROM overlay_edges')
    c.execute('DROP TABLE cohort');c.execute('CREATE TEMP TABLE cohort AS SELECT * FROM field_targets')
    build_b4(c);family_audit=audit_b4(c)
    # Select exact matching lane/cohort/scope/dimension, never sum overlapping cells.
    statrows=rows(c,'SELECT * FROM stats ORDER BY cohort,scope,dimension,lane,key1,key2')
    baseline={(s['cohort'],s['scope'],s['dimension'],s['lane']):s for s in statrows}
    group={(s['cohort'],s['scope'],s['dimension'],s['lane'],s['key1'],s['key2']):s for s in statrows if s['starts']>0}
    relatives={};coverage={}
    for x in rows(c,'SELECT * FROM target_coverage ORDER BY race_key,horse_no'):coverage[x['race_key'],x['horse_no']]=x
    relcols='race_key,horse_no,horse_id,race_date,relative_id,paths,relationships,path_count,relative_profile_date,relative_birth_date,relative_profile_source,history_status,first_observed_date,first_date,first_race_class,first_race_key,scope,first_starts,first_wins,first_top3,early_starts,early_wins,early_top3,early_top3_rate,max_history_date,early_history_keys,sample_status'
    for x in rows(c,f'SELECT {relcols} FROM relative_stats ORDER BY race_key,horse_no,relative_id,scope'):
        key=(x.pop('race_key'),x.pop('horse_no'));require(x.pop('horse_id')==target_meta[key]['horse_id'] and x.pop('race_date')==target_date,'relative identity mismatch');x['evidence_id']=f'{key[0]}:{key[1]:02d}:RELATIVE:{x["relative_id"]}:{x["scope"]}';relatives.setdefault(key,[]).append(x)
    out=[]
    for key,t in sorted(target_meta.items()):
        evidence=[]
        for co in COHORTS:
            for lane in LANES:
                k1,k2=t['keys'][lane]
                for scope in SCOPES:
                    dim=t['dimensions'][scope];bkey=(co,scope,dim,lane);available=k1 is not None and k2 is not None and dim is not None
                    s=group.get((*bkey,k1,k2)) if available else None
                    evidence.append(dict(evidence_id=f'{key[0]}:{key[1]:02d}:{co}:{lane}:{scope}',cohort=co,lane=lane,scope=scope,dimension=dim,key1=k1,key2=k2,**sample_cell(s,baseline.get(bkey),available)))
        cv=coverage[key];rr=relatives.get(key,[]);require(cv['horse_id']==t['horse_id'] and cv['race_date']==target_date,'coverage identity mismatch')
        relcv={k:cv[k] for k in ('dam_status','granddam_status','dam_id','granddam_id','target_profile_date','dam_profile_date','granddam_profile_date','path_candidates','accepted_paths','relative_count','overlapping_paths','first_candidate_relatives','unresolved_first_relatives','no_prior_relatives','complete_early_relatives','status')}
        if relcv['dam_status']!='RESOLVED':relcv['sample_status']='SOURCE_UNAVAILABLE'
        elif relcv['first_candidate_relatives']==0:relcv['sample_status']='NO_SAMPLE'
        else:relcv['sample_status']='LOW_SAMPLE'
        t.pop('keys');t.pop('dimensions');t['population_evidence']=evidence;t['relative_coverage']=relcv;t['relative_evidence']=rr;out.append(t)
    result=dict(schema_version='brdb-debut-review-v0.1-candidate',research_only=True,prediction_safe=False,production_authorized=False,temporal_status=TEMPORAL,source_equivalence_policy='USER_ACCEPTED_PROVIDER_EQUIVALENCE',target_date=target_date,history_cutoff_exclusive=CUTOFF,history_start='2016-01-01',population_start='2017-01-01',history_gap_2026=True,scope_overlap='COHORTS_LANES_SCOPES_AND_RELATIVES_NOT_INDEPENDENT',paci_sha256=expected_sha,source_commit=PARENT,analysis_sha256=ANALYSIS_SHA,warehouse_sha256=WAREHOUSE_SHA,pedigree_sha256=PEDIGREE_SHAS,raw_reader_version=RAW_VERSION,races=[dict(race_key=r['race_key_raw'],race_class_code='A1',surface=r['surface_code'],distance=int(r['distance_raw']),declared_count=r['field_size']) for r in sorted(races,key=lambda x:x['race_key_raw'])],horses=out)
    validate(result,entries);c.close();return result,family_audit

def validate(result,entries=None):
    require(result['research_only'] is True and result['prediction_safe'] is False and result['production_authorized'] is False and result['temporal_status']==TEMPORAL,'research gate')
    target=result['target_date'];cutoff=result['history_cutoff_exclusive'];require(cutoff==CUTOFF and cutoff<=target and result['history_gap_2026'] is True,'cutoff/gap gate')
    field=result['horses'];identities={(h['race_key'],h['horse_no'],h['horse_id']) for h in field};require(len(identities)==len(field) and len({(h['race_key'],h['horse_no']) for h in field})==len(field) and len({h['horse_id'] for h in field})==len(field),'duplicate field')
    if entries is not None:require(identities=={(e['race_key_raw'],e['horse_no'],e['blood_registration_no']) for e in entries},'PACI field identity mismatch')
    require({h['race_key'] for h in field}=={r['race_key'] for r in result['races']},'race identity mismatch')
    for r in result['races']:require(r['race_class_code']=='A1' and sum(h['race_key']==r['race_key'] for h in field)==r['declared_count'],'field completeness')
    ids=set()
    for h in field:
        require(valid_id(h['horse_id']) and h['race_class_code']=='A1' and h['individual_eligibility']['lifetime_first_start_certified'] is False,'invalid target/eligibility')
        require((h['profile_status']=='DATED_PACI_UKC')==(h['profile_date'] is not None) and (h['profile_date'] is None or h['profile_date']<=target),'invalid/future target profile')
        require(all(p['profile_date'] is None or p['profile_date']<=target for p in h['parent_resolution'].values()),'future parent profile')
        for p in h['parent_resolution'].values():require((p['parent_id'] is None and p['status']!='RESOLVED_EXACT') or (p['status']=='RESOLVED_EXACT' and valid_id(p['parent_id']) and p['parent_id']!=h['horse_id'] and p['candidate_count']==1),'parent guard')
        cells=h['population_evidence'];require(len(cells)==40 and {(x['cohort'],x['lane'],x['scope']) for x in cells}=={(co,la,sc) for co in COHORTS for la in LANES for sc in SCOPES},'population cells')
        for x in cells:
            require(x['evidence_id']==f"{h['race_key']}:{h['horse_no']:02d}:{x['cohort']}:{x['lane']}:{x['scope']}" and x['evidence_id'] not in ids,'population evidence ID mismatch');ids.add(x['evidence_id'])
            expected={'SIRE_ID':(h['parent_resolution']['sire']['parent_id'],''),'BMS_ID':(h['parent_resolution']['broodmare_sire']['parent_id'],''),'PARENT_ID_PAIR':(h['parent_resolution']['sire']['parent_id'],h['parent_resolution']['broodmare_sire']['parent_id'])}
            if x['lane'] in expected:require((x['key1'],x['key2'])==expected[x['lane']],'parent evidence identity mismatch')
            else:require(all(k is None or re.fullmatch(r'[0-9]{4}',k) for k in (x['key1'],x['key2'])),'invalid lineage key')
            available=x['key1'] is not None and x['key2'] is not None and x['dimension'] is not None
            require(available==(x['status']!='SOURCE_UNAVAILABLE'),'source availability mismatch')
            race=next(r for r in result['races'] if r['race_key']==h['race_key']);dim={'ALL':'ALL','SURFACE':race['surface'],'SURFACE_DISTANCE':race['surface']+':'+str(race['distance']),'SURFACE_MONTH':race['surface']+':'+target[5:7],'SURFACE_AGE':race['surface']+':'+str(h['age']) if h['age'] is not None else None}
            require(x['dimension']==dim[x['scope']],'scope dimension mismatch')
            require(x['max_history_date'] is None or x['max_history_date']<cutoff<=target,'future result')
            require(0<=x['baseline_top3']<=x['baseline_starts'] and 0<=x['resolved_top3']<=x['resolved_starts']<=x['baseline_starts'],'baseline bounds')
            n=x['starts'];require((n is None and x['status']=='SOURCE_UNAVAILABLE' and x['top3_rate'] is None) or (n==0 and x['status']=='NO_SAMPLE' and x['top3_rate'] is None) or (n is not None and n>0 and x['status']==('LOW_SAMPLE' if n<30 else 'DESCRIPTIVE') and 0<=x['wins']<=x['top3']<=n<=x['resolved_starts'] and x['top3_rate']==x['top3']/n),'sample status/bounds')
        rel=h['relative_evidence'];cv=h['relative_coverage'];require(len(rel)==5*cv['relative_count'] and len({(r['relative_id'],r['scope']) for r in rel})==len(rel),'relative scope count')
        for r in rel:
            require(r['evidence_id']==f"{h['race_key']}:{h['horse_no']:02d}:RELATIVE:{r['relative_id']}:{r['scope']}" and r['evidence_id'] not in ids,'relative evidence ID mismatch');ids.add(r['evidence_id'])
            require(valid_id(r['relative_id']) and r['relative_id']!=h['horse_id'] and r['relative_profile_date']<=target,'relative ID/date')
            require(r['path_count']==len(r['paths'])==len(r['relationships']) and r['path_count']>0,'relative path count')
            require(r['first_observed_date'] is None or r['first_observed_date']<cutoff,'relative observed date')
            require(r['history_status']=='FIRST_OBSERVED_CANDIDATE' or r['early_starts']==0,'unresolved first history used')
            require(r['max_history_date'] is None or r['max_history_date']<cutoff<=target,'relative future history')
            require(r['first_date'] is None or r['first_date']<cutoff,'relative first date')
            require(0<=r['first_wins']<=r['first_top3']<=r['first_starts']<=1 and 0<=r['early_wins']<=r['early_top3']<=r['early_starts']<=3 and r['first_starts']<=r['early_starts'],'relative bounds')
            require((r['early_starts']==0 and r['early_top3_rate'] is None) or (r['early_starts']>0 and r['sample_status']=='LOW_SAMPLE' and r['early_top3_rate']==r['early_top3']/r['early_starts']),'relative missing/low-N guard')
    return True

def run(input_root,paci,expected_sha,race_keys,output):
    require(not output.resolve().is_relative_to(input_root.resolve()),'output inside immutable input');output.mkdir(parents=True,exist_ok=True)
    result,family=generate(input_root,paci,expected_sha,race_keys)
    payload=json.dumps(result,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n';p=output/'PRIVATE_b5_review.json';p.write_text(payload)
    stats=dict(horses=len(result['horses']),races=len(result['races']),profile_status=dict(Counter(h['profile_status'] for h in result['horses'])),individual_status=dict(Counter(h['individual_eligibility']['status'] for h in result['horses'])),population_status=dict(Counter(x['status'] for h in result['horses'] for x in h['population_evidence'])),parent_status={role:dict(Counter(h['parent_resolution'][role]['status'] for h in result['horses'])) for role in ('sire','dam','broodmare_sire')},lanes={lane:dict(Counter(x['status'] for h in result['horses'] for x in h['population_evidence'] if x['lane']==lane)) for lane in LANES},relative_target_status=dict(Counter(h['relative_coverage']['status'] for h in result['horses'])),relative_pairs=sum(h['relative_coverage']['relative_count'] for h in result['horses']),relative_scope_status=dict(Counter(x['sample_status'] for h in result['horses'] for x in h['relative_evidence'])),races_coverage=[dict(race_key=r['race_key'],declared_count=r['declared_count'],reviewed=sum(h['race_key']==r['race_key'] for h in result['horses'])) for r in result['races']])
    receipt=dict(status='PASS_RESEARCH_ONLY',prediction_safe=False,production_authorized=False,source_base_commit=PARENT,main_observed=MAIN,paci_sha256=expected_sha,history_cutoff_exclusive=CUTOFF,analysis_sha256=ANALYSIS_SHA,warehouse_sha256=WAREHOUSE_SHA,pedigree_sha256=PEDIGREE_SHAS,source_sha256={Path(__file__).name:sha(Path(__file__)),**HIST_SOURCE_SHA},private_output_sha256=sha(p),summary=stats,family_audit=family)
    (output/'b5_receipt.json').write_text(json.dumps(receipt,sort_keys=True,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(json.dumps(stats,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input-root',type=Path,required=True);p.add_argument('--paci',type=Path,required=True);p.add_argument('--paci-sha256',required=True);p.add_argument('--race-key',action='append',required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();run(a.input_root,a.paci,a.paci_sha256,set(a.race_key),a.output_dir)
