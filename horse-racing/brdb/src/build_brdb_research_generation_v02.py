#!/usr/bin/env python3
"""Build a separate immutable v0.2 annual-preserving research generation.

Cohort sizes/ID sets come from a SHA-pinned request, not 104/108 constants.
Legacy builders, generations and production pointers are never written.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import tempfile
import zipfile
from collections import Counter,defaultdict
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

from audit_race_year_pedigree import ROOT,annual_availability,csv_write,dump,sha,table,verified
from brdb_research_reader_v02 import (CONTRACT_VERSION,ID_SET_ENCODING,ResearchGenerationReader,ids_sha256,valid_date)
from build_brdb_research_candidate import select_daily,TABLE_KEYS
import build_brdb_pedigree_generation as base_builder
import brdb_parent_relation as relation
import jrdb_ukc
from jrdb_raw import canonical_members

VERSION='research-paci-v0.2'
SELECTION='annual-facts-exact;previous-added-facts-and-selected-source-exact;new-latest-valid-profile-date/archive/member/line;conflict-fails-v0.2'
BASIC=tuple(f for f in base_builder.FIELDS if f not in ('profile_data_date','semantic_hash','source_family','source_generation'))


def recipe_sources():
    return [Path(__file__),Path(sys.modules['brdb_research_reader_v02'].__file__),Path(relation.__file__),
        Path(jrdb_ukc.__file__),base_builder.SCHEMA,ROOT/'horse-racing/brdb/src/build_brdb_research_candidate.py',
        ROOT/'horse-racing/brdb/src/build_brdb_pedigree_generation.py',
        ROOT/'horse-racing/brdb/src/brdb_research_reader.py',ROOT/'horse-racing/brdb/src/brdb_pedigree_reader.py',
        ROOT/'horse-racing/brdb/schema/brdb_research_reader_contract_v0_2.schema.json',
        ROOT/'horse-racing/brdb/src/audit_race_year_pedigree.py',ROOT/'horse-racing/jrdb/src/jrdb_raw.py',
        ROOT/'tools/data-storage/data_storage/convert.py',ROOT/'tools/data-storage/data_storage/validate.py']


def checked_json(root,name,manifest):
    if Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('unsafe input member')
    if manifest['output_sha256'].get(name)!=sha(root/name):raise ValueError('source output SHA mismatch: '+name)
    return json.loads((root/name).read_text())


def checked_archive(data,expected_sha):
    if hashlib.sha256(data).hexdigest()!=expected_sha:raise ValueError('source artifact SHA mismatch')
    z=zipfile.ZipFile(io.BytesIO(data))
    for name,digest in json.loads(z.read('SHA256SUMS.json')).items():
        if Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('unsafe archive member')
        if hashlib.sha256(z.read(name)).hexdigest()!=digest:raise ValueError('artifact member SHA mismatch')
    return z


def validate_sources(args,request):
    base_manifest=json.loads((args.base/'manifest.json').read_text())
    previous_manifest=json.loads((args.previous/'manifest.json').read_text())
    for root,m,key in ((args.base,base_manifest,'base_manifest_sha256'),(args.previous,previous_manifest,'previous_manifest_sha256')):
        if sha(root/'manifest.json')!=request[key] or m['validation_status']!='PASS':raise ValueError('source manifest not pinned/PASS')
        for name,digest in m['output_sha256'].items():
            if sha(root/name)!=digest:raise ValueError('source file SHA mismatch')
    with checked_archive(args.cause_audit.read_bytes(),request['cause_artifact_sha256']) as z:
        cause_manifest=json.loads(z.read('audit/manifest.json'))
        for name,digest in cause_manifest['output_sha256'].items():
            if hashlib.sha256(z.read('audit/'+name)).hexdigest()!=digest:raise ValueError('cause output SHA mismatch')
        additional_rows=json.loads(z.read(request['additional_member']))
        cause_summary=json.loads(z.read('audit/summary.json'))
        if cause_summary['status']!='COMPLETE_FOR_SCOPE':raise ValueError('cause audit incomplete')
        if any(r['primary_reason']!=request['additional_primary_reason'] for r in additional_rows):
            raise ValueError('additional ID has unreviewed cause')
        upstream_data=z.read(request['upstream_artifact_member'])
    with checked_archive(upstream_data,request['upstream_artifact_sha256']) as z:
        upstream_summary=json.loads(z.read('audit/summary.json'))
        source_daily=json.loads(z.read('inputs/paci_source_manifest.json'))
        if z.read('inputs/base_manifest.json')!=(args.base/'manifest.json').read_bytes():raise ValueError('upstream base mismatch')
        if z.read('inputs/research_manifest.json')!=(args.previous/'manifest.json').read_bytes():raise ValueError('upstream previous mismatch')
        previous_2212=json.loads(z.read('inputs/missing_108_audit.json'))
        cohort_entries=[]
        with z.open('audit/entries.csv') as f:
            for r in csv.DictReader(io.TextIOWrapper(f,encoding='utf-8')):
                if r['dataset']=='RESEARCH':cohort_entries.append({k:r[k] for k in ('horse_id','race_date','race_key','horse_no')})
    if len(request['annual'])!=base_manifest['source_archive_count']:raise ValueError('annual input count mismatch')
    if request['annual']!=base_manifest['source_archives']:raise ValueError('annual inventory differs from base')
    normalized=[{k:r[k] for k in ('name','size_bytes','sha256','ukc_members','ukc_record_count')} for r in source_daily]
    if request['daily']!=normalized:raise ValueError('daily inventory differs from audited source')
    for item in request['annual']:verified(args.annual_dir/item['name'],item)
    for item in request['daily']:verified(args.paci_dir/item['name'],item)
    old_rows=checked_json(args.previous,request['previous_added_member'],previous_manifest)
    preserved={r['horse_id'] for r in old_rows};additional={r['horse_id'] for r in additional_rows}
    if len(preserved)!=len(old_rows) or len(additional)!=len(additional_rows) or preserved&additional:
        raise ValueError('input cohort IDs duplicate/overlap')
    for name,ids in (('preserved',preserved),('additional',additional),('combined',preserved|additional)):
        if len(ids)!=request['cohorts'][name]['count'] or ids_sha256(ids)!=request['cohorts'][name]['ids_sha256']:
            raise ValueError('request cohort count/ID SHA mismatch: '+name)
        if any(not re.fullmatch('[0-9]{8}',h) for h in ids):raise ValueError('invalid daily canonical ID')
    if preserved!={r['horse_id'] for r in previous_2212 if r['status']=='FOUND'}:
        raise ValueError('preserved cohort differs from original verified IDs')
    if (len(cohort_entries)!=request['counts']['kyi_entries'] or len({r['horse_id'] for r in cohort_entries})!=request['counts']['kyi_horses']
        or upstream_summary['scope']['zip_count']!=len(request['daily'])):raise ValueError('KYI cohort mismatch')
    previous_reader=ResearchGenerationReader(args.previous)
    if previous_reader.added_ids!=preserved:raise ValueError('previous Reader/addition set mismatch')
    return base_manifest,previous_manifest,preserved,additional,previous_reader,cohort_entries


def scan_all_daily(directory,inventory,base_ids,preserved,additional):
    history=[];valid=defaultdict(list);quarantine=[];sources=[]
    id_spec=next((o,w) for f,o,w in jrdb_ukc.FIELD_SPECS if f=='horse_id')
    for item in sorted(inventory,key=lambda r:r['name']):
        path=directory/item['name'];verified(path,item)
        if not re.fullmatch(r'PACI\d{6}\.zip',path.name):raise ValueError('invalid daily archive name')
        date='20'+path.name[4:10]
        if not valid_date(date):raise ValueError('invalid archive date')
        source={k:item[k] for k in ('name','size_bytes','sha256')};source['members']=[];count=0
        with zipfile.ZipFile(path) as z:
            if z.testzip():raise ValueError('daily ZIP corruption')
            members=canonical_members(z,'UKC')
            if sorted(members)!=sorted(item['ukc_members']):raise ValueError('daily UKC member mismatch')
            for member in members:
                data=z.read(member);member_hash=hashlib.sha256(data).hexdigest();member_count=0
                for line_number,body in enumerate(data.splitlines(),1):
                    count+=1;member_count+=1
                    if len(body)!=jrdb_ukc.RECORD_LENGTH:raise ValueError('daily UKC record length mismatch')
                    hid=jrdb_ukc._text(body,*id_spec);record=None;status='VALID';error=''
                    try:record=jrdb_ukc.parse_ukc_record(body)
                    except (ValueError,UnicodeError) as e:status='PARSER_ERROR';error=str(e)
                    if record:
                        if record.data_date=='99999999':status='SENTINEL_DATE'
                        elif not valid_date(record.data_date):status='INVALID_DATE'
                        elif record.data_date>date:status='PROFILE_AFTER_OBSERVATION'
                    if not re.fullmatch('[0-9]{8}',hid):status='INVALID_ID'
                    raw=asdict(record) if record else {}
                    row={'horse_id':hid,'archive_date':date,'profile_data_date':raw.get('data_date',''),
                        'semantic_hash':record.semantic_hash() if record else '', 'archive':path.name,
                        'archive_size_bytes':item['size_bytes'],'archive_sha256':item['sha256'],
                        'member':member,'member_size_bytes':len(data),'member_sha256':member_hash,'line_number':line_number,
                        'record_sha256':hashlib.sha256(body).hexdigest(),'profile_json':json.dumps(raw,ensure_ascii=False,sort_keys=True),
                        'input_status':status,'error':error,'selected':0,'latest_valid_daily':0,
                        'in_annual_base':int(hid in base_ids),'in_preserved_cohort':int(hid in preserved),
                        'in_additional_cohort':int(hid in additional)}
                    history.append(row)
                    if status=='VALID':valid[hid].append({'record':raw,'semantic_hash':row['semantic_hash'],'archive_date':date,
                        'archive':path.name,'archive_sha256':item['sha256'],'member':member,'line_number':line_number})
                    else:quarantine.append({k:row[k] for k in ('horse_id','archive','member','line_number','input_status','error')})
                source['members'].append({'member':member,'size_bytes':len(data),'sha256':member_hash,'record_count':member_count})
        if count!=item['ukc_record_count']:raise ValueError('daily UKC count mismatch')
        source['record_count']=count;sources.append(source)
    if (preserved|additional)-set(valid):raise ValueError('added cohort has no valid source profile')
    return history,valid,quarantine,sources


def resolve_profiles(profiles,aliases,generation):
    master=relation.HorseMasterIndex(profiles)
    alias_index=relation.AliasIndex(relation.NameAlias(observed_name=a['observed_name'],canonical_name=a['canonical_name'],
        birth_year=a['birth_year'],lineage_code=a['lineage_code'],alias_version=a['alias_version'],evidence_type=a['evidence_type']) for a in aliases)
    result=[]
    for p in profiles:
        for role,value in relation.resolve_first_generation(p,master=master,aliases=alias_index).items():
            result.append({'child_horse_id':p['horse_id'],'role':role,'parent_name':value.requested_name,
                'parent_birth_year':value.requested_birth_year,'parent_lineage_code':value.requested_lineage_code,
                'resolved_parent_horse_id':value.resolved_horse_id,'resolution_status':value.status,
                'resolution_method':value.resolution_method,'candidate_count':value.candidate_count,
                'guard_result':value.guard,'resolver_version':'v0.1','source_generation':generation})
    return result


def relation_differences(old,new,cohort,new_ids):
    keys=('parent_name','parent_birth_year','parent_lineage_code','resolved_parent_horse_id',
          'resolution_status','resolution_method','candidate_count','guard_result')
    before={(r['child_horse_id'],r['role']):r for r in old};result=[]
    for after in new:
        if after['child_horse_id'] not in cohort:continue
        previous=before[after['child_horse_id'],after['role']]
        if all(previous[k]==after[k] for k in keys):continue
        explanation=('RESOLVED_TO_NEW_DAILY_ID' if after['resolved_parent_horse_id'] in new_ids
                     else 'RESOLUTION_OR_CANDIDATE_SET_CHANGED_REVIEW')
        result.append({'horse_id':after['child_horse_id'],'role':after['role'],'explanation':explanation,
            'before':{k:previous[k] for k in keys},'after':{k:after[k] for k in keys}})
    return result


def export_sqlite(con,sqlite_path,stage,rows_by_table):
    from data_storage.convert import convert
    from data_storage.validate import validate
    counts={};hashes={}
    all_keys={**TABLE_KEYS,'daily_observation_history':['archive','member','line_number'],'annual_availability':['horse_id']}
    for name,rows in rows_by_table.items():
        base_builder.table_rows(con,name,rows)
    con.commit()
    for name,keys in all_keys.items():
        target=stage/(name+'.parquet')
        config={'source':{'format':'sqlite','path':str(sqlite_path),'table':name},
            'target':{'path':str(target),'compression':'zstd'},'keys':{'canonical':keys},'sort_by':keys,
            'validation':{'require_row_count_match':True,'require_unique_key':True}}
        conversion=convert(config)
        if not validate(config,conversion)['passed']:raise ValueError('Parquet validation failed: '+name)
        counts[name]=conversion['row_count_source'];hashes[target.name]=sha(target)
    return counts,hashes


def build(args):
    import duckdb,pyarrow
    request=json.loads(args.request.read_text())
    if request.get('request_version')!='0.2' or request.get('selection_contract')!=SELECTION:raise ValueError('unsupported build request')
    bm,pm,preserved,additional,previous_reader,cohort_entries=validate_sources(args,request)
    base=table(args.base/'pedigree_fact.parquet');base_by_id={p['horse_id']:p for p in base}
    old=table(args.previous/'pedigree_fact.parquet');old_by_id={p['horse_id']:p for p in old}
    if len(base_by_id)!=len(base) or len(old_by_id)!=len(old):raise ValueError('source IDs duplicated')
    if (len(base)!=request['counts']['base_profiles'] or len(old)!=request['counts']['previous_profiles']
        or set(old_by_id)-set(base_by_id)!=preserved or set(base_by_id)&additional):raise ValueError('source cohort cardinality mismatch')
    if any(old_by_id.get(h)!=p for h,p in base_by_id.items()):raise ValueError('previous annual facts differ from base')
    aliases=table(args.base/'pedigree_name_alias.parquet');lineage=table(args.base/'lineage_code_master.parquet')
    for name,rows in (('pedigree_name_alias',aliases),('lineage_code_master',lineage)):
        if table(args.previous/(name+'.parquet'))!=rows:raise ValueError('previous reference table differs from base')
    history,valid,quarantine,daily_sources=scan_all_daily(args.paci_dir,request['daily'],set(base_by_id),preserved,additional)
    annual_sources,annual_found,annual_bound=annual_availability(args.annual_dir,
        {'BASE':SimpleNamespace(profiles=base_by_id,manifest=bm,available={})},set(base_by_id))
    if len(annual_found)!=len(base):raise ValueError('annual selected-source provenance incomplete')
    annual_rows=[{'horse_id':key[0],'profile_data_date':key[1],'semantic_hash':key[2],
        'archive_date':source['observation_date'],'archive':source['archive'],'archive_sha256':source['archive_sha256'],
        'member':source['member'],'line_number':source['line']} for key,source in sorted(annual_found.items())]
    deps=recipe_sources()
    identity={'builder_version':VERSION,'selection_contract':SELECTION,'request_sha256':sha(args.request),
        'source_commit':args.source_commit,'source_code_sha256':{p.name:sha(p) for p in deps},
        'base_manifest_sha256':sha(args.base/'manifest.json'),'previous_manifest_sha256':sha(args.previous/'manifest.json'),
        'cause_artifact_sha256':sha(args.cause_audit),'runtime':{'duckdb':duckdb.__version__,'pyarrow':pyarrow.__version__},
        'annual':request['annual'],'daily':request['daily'],'cohorts':request['cohorts']}
    generation=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:16]
    destination=args.output_root/('brdb-pedigree-research-v02-'+generation)
    if destination.exists():raise FileExistsError(destination)
    daily_profiles,selected_history,semantic_changes=select_daily(valid,generation)
    for change in semantic_changes:
        versions={o['semantic_hash']:o['record'] for o in valid[change['horse_id']]}
        change['changed_fields']=[f for f in jrdb_ukc.SEMANTIC_FIELDS
            if len({json.dumps(r.get(f),ensure_ascii=False,sort_keys=True) for r in versions.values()})>1]
    latest_by_id={p['horse_id']:p for p in daily_profiles}
    selected_by_id={r['horse_id']:r for r in selected_history if r['selected']}
    latest_selected_by_id=dict(selected_by_id)
    if ids_sha256({e['horse_id'] for e in cohort_entries})!=ids_sha256(set(valid)):
        raise ValueError('daily source IDs differ from fixed KYI population')
    old_contract=pm.get('research_reader_contract')
    old_history=(table(args.previous/old_contract['observation_history']['path']) if old_contract
                 else json.loads((args.previous/'observation_history.json').read_text()))
    old_selected={r['horse_id']:r for r in old_history if r['selected']}
    if set(old_selected)!=preserved:raise ValueError('old selected-history ID mismatch')
    source_rows={(r['archive'],r['member'],r['line_number']):r for r in history}
    preserved_selection_diff=[]
    for hid in preserved:
        previous=old_selected[hid];chosen=source_rows.get((previous['archive'],previous['member'],previous['line_number']))
        if (not chosen or chosen['input_status']!='VALID' or chosen['horse_id']!=hid
            or chosen['archive_sha256']!=previous['archive_sha256']
            or chosen['semantic_hash']!=old_by_id[hid]['semantic_hash']
            or chosen['profile_data_date']!=old_by_id[hid]['profile_data_date']):raise ValueError('preserved selected profile source mismatch')
        latest=selected_by_id[hid]
        if (latest['archive'],latest['member'],latest['line_number'])!=(previous['archive'],previous['member'],previous['line_number']):
            preserved_selection_diff.append({'horse_id':hid,'preserved_source':previous,'new_daily_latest_source':latest})
        selected_by_id[hid]={**previous,'selected':True}
    profiles=list(base)+[old_by_id[h] for h in sorted(preserved)]+[latest_by_id[h] for h in sorted(additional)]
    profiles.sort(key=lambda p:p['horse_id']);by_id={p['horse_id']:p for p in profiles};added=preserved|additional
    if len(profiles)!=len(by_id) or len(profiles)!=request['counts']['output_profiles']:raise ValueError('output profile count/uniqueness failure')
    if any(by_id[h]!=p for h,p in base_by_id.items()):raise ValueError('annual fact regression')
    if any(by_id[h]!=old_by_id[h] for h in preserved):raise ValueError('previous added fact regression')
    for r in history:
        h=r['horse_id'];chosen=selected_by_id.get(h);latest=latest_selected_by_id.get(h)
        key=r['archive'],r['member'],r['line_number']
        r['latest_valid_daily']=int(bool(latest) and key==(latest['archive'],latest['member'],latest['line_number']))
        if h in added and chosen:
            r['selected']=int(key==(chosen['archive'],chosen['member'],chosen['line_number']))
    # All raw daily rows are retained, but only an added ID can supply a fact.
    if sum(r['selected'] for r in history)!=len(added):raise ValueError('selected observation cardinality mismatch')
    relations=resolve_profiles(profiles,aliases,generation)
    annual_diff=relation_differences(table(args.base/'parent_relation.parquet'),relations,set(base_by_id),added)
    previous_diff=relation_differences(table(args.previous/'parent_relation.parquet'),relations,preserved,additional)
    temporal={r['horse_id']:max(r['archive_date'],r['profile_data_date']) for r in annual_rows}
    for hid in added:temporal[hid]=selected_by_id[hid]['archive_date']
    from brdb_ancestor_graph import ancestor_graph
    relmap=defaultdict(list)
    for r in relations:relmap[r['child_horse_id']].append(r)
    first_seen={}
    for r in history:
        h=r['horse_id']
        if h in added:first_seen[h]=min(first_seen.get(h,r['archive_date']),r['archive_date'])
    added_rows=[];resolution={role:Counter() for role in base_builder.ROLES};depths=Counter()
    for hid in sorted(added):
        p=by_id[hid];selected=selected_by_id[hid]
        graph=ancestor_graph(hid,lambda x:relmap.get(x,[]),max_depth=5)
        depth=max((r['depth'] for r in graph['paths'] if r['horse_id']),default=0);depths[depth]+=1
        row={**p,'cohort':'preserved' if hid in preserved else 'additional',
            'first_observed_archive_date':first_seen[hid],'selected_observation_date':selected['archive_date'],
            'selected_archive':selected['archive'],'selected_member':selected['member'],'selected_line':selected['line_number'],
            'selected_archive_sha256':selected['archive_sha256'],'max_ancestor_depth':depth}
        for r in relmap[hid]:
            role=r['role'];resolution[role][r['resolution_status']]+=1
            row[role+'_canonical_id']=r['resolved_parent_horse_id'];row[role+'_resolution_status']=r['resolution_status']
            row[role+'_guard']=r['guard_result'];row[role+'_candidate_count']=r['candidate_count']
        added_rows.append(row)
    annual_daily_diff=[]
    for hid in sorted(set(latest_by_id)&set(base_by_id)):
        before=base_by_id[hid];after=latest_by_id[hid]
        changed={k:{'annual':before.get(k),'daily':after.get(k)} for k in BASIC if before.get(k)!=after.get(k)}
        if changed or before['semantic_hash']!=after['semantic_hash']:
            annual_daily_diff.append({'horse_id':hid,'fact_changes':changed,'annual_semantic_hash':before['semantic_hash'],
                'daily_semantic_hash':after['semantic_hash'],'action':'ANNUAL_FACT_PRESERVED'})
    audit={'annual_profiles':len(base),'preserved_daily_profiles':len(preserved),'additional_daily_profiles':len(additional),
        'total_daily_additions':len(added),'output_profiles':len(profiles),'daily_observations':len(history),
        'annual_fact_regression':'PASS','previous_fact_regression':'PASS','annual_relation_diff_count':len(annual_diff),
        'previous_relation_diff_count':len(previous_diff),'preserved_selection_diff_count':len(preserved_selection_diff),
        'annual_daily_review_diff_count':len(annual_daily_diff),'daily_quarantine_count':len(quarantine),
        'annual_daily_basic_fact_changed_horses':sum(bool(r['fact_changes']) for r in annual_daily_diff),
        'annual_daily_fact_field_change_counts':dict(Counter(k for r in annual_daily_diff for k in r['fact_changes'])),
        'annual_source_sentinel_count':sum(r['sentinel_date_records'] for r in annual_sources),
        'same_latest_date_conflict_count':0,'daily_input_status_counts':dict(Counter(r['input_status'] for r in history)),
        'semantic_history_change_horses':len(semantic_changes),
        'semantic_history_changed_field_counts':dict(Counter(f for r in semantic_changes for f in r['changed_fields'])),
        'added_parent_resolution':{role:dict(c) for role,c in resolution.items()},
        'added_max_ancestor_depth':{str(k):depths[k] for k in range(6)},'annual_observation_upper_bound':annual_bound,
        'as_of_policy':'selected source observation date, no historical reconstruction; date inclusive; intraday unknown'}
    args.output_root.mkdir(parents=True,exist_ok=True)
    lock=args.output_root/('.'+generation+'.lock')
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.close(fd)
    try:
        if destination.exists():raise FileExistsError(destination)
        with tempfile.TemporaryDirectory(prefix='.building-'+generation+'-',dir=args.output_root) as temp:
            stage=Path(temp);sqlite_path=stage/'stage.sqlite';con=sqlite3.connect(sqlite_path)
            con.executescript(base_builder.SCHEMA.read_text())
            con.execute('''CREATE TABLE daily_observation_history(horse_id TEXT,archive_date TEXT,profile_data_date TEXT,
                semantic_hash TEXT,archive TEXT,archive_size_bytes INTEGER,archive_sha256 TEXT,member TEXT,
                member_size_bytes INTEGER,member_sha256 TEXT,line_number INTEGER,record_sha256 TEXT,profile_json TEXT,
                input_status TEXT,error TEXT,selected INTEGER,latest_valid_daily INTEGER,in_annual_base INTEGER,
                in_preserved_cohort INTEGER,in_additional_cohort INTEGER)''')
            con.execute('''CREATE TABLE annual_availability(horse_id TEXT PRIMARY KEY,profile_data_date TEXT,
                semantic_hash TEXT,archive_date TEXT,archive TEXT,archive_sha256 TEXT,member TEXT,line_number INTEGER)''')
            counts,hashes=export_sqlite(con,sqlite_path,stage,{'pedigree_fact':profiles,'parent_relation':relations,
                'pedigree_name_alias':aliases,'lineage_code_master':lineage,'daily_observation_history':history,
                'annual_availability':annual_rows});con.close();sqlite_path.unlink()
            dump(stage/'added_horses.json',added_rows);csv_write(stage/'added_horses.csv',added_rows)
            dump(stage/'audit.json',audit);dump(stage/'annual_relation_diff.json',annual_diff)
            dump(stage/'previous_relation_diff.json',previous_diff);dump(stage/'preserved_selection_diff.json',preserved_selection_diff)
            dump(stage/'annual_daily_profile_review.json',annual_daily_diff);dump(stage/'semantic_history_changes.json',semantic_changes)
            dump(stage/'quarantine.json',quarantine);dump(stage/'input_inventory.json',{'annual':annual_sources,'daily':daily_sources})
            dump(stage/'build_request.json',request)
            dump(stage/'profile_regression.json',{'annual_count':len(base),'preserved_count':len(preserved),
                'annual_exact_match':True,'preserved_exact_match':True,'previous_generation_id':pm['generation_id'],
                'base_generation_id':bm['generation_id']})
            # Compact provenance CSV plus complete original parsed record JSON in Parquet.
            csv_write(stage/'daily_observation_history.csv',[{k:v for k,v in r.items() if k!='profile_json'} for r in history])
            for name in ('annual_relation_diff','previous_relation_diff'):
                rs=annual_diff if name=='annual_relation_diff' else previous_diff
                flat=[{'horse_id':r['horse_id'],'role':r['role'],'explanation':r['explanation'],
                    'before':json.dumps(r['before'],sort_keys=True),'after':json.dumps(r['after'],sort_keys=True)} for r in rs]
                if flat:csv_write(stage/(name+'.csv'),flat)
                else:(stage/(name+'.csv')).write_text('horse_id,role,explanation,before,after\n')
            for p in sorted(stage.iterdir()):
                if p.is_file():hashes[p.name]=sha(p)
            def ref(name):return {'path':name,'sha256':hashes[name]}
            manifest={'artifact_type':'brdb_pedigree','generation_id':generation,'schema_version':'v0.1',
                'builder_version':VERSION,'research_only':True,'source_family':'UKC+PACI_UKC',
                'source_archive_count':len(request['annual'])+len(request['daily']),
                'source_min_data_date':bm['source_min_data_date'],
                'source_max_data_date':max(p['profile_data_date'] for p in profiles),
                'source_archives':request['annual']+[ {k:r[k] for k in ('name','size_bytes','sha256')} for r in request['daily']],
                'base_generation_id':bm['generation_id'],'previous_generation_id':pm['generation_id'],
                'row_counts':counts,'canonical_keys':{'pedigree_fact':['horse_id'],'parent_relation':['child_horse_id','role']},
                'alias_version':bm['alias_version'],'lineage_source_version':bm['lineage_source_version'],
                'validation_status':'PASS','output_sha256':hashes,'identity':identity,'source_commit':args.source_commit,
                'research_reader_contract':{'version':CONTRACT_VERSION,'id_set_encoding':ID_SET_ENCODING,
                    'added_count':len(added),'added_ids_sha256':ids_sha256(added),'annual_count':len(base),
                    'annual_ids_sha256':ids_sha256(base_by_id),'added_audit':ref('added_horses.json'),
                    'observation_history':ref('daily_observation_history.parquet'),'annual_availability':ref('annual_availability.parquet'),
                    'as_of_policy':'selected_latest_observation_date'}}
            dump(stage/'manifest.json',manifest)
            ResearchGenerationReader(stage)  # refuse publication if the new Reader rejects it
            stage.rename(destination)
    finally:lock.unlink(missing_ok=True)
    result={'output':str(destination),'generation_id':generation,'audit':audit}
    print(json.dumps(result,ensure_ascii=False));return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('request','base','previous','cause_audit','annual_dir','paci_dir','output_root'):
        p.add_argument('--'+name.replace('_','-'),required=True,type=Path)
    p.add_argument('--source-commit',required=True)
    build(p.parse_args())

if __name__=='__main__':main()
