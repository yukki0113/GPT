import argparse, csv, json, hashlib, sys
from collections import Counter
from pathlib import Path
from brdb_research_history_reader_v03 import ResearchHistoryReader, validate_observation

parser=argparse.ArgumentParser()
parser.add_argument('--generation',type=Path,required=True)
parser.add_argument('--cohort',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
if hashlib.sha256(args.cohort.read_bytes()).hexdigest() != '5bd031a957fc5a311068c00b7c313bca20ccccb272bce5962e7cc223935ebb39':
 raise ValueError('fixed cohort CSV SHA mismatch')
root=args.generation
args.output.mkdir(parents=True,exist_ok=True)
r=ResearchHistoryReader(root,expected_generation_id='5279af0bd8226cde',expected_manifest_sha256='7efb70ab370cafd18d39eb20ea4fc2bb32490653364a58b44b1382cf9fa5f16c')
con=r.latest._reader._connect()
allrows=r.latest._reader._rows(con.execute('SELECT * FROM read_parquet(?)',[str(root/'daily_observation_history.parquet')]))
codes={row[0] for row in con.execute('SELECT lineage_code FROM read_parquet(?)', [str(root/'lineage_code_master.parquet')]).fetchall()}
con.close()
invalid=0
for row in allrows:
 if row['input_status']=='VALID':
  try: validate_observation(row)
  except ValueError: invalid+=1
if invalid: raise RuntimeError(f'invalid valid observations: {invalid}')
counts=Counter(); seen={x:set() for x in ('static','latest','history')}; fields=['sire_name','dam_name','broodmare_sire_name','sire_line_code','broodmare_sire_line_code']; rows=[]
with args.cohort.open(encoding='utf8',newline='') as f:
 for old in csv.DictReader(f):
  hid=old['horse_id']; date=old['race_date']; result=r.horse_profile(hid,as_of=date); p=result['profile']; counts['entries']+=1; counts['status_'+result['status']]+=1
  out={k:old[k] for k in ('race_date','race_key','horse_no','horse_id','horse_name')}
  out.update(status=result['status'],profile_data_date=result['profile_data_date'] or '',observed_date=result['observed_date'] or '',source_archive=(result['source'] or {}).get('archive',''),source_member=(result['source'] or {}).get('member',''),source_line=(result['source'] or {}).get('line_number',''))
  out['history_semantic_hash']=(result['source'] or {}).get('semantic_hash', (p or {}).get('semantic_hash',''))
  for name in fields: out['history_'+name]=(p or {}).get(name,'')
  for mode,available,profile in [('static',True,r.facts[hid]),('latest',r.latest._available(hid,date),r.facts[hid]),('history',p is not None,p)]:
   if available: seen[mode].add(hid);counts[mode+'_entries']+=1
   out[mode+'_available']=int(available)
   for name in fields:
    present=bool(available and profile.get(name));out[mode+'_'+name+'_present']=int(present);counts[mode+'_'+name+'_present']+=present
   for name in ('sire_line_code','broodmare_sire_line_code'):
    mapped=bool(available and profile.get(name) in codes);out[mode+'_'+name+'_mapped']=int(mapped);counts[mode+'_'+name+'_mapped']+=mapped
   for role in ('sire','dam','broodmare_sire'):
    if mode=='history': resolved=False
    else: resolved=available and old[('static_' if mode=='static' else 'as_of_')+role+'_id_resolved']=='1'
    out[mode+'_'+role+'_id_resolved']=int(resolved);out[mode+'_'+role+'_id_unknown']=int(available and not resolved)
    counts[mode+'_'+role+'_id_resolved']+=resolved;counts[mode+'_'+role+'_id_unknown']+=available and not resolved
  if p and (result['profile_data_date']>date or result['observed_date']>date): counts['future_profile_leaks']+=1
  rows.append(out)
for mode in seen: counts[mode+'_horses']=len(seen[mode])
counts['history_rows_validated']=len(allrows);counts['invalid_valid_history']=invalid
outdir=args.output
with (outdir/'cohort_entries.csv').open('w',encoding='utf8',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
if len(rows)!=39543 or len(seen['static'])!=10680 or counts['static_entries']!=39543 or counts['latest_entries']!=33029:
 raise RuntimeError('fixed cohort regression mismatch')
(outdir/'summary.json').write_text(json.dumps(dict(counts),indent=2,ensure_ascii=False,sort_keys=True)+'\n')
print(json.dumps(dict(counts),sort_keys=True))
