#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate observable RaceNote Forecast research records before Freeze."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

VERSION = "racenote-forecast-decision-trace-validator-0.1.0"


def load_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, list) else [value]


def _name(horse: Any) -> str:
    if not isinstance(horse, dict):
        return ""
    return str(horse.get("horse_name") or "").strip()


def validate_record(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    ident = record.get("identity") or {}
    pred = record.get("prediction") or {}
    marks = pred.get("marks") or {}
    trace = record.get("decision_trace") or {}
    research = record.get("research") or {}
    audit = record.get("audit") or {}

    prefix = f"{ident.get('target_date','?')} {ident.get('venue','?')}{ident.get('race_no','?')}R"

    if record.get("schema_version") != "RaceNote-Forecast-Research-Record-0.2":
        errors.append(f"{prefix}: schema_version must be v0.2")
    if research.get("logic_version") != "RaceNote-Baseline-Reader-0.2":
        errors.append(f"{prefix}: logic_version must be RaceNote-Baseline-Reader-0.2")

    main = marks.get("main") or pred.get("axis")
    second = marks.get("second")
    main_name = _name(main)
    second_name = _name(second)

    if not main_name or not second_name:
        errors.append(f"{prefix}: main/second horse is missing")

    thesis = str(trace.get("race_thesis") or "").strip()
    if len(thesis) < 20:
        errors.append(f"{prefix}: race_thesis is too short")

    factors = trace.get("decisive_factors")
    if not isinstance(factors, list) or not 2 <= len(factors) <= 4:
        errors.append(f"{prefix}: decisive_factors must contain 2-4 items")
    else:
        for i, factor in enumerate(factors, 1):
            if not isinstance(factor, dict):
                errors.append(f"{prefix}: decisive_factor[{i}] must be object")
                continue
            if len(str(factor.get("observation") or "").strip()) < 8:
                errors.append(f"{prefix}: decisive_factor[{i}] observation too short")
            if len(str(factor.get("interpretation") or "").strip()) < 12:
                errors.append(f"{prefix}: decisive_factor[{i}] interpretation too short")

    comparison = trace.get("main_vs_second") or {}
    cmp_main = _name(comparison.get("main"))
    cmp_second = _name(comparison.get("second"))
    why = str(comparison.get("why_main_over_second") or "").strip()
    if cmp_main != main_name:
        errors.append(f"{prefix}: decision_trace main does not match marks.main")
    if cmp_second != second_name:
        errors.append(f"{prefix}: decision_trace second does not match marks.second")
    if len(why) < 20:
        errors.append(f"{prefix}: why_main_over_second is too short")
    if main_name and main_name not in why:
        errors.append(f"{prefix}: why_main_over_second must explicitly name ◎ {main_name}")
    if second_name and second_name not in why:
        errors.append(f"{prefix}: why_main_over_second must explicitly name ○ {second_name}")

    counter = str(trace.get("strongest_counter") or "").strip()
    if len(counter) < 15:
        errors.append(f"{prefix}: strongest_counter is too short")
    if main_name and main_name not in counter:
        errors.append(f"{prefix}: strongest_counter must explicitly refer to ◎ {main_name}")

    down = trace.get("downweighted_evidence")
    if not isinstance(down, list):
        errors.append(f"{prefix}: downweighted_evidence must be an array")
    elif len(down) > 3:
        errors.append(f"{prefix}: downweighted_evidence max is 3")
    else:
        for i, item in enumerate(down, 1):
            if not isinstance(item, dict):
                errors.append(f"{prefix}: downweighted_evidence[{i}] must be object")
                continue
            if len(str(item.get("evidence") or "").strip()) < 5:
                errors.append(f"{prefix}: downweighted_evidence[{i}] evidence too short")
            if len(str(item.get("reason_downweighted") or "").strip()) < 10:
                errors.append(f"{prefix}: downweighted_evidence[{i}] reason too short")

    reversal = str(trace.get("reversal_condition") or "").strip()
    if len(reversal) < 15:
        errors.append(f"{prefix}: reversal_condition is too short")
    if second_name and second_name not in reversal:
        errors.append(f"{prefix}: reversal_condition must explicitly refer to ○ {second_name}")

    generic_only = {
        "総合的にまとまる",
        "上位候補間の差は大きくない",
        "展開や位置取りで順位が入れ替わる",
        "能力水準、近走内容、今回の仕上がりを横並びで比較",
    }
    combined = " ".join([thesis, why, counter, reversal])
    if sum(1 for phrase in generic_only if phrase in combined) >= 3:
        errors.append(f"{prefix}: decision trace is dominated by generic boilerplate")

    if audit.get("result_visible_at_freeze") is not False:
        errors.append(f"{prefix}: result_visible_at_freeze must be false")
    if audit.get("pre_result_guard") != "PASS":
        errors.append(f"{prefix}: pre_result_guard must be PASS")

    return errors


def audit_turn(records: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    for record in records:
        errors.extend(validate_record(record))

    def values(path_fn):
        return [str(path_fn(r) or "").strip() for r in records]

    comparisons = values(lambda r: (r.get("decision_trace") or {}).get("main_vs_second", {}).get("why_main_over_second"))
    theses = values(lambda r: (r.get("decision_trace") or {}).get("race_thesis"))
    counters = values(lambda r: (r.get("decision_trace") or {}).get("strongest_counter"))

    duplicate_stats = {}
    for label, seq in [("race_thesis", theses), ("main_vs_second", comparisons), ("strongest_counter", counters)]:
        nonempty = [x for x in seq if x]
        unique = len(set(nonempty))
        total = len(nonempty)
        duplicate_stats[label] = {
            "total": total,
            "unique": unique,
            "unique_ratio": round(unique / total, 4) if total else 0.0,
        }
        if total >= 10 and unique / total < 0.75:
            errors.append(f"TURN: {label} unique ratio too low ({unique}/{total}); possible template-driven execution")

    return {
        "validator_version": VERSION,
        "status": "PASS" if not errors else "FAIL",
        "record_count": len(records),
        "error_count": len(errors),
        "errors": errors,
        "duplicate_stats": duplicate_stats,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = audit_turn(load_records(args.records))
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
