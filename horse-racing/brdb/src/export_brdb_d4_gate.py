#!/usr/bin/env python3
"""Export exact D4 tracked source and run staged research regression suites."""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

FILES=(
 'horse-racing/brdb/src/brdb_d4_supplemental_adapter.py',
 'horse-racing/brdb/src/run_brdb_d4_sidecar.py',
 'horse-racing/brdb/tests/test_brdb_d4_supplemental_adapter.py',
)

def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args();out=args.output_dir
    repo=Path(__file__).resolve().parents[3]
    out.mkdir(parents=True,exist_ok=True)
    hashes={}
    for relative in FILES:
        source=repo/relative;target=out/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
        hashes[relative]=hashlib.sha256(target.read_bytes()).hexdigest()
    suites=[]
    testdir=repo/'horse-racing/brdb/tests'
    for pattern in ('test_brdb_stage3*.py','test_brdb_stage4*.py',
                    'test_brdb_d3*.py','test_brdb_d4*.py'):
        command=[sys.executable,'-m','unittest','discover','-s',str(testdir),
                 '-p',pattern,'-v']
        result=subprocess.run(command,cwd=repo,capture_output=True,text=True,
                              errors='replace',timeout=240)
        print(result.stderr,file=sys.stderr)
        suites.append({'pattern':pattern,'return_code':result.returncode,
                       'stdout':result.stdout,'stderr':result.stderr})
    audit={'schema_version':'brdb-d4-source-test-gate-v0.1',
           'research_only':True,'prediction_safe':False,
           'source_sha256':hashes,'test_suites':suites,
           'status':'PASS' if all(x['return_code']==0 for x in suites) else 'FAIL'}
    (out/'d4_export_test_audit.json').write_text(
        json.dumps(audit,ensure_ascii=False,indent=2,sort_keys=True)+'\n',
        encoding='utf-8')
    if audit['status']!='PASS':
        sys.exit(1)

if __name__=='__main__':main()