#!/usr/bin/env python3
"""Transfer exact committed BRDB research Python source into private Chat runtime.
No historical or proprietary data is included. Temporary branch only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

FILES = [
  "horse-racing/brdb/src/build_brdb_result_mart.py",
  "horse-racing/brdb/src/build_lineage_condition_report.py",
  "horse-racing/brdb/tests/test_build_brdb_result_mart.py",
  "horse-racing/brdb/tests/test_build_lineage_condition_report.py",
]
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args()
    root=Path(__file__).resolve().parents[2]
    out=a.output_dir
    manifest=[]
    for relative in FILES:
        src=root/relative
        dst=out/relative
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,dst)
        content=dst.read_bytes()
        manifest.append({"file":relative,"sha256":hashlib.sha256(content).hexdigest(),"bytes":len(content)})
    (out/"source_bundle_audit.json").write_text(json.dumps({"status":"PASS","files":manifest},indent=2)+"\n")
    print(json.dumps({"status":"PASS","files":len(manifest),"contains_jrdb_data":False}))
if __name__=="__main__":
    main()
