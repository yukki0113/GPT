#!/usr/bin/env python3
"""Audit-only bootstrap study for lower-confidence JRDB Edge candidates.

This study does not mutate Registry state or serving eligibility. It selects
final REJECTED / temporal ACTIVE candidates whose non-neutral channel q-value
falls inside a predeclared research band, then evaluates the existing
race-date cluster bootstrap for only those channels.
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Mapping

VERSION = "0.1.0"
DEFAULT_Q_LOW = 0.05
DEFAULT_Q_HIGH = 0.10
DEFAULT_BOOTSTRAP_SAMPLES = 400


def in_research_band(q_value: Any, *, q_low: float, q_high: float) -> bool:
    if q_value is None:
        return False
    q = float(q_value)
    return q_low < q <= q_high


def selected_channels(row: Mapping[str, Any], *, q_low: float, q_high: float) -> tuple[str, ...]:
    selected: list[str] = []
    for channel in ("performance", "value"):
        if str(row.get(f"{channel}_signal", "NEUTRAL")) == "NEUTRAL":
            continue
        if in_research_band(row.get(f"{channel}_q_value"), q_low=q_low, q_high=q_high):
            selected.append(channel)
    return tuple(selected)


def ci_supports(direction: str, low: Any, high: Any) -> bool:
    if low is None or high is None:
        return False
    if direction == "POSITIVE":
        return float(low) > 0.0
    if direction == "NEGATIVE":
        return float(high) < 0.0
    return False


def _load_temporal_audit(path: str | Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = payload.get("validation_rows")
    if not isinstance(rows, list):
        raise ValueError("registry audit has no validation_rows")
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        candidate = row.get("candidate") if isinstance(row, dict) else None
        if not isinstance(candidate, dict) or not candidate.get("candidate_id"):
            continue
        cid = str(candidate["candidate_id"])
        if cid in out:
            raise ValueError(f"duplicate candidate_id in registry audit: {cid}")
        out[cid] = row
    return out


def _load_population(registry_path: str | Path) -> tuple[str, list[dict[str, Any]]]:
    con = sqlite3.connect(registry_path)
    con.row_factory = sqlite3.Row
    try:
        integrity = str(con.execute("PRAGMA integrity_check").fetchone()[0])
        if integrity != "ok":
            raise ValueError(f"registry integrity_check failed: {integrity}")
        rows = con.execute(
            """
            SELECT d.edge_id, d.family, d.polarity, d.performance_signal, d.value_signal,
                   d.sample_n, d.unique_horses, d.unique_races,
                   d.performance_lift, d.place_roi,
                   g.candidate_id, g.hypothesis_family AS template_id,
                   g.temporal_status, g.statistical_status,
                   g.performance_p_value, g.performance_q_value,
                   g.value_p_value, g.value_q_value,
                   g.bootstrap_samples
            FROM edge_definition AS d
            JOIN edge_statistical_guard AS g ON g.edge_id=d.edge_id
            WHERE d.status='REJECTED'
              AND g.temporal_status='ACTIVE'
              AND g.statistical_status='WATCH'
            ORDER BY d.edge_id
            """
        ).fetchall()
        return integrity, [dict(r) for r in rows]
    finally:
        con.close()


def _default_evaluator(
    mart_path: str | Path,
    candidate: Mapping[str, Any],
    temporal: Mapping[str, Any],
    bootstrap_samples: int,
) -> dict[str, Any]:
    import apply_jrdb_edge_statistical_guard_v0_2 as guard_v02

    return guard_v02._evaluate_v02(
        mart_path, candidate, temporal, bootstrap_samples=bootstrap_samples
    )


def _p_matches(stored: Any, recomputed: Any, *, atol: float = 1e-12) -> bool:
    if stored is None or recomputed is None:
        return stored is None and recomputed is None
    return math.isclose(float(stored), float(recomputed), rel_tol=1e-10, abs_tol=atol)


def run_study(
    mart_path: str | Path,
    registry_path: str | Path,
    registry_audit_path: str | Path,
    *,
    q_low: float = DEFAULT_Q_LOW,
    q_high: float = DEFAULT_Q_HIGH,
    bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    evaluator: Callable[[str | Path, Mapping[str, Any], Mapping[str, Any], int], dict[str, Any]] = _default_evaluator,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not (0.0 <= q_low < q_high <= 1.0):
        raise ValueError("q band must satisfy 0 <= q_low < q_high <= 1")
    if bootstrap_samples <= 0:
        raise ValueError("bootstrap_samples must be positive")

    temporal_by_id = _load_temporal_audit(registry_audit_path)
    integrity, population = _load_population(registry_path)
    selected = [r for r in population if selected_channels(r, q_low=q_low, q_high=q_high)]

    output: list[dict[str, Any]] = []
    for row in selected:
        cid = str(row["candidate_id"])
        temporal = temporal_by_id.get(cid)
        if temporal is None:
            raise ValueError(f"candidate missing from registry audit: {cid}")
        candidate = temporal.get("candidate")
        if not isinstance(candidate, dict):
            raise ValueError(f"candidate payload missing from registry audit: {cid}")
        if str(temporal.get("status")) != "ACTIVE":
            raise ValueError(f"temporal audit status mismatch for {cid}")

        detailed = evaluator(mart_path, candidate, temporal, bootstrap_samples)
        research_channels: dict[str, dict[str, Any]] = {}
        for channel in selected_channels(row, q_low=q_low, q_high=q_high):
            stored_p = row.get(f"{channel}_p_value")
            recomputed_p = detailed.get(f"{channel}_p_value")
            if not _p_matches(stored_p, recomputed_p):
                raise ValueError(
                    f"{cid} {channel} p-value mismatch: registry={stored_p!r} mart={recomputed_p!r}"
                )
            direction = str(row[f"{channel}_signal"])
            low = detailed.get(f"{channel}_ci_low")
            high = detailed.get(f"{channel}_ci_high")
            research_channels[channel] = {
                "signal": direction,
                "p_value": stored_p,
                "q_value": row.get(f"{channel}_q_value"),
                "ci_low": low,
                "ci_high": high,
                "ci_supports_direction": ci_supports(direction, low, high),
            }

        supported = any(c["ci_supports_direction"] for c in research_channels.values())
        output.append(
            {
                "edge_id": row["edge_id"],
                "candidate_id": cid,
                "family": row["family"],
                "template_id": row["template_id"],
                "polarity": row["polarity"],
                "sample_n": row["sample_n"],
                "unique_horses": row["unique_horses"],
                "unique_races": row["unique_races"],
                "performance_lift": row["performance_lift"],
                "place_roi": row["place_roi"],
                "q_band": {"low_exclusive": q_low, "high_inclusive": q_high},
                "bootstrap_samples": bootstrap_samples,
                "research_channels": research_channels,
                "bootstrap_supported": supported,
            }
        )

    summary = summarize(output)
    summary.update(
        {
            "audit_version": VERSION,
            "integrity_check": integrity,
            "population_temporal_active_rejected": len(population),
            "q_band": {"low_exclusive": q_low, "high_inclusive": q_high},
            "bootstrap_samples": bootstrap_samples,
        }
    )
    return output, summary


def summarize(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    family_selected: Counter[str] = Counter()
    family_supported: Counter[str] = Counter()
    template_selected: Counter[str] = Counter()
    template_supported: Counter[str] = Counter()
    polarity_selected: Counter[str] = Counter()
    polarity_supported: Counter[str] = Counter()
    channel_selected: Counter[str] = Counter()
    channel_supported: Counter[str] = Counter()

    for row in rows:
        family = str(row.get("family"))
        template = str(row.get("template_id"))
        polarity = str(row.get("polarity"))
        family_selected[family] += 1
        template_selected[template] += 1
        polarity_selected[polarity] += 1
        if bool(row.get("bootstrap_supported")):
            family_supported[family] += 1
            template_supported[template] += 1
            polarity_supported[polarity] += 1
        for channel, evidence in dict(row.get("research_channels") or {}).items():
            channel_selected[str(channel)] += 1
            if bool(evidence.get("ci_supports_direction")):
                channel_supported[str(channel)] += 1

    def nested(selected: Counter[str], supported: Counter[str]) -> dict[str, dict[str, int]]:
        return {
            key: {"selected": selected[key], "supported": supported[key]}
            for key in sorted(selected)
        }

    return {
        "status": "PASS",
        "selected_candidates": len(rows),
        "bootstrap_supported_candidates": sum(bool(r.get("bootstrap_supported")) for r in rows),
        "family_counts": nested(family_selected, family_supported),
        "template_counts": nested(template_selected, template_supported),
        "polarity_counts": nested(polarity_selected, polarity_supported),
        "channel_counts": nested(channel_selected, channel_supported),
    }


def write_markdown(report: Mapping[str, Any], path: str | Path) -> None:
    selected = int(report["selected_candidates"])
    supported = int(report["bootstrap_supported_candidates"])
    pct = (100.0 * supported / selected) if selected else 0.0
    q = report["q_band"]
    lines = [
        "# JRDB Edge SUGGESTIVE Bootstrap Research Audit",
        "",
        f"- Integrity: `{report['integrity_check']}`",
        f"- Temporal-ACTIVE REJECTED population: {report['population_temporal_active_rejected']}",
        f"- Research q band: `{q['low_exclusive']} < q <= {q['high_inclusive']}`",
        f"- Bootstrap samples: {report['bootstrap_samples']}",
        f"- Selected candidates: {selected}",
        f"- Directional-CI supported candidates: {supported} ({pct:.2f}%)",
        "",
        "## Family",
        "",
        "| Family | Selected | CI-supported |",
        "|---|---:|---:|",
    ]
    for name, counts in report["family_counts"].items():
        lines.append(f"| {name} | {counts['selected']} | {counts['supported']} |")
    lines.extend(["", "## Channel", "", "| Channel | Selected | CI-supported |", "|---|---:|---:|"])
    for name, counts in report["channel_counts"].items():
        lines.append(f"| {name} | {counts['selected']} | {counts['supported']} |")
    lines.extend([
        "",
        "> Research only. This output does not change Registry status or Matcher serving behavior.",
    ])
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mart", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--registry-audit", required=True)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--audit-json", required=True)
    parser.add_argument("--audit-md")
    parser.add_argument("--q-low", type=float, default=DEFAULT_Q_LOW)
    parser.add_argument("--q-high", type=float, default=DEFAULT_Q_HIGH)
    parser.add_argument("--bootstrap-samples", type=int, default=DEFAULT_BOOTSTRAP_SAMPLES)
    parser.add_argument("--expected-selected", type=int)
    args = parser.parse_args()

    rows, report = run_study(
        args.mart,
        args.registry,
        args.registry_audit,
        q_low=args.q_low,
        q_high=args.q_high,
        bootstrap_samples=args.bootstrap_samples,
    )
    if args.expected_selected is not None and report["selected_candidates"] != args.expected_selected:
        raise ValueError(
            f"selected candidate count mismatch: expected={args.expected_selected} actual={report['selected_candidates']}"
        )
    with Path(args.output_jsonl).open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    Path(args.audit_json).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if args.audit_md:
        write_markdown(report, args.audit_md)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
