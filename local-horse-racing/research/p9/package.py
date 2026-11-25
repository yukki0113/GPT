"""Private detailed Freeze packages and compact portable evidence, no canonical raw/labels."""
import json,hashlib,zipfile
from pathlib import Path
O=Path(__file__).parent;D=O.parent/'NAR_P9_DELIVERY_20261125';D.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();dump=lambda p,x:p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');details=[]
def archive(name,files):
 p=D/name;files=sorted(set(files));entries={str(f.relative_to(O)):sha(f) for f in files}
 with zipfile.ZipFile(p,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as z:
  for f in files:z.write(f,str(f.relative_to(O)))
  z.writestr('SHA256SUMS',''.join(f'{h}  {n}\n' for n,h in entries.items()))
 with zipfile.ZipFile(p) as z:assert all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in entries.items())
 details.append({'name':name,'bytes':p.stat().st_size,'sha256':sha(p),'files':len(entries)})
archive('NAR_P9_FEATURES.zip',[O/'devval/features_t4.parquet'])
archive('NAR_P9_LINEAGE.zip',[O/'devval/targets.parquet',O/'devval/history.parquet'])
for f in ['astar','j','tk','p','s','d']:
 names=[p for p in (O/'dev').glob('*.parquet') if (p.stem=='astar' if f=='astar' else p.stem.startswith(f) and p.stem!='astar')]
 archive(f'NAR_P9_DEV_{f}.zip',names)
archive('NAR_P9_VAL.zip',list((O/'val').glob('*.parquet')))
files=[p for p in O.iterdir() if p.is_file() and p.suffix in ['.py','.json','.md','.csv','.log']]
for sub in ['devval','dev','val']:files.extend(p for p in (O/sub).iterdir() if p.is_file() and p.suffix in ['.json','.csv'])
archive('NAR_P9_EVIDENCE_20261125.zip',files)
for n in ['NAR_P9_REPORT_20261125.md','P10_HANDOFF.md','candidate_config.json','shortlist.json','decision_ledger.csv']:(D/n).write_bytes((O/n).read_bytes())
dump(D/'delivery_manifest.json',{'status':'LOCAL_VERIFIED','details':details,'base':'P8-Astar-r1','new_candidate':None,'confirmation':'NOT_APPLICABLE_NO_QUALIFIED_CANDIDATE','note':'Exact derived features, all candidate predictions; t1 parity verified and t4 Freeze retained, no canonical inputs/evaluator labels distributed.'});(D/'SHA256SUMS').write_text(''.join(f'{sha(p)}  {p.name}\n' for p in sorted(D.iterdir()) if p.is_file() and p.name!='SHA256SUMS'))
print(details);print('total',sum(p.stat().st_size for p in D.iterdir()))
