#!/usr/bin/env python3
"""Stable Forecast Reader execution adapter for the common Actions fallback.

This is transport/orchestration only: all forecasting logic remains in
forecast_reader_runner.py. No source data is embedded or made public.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "forecast_reader_runner.py"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=("plan-smoke", "run"), required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--request")
    p.add_argument("--inputs")
    p.add_argument("--date", default="2026-10-25")
    p.add_argument("--venue", default="京都")
    p.add_argument("--race-no", type=int, default=11)
    p.add_argument("--as-of", default="2026-10-25T12:00:00+09:00")
    args = p.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    if args.mode == "plan-smoke":
        request = {
            "schema_version": "forecast-reader-request.v1",
            "protocol": "human_statistics_v1",
            "target": {"date": args.date, "venue": args.venue, "race_no": args.race_no},
            "as_of": args.as_of,
            "history_years": 10,
            "mode": "historical_backtest",
            "detail": {"previous_runs": 1},
        }
        request_path = out / "request.json"
        request_path.write_text(json.dumps(request, ensure_ascii=False, sort_keys=True) + "\n")
        cmd = [sys.executable, str(RUNNER), "--request", str(request_path),
               "--plan", "--output-dir", str(out)]
    else:
        if not args.request or not args.inputs:
            p.error("--run requires --request and --inputs")
        cmd = [sys.executable, str(RUNNER), "--request", args.request,
               "--run", "--inputs", args.inputs, "--output-dir", str(out)]
    run = subprocess.run(cmd, text=True, capture_output=True, check=False)
    (out / "reader_stdout.json").write_text(run.stdout)
    (out / "reader_stderr.log").write_text(run.stderr)
    if run.stdout:
        print(run.stdout, end="")
    if run.stderr:
        print(run.stderr, end="", file=sys.stderr)
    if run.returncode:
        return run.returncode
    parsed = json.loads(run.stdout)
    if args.mode == "plan-smoke" and (parsed.get("status") != "NEED_INPUT" or
                                      not (out / "acquisition_plan.json").is_file()):
        raise ValueError("PLAN_SMOKE_FAILED")
    if args.mode == "run" and parsed.get("status") != "PASS":
        raise ValueError("READER_NOT_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
