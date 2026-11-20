#!/usr/bin/env python3
"""Export exact tracked JPDB P1.2 sources for licensed private local E2E.

No source data is exported; only repository Python and reviewed manifest.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
from pathlib import Path

PATHS = (
    "horse-racing/jrdb/src/jpdb_history_reader.py",
    "horse-racing/jrdb/src/jpdb_performance_reader_v11.py",
    "horse-racing/jrdb/src/jpdb_performance_reader_v12.py",
    "horse-racing/jrdb/src/jpdb_p12_private_real_e2e_audit.py",
    "horse-racing/jrdb/src/jrdb_raw.py",
    "horse-racing/jrdb/src/jrdb_ukc.py",
    "horse-racing/jrdb/tests/test_jpdb_performance_reader_v12.py",
    "horse-racing/jrdb/src/jpdb_p2_condition_reader.py",
    "horse-racing/jrdb/src/jpdb_p2_real_condition_e2e_audit.py",
    "horse-racing/jrdb/tests/test_jpdb_p2_condition_reader.py",
    "horse-racing/jrdb/src/jpdb_p2_course_master_reader.py",
    "horse-racing/jrdb/src/jpdb_p2_course_master_e2e_audit.py",
    "horse-racing/jrdb/tests/test_jpdb_p2_course_master_reader.py",
    "horse-racing/jrdb/src/jpdb_p3_market_baselines.py",
    "horse-racing/jrdb/tests/test_jpdb_p3_market_baselines.py",
    "horse-racing/jrdb/src/jpdb_p3_market_research_runner.py",
    "horse-racing/jrdb/src/jpdb_p3_condition_robustness.py",
    "horse-racing/jrdb/tests/test_jpdb_p3_condition_robustness.py",
    "horse-racing/jrdb/src/jpdb_p3_prerace_proxy_experiment.py",
    "horse-racing/jrdb/tests/test_jpdb_p3_prerace_proxy.py",
    "horse-racing/jrdb/config/public_drive/jpdb_p0_current_2023_2025_readonly_v0_1.json",
)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", required=True, type=Path)
    args = ap.parse_args()
    repo = Path(__file__).resolve().parents[3]
    dest = args.output_dir.resolve()
    dest.mkdir(parents=True,exist_ok=True)
    files=[]
    for path in PATHS:
        source=repo/path
        if not source.is_file():
            raise FileNotFoundError(path)
        target=dest/path
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
        blob=target.read_bytes()
        files.append({"path":path,"size_bytes":len(blob),
                      "sha256":hashlib.sha256(blob).hexdigest()})
    (dest/"jpdb_p12_exact_source_manifest.json").write_text(
        json.dumps({"schema":"jpdb-p12-source-export-v1","files":files},
                   sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"PASS","exported_files":len(files)}))

if __name__=="__main__":
    main()
