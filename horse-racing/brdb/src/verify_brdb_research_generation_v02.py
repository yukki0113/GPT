#!/usr/bin/env python3
"""Full-data regression, Reader and fixed KYI audit for a v0.2 generation."""
from __future__ import annotations
import argparse
import hashlib
import json
import zipfile
from collections import Counter,defaultdict
from dataclasses import asdict
from datetime import datetime,timedelta
from pathlib import Path

from audit_race_year_pedigree import (AuditSnapshot,aggregate,csv_write,dump,parse_entries,sha,table,rate)
from build_brdb_research_generation_v02 import validate_sources,relation_differences,recipe_sources
from brdb_research_reader_v02 import ResearchGenerationReader,ids_sha256
from brdb_research_reader import ResearchPedigreeReader
from brdb_ancestor_graph import ancestor_graph
import jrdb_ukc


def run(args):
    if args.output.exists():raise FileExistsError(args.output)
    args.output.mkdir(parents=True)
    request=json.loads(args.request.read_text())
    bm,pm,preserved,additional,legacy_wrapper,expected_entries=validate_sources(args,request)
    added=preserved|additional
    root=args.generation;manifest=json.loads((root/'manifest.json').read_text())
    for name,digest in manifest['output_sha256'].items():
        if sha(root/name)!=digest:raise ValueError('generation output SHA mismatch: '+name)
    identity=manifest['identity']
    if identity['source_code_sha256']!={p.name:sha(p) for p in recipe_sources()}:
        raise ValueError('executing recipe sources differ from generation identity')
    digest=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()[:16]
    if digest(identity)!=manifest['generation_id'] or identity['request_sha256']!=sha(args.request):raise ValueError('generation identity mismatch')
    altered=json.loads(json.dumps(identity));altered['request_sha256']='0'*64
    if digest(altered)==manifest['generation_id']:raise ValueError('input identity not sensitive')
    altered=json.loads(json.dumps(identity));altered['source_code_sha256']['build_brdb_research_generation_v02.py']='0'*64
    if digest(altered)==manifest['generation_id']:raise ValueError('code identity not sensitive')
    if args.repeat:
        if {p.name for p in root.iterdir()}!={p.name for p in args.repeat.iterdir()}:raise ValueError('rebuild file set differs')
        matches={p.name:sha(p)==sha(args.repeat/p.name) for p in root.iterdir()}
        if not all(matches.values()):raise ValueError('rebuild byte comparison failure')
        dump(args.output/'rebuild_verification.json',{'status':'PASS','all_files_byte_equal':True,'files':matches})
    reader=ResearchGenerationReader(root)
    snapshot=AuditSnapshot(root);snapshot.available=reader.available_from
    base={p['horse_id']:p for p in table(args.base/'pedigree_fact.parquet')}
    previous={p['horse_id']:p for p in table(args.previous/'pedigree_fact.parquet')}
    if len(snapshot.profiles)!=request['counts']['output_profiles'] or set(snapshot.profiles)!=set(base)|added:
        raise ValueError('full output cardinality/ID union failure')
    if any(snapshot.profiles[h]!=p for h,p in base.items()):raise ValueError('annual profile regression')
    if any(snapshot.profiles[h]!=previous[h] for h in preserved):raise ValueError('previous cohort regression')
    all_relations=[r for rs in snapshot.relations.values() for r in rs]
    annual_diff=relation_differences(table(args.base/'parent_relation.parquet'),all_relations,set(base),added)
    previous_diff=relation_differences(table(args.previous/'parent_relation.parquet'),all_relations,preserved,additional)
    if annual_diff!=json.loads((root/'annual_relation_diff.json').read_text()) or previous_diff!=json.loads((root/'previous_relation_diff.json').read_text()):
        raise ValueError('reported relation differences inconsistent')
    raw_count=0;source_inventory={r['name']:r for r in request['daily']};cache={};archives={}
    history=table(root/'daily_observation_history.parquet');selected={};raw_status=Counter()
    for o in history:
        arc=o['archive'];member=o['member'];key=arc,member
        if arc not in archives:
            path=args.paci_dir/arc;source=source_inventory[arc]
            if sha(path)!=source['sha256'] or path.stat().st_size!=o['archive_size_bytes']:raise ValueError('raw archive binding mismatch')
            archives[arc]=zipfile.ZipFile(path)
        if key not in cache:
            data=archives[arc].read(member)
            if hashlib.sha256(data).hexdigest()!=o['member_sha256'] or len(data)!=o['member_size_bytes']:raise ValueError('raw member binding mismatch')
            cache[key]=data.splitlines()
        raw=cache[key][o['line_number']-1]
        if hashlib.sha256(raw).hexdigest()!=o['record_sha256']:raise ValueError('raw record binding mismatch')
        raw_count+=1;raw_status[o['input_status']]+=1
        if o['input_status']=='VALID':
            parsed=jrdb_ukc.parse_ukc_record(raw)
            if asdict(parsed)!=json.loads(o['profile_json']) or parsed.semantic_hash()!=o['semantic_hash']:raise ValueError('parsed history mismatch')
        if o['selected']:
            if o['horse_id'] in selected or o['input_status']!='VALID':raise ValueError('duplicate/invalid selected observation')
            selected[o['horse_id']]=o
            fact=snapshot.profiles[o['horse_id']];record=json.loads(o['profile_json'])
            fields=('horse_id','horse_name','sex_code','birth_date','sire_name','sire_birth_year','dam_name','dam_birth_year',
                    'broodmare_sire_name','broodmare_sire_birth_year','sire_line_code','broodmare_sire_line_code','breeding_place')
            if any(fact[f]!=record[f] for f in fields) or fact['semantic_hash']!=o['semantic_hash'] or fact['profile_data_date']!=o['profile_data_date']:
                raise ValueError('selected raw profile/fact mismatch')
    for z in archives.values():z.close()
    if raw_count!=sum(x['ukc_record_count'] for x in request['daily']) or set(selected)!=added:
        raise ValueError('observation/source cohort count mismatch')
    end=max(o['archive_date'] for o in history)
    batch=reader.profiles_for_horses(sorted(added),as_of=end)
    if set(batch)!=added or reader.profiles_for_horses(sorted(added),as_of='20251231'):
        raise ValueError('added static join or pre-2026 leakage')
    checks=[]
    for i,h in enumerate(sorted(added),1):
        date=selected[h]['archive_date'];before=(datetime.strptime(date,'%Y%m%d')-timedelta(days=1)).strftime('%Y%m%d')
        point=reader.horse_profile(h,as_of=date)
        if point!=batch[h] or reader.horse_profile(h,as_of=before) is not None:raise ValueError('single/batch or selected-date guard failure')
        if any(not point[f] for f in ('sire_name','dam_name','broodmare_sire_name')) or any(point[f] not in snapshot.mapped for f in ('sire_line_code','broodmare_sire_line_code')):
            raise ValueError('added basic pedigree/official mapping incomplete')
        checks.append({'horse_id':h,'cohort':'preserved' if h in preserved else 'additional','selected_date':date,
                       'point_equals_batch':True,'day_before_selected_hidden':True})
        if i%500==0:print(f'single/batch verified {i}/{len(added)}',flush=True)
    csv_write(args.output/'single_batch_checks.csv',checks)
    old=ResearchPedigreeReader(args.previous)
    legacy_batch=legacy_wrapper.profiles_for_horses(sorted(preserved),as_of=end)
    if legacy_batch!=old.profiles_for_horses(sorted(preserved),as_of=end):raise ValueError('legacy batch compatibility failure')
    for h in sorted(preserved):
        if old.horse_pedigree(h,as_of=end)!=legacy_wrapper.horse_pedigree(h,as_of=end):raise ValueError('legacy single compatibility failure')
        if batch[h]!=previous[h]:raise ValueError('new generation preserved profile differs from old Reader')
    # Exercise real projected lineage/relations including alias and conflict cases.
    projection_ids=set(sorted(added)[:5])|set(sorted(preserved)[:5])
    for status in ('RESOLVED_ALIAS','CONFLICT','NO_CANDIDATE'):
        matches=sorted({r['child_horse_id'] for r in all_relations if r['child_horse_id'] in added and r['resolution_status']==status})
        projection_ids.update(matches[:5])
    for h in sorted(projection_ids):
        value=reader.horse_pedigree(h,as_of=end)
        if not value or value['horse_id']!=h or not value['sire']['lineage'] or not value['broodmare_sire']['lineage']:
            raise ValueError('real pedigree projection failure')
    entries,inventory=parse_entries(args.paci_dir,request['daily'])
    key=lambda e:(e['race_date'],e['race_key'],int(e['horse_no']),e['horse_id'])
    if sorted(map(key,entries))!=sorted(map(key,expected_entries)):raise ValueError('fixed KYI cohort differs')
    groups=defaultdict(list);days=defaultdict(set)
    for e in entries:groups[e['horse_id']].append(e);days[e['race_date']].add(e['horse_id'])
    ids=set(groups);static=reader.profiles_for_horses(sorted(ids),as_of=end)
    if set(static)!=ids:raise ValueError('new generation fails actual fixed-cohort static 100% join')
    day_rows=[];reader_safe=set()
    for date,hids in sorted(days.items()):
        actual=reader.profiles_for_horses(sorted(hids),as_of=date)
        expected={h for h in hids if snapshot.safe(h,date)}
        if set(actual)!=expected:raise ValueError('Reader/as-of audit mismatch')
        for h in actual:
            if reader.available_from[h]>date or actual[h]['profile_data_date']>date:raise ValueError('future profile exposed')
            reader_safe.add((date,h))
        day_rows.append({'date':date,'horses':len(hids),'as_of_available':len(actual),'future_profile_leaks':0})
    first=[(h,es[0]['race_date']) for h,es in sorted(groups.items())];all_entries=[(e['horse_id'],e['race_date']) for e in entries]
    stats={'static_horses':aggregate(snapshot,first),'static_entries':aggregate(snapshot,all_entries),
           'as_of_first_entry_horses':aggregate(snapshot,first,True),'as_of_entries':aggregate(snapshot,all_entries,True)}
    actual_safe=sum((e['race_date'],e['horse_id']) in reader_safe for e in entries)
    if actual_safe!=stats['as_of_entries']['metrics']['id_joined']['count']:raise ValueError('Reader safe total mismatch')
    cause_summary=None
    with zipfile.ZipFile(args.cause_audit) as z:cause_summary=json.loads(z.read('audit/summary.json'))
    predicted=cause_summary['recovery_potential']['conditional_latest_snapshot_safe_total_entries']['count']
    contributions={}
    for label,hids in (('annual',set(base)),('preserved',preserved),('additional',additional)):
        es=[e for e in entries if e['horse_id'] in hids]
        contributions[label]={'cohort_horses':len(ids&hids),'entries':len(es),
            'as_of_entries':sum((e['race_date'],e['horse_id']) in reader_safe for e in es)}
    horse_rows=[]
    for h,es in sorted(groups.items()):
        p=static[h];rmap={r['role']:r for r in snapshot.relations[h]}
        row={'horse_id':h,'kyi_name':es[0]['horse_name'],'first_entry_date':es[0]['race_date'],
            'last_entry_date':es[-1]['race_date'],'entry_count':len(es),
            'as_of_available_entries':sum((e['race_date'],h) in reader_safe for e in es),
            'profile_observed_date':reader.available_from[h],**p,**snapshot.flags(h),**snapshot.depths(h)}
        for role,r in rmap.items():row[role+'_canonical_id']=r['resolved_parent_horse_id'];row[role+'_status']=r['resolution_status']
        horse_rows.append(row)
    csv_write(args.output/'cohort_horses.csv',horse_rows)
    csv_write(args.output/'cohort_entries.csv',[{**e,'profile_observed_date':reader.available_from[e['horse_id']],
        'as_of_available':(e['race_date'],e['horse_id']) in reader_safe,
        **{'static_'+k:v for k,v in snapshot.flags(e['horse_id']).items()},
        **{'as_of_'+k:v for k,v in snapshot.flags(e['horse_id'],e['race_date']).items()},
        **{'as_of_'+k:v for k,v in snapshot.depths(e['horse_id'],e['race_date']).items()}} for e in entries])
    csv_write(args.output/'reader_day_checks.csv',day_rows);dump(args.output/'kyi_inventory.json',inventory)
    summary={'status':'PASS','generation_id':reader.generation_id,'source_commit':manifest['source_commit'],
        'scope':{'zip_count':len(inventory),'min_date':min(days),'max_date':max(days),'horses':len(ids),'entries':len(entries),
                 'population':'KYI declarations; actual start/cancellation and intraday publication times unverified'},
        'master_profiles':len(snapshot.profiles),'annual_profiles':len(base),'preserved_daily_profiles':len(preserved),
        'additional_daily_profiles':len(additional),'added_profiles':len(added),'daily_observations':raw_count,
        'annual_fact_regression':'PASS','previous_fact_regression':'PASS','annual_relation_diff_count':len(annual_diff),
        'previous_relation_diff_count':len(previous_diff),'single_batch_added_profiles_checked':len(checks),
        'legacy_single_batch_profiles_checked':len(preserved),'real_pedigree_projection_samples':len(projection_ids),
        'pre_2026_daily_profiles_exposed':0,'future_profile_leaks':0,'actual_as_of_entries':actual_safe,
        'predicted_as_of_entries':predicted,'prediction_difference':actual_safe-predicted,'contributions':contributions,
        'metrics':stats,'rebuild_all_output_bytes_equal':bool(args.repeat),'source_guard_status_counts':dict(raw_status),
        'new_generation_is_research_only':True,'production_writes':0}
    dump(args.output/'summary.json',summary)
    dump(args.output/'verification.json',{'status':'PASS','generation_id':reader.generation_id,
        'all_manifest_output_sha_verified':len(manifest['output_sha256']),'generation_identity_recomputed':True,
        'input_and_code_identity_changes_detected':True,'raw_observations_verified':raw_count,'single_batch_verified':len(checks),
        'legacy_profiles_verified':len(preserved),'rebuild_all_output_bytes_equal':bool(args.repeat),
        'annual_profiles_exact':len(base),'previous_profiles_exact':len(preserved),'future_profile_leaks':0,
        'as_of_prediction_difference':actual_safe-predicted,'generation_manifest_sha256':sha(root/'manifest.json')})
    dump(args.output/'audit_manifest.json',{'generation_manifest_sha256':sha(root/'manifest.json'),
        'source_commit':manifest['source_commit'],'request_sha256':sha(args.request),
        'verifier_source_sha256':sha(Path(__file__)),
        'output_sha256':{p.name:sha(p) for p in sorted(args.output.iterdir()) if p.is_file()}})
    print(json.dumps({'generation_id':reader.generation_id,'static_horses':len(static),'static_entries':len(entries),
                     'as_of_entries':actual_safe,'prediction_difference':actual_safe-predicted}),flush=True)
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('generation','request','base','previous','cause_audit','annual_dir','paci_dir','output'):
        p.add_argument('--'+name.replace('_','-'),type=Path,required=True)
    p.add_argument('--repeat',type=Path)
    run(p.parse_args())

if __name__=='__main__':main()
