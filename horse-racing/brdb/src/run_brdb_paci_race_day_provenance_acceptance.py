#!/usr/bin/env python3
from __future__ import annotations
import argparse, io, json, pathlib, sys, unittest
ROOT=pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'horse-racing/brdb/src'))
from audit_brdb_paci_race_day_provenance import audit

def main():
 p=argparse.ArgumentParser(); p.add_argument('--paci-root',type=pathlib.Path,required=True); p.add_argument('--output-dir',type=pathlib.Path,required=True); a=p.parse_args()
 s=io.StringIO(); suite=unittest.defaultTestLoader.discover(str(ROOT/'horse-racing/brdb/tests'),pattern='test_audit_brdb_paci_race_day_provenance.py')
 result=unittest.TextTestRunner(stream=s,verbosity=2).run(suite)
 if result.testsRun!=6 or not result.wasSuccessful(): raise SystemExit('provenance tests failed: '+s.getvalue())
 meta=json.loads((ROOT/'horse-racing/brdb/config/paci_20261115_drive_metadata_snapshot.json').read_text(encoding='utf-8'))
 out=audit(paci=a.paci_root/'PACI261115.zip',race_key='05265412',drive_metadata=meta,expected_sha256='3c80e70a74a13874a82b7f7cf4c5f9415d6abbf186ec0ccfa1d2842e51a7b050',expected_parent_id='1zFajenPU5jxInZCcmqZzkgiaYil3MD8r')
 if out['paci_acquisition_status']!='PRE_OFF_DRIVE_BYTES_ATTESTED': raise SystemExit('real PACI pre-off attestation did not pass')
 a.output_dir.mkdir(parents=True,exist_ok=True)
 (a.output_dir/'paci_race_day_provenance_20261115_05265412.json').write_text(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
 (a.output_dir/'paci_race_day_provenance_tests.log').write_text(s.getvalue(),encoding='utf-8')
 print(json.dumps({'status':'PASS','tests':6,'paci_acquisition_status':out['paci_acquisition_status'],'provider_release_status':out['provider_release_status'],'scheduled_post_time_jst':out['scheduled_post_time_jst'],'drive_modified_time_jst':out['drive_modified_time_jst']},sort_keys=True))
if __name__=='__main__': main()
