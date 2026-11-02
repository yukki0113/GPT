#!/usr/bin/env python3
"""Audit why final JRDB Edge Registry records remain WATCH.

This is a downstream-only diagnostic. It never changes Edge status or thresholds.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

VERSION = "0.1.0"


def classify_watch(guard: Mapping[str, Any] | None) -> str:
    if guard is None:
        return "UNKNOWN_GUARD"
    temporal = str(guard.get("temporal_status") or "")
    statistical = str(guard.get("statistical_status") or "")
    if temporal == "WATCH":
        return "TEMPORAL_WATCH"
    if statistical == "WATCH" and temporal == "ACTIVE":
        return "STAT_DOWNGRADE_FROM_ACTIVE"
    if statistical == "WATCH" and temporal == "PROVISIONAL":
        return "STAT_DOWNGRADE_FROM_PROVISIONAL"
    return f"OTHER:{temporal}->{statistical}"


def _nested(counter_map: Mapping[str, Counter[str]]) -> dict[str, dict[str, int]]:
    return {
        key: dict(sorted(counts.items()))
        for key, counts in sorted(counter_map.items())
    }


def audit_registry(path: str | Path) -> dict[str, Any]:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        guard_exists = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='edge_statistical_guard'"
        ).fetchone()
        if not guard_exists:
            raise ValueError("edge_statistical_guard table is required")

        rows = con.execute(
            """
            SELECT d.edge_id, d.family, d.conditions_json, d.status,
                   g.temporal_status, g.statistical_status
            FROM edge_definition AS d
            LEFT JOIN edge_statistical_guard AS g ON g.edge_id=d.edge_id
            WHERE d.status='WATCH'
            ORDER BY d.edge_id
            """
        ).fetchall()

        reason_counts: Counter[str] = Counter()
        family_counts: dict[str, Counter[str]] = defaultdict(Counter)
        template_counts: dict[str, Counter[str]] = defaultdict(Counter)

        for row in rows:
            guard = None
            if row["temporal_status"] is not None or row["statistical_status"] is not None:
                guard = {
                    "temporal_status": row["temporal_status"],
                    "statistical_status": row["statistical_status"],
                }
            reason = classify_watch(guard)
            family = str(row["family"])
            try:
                conditions = json.loads(str(row["conditions_json"]))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid conditions_json for {row['edge_id']}") from exc
            template = str(conditions.get("template_id") or "UNKNOWN_TEMPLATE")
            reason_counts[reason] += 1
            family_counts[family][reason] += 1
            template_counts[template][reason] += 1

        return {
            "audit_version": VERSION,
            "integrity_check": integrity,
            "watch_count": len(rows),
            "reason_counts": dict(sorted(reason_counts.items())),
            "family_reason_counts": _nested(family_counts),
            "template_reason_counts": _nested(template_counts),
        }
    finally:
        con.close()


def write_markdown(report: Mapping[str, Any], path: str | Path) -> None:
    lines = [
        "# JRDB Edge WATCH Audit",
        "",
        f"- Integrity: `{report['integrity_check']}`",
        f"- WATCH: {report['watch_count']}",
        f"- Reasons: `{json.dumps(report['reason_counts'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Family",
        "",
        "| Family | Temporal WATCH | Active→WATCH | Provisional→WATCH | Other |",
        "|---|---:|---:|---:|---:|",
    ]
    for family, counts in report["family_reason_counts"].items():
        known = (
            counts.get("TEMPORAL_WATCH", 0)
            + counts.get("STAT_DOWNGRADE_FROM_ACTIVE", 0)
            + counts.get("STAT_DOWNGRADE_FROM_PROVISIONAL", 0)
        )
        other = sum(counts.values()) - known
        lines.append(
            f"| {family} | {counts.get('TEMPORAL_WATCH', 0)} | "
            f"{counts.get('STAT_DOWNGRADE_FROM_ACTIVE', 0)} | "
            f"{counts.get('STAT_DOWNGRADE_FROM_PROVISIONAL', 0)} | {other} |"
        )
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
