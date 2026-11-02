#!/usr/bin/env python3
"""Apply the frozen JRDB Edge v0.3 Stage-B2b Performance gate in SHADOW_ONLY mode.

The input is the immutable Stage-B2a statistical artifact. This program is
purely deterministic: it does not query race results, tune thresholds, build a
production catalog, or mutate v0.2 serving.

Value promotion remains fail-closed until a separate inferential Value policy is
frozen.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

VERSION = "0.3.0-stage-b2b"


class GatePolicyError(RuntimeError):
    """Raised when the frozen gate policy or immutable input is inconsistent."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GatePolicyError(f"JSON object required: {path}")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise GatePolicyError(f"{path}:{number}: object required")
        output.append(value)
    return output


def _require_number(value: Any, label: str) -> float:
    if value is None:
        raise GatePolicyError(f"missing numeric diagnostic: {label}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise GatePolicyError(f"invalid numeric diagnostic: {label}") from exc


def _classify(row: Mapping[str, Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    performance = row.get("performance")
    if not isinstance(performance, Mapping):
        raise GatePolicyError(f"{row.get('edge_id')}: performance diagnostics missing")

    gate = policy["performance_gate"]
    temporal_policy = gate["temporal"]
    temporal = performance.get("temporal_sensitivity")
    if not isinstance(temporal, Mapping):
        raise GatePolicyError(f"{row.get('edge_id')}: temporal diagnostics missing")

    yearly_min = int(temporal_policy["yearly_min_child_n"])
    if yearly_min != int(temporal_policy["yearly_min_parent_complement_n"]):
        raise GatePolicyError("current policy requires equal child/complement yearly minima")
    temporal_row = temporal.get(str(yearly_min))
    if not isinstance(temporal_row, Mapping):
        raise GatePolicyError(
            f"{row.get('edge_id')}: temporal sensitivity n={yearly_min} missing"
        )

    q_value = _require_number(
        performance.get("q_value_global_bh"),
        f"{row.get('edge_id')}.q_value_global_bh",
    )
    q_max = float(gate["multiple_testing"]["q_max"])
    q_pass = q_value <= q_max

    bootstrap = performance.get("bootstrap")
    if not isinstance(bootstrap, Mapping):
        raise GatePolicyError(f"{row.get('edge_id')}: bootstrap diagnostics missing")
    bootstrap_pass = bool(
        bootstrap.get("ci_excludes_zero_in_full_direction")
    )

    eligible_years = int(temporal_row.get("eligible_years") or 0)
    min_eligible_years = int(temporal_policy["min_eligible_years"])
    coverage_pass = eligible_years >= min_eligible_years

    full_consistency_raw = temporal_row.get("sign_consistency")
    recent_consistency_raw = temporal_row.get("recent4_sign_consistency")
    full_consistency = (
        float(full_consistency_raw) if full_consistency_raw is not None else None
    )
    recent_consistency = (
        float(recent_consistency_raw) if recent_consistency_raw is not None else None
    )
    full_min = float(temporal_policy["min_full_period_same_direction_fraction"])
    recent_min = float(temporal_policy["min_recent_same_direction_fraction"])
    full_pass = full_consistency is not None and full_consistency >= full_min
    recent_pass = recent_consistency is not None and recent_consistency >= recent_min

    checks = {
        "global_fdr_q": {
            "pass": q_pass,
            "actual": q_value,
            "maximum": q_max,
        },
        "bootstrap_ci": {
            "pass": bootstrap_pass,
            "confidence": bootstrap.get("confidence"),
            "ci_low": bootstrap.get("ci_low"),
            "ci_high": bootstrap.get("ci_high"),
        },
        "temporal_coverage": {
            "pass": coverage_pass,
            "yearly_min_each_group_n": yearly_min,
            "actual_eligible_years": eligible_years,
            "minimum_eligible_years": min_eligible_years,
        },
        "temporal_full_direction": {
            "pass": full_pass,
            "actual": full_consistency,
            "minimum": full_min,
        },
        "temporal_recent_direction": {
            "pass": recent_pass,
            "recent_eligible_year_count": int(
                temporal_policy["recent_eligible_year_count"]
            ),
            "actual": recent_consistency,
            "minimum": recent_min,
        },
    }

    failed = [name for name, value in checks.items() if not value["pass"]]
    if not coverage_pass:
        shadow_class = policy["classification"]["insufficient_temporal_coverage"]
        reason = "TEMPORAL_COVERAGE_INSUFFICIENT"
    elif failed:
        shadow_class = policy["classification"]["sufficient_but_gate_fail"]
        reason = "INCREMENTAL_PERFORMANCE_GATE_FAIL"
    else:
        shadow_class = policy["classification"]["performance_pass"]
        reason = "INCREMENTAL_PERFORMANCE_GATE_PASS"

    metrics = row.get("b1_metrics")
    if not isinstance(metrics, Mapping):
        raise GatePolicyError(f"{row.get('edge_id')}: B1 metrics missing")
    incremental_direction = str(
        metrics.get("incremental_performance_direction") or "UNASSESSED"
    ).upper()
    current_direction = str(row.get("current_performance_signal") or "").upper()
    is_reversal = (
        incremental_direction in {"POSITIVE", "NEGATIVE"}
        and current_direction in {"POSITIVE", "NEGATIVE"}
        and incremental_direction != current_direction
    )

    return {
        **dict(row),
        "stage_b2b": {
            "shadow_class": shadow_class,
            "reason": reason,
            "performance_gate_pass": not failed,
            "failed_checks": failed,
            "checks": checks,
            "incremental_performance_direction": incremental_direction,
            "v02_performance_direction": current_direction,
            "is_reversal_vs_v02": is_reversal,
            "value_gate": "DEFERRED_FAIL_CLOSED",
        },
    }


def run(
    *,
    policy_path: Path,
    b2a_jsonl: Path,
    b2a_summary: Path,
    output_jsonl: Path,
    output_summary: Path,
) -> dict[str, Any]:
    policy = _load_json(policy_path)
    if policy.get("mode") != "SHADOW_ONLY":
        raise GatePolicyError("B2b policy must be SHADOW_ONLY")
    if policy.get("value_gate", {}).get("status") != "DEFERRED_FAIL_CLOSED":
        raise GatePolicyError("Value gate must remain fail-closed in this policy")

    source = policy.get("source")
    if not isinstance(source, Mapping):
        raise GatePolicyError("policy source metadata missing")
    actual_jsonl_sha = _sha256(b2a_jsonl)
    actual_summary_sha = _sha256(b2a_summary)
    if actual_jsonl_sha != source.get("statistical_edges_sha256"):
        raise GatePolicyError(
            f"B2a statistical_edges SHA mismatch: {actual_jsonl_sha}"
        )
    if actual_summary_sha != source.get("summary_sha256"):
        raise GatePolicyError(f"B2a summary SHA mismatch: {actual_summary_sha}")

    summary_input = _load_json(b2a_summary)
    if summary_input.get("status") != "PASS":
        raise GatePolicyError("B2a summary is not PASS")
    if summary_input.get("mode") != "SHADOW_ONLY":
        raise GatePolicyError("B2a summary is not SHADOW_ONLY")
    if summary_input.get("threshold_policy") != "NOT_FROZEN":
        raise GatePolicyError("B2a threshold policy must be NOT_FROZEN")

    rows = _load_jsonl(b2a_jsonl)
    expected = int(summary_input.get("b2_metrics_ready") or 0)
    if len(rows) != expected:
        raise GatePolicyError(
            f"B2a row count mismatch: expected={expected} actual={len(rows)}"
        )

    output_rows = [_classify(row, policy) for row in rows]
    with output_jsonl.open("w", encoding="utf-8", newline="\n") as handle:
        for row in output_rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    classes = Counter()
    template_pass = Counter()
    direction_pass = Counter()
    failure_checks = Counter()
    reversal_pass = 0
    for row in output_rows:
        b2b = row["stage_b2b"]
        shadow_class = str(b2b["shadow_class"])
        classes[shadow_class] += 1
        for check in b2b["failed_checks"]:
            failure_checks[str(check)] += 1
        if b2b["performance_gate_pass"]:
            template_pass[str(row.get("template_id") or "")] += 1
            direction_pass[str(b2b["incremental_performance_direction"])] += 1
            if b2b["is_reversal_vs_v02"]:
                reversal_pass += 1

    pass_class = policy["classification"]["performance_pass"]
    passed = int(classes[pass_class])
    summary = {
        "status": "PASS",
        "version": VERSION,
        "stage": "B2B_FROZEN_PERFORMANCE_GATE",
        "mode": "SHADOW_ONLY",
        "policy_id": policy.get("policy_id"),
        "policy_sha256": _sha256(policy_path),
        "b2a_run_id": source.get("b2a_run_id"),
        "b2a_statistical_edges_sha256": actual_jsonl_sha,
        "b2a_summary_sha256": actual_summary_sha,
        "input_rows": len(output_rows),
        "shadow_class_counts": dict(sorted(classes.items())),
        "incremental_performance_pass": passed,
        "incremental_performance_pass_rate": (
            passed / len(output_rows) if output_rows else None
        ),
        "pass_template_counts": dict(sorted(template_pass.items())),
        "pass_direction_counts": dict(sorted(direction_pass.items())),
        "pass_reversal_vs_v02": reversal_pass,
        "failed_check_counts": dict(sorted(failure_checks.items())),
        "value_gate": "DEFERRED_FAIL_CLOSED",
        "threshold_policy": "FROZEN_B2B_PERFORMANCE_ONLY",
        "production_serving_changed": False,
        "note": (
            "Frozen Performance gates applied to the immutable B2a diagnostics. "
            "Value promotion remains fail-closed. No v0.2 production serving or "
            "Newspaper/RaceNote route is changed."
        ),
    }
    output_summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--b2a-jsonl", type=Path, required=True)
    parser.add_argument("--b2a-summary", type=Path, required=True)
    parser.add_argument("--output-jsonl", type=Path, required=True)
    parser.add_argument("--output-summary", type=Path, required=True)
    args = parser.parse_args()
    result = run(
        policy_path=args.policy,
        b2a_jsonl=args.b2a_jsonl,
        b2a_summary=args.b2a_summary,
        output_jsonl=args.output_jsonl,
        output_summary=args.output_summary,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
