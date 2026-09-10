#!/usr/bin/env python3
"""Diagnose statistical-guard rejects in a JRDB Edge Registry.

This module is audit-only. It reproduces the existing q-value and directional
CI pass conditions but never changes Registry status or validation thresholds.
It accepts both legacy final WATCH and v0.2 final REJECTED mappings.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

VERSION = "0.2.0"
ACTIVE_Q = 0.05
PROVISIONAL_Q = 0.10


def _ci_pass(direction: str, low: Any, high: Any) -> bool:
    if low is None or high is None:
        return False
    if direction == "POSITIVE":
        return float(low) > 0.0
    if direction == "NEGATIVE":
        return float(high) < 0.0
    return False


def classify_channel(
    direction: str,
    q_value: Any,
    ci_low: Any,
    ci_high: Any,
    temporal_status: str,
) -> str:
    if direction == "NEUTRAL":
        return "NEUTRAL"
    if q_value is None:
        return "MISSING_Q"
    threshold = ACTIVE_Q if temporal_status == "ACTIVE" else PROVISIONAL_Q
    q_pass = float(q_value) <= threshold
    ci_pass = _ci_pass(direction, ci_low, ci_high)
    if q_pass and ci_pass:
        return "PASS"
    if q_pass:
        return "CI_FAIL_ONLY"
    if ci_pass:
        return "FDR_FAIL_ONLY"
    return "FDR_AND_CI_FAIL"


def classify_record(performance_reason: str, value_reason: str) -> str:
    reasons = [x for x in (performance_reason, value_reason) if x != "NEUTRAL"]
    if not reasons:
        return "NO_NON_NEUTRAL_SIGNAL"
    if "MISSING_Q" in reasons:
        return "MISSING_Q_PRESENT"
    if "CI_FAIL_ONLY" in reasons:
        return "Q_PASS_BUT_CI_FAIL_PRESENT"
    if "FDR_FAIL_ONLY" in reasons:
        return "CI_PASS_BUT_FDR_FAIL_PRESENT"
    if reasons and all(x == "FDR_AND_CI_FAIL" for x in reasons):
        return "ALL_SIGNAL_FDR_AND_CI_FAIL"
    return "OTHER_COMBINATION"


def _nested(values: Mapping[str, Counter[str]]) -> dict[str, dict[str, int]]:
    return {key: dict(sorted(counter.items())) for key, counter in sorted(values.items())}


def audit_registry(path: str | Path) -> dict[str, Any]:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        rows = con.execute(
            """
            SELECT d.edge_id, d.family, d.status AS final_status,
                   d.performance_signal, d.value_signal,
                   g.hypothesis_family AS template_id,
                   g.temporal_status, g.statistical_status,
                   g.performance_q_value, g.value_q_value,
                   g.performance_ci_low, g.performance_ci_high,
                   g.value_ci_low, g.value_ci_high
            FROM edge_definition AS d
            JOIN edge_statistical_guard AS g ON g.edge_id=d.edge_id
            WHERE d.status IN ('WATCH','REJECTED')
              AND g.temporal_status IN ('ACTIVE','PROVISIONAL')
              AND g.statistical_status='WATCH'
            ORDER BY d.edge_id
            """
        ).fetchall()

        overall: Counter[str] = Counter()
        performance: Counter[str] = Counter()
        value: Counter[str] = Counter()
        temporal: dict[str, Counter[str]] = defaultdict(Counter)
        family: dict[str, Counter[str]] = defaultdict(Counter)
        template: dict[str, Counter[str]] = defaultdict(Counter)
        final_status: Counter[str] = Counter()

        for row in rows:
            temporal_status = str(row["temporal_status"])
            p_reason = classify_channel(
                str(row["performance_signal"]), row["performance_q_value"],
                row["performance_ci_low"], row["performance_ci_high"], temporal_status,
            )
            v_reason = classify_channel(
                str(row["value_signal"]), row["value_q_value"],
                row["value_ci_low"], row["value_ci_high"], temporal_status,
            )
            reason = classify_record(p_reason, v_reason)
            overall[reason] += 1
            performance[p_reason] += 1
            value[v_reason] += 1
            temporal[temporal_status][reason] += 1
            family[str(row["family"])][reason] += 1
            template[str(row["template_id"] or "UNKNOWN_TEMPLATE")][reason] += 1
            final_status[str(row["final_status"])] += 1

        return {
            "audit_version": VERSION,
            "integrity_check": integrity,
            "thresholds": {"ACTIVE": ACTIVE_Q, "PROVISIONAL": PROVISIONAL_Q},
            "statistical_reject_count": len(rows),
            "final_status_counts": dict(sorted(final_status.items())),
            "reason_counts": dict(sorted(overall.items())),
            "performance_channel_counts": dict(sorted(performance.items())),
            "value_channel_counts": dict(sorted(value.items())),
            "temporal_status_reason_counts": _nested(temporal),
            "family_reason_counts": _nested(family),
            "template_reason_counts": _nested(template),
        }
    finally:
        con.close()


def write_markdown(report: Mapping[str, Any], path: str | Path) -> None:
    lines = [
        "# JRDB Edge Statistical Reject Audit",
        "",
        f"- Integrity: `{report['integrity_check']}`",
        f"- Statistical rejects: {report['statistical_reject_count']}",
        f"- Final status: `{json.dumps(report['final_status_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- Reasons: `{json.dumps(report['reason_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- Performance channel: `{json.dumps(report['performance_channel_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- Value channel: `{json.dumps(report['value_channel_counts'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Family",
        "",
        "| Family | Both FDR+CI fail | q pass / CI fail | CI pass / FDR fail | Other |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, counts in report["family_reason_counts"].items():
        a = counts.get("ALL_SIGNAL_FDR_AND_CI_FAIL", 0)
        b = counts.get("Q_PASS_BUT_CI_FAIL_PRESENT", 0)
        c = counts.get("CI_PASS_BUT_FDR_FAIL_PRESENT", 0)
        other = sum(counts.values()) - a - b - c
        lines.append(f"| {name} | {a} | {b} | {c} | {other} |")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md")
    args = parser.parse_args()
    report = audit_registry(args.registry)
    Path(args.output_json).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.output_md:
        write_markdown(report, args.output_md)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
