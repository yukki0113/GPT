#!/usr/bin/env python3
"""Sensitivity audit for SUGGESTIVE bootstrap support.

Re-evaluate only the channels that were supported by a baseline SUGGESTIVE
research output. This is audit-only: Registry status and matcher eligibility
are never mutated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Mapping

import research_jrdb_edge_suggestive_bootstrap_v0_1 as baseline_study

VERSION = "0.1.0"
DEFAULT_BOOTSTRAP_SAMPLES = 2000


def _load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        row = json.loads(raw)
        if not isinstance(row, dict):
            raise ValueError(f"baseline line {line_no} is not an object")
        rows.append(row)
    return rows


def _sha_lines(values: list[str]) -> str:
    payload = "\n".join(sorted(values)) + "\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _baseline_supported(rows: list[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    candidates: list[dict[str, Any]] = []
    channel_keys: list[str] = []
    seen_edges: set[str] = set()
    for row in rows:
        edge_id = str(row.get("edge_id") or "")
        candidate_id = str(row.get("candidate_id") or "")
        if not edge_id or not candidate_id:
            raise ValueError("baseline row missing edge_id/candidate_id")
        if edge_id in seen_edges:
            raise ValueError(f"duplicate edge_id in baseline research: {edge_id}")
        seen_edges.add(edge_id)
        supported_channels: list[str] = []
        for channel, evidence in dict(row.get("research_channels") or {}).items():
            if channel not in {"performance", "value"}:
                raise ValueError(f"unsupported baseline channel: {channel}")
            if bool(evidence.get("ci_supports_direction")):
                supported_channels.append(channel)
                channel_keys.append(f"{edge_id}|{channel}")
        if supported_channels:
            candidates.append({
                "edge_id": edge_id,
                "candidate_id": candidate_id,
                "family": row.get("family"),
                "template_id": row.get("template_id"),
                "polarity": row.get("polarity"),
                "supported_channels": tuple(sorted(supported_channels)),
                "baseline": dict(row),
            })
    return candidates, channel_keys


def _default_evaluator(
    mart_path: str | Path,
    candidate: Mapping[str, Any],
    temporal: Mapping[str, Any],
    bootstrap_samples: int,
) -> dict[str, Any]:
    return baseline_study._default_evaluator(
        mart_path, candidate, temporal, bootstrap_samples
    )


def run_sensitivity(
    mart_path: str | Path,
    registry_path: str | Path,
    registry_audit_path: str | Path,
    baseline_jsonl_path: str | Path,
    *,
    bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    expected_baseline_candidates: int | None = None,
    expected_baseline_channels: int | None = None,
    expected_edge_set_sha256: str | None = None,
    expected_channel_set_sha256: str | None = None,
    evaluator: Callable[[str | Path, Mapping[str, Any], Mapping[str, Any], int], dict[str, Any]] = _default_evaluator,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if bootstrap_samples <= 0:
        raise ValueError("bootstrap_samples must be positive")

    baseline_rows = _load_jsonl(baseline_jsonl_path)
    selected, channel_keys = _baseline_supported(baseline_rows)
    edge_ids = [str(row["edge_id"]) for row in selected]
    edge_hash = _sha_lines(edge_ids)
    channel_hash = _sha_lines(channel_keys)

    if expected_baseline_candidates is not None and len(selected) != expected_baseline_candidates:
        raise ValueError(
            f"baseline supported candidate count mismatch: expected={expected_baseline_candidates} actual={len(selected)}"
        )
    if expected_baseline_channels is not None and len(channel_keys) != expected_baseline_channels:
        raise ValueError(
            f"baseline supported channel count mismatch: expected={expected_baseline_channels} actual={len(channel_keys)}"
        )
    if expected_edge_set_sha256 is not None and edge_hash != expected_edge_set_sha256:
        raise ValueError(
            f"baseline supported edge set hash mismatch: expected={expected_edge_set_sha256} actual={edge_hash}"
        )
    if expected_channel_set_sha256 is not None and channel_hash != expected_channel_set_sha256:
        raise ValueError(
            f"baseline supported channel set hash mismatch: expected={expected_channel_set_sha256} actual={channel_hash}"
        )

    temporal_by_id = baseline_study._load_temporal_audit(registry_audit_path)
    integrity, population = baseline_study._load_population(registry_path)
    population_by_edge = {str(row["edge_id"]): row for row in population}

    output: list[dict[str, Any]] = []
    for item in selected:
        edge_id = str(item["edge_id"])
        candidate_id = str(item["candidate_id"])
        registry_row = population_by_edge.get(edge_id)
        if registry_row is None:
            raise ValueError(f"baseline supported edge missing from sensitivity population: {edge_id}")
        if str(registry_row["candidate_id"]) != candidate_id:
            raise ValueError(f"candidate_id mismatch for {edge_id}")
        temporal = temporal_by_id.get(candidate_id)
        if temporal is None or str(temporal.get("status")) != "ACTIVE":
            raise ValueError(f"temporal ACTIVE audit row missing for {candidate_id}")
        candidate = temporal.get("candidate")
        if not isinstance(candidate, dict):
            raise ValueError(f"candidate payload missing for {candidate_id}")

        detailed = evaluator(mart_path, candidate, temporal, bootstrap_samples)
        channel_results: dict[str, dict[str, Any]] = {}
        for channel in item["supported_channels"]:
            base_evidence = dict(item["baseline"]["research_channels"][channel])
            signal = str(base_evidence.get("signal"))
            stored_p = registry_row.get(f"{channel}_p_value")
            recomputed_p = detailed.get(f"{channel}_p_value")
            if not baseline_study._p_matches(stored_p, recomputed_p):
                raise ValueError(
                    f"{candidate_id} {channel} p-value mismatch: registry={stored_p!r} mart={recomputed_p!r}"
                )
            q_value = registry_row.get(f"{channel}_q_value")
            if not baseline_study.in_research_band(q_value, q_low=0.05, q_high=0.10):
                raise ValueError(f"{candidate_id} {channel} no longer in frozen q band")
            low = detailed.get(f"{channel}_ci_low")
            high = detailed.get(f"{channel}_ci_high")
            retained = baseline_study.ci_supports(signal, low, high)
            channel_results[channel] = {
                "signal": signal,
                "q_value": q_value,
                "baseline_ci_low": base_evidence.get("ci_low"),
                "baseline_ci_high": base_evidence.get("ci_high"),
                "sensitivity_ci_low": low,
                "sensitivity_ci_high": high,
                "retained_support": retained,
            }

        output.append({
            "edge_id": edge_id,
            "candidate_id": candidate_id,
            "family": item["family"],
            "template_id": item["template_id"],
            "polarity": item["polarity"],
            "baseline_bootstrap_samples": int(item["baseline"].get("bootstrap_samples") or 0),
            "sensitivity_bootstrap_samples": bootstrap_samples,
            "channel_results": channel_results,
            "candidate_retained_support": any(v["retained_support"] for v in channel_results.values()),
        })

    report = summarize(output)
    report.update({
        "audit_version": VERSION,
        "integrity_check": integrity,
        "population_temporal_active_rejected": len(population),
        "baseline_supported_candidates": len(selected),
        "baseline_supported_channels": len(channel_keys),
        "baseline_edge_set_sha256": edge_hash,
        "baseline_channel_set_sha256": channel_hash,
        "sensitivity_bootstrap_samples": bootstrap_samples,
    })
    return output, report


def summarize(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    family_total: Counter[str] = Counter()
    family_retained: Counter[str] = Counter()
    template_total: Counter[str] = Counter()
    template_retained: Counter[str] = Counter()
    polarity_total: Counter[str] = Counter()
    polarity_retained: Counter[str] = Counter()
    channel_total: Counter[str] = Counter()
    channel_retained: Counter[str] = Counter()

    retained_candidates = 0
    for row in rows:
        family = str(row.get("family"))
        template = str(row.get("template_id"))
        polarity = str(row.get("polarity"))
        family_total[family] += 1
        template_total[template] += 1
        polarity_total[polarity] += 1
        if bool(row.get("candidate_retained_support")):
            retained_candidates += 1
            family_retained[family] += 1
            template_retained[template] += 1
            polarity_retained[polarity] += 1
        for channel, evidence in dict(row.get("channel_results") or {}).items():
            channel_total[str(channel)] += 1
            if bool(evidence.get("retained_support")):
                channel_retained[str(channel)] += 1

    def nested(total: Counter[str], retained: Counter[str]) -> dict[str, dict[str, int]]:
        return {
            key: {"baseline_supported": total[key], "retained": retained[key], "lost": total[key] - retained[key]}
            for key in sorted(total)
        }

    total_channels = sum(channel_total.values())
    retained_channels = sum(channel_retained.values())
    return {
        "status": "PASS",
        "retained_candidates": retained_candidates,
        "lost_candidates": len(rows) - retained_candidates,
        "retained_channels": retained_channels,
        "lost_channels": total_channels - retained_channels,
        "candidate_retention_rate": (retained_candidates / len(rows)) if rows else 0.0,
        "channel_retention_rate": (retained_channels / total_channels) if total_channels else 0.0,
        "family_counts": nested(family_total, family_retained),
        "template_counts": nested(template_total, template_retained),
        "polarity_counts": nested(polarity_total, polarity_retained),
        "channel_counts": nested(channel_total, channel_retained),
    }


def write_markdown(report: Mapping[str, Any], path: str | Path) -> None:
    lines = [
        "# JRDB Edge SUGGESTIVE Bootstrap Sensitivity Audit",
        "",
        f"- Integrity: `{report['integrity_check']}`",
        f"- Baseline-supported candidates: {report['baseline_supported_candidates']}",
        f"- Baseline-supported channels: {report['baseline_supported_channels']}",
        f"- Sensitivity bootstrap samples: {report['sensitivity_bootstrap_samples']}",
        f"- Candidate retained: {report['retained_candidates']} ({100.0 * report['candidate_retention_rate']:.2f}%)",
        f"- Channel retained: {report['retained_channels']} ({100.0 * report['channel_retention_rate']:.2f}%)",
        "",
        "## Channel",
        "",
        "| Channel | Baseline-supported | Retained | Lost |",
        "|---|---:|---:|---:|",
    ]
    for name, counts in report["channel_counts"].items():
        lines.append(
            f"| {name} | {counts['baseline_supported']} | {counts['retained']} | {counts['lost']} |"
        )
    lines.extend([
        "",
        "> Sensitivity audit only. This output does not change Registry status or Matcher serving behavior.",
    ])
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mart", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--registry-audit", required=True)
    parser.add_argument("--baseline-jsonl", required=True)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--audit-json", required=True)
    parser.add_argument("--audit-md")
    parser.add_argument("--bootstrap-samples", type=int, default=DEFAULT_BOOTSTRAP_SAMPLES)
    parser.add_argument("--expected-baseline-candidates", type=int)
    parser.add_argument("--expected-baseline-channels", type=int)
    parser.add_argument("--expected-edge-set-sha256")
    parser.add_argument("--expected-channel-set-sha256")
    args = parser.parse_args()

    rows, report = run_sensitivity(
        args.mart,
        args.registry,
        args.registry_audit,
        args.baseline_jsonl,
        bootstrap_samples=args.bootstrap_samples,
        expected_baseline_candidates=args.expected_baseline_candidates,
        expected_baseline_channels=args.expected_baseline_channels,
        expected_edge_set_sha256=args.expected_edge_set_sha256,
        expected_channel_set_sha256=args.expected_channel_set_sha256,
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
