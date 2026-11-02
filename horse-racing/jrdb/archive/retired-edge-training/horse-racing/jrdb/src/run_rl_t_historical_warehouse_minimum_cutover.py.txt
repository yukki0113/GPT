#!/usr/bin/env python3
"""Minimum RL-T Historical Warehouse cutover runner.

All Warehouse assets are read-only inputs. The script builds the existing Index
Base schema, runs the existing dual-read auditor, and then invokes the existing
RunPerf/Official/Training Research builders. It does not change model code or
the 2026 PACI route.
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, sqlite3, subprocess, sys
from pathlib import Path

YEARS = tuple(range(2010, 2026))
REPRESENTATIVE = (2010, 2018, 2025)
TABLES = ("race_context","race_result_context","runner_pre","runner_previous_link",
          "runner_result","workout_main","training_analysis","horse_profile_observation")

def run(cmd, env, log):
    proc = subprocess.run(cmd, env=env, text=True, stdout=log, stderr=subprocess.STDOUT)
    return proc.returncode

def db_summary(path):
    con = sqlite3.connect(path)
    try:
        integ = con.execute("PRAGMA integrity_check").fetchone()[0]
        counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}
        dup = con.execute("SELECT COUNT(*) FROM (SELECT race_key,horse_no,COUNT(*) n FROM runner_pre GROUP BY race_key,horse_no HAVING n>1)").fetchone()[0]
        return {"integrity": integ, "counts": counts, "runner_pre_duplicate_keys": dup}
    finally:
        con.close()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--warehouse-manifest", type=Path, required=True)
    p.add_argument("--asset-root", action="append", required=True)
    p.add_argument("--raw-root", type=Path, required=True,
                   help="Raw is audit-only and never the default builder input")
    p.add_argument("--record-hash-compat-manifest", type=Path)
    p.add_argument("--work-root", type=Path, required=True)
    p.add_argument("--source-git-commit", required=True)
    p.add_argument("--result-json", type=Path, required=True)
    a = p.parse_args()
    root = a.work_root
    root.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PYTHONPATH"] = "tools/data-storage:horse-racing/jrdb/src:" + env.get("PYTHONPATH","")
    roots = a.asset_root
    manifest = json.loads(a.warehouse_manifest.read_text(encoding="utf-8"))
    if manifest.get("generation_id") != "jrdb_normalized_warehouse_v1_2010_2025_g20260921" or manifest.get("status") != "PASS":
        raise SystemExit("accepted Warehouse manifest gate failed")
    report = {"status":"PASS","warehouse_generation":manifest["generation_id"],"representative":{}, "full":{}, "downstream":{}}
    log_path = root / "runner.log"
    with log_path.open("w", encoding="utf-8") as log:
        def build(years, out):
            cmd=["python","horse-racing/jrdb/src/build_jrdb_index_base_from_warehouse.py",
                 "--warehouse-manifest",str(a.warehouse_manifest)]
            for r in roots: cmd += ["--asset-root",r]
            if a.record_hash_compat_manifest: cmd += ["--record-hash-compat-manifest",str(a.record_hash_compat_manifest)]
            cmd += ["--years", *map(str,years), "--db",str(out)]
            return run(cmd, env, log)
        for year in REPRESENTATIVE:
            out = root / f"index_{year}.sqlite"
            code = build((year,), out)
            item={"exit_code":code}
            if code==0 and out.exists(): item.update(db_summary(out))
            item["status"]="PASS" if code==0 and item.get("integrity")=="ok" and item.get("runner_pre_duplicate_keys")==0 else "FAIL"
            report["representative"][str(year)] = item
            if item["status"] != "PASS": report["status"]="FAIL"
        full = root / "index_2010_2025.sqlite"
        code = build(YEARS, full)
        report["full"]={"exit_code":code}
        if code==0 and full.exists(): report["full"].update(db_summary(full))
        if report["full"].get("integrity")!="ok" or report["full"].get("runner_pre_duplicate_keys")!=0: report["status"]="FAIL"

        audit = root / "dual_read_2010_2018_2025.json"
        cmd=["python","horse-racing/jrdb/src/audit_jrdb_index_base_raw_vs_warehouse.py",
             "--raw-root",str(a.raw_root),"--warehouse-manifest",str(a.warehouse_manifest)]
        for r in roots: cmd += ["--asset-root",r]
        if a.record_hash_compat_manifest: cmd += ["--record-hash-compat-manifest",str(a.record_hash_compat_manifest)]
        cmd += ["--years","2010","2018","2025","--audit-json",str(audit)]
        code = run(cmd, env, log)
        report["dual_read"]={"exit_code":code}
        if audit.exists():
            report["dual_read"].update(json.loads(audit.read_text(encoding="utf-8")))
        if code != 0 or report["dual_read"].get("status") != "PASS": report["status"]="FAIL"

        if full.exists() and report["status"]=="PASS":
            runperf=root/"runperf.sqlite"; official=root/"official.sqlite"; research=root/"training_research.sqlite"
            commands=[
              ["python","horse-racing/jrdb/src/build_jrdb_runperf_features.py","--index-db",str(full),"--out",str(runperf),"--methods","EXPANDING"],
              ["python","horse-racing/jrdb/src/build_jrdb_official_runperf.py","--runperf-db",str(runperf),"--out",str(official)],
              ["python","horse-racing/jrdb/src/build_jrdb_training_research.py","--index-db",str(full),"--official-runperf-db",str(official),"--out",str(research),"--source-git-commit",a.source_git_commit,"--result-json",str(root/"training_research_result.json")],
            ]
            names=("runperf","official","training_research")
            for name,cmd in zip(names,commands):
                c=run(cmd,env,log); report["downstream"][name]={"exit_code":c,"status":"PASS" if c==0 else "FAIL"}
                if c!=0: report["status"]="FAIL"
    report["source_mode"]="historical_warehouse"
    report["raw_role"]="audit_only"
    report["workflow_cutover_authorized"]=report["status"]=="PASS"
    a.result_json.parent.mkdir(parents=True, exist_ok=True)
    a.result_json.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report["status"]=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
