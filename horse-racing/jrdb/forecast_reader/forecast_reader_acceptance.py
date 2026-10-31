#!/usr/bin/env python3
"""Chat/Actions acceptance entrypoint; reuses canonical Reader and test suite."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import os

ROOT = Path(__file__).resolve().parents[3]
RUNNER = Path(__file__).with_name("forecast_reader_runner.py")
TEST_PATHS = [
    "horse-racing/jrdb/forecast_reader/tests",
    "horse-racing/jrdb/tests/test_jrdb_raw_common.py",
    "horse-racing/jrdb/tests/test_jrdb_raw_history_batch.py",
    "tools/data-storage/tests",
]

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=("smoke", "run"), default="smoke")
    p.add_argument("--request", help="Verified request JSON, required for run")
    p.add_argument("--inputs", help="Verified input sources JSON, required for run")
    p.add_argument("--output-dir", required=True)
    args = p.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = {"schema_version": "forecast-reader-acceptance.v1", "mode": args.mode,
              "checks": [], "status": "FAIL"}
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / 'horse-racing/jrdb/src'), str(ROOT / 'tools/data-storage'), env.get('PYTHONPATH', '')])
    if args.mode == "smoke":
        request = {"schema_version":"forecast-reader-request.v1","protocol":"human_statistics_v1",
                   "target":{"date":"2026-10-25","venue":"京都","race_no":11},
                   "as_of":"2026-10-25T15:30:00+09:00","history_years":10,
                   "mode":"historical_backtest","detail":{"previous_runs":1}}
        request_path = out / "request.json"
        request_path.write_text(json.dumps(request, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        command = [sys.executable, str(RUNNER), "--request", str(request_path),
                   "--plan", "--output-dir", str(out / "plan")]
        cp = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        plan_ok = cp.returncode == 0 and (out / "plan/acquisition_plan.json").is_file()
        report["checks"].append({"name":"canonical_plan","pass":plan_ok,"exit_code":cp.returncode,
                                  "stdout":cp.stdout[-3000:],"stderr":cp.stderr[-3000:]})
        bootstrap = subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "pytest"], cwd=ROOT, env=env, capture_output=True, text=True)
        report["checks"].append({"name":"pytest_bootstrap","pass":bootstrap.returncode == 0,"exit_code":bootstrap.returncode,"tail":(bootstrap.stdout + bootstrap.stderr)[-1000:]})
        tests = subprocess.run([sys.executable, "-m", "pytest", *TEST_PATHS, "-q"],
                               cwd=ROOT, capture_output=True, text=True)
        (out / "pytest.log").write_text(tests.stdout + "\n" + tests.stderr, encoding="utf-8")
        report["checks"].append({"name":"canonical_regressions","pass":tests.returncode == 0,
                                  "exit_code":tests.returncode,"tail":tests.stdout[-1500:]})
    else:
        if not args.request or not args.inputs:
            p.error("--mode run requires --request and --inputs")
        command = [sys.executable, str(RUNNER), "--request", args.request,
                   "--run", "--inputs", args.inputs, "--output-dir", str(out / "evidence")]
        cp = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        (out / "reader_stdout.json").write_text(cp.stdout, encoding="utf-8")
        (out / "reader_stderr.log").write_text(cp.stderr, encoding="utf-8")
        try:
            outcome = json.loads(cp.stdout)
        except json.JSONDecodeError:
            outcome = {}
        ok = cp.returncode == 0 and outcome.get("status") == "PASS"
        report["checks"].append({"name":"real_reader_run","pass":ok,"exit_code":cp.returncode,
                                  "reader_status":outcome.get("status"),"failure_code":outcome.get("failure_code")})
    report["status"] = "PASS" if all(c["pass"] for c in report["checks"]) else "FAIL"
    (out / "acceptance_report.json").write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status":report["status"],"mode":args.mode,"report":str(out / "acceptance_report.json")}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
