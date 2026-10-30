"""Independent reaggregation and previous-reader regression for v0.4 audit CSV."""
import argparse, csv, hashlib, io, json, zipfile
from collections import Counter
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run():
 p=argparse.ArgumentParser();p.add_argument('--audit',type=Path,required=True);p.add_argument('--v03-zip',type=Path,required=True);args=p.parse_args()
 if sha(args.v03_zip)!='6eee5cc3ad8f6afe2b2ee4a2138a7efdfd7c61b244b5ed7a59668d73854dffdf':raise ValueError('v0.3 artifact SHA mismatch')
 key=lambda x:(x['race_date'],x['race_key'],x['horse_no'],x['horse_id'])
 with zipfile.ZipFile(args.v03_zip) as z:
  with z.open('cohort_entries.csv') as f:old={key(x):x for x in csv.DictReader(io.TextIOWrapper(f,encoding='utf8'))}
 with (args.audit/'entries.csv').open(encoding='utf8',newline='') as f:rows=list(csv.DictReader(f))
 if len(rows)!=39543 or len(old)!=len(rows) or len({key(x) for x in rows})!=len(rows):raise ValueError('cohort cardinality mismatch')
 total=Counter()
 for row in rows:
  prev=old[key(row)]; date=row['race_date']
  if prev['status']!=row['profile_status'] or prev['profile_data_date']!=row['profile_data_date'] or prev['observed_date']!=row['observed_date'] or prev['history_available']!='1':raise ValueError('v0.3 profile regression')
  if row['profile_data_date']>date or row['observed_date']>date:raise ValueError('future child')
  paths=json.loads(row['ancestor_paths']);depth=max((p['depth'] for p in paths if p['horse_id']),default=0)
  if depth!=int(row['depth']) or any(p['depth']>5 or (p['horse_id'] and p['status']!='RESOLVED') for p in paths):raise ValueError('invalid ancestor graph')
  total['depth_'+str(depth)]+=1
  for role in ('sire','dam','broodmare_sire'):
   hid=row[role+'_canonical_id'];status=row[role+'_status']
   if hid:
    if status!='RESOLVED_EXACT' or not row[role+'_parent_observed_date'] or row[role+'_parent_observed_date']>date or row[role+'_parent_profile_data_date']>date:raise ValueError('future/unverified parent')
   elif status.startswith('RESOLVED'):raise ValueError('resolved status has no ID')
   total[role+'_resolved' if hid else role+'_unknown']+=1
  total['entries']+=1
 summary=json.loads((args.audit/'summary.json').read_text())['entries']
 for k,v in total.items():
  if summary.get(k,0)!=v:raise ValueError('summary mismatch: '+k)
 with (args.audit/'horses_first_entry.csv').open(encoding='utf8',newline='') as f:first=list(csv.DictReader(f))
 if len(first)!=10680 or len({r['horse_id'] for r in first})!=10680:raise ValueError('first-entry horse cardinality mismatch')
 grouped={}
 for row in first:
  c=grouped.setdefault(row['cohort'],Counter());c['horses']+=1;c['depth_'+row['depth']]+=1
  for role in ('sire','dam','broodmare_sire'):
   c[role+'_'+row[role+'_status']]+=1;c[role+'_resolved' if row[role+'_canonical_id'] else role+'_unknown']+=1
 result={'status':'PASS','entries':len(rows),'v03_profile_date_regression':0,'future_child_parent':0,'ancestor_depth_reaggregated':True,'role_counts_reaggregated':True,'first_entry_horses_by_cohort':{k:dict(v) for k,v in sorted(grouped.items())}}
 (args.audit/'independent_verification.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
 print(json.dumps(result,sort_keys=True))
if __name__=='__main__':run()
