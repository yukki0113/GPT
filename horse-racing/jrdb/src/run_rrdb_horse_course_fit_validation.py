"""Rebuild Phase3 and validate an isolated Course Fit generation + restart."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from jrdb_horse_course_fit import REPO, sha256_file, verify_course_master, write_json


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--warehouse-root',type=Path,required=True)
    ap.add_argument('--rrdb-artifact-root',type=Path,required=True)
    ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--as-of-date',default='2026-01-01')
    args=ap.parse_args()
    out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
    # All staged Warehouse bytes must match the repository-reviewed source manifests.
    receipts=[]
    for family in ('bac','sed'):
        manifest=REPO/f'horse-racing/jrdb/config/course_profile/jra_{family}_2010_2025_public_drive_manifest.json'
        for asset in json.loads(manifest.read_text())['artifacts']:
            path=args.warehouse_root/asset['destination']
            if path.stat().st_size!=asset['expected_size'] or sha256_file(path)!=asset['sha256']:
                raise ValueError(f'Warehouse integrity mismatch: {asset["artifact_id"]}')
            receipts.append(dict(artifact_id=asset['artifact_id'],sha256=asset['sha256'],size_bytes=path.stat().st_size))
    write_json(out/'reports/warehouse_input_validation.json',{'status':'PASS','assets':receipts})
    src=REPO/'horse-racing/jrdb/src'
    def execute(module,argv):
        subprocess.run([sys.executable,str(src/module),*map(str,argv)],check=True,cwd=REPO)
    execute('audit_jra_course_profile_phase1.py',['--input-root',args.warehouse_root,'--output',out/'course_master/phase1_audit.json'])
    official=REPO/'horse-racing/jrdb/config/course_profile/official_current_course_geometry_v0_1.json'
    execute('build_jra_course_profile_phase3.py',['--phase1-audit',out/'course_master/phase1_audit.json',
                '--official-config',official,'--output-dir',out/'course_master'])
    write_json(out/'reports/course_master_validation.json',verify_course_master(out/'course_master',official))
    roots=[]
    for p in args.rrdb_artifact_root.rglob('current.json'):
        if json.loads(p.read_text()).get('artifact_type')=='jrdb_postrace_review':roots.append(p.parent)
    if len(roots)!=1:raise ValueError(f'unique canonical RRDB root required; found {len(roots)}')
    argv=['--warehouse-root',args.warehouse_root,'--rrdb-root',roots[0],
          '--course-master-dir',out/'course_master','--output-dir',out/'fit','--as-of-date',args.as_of_date]
    execute('jrdb_horse_course_fit.py',argv)
    first=json.loads((out/'fit/manifest.json').read_text())
    before={name:sha256_file(Path(meta['path'])) for name,meta in first['artifacts'].items()}
    execute('jrdb_horse_course_fit.py',argv)
    second=json.loads((out/'fit/manifest.json').read_text())
    after={name:sha256_file(Path(meta['path'])) for name,meta in second['artifacts'].items()}
    if before!=after or set(second['reused_stages'])!=set(before):
        raise ValueError('restartability failed')
    write_json(out/'reports/restartability.json',{'status':'PASS','identical_artifact_count':len(before),
                                                'reused_stages':second['reused_stages']})
    audit=json.loads((out/'fit/audit.json').read_text())
    write_json(out/'reports/result.json',{'status':audit['status'],'as_of_date':args.as_of_date,
        'counts':audit['counts'],'audit_checks':audit['checks'],'artifacts':second['artifacts'],
        'source_git_sha':second['source_git_sha'],'rrdb_v03_modified':False})


if __name__=='__main__':main()
