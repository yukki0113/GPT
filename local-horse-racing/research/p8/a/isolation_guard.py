"""Run scorers in temporary stage directory without canonical/history/labels, then with poisoned label file. Score bytes unchanged."""
from pathlib import Path
import shutil,tempfile,subprocess,hashlib,json,sys,os
O=Path(__file__).parent; sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest(); mode=sys.argv[1]
script='a34_score.py' if mode.startswith('a34') else 'score.py'
with tempfile.TemporaryDirectory(prefix='p8a_score_only_') as temp:
 d=Path(temp);shutil.copyfile(O/script,d/script)
 for p in O.glob('*'):
  if p.name.startswith('features_') and p.name.endswith('_t4.parquet') or p.name.startswith('a34_features_') and p.name.endswith('_t4.parquet') or p.name in ('run_config.json','feature_manifest.json','a1_selection.json','shortlist.json','a34_config.json','a34_feature_manifest.json','a34_shortlist.json'):
   (d/p.name).symlink_to(p)
 def run():
  subprocess.run([sys.executable,str(d/script),mode,'4'],cwd=d,check=True,stdout=subprocess.DEVNULL);return {p.name:sha(p) for p in sorted(d.glob('pred_*.parquet'))}
 a=run();assert a and all(sha(O/k)==v for k,v in a.items());(d/'labels.parquet').write_bytes(b'POISONED RESULT: change all finish positions; not a valid Parquet file');b=run();assert a==b
 (O/f'isolation_{mode}.json').write_text(json.dumps({'status':'PASS','scope':'score subprocess with no canonical/history/label files, then poisoned inaccessible-format label file; explicit file allowlist, no OS sandbox claim','freeze_sha256':a},indent=2)+'\n')
