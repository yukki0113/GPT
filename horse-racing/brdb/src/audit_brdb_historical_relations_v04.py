"""Audit every fixed 2026 KYI declaration using date-specific parent candidates."""
import argparse, csv, hashlib, json, time, resource
from collections import Counter, defaultdict
from pathlib import Path
from brdb_research_historical_relations_v04 import HistoricalRelationsReader

GEN='5279af0bd8226cde'; MANIFEST='7efb70ab370cafd18d39eb20ea4fc2bb32490653364a58b44b1382cf9fa5f16c'
COHORT='5bd031a957fc5a311068c00b7c313bca20ccccb272bce5962e7cc223935ebb39'
ROLES=('sire','dam','broodmare_sire')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def run():
 p=argparse.ArgumentParser();p.add_argument('--generation',type=Path,required=True);p.add_argument('--cohort',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
 if sha(args.cohort)!=COHORT: raise ValueError('fixed cohort SHA mismatch')
 args.output.mkdir(parents=True,exist_ok=True)
 with args.cohort.open(encoding='utf8',newline='') as f: entries=list(csv.DictReader(f))
 if len(entries)!=39543 or len({x['horse_id'] for x in entries})!=10680:raise ValueError('fixed cohort counts differ')
 r=HistoricalRelationsReader(args.generation,expected_generation_id=GEN,expected_manifest_sha256=MANIFEST)
 con=r.history.latest._reader._connect(); raw=r.history.latest._reader._rows(con.execute('SELECT child_horse_id,role,resolved_parent_horse_id FROM read_parquet(?)',[str(args.generation/'parent_relation.parquet')]));con.close()
 static={(x['child_horse_id'],x['role']):x['resolved_parent_horse_id'] for x in raw};del raw
 days=defaultdict(list)
 for e in entries:days[e['race_date']].append(e)
 counts=Counter(); dayrows=[]; month=defaultdict(Counter); cohort=defaultdict(Counter); rows=[]; first_horse={}; month_horses=defaultdict(set); t=time.monotonic()
 for date,es in sorted(days.items()):
  perdate=Counter(); perhorse={}
  for e in es:
   hid=e['horse_id']
   if hid not in perhorse:
    profile=r.horse_profile(hid,as_of=date)
    rel=r.parent_relations(hid,as_of=date)
    graph=r.ancestor_graph(hid,as_of=date)
    depth=max((n['depth'] for n in graph['paths'] if n['horse_id']),default=0)
    perhorse[hid]=(profile,rel,graph,depth)
   profile,rel,graph,depth=perhorse[hid]
   if profile['profile'] is None:raise ValueError('v03 profile coverage regression')
   if profile['profile_data_date']>date or profile['observed_date']>date:raise ValueError('future child profile')
   label='daily' if hid in r.history.latest.added_ids else 'annual'
   out={k:e[k] for k in ('race_date','race_key','horse_no','horse_id','horse_name')}
   out.update(cohort=label,profile_status=profile['status'],profile_data_date=profile['profile_data_date'],observed_date=profile['observed_date'],child_source=json.dumps(profile['source'],ensure_ascii=False,sort_keys=True,separators=(',',':')),depth=depth,
              ancestor_paths=json.dumps(graph['paths'],ensure_ascii=False,sort_keys=True,separators=(',',':')))
   counts['entries']+=1; perdate['entries']+=1; month[date[:6]]['entries']+=1;cohort[label]['entries']+=1
   for bucket in (counts,perdate,month[date[:6]],cohort[label]):bucket['depth_'+str(depth)]+=1
   for relrow in rel:
    role=relrow['role']; status=relrow['resolution_status'];parent=relrow['resolved_parent_horse_id']
    if parent:
     parent_profile=r.horse_profile(parent,as_of=date)
     if not parent_profile['profile'] or parent_profile['profile_data_date']>date or parent_profile['observed_date']>date:raise ValueError('future parent profile')
     if status!='RESOLVED_EXACT': raise ValueError('undated alias was used')
    for bucket in (counts,perdate,month[date[:6]],cohort[label]):
     bucket[role+'_'+status]+=1
     bucket[role+'_resolved' if parent else role+'_unknown']+=1
     if parent!=static.get((hid,role)):bucket[role+'_diff_static']+=1
    out.update({role+'_canonical_id':parent or '',role+'_status':status,role+'_guard':relrow['guard_result'],role+'_candidate_count':relrow['candidate_count'],role+'_parent_profile_data_date':relrow.get('parent_profile_data_date') or '',role+'_parent_observed_date':relrow.get('parent_observed_date') or '',role+'_parent_source':json.dumps(relrow['parent_source'],ensure_ascii=False,sort_keys=True,separators=(',',':')) if parent else ''})
   rows.append(out)
   first_horse.setdefault(hid,out)
   month_horses[date[:6]].add(hid)
  perdate['horses']=len(perhorse);perdate['available_candidate_profiles']=len(r._profiles)
  dayrows.append({'date':date,**dict(perdate)})
  print(f'{date} {len(es)} entries; {len(r._profiles)} candidate profiles; elapsed {time.monotonic()-t:.1f}s',flush=True)
 if len(rows)!=39543:raise ValueError('row count mismatch')
 def write_csv(path,data):
  fields=list(data[0]);
  with path.open('w',encoding='utf8',newline='') as f:
   w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
 write_csv(args.output/'entries.csv',rows)
 write_csv(args.output/'horses_first_entry.csv',[first_horse[k] for k in sorted(first_horse)])
 for key,ids in month_horses.items():month[key]['horses']=len(ids)
 first_counts=Counter()
 for out in first_horse.values():
  first_counts['depth_'+str(out['depth'])]+=1
  first_counts[out['cohort']+'_horses']+=1
  for role in ROLES:
   first_counts[role+'_'+out[role+'_status']]+=1
   first_counts[role+'_resolved' if out[role+'_canonical_id'] else role+'_unknown']+=1
 allkeys=sorted(set().union(*(x.keys() for x in dayrows)));write_csv(args.output/'days.csv',[{k:x.get(k,0) for k in allkeys} for x in dayrows])
 summary={'generation_id':GEN,'entries':dict(counts),'first_entry_horses':dict(first_counts),'by_cohort':{k:dict(v) for k,v in sorted(cohort.items())},'by_month':{k:dict(v) for k,v in sorted(month.items())},'days':len(days),'horses':len({e['horse_id'] for e in entries}),'future_child_parent_leaks':0,'alias_used':0,'input_cohort_sha256':COHORT,'manifest_sha256':MANIFEST,'same_day_publication_time':'UNKNOWN','annual_history':'SELECTED_SNAPSHOT_ONLY','max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
 (args.output/'summary.json').write_text(json.dumps(summary,sort_keys=True,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps({'entries':counts['entries'],'days':len(days),'rss_kib':summary['max_rss_kib'],'elapsed_seconds':round(time.monotonic()-t,2)},sort_keys=True),flush=True)
if __name__=='__main__':run()
