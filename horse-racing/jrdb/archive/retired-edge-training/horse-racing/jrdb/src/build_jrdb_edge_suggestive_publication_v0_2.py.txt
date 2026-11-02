#!/usr/bin/env python3
"""Build v0.2 Edge serving publication with channel-specific SUGGESTIVE evidence.

This builder is sidecar-only. It never mutates the Registry, never changes ACTIVE
status, and never rewrites the legacy edge_registry_active.jsonl export.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Mapping

VERSION = "0.2.0"
SUGGESTIVE_BOOTSTRAP_SAMPLES = 2000
Q_LOW = 0.05
Q_HIGH = 0.10


def _load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        row = json.loads(raw)
        if not isinstance(row, dict):
            raise ValueError(f"JSONL line {line_no} is not an object")
        rows.append(row)
    return rows


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _same_number(left: Any, right: Any, *, atol: float = 1e-12) -> bool:
    if left is None or right is None:
        return left is None and right is None
    return math.isclose(float(left), float(right), rel_tol=1e-10, abs_tol=atol)


def _load_registry_rows(registry_path: str | Path) -> tuple[str, str, dict[str, dict[str, Any]]]:
    connection = sqlite3.connect(registry_path)
    connection.row_factory = sqlite3.Row
    try:
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        if integrity != "ok":
            raise ValueError(f"registry integrity_check failed: {integrity}")
        meta = connection.execute(
            "SELECT * FROM edge_registry_meta ORDER BY generated_at DESC LIMIT 1"
        ).fetchone()
        if meta is None:
            raise ValueError("edge_registry_meta is missing")
        rows = connection.execute(
            """
            SELECT d.*,
                   m.sample_n,m.unique_horses,m.unique_races,m.win_rate,m.place_rate,
                   m.win_roi,m.place_roi,m.baseline_place_rate,m.performance_lift,
                   m.largest_return_share,m.top3_return_share,m.largest_horse_sample_share,
                   g.candidate_id,g.hypothesis_family AS template_id,
                   g.temporal_status,g.statistical_status,
                   g.performance_p_value,g.performance_q_value,
                   g.value_p_value,g.value_q_value,
                   g.performance_ci_low AS guard_performance_ci_low,
                   g.performance_ci_high AS guard_performance_ci_high,
                   g.value_ci_low AS guard_value_ci_low,
                   g.value_ci_high AS guard_value_ci_high,
                   g.performance_stat_pass,g.value_stat_pass,
                   g.redundancy_group_id,g.multiple_testing_version,
                   g.bootstrap_samples AS guard_bootstrap_samples
            FROM edge_definition AS d
            JOIN edge_metric_snapshot AS m
              ON m.edge_id=d.edge_id AND m.slice_kind='ALL' AND m.slice_label='all'
            JOIN edge_statistical_guard AS g ON g.edge_id=d.edge_id
            ORDER BY d.edge_id
            """
        ).fetchall()
        output: dict[str, dict[str, Any]] = {}
        for row in rows:
            payload = dict(row)
            payload["conditions"] = json.loads(str(payload.pop("conditions_json")))
            edge_id = str(payload["edge_id"])
            if edge_id in output:
                raise ValueError(f"duplicate edge_id in Registry join: {edge_id}")
            output[edge_id] = payload
        return integrity, str(meta["registry_version"]), output
    finally:
        connection.close()


def _confirmed_levels(row: Mapping[str, Any]) -> tuple[str, str]:
    if str(row.get("status")) != "ACTIVE":
        return "NONE", "NONE"
    performance = "CONFIRMED" if bool(row.get("performance_stat_pass")) else "NONE"
    value = "CONFIRMED" if bool(row.get("value_stat_pass")) else "NONE"
    return performance, value


def _suggestive_levels(
    row: Mapping[str, Any], sensitivity: Mapping[str, Any]
) -> tuple[str, str, dict[str, dict[str, Any]]]:
    if str(row.get("status")) != "REJECTED":
        raise ValueError(f"SUGGESTIVE edge must remain REJECTED: {row.get('edge_id')}")
    if str(row.get("temporal_status")) != "ACTIVE":
        raise ValueError(f"SUGGESTIVE edge temporal_status must be ACTIVE: {row.get('edge_id')}")
    if str(row.get("statistical_status")) != "WATCH":
        raise ValueError(f"SUGGESTIVE edge statistical_status must be WATCH: {row.get('edge_id')}")
    if int(sensitivity.get("sensitivity_bootstrap_samples") or 0) != SUGGESTIVE_BOOTSTRAP_SAMPLES:
        raise ValueError(f"SUGGESTIVE sensitivity samples must be {SUGGESTIVE_BOOTSTRAP_SAMPLES}: {row.get('edge_id')}")

    channel_results = sensitivity.get("channel_results")
    if not isinstance(channel_results, Mapping):
        raise ValueError(f"channel_results missing for {row.get('edge_id')}")

    published: dict[str, dict[str, Any]] = {}
    levels = {"performance": "NONE", "value": "NONE"}
    for channel in ("performance", "value"):
        evidence = channel_results.get(channel)
        if not isinstance(evidence, Mapping) or not bool(evidence.get("retained_support")):
            continue
        signal = str(row.get(f"{channel}_signal") or "NEUTRAL")
        if signal == "NEUTRAL":
            raise ValueError(f"retained {channel} channel is neutral: {row.get('edge_id')}")
        if str(evidence.get("signal")) != signal:
            raise ValueError(f"{channel} signal mismatch for {row.get('edge_id')}")
        stored_q = row.get(f"{channel}_q_value")
        if stored_q is None or not (Q_LOW < float(stored_q) <= Q_HIGH):
            raise ValueError(f"{channel} q outside SUGGESTIVE band for {row.get('edge_id')}: {stored_q}")
        if not _same_number(stored_q, evidence.get("q_value")):
            raise ValueError(f"{channel} q mismatch for {row.get('edge_id')}")
        low = evidence.get("sensitivity_ci_low")
        high = evidence.get("sensitivity_ci_high")
        if low is None or high is None:
            raise ValueError(f"{channel} sensitivity CI missing for {row.get('edge_id')}")
        if signal == "POSITIVE" and float(low) <= 0.0:
            raise ValueError(f"{channel} POSITIVE CI does not exclude zero for {row.get('edge_id')}")
        if signal == "NEGATIVE" and float(high) >= 0.0:
            raise ValueError(f"{channel} NEGATIVE CI does not exclude zero for {row.get('edge_id')}")
        levels[channel] = "SUGGESTIVE"
        published[channel] = {
            "signal": signal,
            "p_value": row.get(f"{channel}_p_value"),
            "q_value": stored_q,
            "ci_low": low,
            "ci_high": high,
            "bootstrap_samples": SUGGESTIVE_BOOTSTRAP_SAMPLES,
        }

    if not published:
        raise ValueError(f"sensitivity row has no retained channels: {row.get('edge_id')}")
    return levels["performance"], levels["value"], published


def _base_publication_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "edge_id": row["edge_id"],
        "candidate_id": row.get("candidate_id"),
        "registry_status": row["status"],
        "status": row["status"],
        "family": row["family"],
        "anchor_type": row.get("anchor_type"),
        "anchor_name": row.get("anchor_name"),
        "validation_class": row.get("validation_class"),
        "policy_id": row.get("policy_id"),
        "polarity": row["polarity"],
        "performance_signal": row.get("performance_signal"),
        "value_signal": row.get("value_signal"),
        "conditions": row["conditions"],
        "display_text": row["display_text"],
        "edge_cluster": row.get("edge_cluster"),
        "parent_edge_id": row.get("parent_edge_id"),
        "specificity": row.get("specificity"),
        "first_observed_date": row.get("first_observed_date"),
        "last_observed_date": row.get("last_observed_date"),
        "last_validated_at": row.get("last_validated_at"),
        "next_review_at": row.get("next_review_at"),
        "expires_at": row.get("expires_at"),
        "strength_score": row.get("strength_score"),
        "confidence_band": row.get("confidence_band"),
        "sample_n": row.get("sample_n"),
        "unique_horses": row.get("unique_horses"),
        "unique_races": row.get("unique_races"),
        "win_rate": row.get("win_rate"),
        "place_rate": row.get("place_rate"),
        "win_roi": row.get("win_roi"),
        "place_roi": row.get("place_roi"),
        "baseline_place_rate": row.get("baseline_place_rate"),
        "performance_lift": row.get("performance_lift"),
        "largest_return_share": row.get("largest_return_share"),
        "top3_return_share": row.get("top3_return_share"),
        "largest_horse_sample_share": row.get("largest_horse_sample_share"),
        "performance_p_value": row.get("performance_p_value"),
        "performance_q_value": row.get("performance_q_value"),
        "value_p_value": row.get("value_p_value"),
        "value_q_value": row.get("value_q_value"),
        "redundancy_group_id": row.get("redundancy_group_id"),
        "multiple_testing_version": row.get("multiple_testing_version"),
        "registry_version": row.get("registry_version"),
    }


def build_publication(
    registry_path: str | Path,
    sensitivity_jsonl_path: str | Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    integrity, registry_version, registry = _load_registry_rows(registry_path)
    sensitivity_rows = _load_jsonl(sensitivity_jsonl_path)
    sensitivity_by_edge: dict[str, dict[str, Any]] = {}
    for item in sensitivity_rows:
        edge_id = str(item.get("edge_id") or "")
        if not edge_id:
            raise ValueError("sensitivity row missing edge_id")
        if edge_id in sensitivity_by_edge:
            raise ValueError(f"duplicate edge_id in sensitivity input: {edge_id}")
        if bool(item.get("candidate_retained_support")):
            sensitivity_by_edge[edge_id] = item

    suggestive_rows: list[dict[str, Any]] = []
    for edge_id in sorted(sensitivity_by_edge):
        row = registry.get(edge_id)
        if row is None:
            raise ValueError(f"sensitivity edge missing from Registry: {edge_id}")
        sensitivity = sensitivity_by_edge[edge_id]
        if str(row.get("candidate_id")) != str(sensitivity.get("candidate_id")):
            raise ValueError(f"candidate_id mismatch for {edge_id}")
        if str(row.get("family")) != str(sensitivity.get("family")):
            raise ValueError(f"family mismatch for {edge_id}")
        if str(row.get("template_id")) != str(sensitivity.get("template_id")):
            raise ValueError(f"template_id mismatch for {edge_id}")
        performance_level, value_level, research_evidence = _suggestive_levels(row, sensitivity)
        payload = _base_publication_row(row)
        payload.update({
            "performance_evidence_level": performance_level,
            "value_evidence_level": value_level,
            "research_version": VERSION,
            "suggestive_bootstrap_samples": SUGGESTIVE_BOOTSTRAP_SAMPLES,
            "suggestive_evidence": research_evidence,
        })
        suggestive_rows.append(payload)

    active_rows: list[dict[str, Any]] = []
    for edge_id in sorted(registry):
        row = registry[edge_id]
        if str(row.get("status")) != "ACTIVE":
            continue
        performance_level, value_level = _confirmed_levels(row)
        if performance_level == "NONE" and value_level == "NONE":
            raise ValueError(f"ACTIVE edge has no confirmed channel: {edge_id}")
        payload = _base_publication_row(row)
        payload.update({
            "performance_evidence_level": performance_level,
            "value_evidence_level": value_level,
            "research_version": None,
            "suggestive_bootstrap_samples": None,
            "suggestive_evidence": {},
        })
        payload["confirmed_evidence"] = {
            "performance": {
                "signal": row.get("performance_signal"),
                "p_value": row.get("performance_p_value"),
                "q_value": row.get("performance_q_value"),
                "ci_low": row.get("guard_performance_ci_low"),
                "ci_high": row.get("guard_performance_ci_high"),
                "bootstrap_samples": row.get("guard_bootstrap_samples"),
            } if performance_level == "CONFIRMED" else None,
            "value": {
                "signal": row.get("value_signal"),
                "p_value": row.get("value_p_value"),
                "q_value": row.get("value_q_value"),
                "ci_low": row.get("guard_value_ci_low"),
                "ci_high": row.get("guard_value_ci_high"),
                "bootstrap_samples": row.get("guard_bootstrap_samples"),
            } if value_level == "CONFIRMED" else None,
        }
        active_rows.append(payload)

    serving_rows = active_rows + suggestive_rows
    serving_rows.sort(
        key=lambda row: (
            0 if str(row["registry_status"]) == "ACTIVE" else 1,
            str(row.get("redundancy_group_id") or ""),
            -int(row.get("specificity") or 0),
            str(row["edge_id"]),
        )
    )
    suggestive_rows.sort(key=lambda row: str(row["edge_id"]))

    performance_suggestive = sum(
        row["performance_evidence_level"] == "SUGGESTIVE" for row in suggestive_rows
    )
    value_suggestive = sum(
        row["value_evidence_level"] == "SUGGESTIVE" for row in suggestive_rows
    )
    both_suggestive = sum(
        row["performance_evidence_level"] == "SUGGESTIVE"
        and row["value_evidence_level"] == "SUGGESTIVE"
        for row in suggestive_rows
    )
    performance_confirmed = sum(
        row["performance_evidence_level"] == "CONFIRMED" for row in active_rows
    )
    value_confirmed = sum(
        row["value_evidence_level"] == "CONFIRMED" for row in active_rows
    )
    report = {
        "status": "PASS",
        "builder_version": VERSION,
        "integrity_check": integrity,
        "registry_version": registry_version,
        "active_rows": len(active_rows),
        "suggestive_rows": len(suggestive_rows),
        "serving_rows": len(serving_rows),
        "confirmed_performance_channels": performance_confirmed,
        "confirmed_value_channels": value_confirmed,
        "suggestive_performance_channels": performance_suggestive,
        "suggestive_value_channels": value_suggestive,
        "suggestive_both_channels": both_suggestive,
        "suggestive_total_channels": performance_suggestive + value_suggestive,
        "sensitivity_input_rows": len(sensitivity_rows),
        "sensitivity_retained_candidates": len(sensitivity_by_edge),
        "suggestive_bootstrap_samples": SUGGESTIVE_BOOTSTRAP_SAMPLES,
        "q_band": {"low_exclusive": Q_LOW, "high_inclusive": Q_HIGH},
    }
    return suggestive_rows, serving_rows, report


def _write_jsonl(rows: Iterable[Mapping[str, Any]], path: str | Path) -> None:
    with Path(path).open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True)
    parser.add_argument("--sensitivity-jsonl", required=True)
    parser.add_argument("--output-suggestive-jsonl", required=True)
    parser.add_argument("--output-serving-jsonl", required=True)
    parser.add_argument("--audit-json", required=True)
    parser.add_argument("--expected-registry-version")
    parser.add_argument("--expected-suggestive-rows", type=int)
    parser.add_argument("--expected-suggestive-channels", type=int)
    args = parser.parse_args()

    suggestive_rows, serving_rows, report = build_publication(
        args.registry, args.sensitivity_jsonl
    )
    if args.expected_registry_version and report["registry_version"] != args.expected_registry_version:
        raise ValueError(
            f"registry_version mismatch: expected={args.expected_registry_version} actual={report['registry_version']}"
        )
    if args.expected_suggestive_rows is not None and report["suggestive_rows"] != args.expected_suggestive_rows:
        raise ValueError(
            f"suggestive row count mismatch: expected={args.expected_suggestive_rows} actual={report['suggestive_rows']}"
        )
    if args.expected_suggestive_channels is not None and report["suggestive_total_channels"] != args.expected_suggestive_channels:
        raise ValueError(
            f"suggestive channel count mismatch: expected={args.expected_suggestive_channels} actual={report['suggestive_total_channels']}"
        )

    _write_jsonl(suggestive_rows, args.output_suggestive_jsonl)
    _write_jsonl(serving_rows, args.output_serving_jsonl)
    report.update({
        "registry_sha256": _sha256_file(args.registry),
        "sensitivity_sha256": _sha256_file(args.sensitivity_jsonl),
        "suggestive_sha256": _sha256_file(args.output_suggestive_jsonl),
        "serving_catalog_sha256": _sha256_file(args.output_serving_jsonl),
    })
    Path(args.audit_json).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
