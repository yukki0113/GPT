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
    if not isinstance(request, dict) or set(request) != {'schema_version','protocol','target','as_of','history_years','mode','detail'}:
        raise ValueError('INVALID_REQUEST')
    if set(request.get('target', {})) - {'date','venue','race_no','assertions'} or set(request.get('detail', {})) != {'previous_runs'}:
        raise ValueError('INVALID_REQUEST')
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
        {"key": "jrdb.previous_raw", "required": "if PACI ZED misses previous runs"},
        {"key": "jrdb.history.references", "required": "if previous-history references predate available cohort partitions"}],
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


def run(request, inputs, output_dir=None):
    from input_source_resolver import verify
    from race_condition_resolver import resolve
    from history_reader import read_history
    from forecast_orchestrator import build, publish
    day, asof = validate(request)
    sources = inputs.get('sources', {})
    required = ('jrdb.paci.daily', 'jrdb.analysis.current')
    if any(k not in sources for k in required):
        return plan(request)
    paths, audits = {}, []
    for key, source in sorted(sources.items()):
        paths[key], audit = verify(source, key, asof)
        audits.append(audit)
    expected = f'PACI{day:%y%m%d}.zip'
    if sources['jrdb.paci.daily']['name'] != expected:
        raise ValueError('SOURCE_CHANGED: unexpected PACI date')
    target, expected_runners = resolve(paths['jrdb.paci.daily'], request['target'], asof)
    history_path = paths.get('jrdb.history.normalized', paths['jrdb.analysis.current'])
    races, rows, query_audit = read_history(history_path, target['date'])
    if query_audit.get('years_missing'):
        return {'status': 'NEED_INPUT', 'failure_code': 'SOURCE_NOT_FOUND', 'history_coverage': query_audit}
    if query_audit.get('missing_conditions') and 'jrdb.historical_conditions' in paths:
        conditions = json.loads(paths['jrdb.historical_conditions'].read_text())
        if conditions.get('schema_version') != 'forecast-conditions.v1':
            raise ValueError('INVALID_REQUEST: condition schema')
        races = conditions['races']
        by_race = {r['race_key']: r for r in races}
        if len(by_race) != len(races):
            raise ValueError('DUPLICATE_RACE_OR_RUN')
        # Preserve unknowns for any historical record not covered by the verified
        # condition export. Never drop such a race merely to claim completeness.
        row_keys = {r['race_key'] for r in rows}
        if not row_keys.issubset(by_race):
            return {'status':'NEED_INPUT','failure_code':'UNKNOWN_CONDITION','missing_race_count':len(row_keys - set(by_race))}
        for row in rows:
            row['race_class'] = by_race[row['race_key']]['race_class']
        query_audit['missing_conditions'] = []
    if query_audit.get('missing_conditions'):
        return {'status': 'NEED_INPUT', 'failure_code': 'UNKNOWN_CONDITION',
                'missing_conditions': query_audit['missing_conditions'], 'history_coverage': query_audit, 'plan': plan(request)}
    runners, coverage = read_previous(paths['jrdb.paci.daily'], target['race_key'], day)
    raw_sources = [p for k,p in paths.items() if k.startswith('jrdb.previous_raw.')]
    if coverage['missing_previous'] and raw_sources:
        from previous_run_reader import supplement_previous
        roots = {p.parent.parent for p in raw_sources}
        if len(roots) != 1:
            raise ValueError('SOURCE_AMBIGUOUS')
        # RawHistory is restricted to the verified staged root. All archives
        # visible to its scanner must be declared and SHA verified.
        root = next(iter(roots))
        if set(root.glob('SED/SED_*.zip')) != set(raw_sources):
            raise ValueError('SOURCE_CHANGED: undeclared history archives')
        runners = supplement_previous(runners, root, day)
        coverage['previous_available'] = sum(bool(r['previous_run']) for r in runners)
        coverage['missing_previous'] = len(runners) - coverage['previous_available']
    if len(runners) != expected_runners:
        raise ValueError('SOURCE_CHANGED: BAC/KYI field count')
    rules = json.loads((Path(__file__).parent / 'config/sampling_rules_v1.json').read_text())
    reference_rows = rows
    if 'jrdb.history.references' in paths:
        _, additional, _ = read_history(paths['jrdb.history.references'], target['date'])
        reference_rows = rows + additional
    evidence = build(target, races, rows, runners, rules, reference_rows=reference_rows)
    evidence['policy'] = {'version': request['protocol'], 'years_from': day.year - 10, 'years_to': day.year - 1}
    evidence['provenance'] = {'input_artifacts': audits}
    evidence['states'] = ['INIT', 'SOURCE_READY', 'TARGET_RESOLVED', 'EXACT_SELECTED', 'BRANCH_SELECTED',
                          'SUPPLEMENT_SELECTED', 'TREND_READY', 'RUNS_READY', 'MATCH_READY', 'CONTRACT_VALIDATED']
    source_audit = {'sources': audits, 'coverage': coverage, 'query': query_audit,
                    'as_of': request['as_of'], 'as_of_exclusive': target['date'], 'target_results_read': False}
    if output_dir:
        destination = publish(output_dir, request, evidence, evidence['sampling'], source_audit)
        return {'status': evidence['status'], 'output_dir': str(destination)}
    return evidence


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
        result = plan(request) if args.plan or not args.inputs else run(request, json.loads(Path(args.inputs).read_text()), args.output_dir)
    except (ValueError, KeyError, OSError, TypeError) as exc:
        result = {"status": "BLOCKED", "failure_code": str(exc) or "INVALID_REQUEST"}
    if args.plan and result.get('status') == 'NEED_INPUT':
        output = Path(args.output_dir)
        output.mkdir(parents=True, exist_ok=True)
        (output / 'acquisition_plan.json').write_text(json.dumps(result, ensure_ascii=False, sort_keys=True) + '\n')
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if (args.plan and result.get("status") == "NEED_INPUT") or result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
