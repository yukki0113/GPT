"""P9 final audit: no 2024/25 outcome evaluation; byte/row count checks only."""
import duckdb,numpy as np,hashlib,json,zipfile,subprocess,sys,csv,os,tempfile,shutil
from pathlib import Path
O=Path(__file__).parent;P=Path('/mnt/data');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();dump=lambda p,x:p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
# exact shared dependency_report implementation from Git main is checked against blob hash before import
source='''from __future__ import annotations

import importlib.metadata
import importlib.util
import platform

REQUIRED = ("duckdb", "pyarrow")
PINNED_VERSIONS = {"duckdb": "2.0.1"}


def dependency_report() -> dict:
    packages = {}
    missing = []
    mismatched = []
    for name in REQUIRED:
        available = importlib.util.find_spec(name) is not None
        version = importlib.metadata.version(name) if available else None
        required = PINNED_VERSIONS.get(name)
        packages[name] = {"available": available, "version": version, "required_version": required}
        if available and required is not None and version != required:
            mismatched.append({"package": name, "actual": version, "expected": required})
        if not available:
            missing.append(name)
    return {
        "status": "DEPENDENCY_MISSING" if missing else ("DEPENDENCY_MISMATCH" if mismatched else "success"),
        "python_version": platform.python_version(),
        "packages": packages,
        "missing_packages": missing,
        "version_mismatches": mismatched,
    }

'''
b=source.encode(); blob=hashlib.sha1(f'blob {len(b)}\0'.encode()+b).hexdigest();assert blob=='7b5b8cdebf9d811b828c573ed4b1bb7950f83df3',blob
ns={};exec(compile(source,'shared_dependencies.py','exec'),ns);deps=ns['dependency_report']();assert deps['status']=='success';dump(O/'deps.json',dict(deps,source_blob=blob,numpy=np.__version__))
m=json.loads((P/'manifest.json').read_text());ledger=dict((b,a) for a,b in (l.split('  ',1) for l in (P/'CHECKSUMS.sha256.txt').read_text().splitlines()));c=duckdb.connect();assets=[]
folders={'runner':'pre/runner','race':'pre/race','result':'post/runner_result','status':'control/race_status'}
for y in [2024,2025]:
 for tbl,folder in folders.items():
  rel=f'{folder}/race_year={y}/data.parquet'; a=next(x for x in m['parquet_files'] if x['relative_path']==rel);p=P/'p8_fetch'/f'2024_{list(folders).index(tbl)}.bin' if y==2024 else O/'input2025'/f'{tbl}_2025.bin';assert sha(p)==a['sha256']==ledger[rel] and p.stat().st_size==a['size_bytes'];assert c.execute(f"select count(*) from read_parquet('{p}')").fetchone()[0]==a['row_count'];assets.append(a)
# Full archive internal manifest verification incl already-opened P8 confirmation archives; no prediction metrics opened.
index=json.loads((P/'delivery_manifest.json').read_text());arch=[]
for a in index['details']:
 if 'FREEZE' not in a['name'] and 'CONFIRM' not in a['name']:continue
 p=P/a['name'];assert p.stat().st_size==a['bytes'] and sha(p)==a['sha256'];
 with zipfile.ZipFile(p) as z:
  sums=dict((b,a) for a,b in (l.split('  ',1) for l in z.read('SHA256SUMS').decode().splitlines()));assert set(sums)==set(z.namelist())-{'SHA256SUMS'};assert all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in sums.items());arch.append({'archive':a['name'],'sha256':a['sha256'],'internal_files':len(sums)})
dump(O/'remaining_input_audit.json',{'status':'PASS','additional_byte_row_only':assets,'all_prediction_archives':arch,'2024_25_outcome_evaluation':False})
# Physically separate scoring tree with derived feature files and prediction freeze only, no labels then poisoned labels.
with tempfile.TemporaryDirectory(prefix='p9isolation') as tmp:
 t=Path(tmp);(t/'devval').mkdir();(t/'val').mkdir();shutil.copy2(O/'score.py',t/'score.py');shutil.copy2(O/'shortlist.json',t/'shortlist.json')
 for p in [O/'devval/features_t4.parquet',O/'devval/feature_audit.json',*sorted((O/'devval').glob('thread_parity_*.json'))]:os.link(p,t/'devval'/p.name)
 for p in [O/'val/prediction_manifest.json',*sorted((O/'val').glob('*.parquet'))]:os.link(p,t/'val'/p.name)
 subprocess.run([sys.executable,str(t/'score.py'),'val','1'],check=True,stdout=subprocess.DEVNULL);a=sha(t/'val/prediction_parity.json');(t/'devval/labels.parquet').write_bytes(b'poisoned: deliberately invalid parquet / not read by scoring process');subprocess.run([sys.executable,str(t/'score.py'),'val','1'],check=True,stdout=subprocess.DEVNULL);b=sha(t/'val/prediction_parity.json');assert a==b
 dump(O/'isolation_audit.json',{'status':'PASS','val_score_no_labels_sha256':a,'poisoned_labels_sha256':b,'same_predictions':True,'source':'isolated work tree, only feature+audits+prediction freeze, no canonical/post files passed to scorer','note':'not an OS sandbox; scorer has explicit input path, exact derived allowlist'})
# Validation paired date bootstrap diagnostic, no tuning/selection. All supports identical.
rows=list(csv.DictReader((O/'val/blocks.csv').open())); out={}
for model in sorted({x['model'] for x in rows}):
 rng=np.random.default_rng(20261124);D=[];V=[]
 for y in [2022,2023]:
  rr=[x for x in rows if x['model']==model and x['race_date'].startswith(str(y))];ds={}
  for x in rr:
   v=ds.setdefault(x['race_date'],[0,0]);v[0]+=int(x['den']);v[1]+=int(x['delta'])
  arr=np.array(list(ds.values())); idx=rng.integers(0,len(arr),(2000,len(arr))); sm=arr[idx].sum(axis=1);D.append(sm[:,0]);V.append(sm[:,1])
 delta=(np.sum(V,axis=0)/np.sum(D,axis=0)*100);out[model]=dict(ci95_pp=np.quantile(delta,[.025,.975]).tolist(),reps=2000,seed=20261124)
dump(O/'validation_ci.json',out)
print('audit PASS',len(assets),'additional',len(arch),'archives',out,flush=True)
