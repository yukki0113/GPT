#!/usr/bin/env python3
"""Produce a compact human/machine audit report from a built JRDB Edge Registry.

The report is intentionally downstream-only: it never changes edge status.  It
summarizes final registry state, Performance/Value signal combinations,
statistical-guard outcomes, and representative active/provisional edges so a
production build can be reviewed without manually inspecting SQLite/JSONL.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

VERSION = "0.1.0"
LIVE_STATUSES = ("ACTIVE", "PROVISIONAL")


def _all_metric(con: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    rows = con.execute(
        "SELECT * FROM edge_metric_snapshot WHERE slice_kind='ALL' AND slice_label='all'"
    ).fetchall()
    return {str(row["edge_id"]): row for row in rows}


def _guard_map(con: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    exists = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='edge_statistical_guard'"
    ).fetchone()
    if not exists:
        return {}
    return {
        str(row["edge_id"]): row
        for row in con.execute("SELECT * FROM edge_statistical_guard")
    }


def _round(value: Any, digits: int = 4) -> float | None:
    return None if value is None else round(float(value), digits)


def _edge_record(
    definition: sqlite3.Row,
    metric: sqlite3.Row | None,
    guard: sqlite3.Row | None,
) -> dict[str, Any]:
    record = {
        "edge_id": definition["edge_id"],
        "status": definition["status"],
        "family": definition["family"],
        "anchor_type": definition["anchor_type"],
        "anchor_name": definition["anchor_name"],
        "polarity": definition["polarity"],
        "performance_signal": definition["performance_signal"],
        "value_signal": definition["value_signal"],
        "display_text": definition["display_text"],
        "specificity": definition["specificity"],
        "strength_score": _round(definition["strength_score"], 2),
        "confidence_band": definition["confidence_band"],
        "parent_edge_id": definition["parent_edge_id"],
        "edge_cluster": definition["edge_cluster"],
    }
    if metric is not None:
        record.update(
            {
                "sample_n": metric["sample_n"],
                "unique_horses": metric["unique_horses"],
                "unique_races": metric["unique_races"],
                "win_rate": _round(metric["win_rate"]),
                "place_rate": _round(metric["place_rate"]),
                "win_roi": _round(metric["win_roi"]),
                "place_roi": _round(metric["place_roi"]),
                "baseline_place_rate": _round(metric["baseline_place_rate"]),
                "performance_lift": _round(metric["performance_lift"]),
                "largest_return_share": _round(metric["largest_return_share"]),
                "top3_return_share": _round(metric["top3_return_share"]),
            }
        )
    if guard is not None:
        record.update(
            {
                "statistical_status": guard["statistical_status"],
                "performance_q_value": _round(guard["performance_q_value"], 6),
                "value_q_value": _round(guard["value_q_value"], 6),
                "performance_ci_low": _round(guard["performance_ci_low"], 6),
                "performance_ci_high": _round(guard["performance_ci_high"], 6),
                "value_ci_low": _round(guard["value_ci_low"], 6),
                "value_ci_high": _round(guard["value_ci_high"], 6),
                "performance_stat_pass": bool(guard["performance_stat_pass"]),
                "value_stat_pass": bool(guard["value_stat_pass"]),
                "redundancy_group_id": guard["redundancy_group_id"],
            }
        )
    return record


def _top(records: list[dict[str, Any]], *, n: int) -> list[dict[str, Any]]:
    def score(row: dict[str, Any]) -> tuple[float, int, str]:
        return (
            float(row.get("strength_score") or 0.0),
            int(row.get("sample_n") or 0),
            str(row["edge_id"]),
        )

    return sorted(records, key=score, reverse=True)[:n]


def summarize(registry_path: str | Path, *, top_n: int = 20) -> dict[str, Any]:
    con = sqlite3.connect(registry_path)
    con.row_factory = sqlite3.Row
    try:
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        meta = con.execute("SELECT * FROM edge_registry_meta ORDER BY generated_at DESC LIMIT 1").fetchone()
        definitions = con.execute("SELECT * FROM edge_definition ORDER BY edge_id").fetchall()
        metrics = _all_metric(con)
        guards = _guard_map(con)

        status_counts = Counter(str(row["status"]) for row in definitions)
        family_counts: dict[str, Counter[str]] = defaultdict(Counter)
        polarity_counts = Counter()
        signal_counts = Counter()
        live_records: list[dict[str, Any]] = []
        guard_pass_counts = Counter()
        redundancy_counts = Counter()

        for row in definitions:
            family_counts[str(row["family"])][str(row["status"])] += 1
            if row["status"] not in LIVE_STATUSES:
                continue
            polarity_counts[str(row["polarity"])] += 1
            perf = str(row["performance_signal"])
            value = str(row["value_signal"])
            perf_non_neutral = perf not in {"NEUTRAL", "UNASSESSED"}
            value_non_neutral = value not in {"NEUTRAL", "UNASSESSED"}
            if perf_non_neutral and value_non_neutral:
                signal_counts["PERFORMANCE_AND_VALUE"] += 1
            elif perf_non_neutral:
                signal_counts["PERFORMANCE_ONLY"] += 1
            elif value_non_neutral:
                signal_counts["VALUE_ONLY"] += 1
            else:
                signal_counts["NO_NON_NEUTRAL_SIGNAL"] += 1

            guard = guards.get(str(row["edge_id"]))
            if guard is not None:
                perf_pass = bool(guard["performance_stat_pass"])
                value_pass = bool(guard["value_stat_pass"])
                if perf_pass and value_pass:
                    guard_pass_counts["PERFORMANCE_AND_VALUE"] += 1
                elif perf_pass:
                    guard_pass_counts["PERFORMANCE_ONLY"] += 1
                elif value_pass:
                    guard_pass_counts["VALUE_ONLY"] += 1
                else:
                    guard_pass_counts["NEITHER"] += 1
                if guard["redundancy_group_id"]:
                    redundancy_counts[str(guard["redundancy_group_id"])] += 1

            live_records.append(
                _edge_record(row, metrics.get(str(row["edge_id"])), guard)
            )

        positive = [row for row in live_records if row["polarity"] == "POSITIVE"]
        negative = [row for row in live_records if row["polarity"] == "NEGATIVE"]
        both_stat = [
            row for row in live_records
            if row.get("performance_stat_pass") and row.get("value_stat_pass")
        ]
        redundancy_groups = [
            {"redundancy_group_id": key, "live_edges": count}
            for key, count in sorted(
                redundancy_counts.items(), key=lambda item: (-item[1], item[0])
            )
            if count >= 2
        ]

        return {
            "report_version": VERSION,
            "registry_version": meta["registry_version"] if meta else None,
            "registry_status": meta["status"] if meta else None,
            "generated_at": meta["generated_at"] if meta else None,
            "integrity_check": integrity,
            "stored_edges": len(definitions),
            "live_edges": len(live_records),
            "status_counts": dict(sorted(status_counts.items())),
            "family_status_counts": {
                family: dict(sorted(counts.items()))
                for family, counts in sorted(family_counts.items())
            },
            "live_polarity_counts": dict(sorted(polarity_counts.items())),
            "live_signal_counts": dict(sorted(signal_counts.items())),
            "live_statistical_pass_counts": dict(sorted(guard_pass_counts.items())),
            "live_redundancy_group_count": len(redundancy_groups),
            "live_redundancy_groups": redundancy_groups,
            "top_live_edges": _top(live_records, n=top_n),
            "top_positive_edges": _top(positive, n=top_n),
            "top_negative_edges": _top(negative, n=top_n),
            "top_both_stat_edges": _top(both_stat, n=top_n),
        }
    finally:
        con.close()


def write_markdown(report: dict[str, Any], path: str | Path) -> None:
    lines = [
        "# JRDB Edge Registry Audit Summary",
        "",
        f"- Registry: `{report.get('registry_version')}`",
        f"- Integrity: `{report.get('integrity_check')}`",
        f"- Stored edges: {report.get('stored_edges')}",
        f"- Live edges (ACTIVE + PROVISIONAL): {report.get('live_edges')}",
        f"- Status counts: `{json.dumps(report.get('status_counts', {}), ensure_ascii=False, sort_keys=True)}`",
        f"- Live polarity: `{json.dumps(report.get('live_polarity_counts', {}), ensure_ascii=False, sort_keys=True)}`",
        f"- Statistical passes: `{json.dumps(report.get('live_statistical_pass_counts', {}), ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Top live edges",
        "",
        "| Status | Family | Polarity | Edge | N | Place% | Place ROI | Lift | Strength |",
        "|---|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in report.get("top_live_edges", []):
        place_rate = row.get("place_rate")
        place_roi = row.get("place_roi")
        lines.append(
            "| {status} | {family} | {polarity} | {text} | {n} | {pr} | {roi} | {lift} | {strength} |".format(
                status=row.get("status", ""),
                family=row.get("family", ""),
                polarity=row.get("polarity", ""),
                text=str(row.get("display_text", "")).replace("|", "\\|"),
                n=row.get("sample_n", ""),
                pr="" if place_rate is None else f"{100*float(place_rate):.1f}%",
                roi="" if place_roi is None else f"{100*float(place_roi):.1f}%",
                lift="" if row.get("performance_lift") is None else f"{float(row['performance_lift']):.3f}",
                strength="" if row.get("strength_score") is None else f"{float(row['strength_score']):.1f}",
            )
        )
    lines.extend(["", "## Live redundancy groups", ""])
    groups = report.get("live_redundancy_groups", [])
    if groups:
        for group in groups:
            lines.append(f"- `{group['redundancy_group_id']}`: {group['live_edges']} edges")
    else:
        lines.append("- None with 2+ live edges.")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md")
    parser.add_argument("--top-n", type=int, default=20)
    args = parser.parse_args()
    if args.top_n <= 0:
        raise ValueError("--top-n must be positive")
    report = summarize(args.registry, top_n=args.top_n)
    Path(args.output_json).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if args.output_md:
        write_markdown(report, args.output_md)
    print(json.dumps({
        "status": "PASS",
        "stored_edges": report["stored_edges"],
        "live_edges": report["live_edges"],
        "output_json": args.output_json,
        "output_md": args.output_md,
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
