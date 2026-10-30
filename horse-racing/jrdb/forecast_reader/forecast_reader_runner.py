#!/usr/bin/env python3
"""Forecast reader entrypoint. Incomplete data adapters fail closed."""
from __future__ import annotations

import argparse
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from previous_run_reader import read_previous
from jrdb_raw import Parser, ReaderAudit, iter_archive_records

VENUES = {"札幌": "01", "函館": "02", "福島": "03", "新潟": "04", "東京": "05",
          "中山": "06", "中京": "07", "京都": "08", "阪神": "09", "小倉": "10"}


def validate(request):
    if request.get("schema_version") != "forecast-reader-request.v1" or request.get("protocol") != "human_statistics_v1":
        raise ValueError("INVALID_REQUEST")
    if request.get("history_years") != 10 or request.get("mode") not in ("pre_race", "historical_backtest"):
        raise ValueError("INVALID_REQUEST")
    if request.get("detail", {}).get("previous_runs") != 1:
        raise ValueError("INVALID_REQUEST")
    target = request["target"]
    day = date.fromisoformat(target["date"])
    timestamp = datetime.fromisoformat(request["as_of"])
    if timestamp.utcoffset() is None or target.get("venue") not in VENUES or type(target.get("race_no")) is not int or not 1 <= target["race_no"] <= 12:
        raise ValueError("INVALID_REQUEST")
    if timestamp.astimezone(ZoneInfo("Asia/Tokyo")).date() > day:
        raise ValueError("FUTURE_LEAK")
    return day, timestamp


def plan(request):
    day, _ = validate(request)
    return {"status": "NEED_INPUT", "target": request["target"], "sources": [
        {"key": "jrdb.paci.daily", "expected_name": f"PACI{day:%y%m%d}.zip", "required": True},
        {"key": "jrdb.analysis.current", "expected_name": "jrdb_analysis_v1_4_canonical_current.tar.xz", "required": True},
        {"key": "jrdb.historical_conditions", "required": "if Analysis lacks conditions"},
        {"key": "jrdb.previous_raw", "required": "if PACI ZED misses previous runs"}],
        "years_from": day.year - 10, "years_to": day.year - 1}


def verify_source(source):
    path = Path(source["path"])
    if not path.is_file():
        raise ValueError("SOURCE_NOT_FOUND")
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    if len(data) != source["size_bytes"] or sha != source["sha256"]:
        raise ValueError("HASH_MISMATCH")
    return path


def run(request, inputs):
    day, asof = validate(request)
    sources = inputs.get("sources", {})
    if "jrdb.paci.daily" not in sources or "jrdb.analysis.current" not in sources:
        return plan(request)
    paci = verify_source(sources["jrdb.paci.daily"])
    verify_source(sources["jrdb.analysis.current"])
    audit = ReaderAudit()
    parser = Parser(audit)
    target = request["target"]
    records = [parser.bac(r) for _, r in iter_archive_records(paci, "BAC", audit)]
    matches = [x for x in records if x["date_raw"] == day.strftime("%Y%m%d") and
               x["race_key_raw"][:2] == VENUES[target["venue"]] and
               x["race_key_raw"][-2:] == f"{target['race_no']:02d}"]
    if audit.record_length_errors or len(matches) != 1:
        raise ValueError("SOURCE_AMBIGUOUS" if len(matches) > 1 else "SOURCE_NOT_FOUND")
    bac = matches[0]
    try:
        post = datetime.strptime(bac["date_raw"] + bac["post_time_raw"], "%Y%m%d%H%M").replace(tzinfo=ZoneInfo("Asia/Tokyo"))
    except ValueError as exc:
        raise ValueError("UNVERIFIED_AS_OF") from exc
    if asof > post:
        raise ValueError("FUTURE_LEAK")
    timestamp = sources["jrdb.paci.daily"].get("snapshot_at")
    if not timestamp:
        raise ValueError("UNVERIFIED_AS_OF")
    snapshot = datetime.fromisoformat(timestamp)
    if snapshot.utcoffset() is None or snapshot > asof:
        raise ValueError("UNVERIFIED_AS_OF")
    runners, coverage = read_previous(paci, bac["race_key_raw"], day)
    # Never publish a PASS or an incomplete evidence bundle until history
    # selection, trends, leak guards and contract validation are implemented.
    return {"status": "BLOCKED", "failure_code": "INCOMPLETE_8_AXES",
            "target": {"race_key": bac["race_key_raw"], "race_name": bac["race_name"]},
            "coverage": coverage, "runner_count": len(runners)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--plan", action="store_true")
    group.add_argument("--run", action="store_true")
    parser.add_argument("--inputs")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    try:
        request = json.loads(Path(args.request).read_text())
        result = plan(request) if args.plan or not args.inputs else run(request, json.loads(Path(args.inputs).read_text()))
    except (ValueError, KeyError, OSError, TypeError) as exc:
        result = {"status": "BLOCKED", "failure_code": str(exc) or "INVALID_REQUEST"}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if args.plan and result.get("status") == "NEED_INPUT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
