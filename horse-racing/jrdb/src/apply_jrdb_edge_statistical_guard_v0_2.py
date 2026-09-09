#!/usr/bin/env python3
"""Apply v0.2 statistical guard with HUMAN residual-aware evaluation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import jrdb_edge_statistical_guard as stats
import apply_jrdb_edge_statistical_guard as guard_base
from build_jrdb_edge_registry import export_registry
from jrdb_edge_human_residual_v0_2 import BASELINE_MODE as HUMAN_BASELINE_MODE, evaluate_human_statistical

VERSION = "0.2.2"
V02_FIELDS = {
    "frame_no", "horse_age", "rotation_interval", "pre_idm", "training_score",
    "stable_score", "uptrend_code", "training_arrow_code", "stable_evaluation_code",
    "body_weight_pre_kg", "body_weight_change_pre_kg", "track_condition_bucket",
}
stats.ALLOWED_FIELDS.update(V02_FIELDS)
_ORIG_EVALUATE = guard_base.evaluate_candidate


def _evaluate_v02(mart_path, candidate, temporal_result, *, bootstrap_samples=stats.DEFAULT_BOOTSTRAP_SAMPLES):
    if candidate.get("baseline") == HUMAN_BASELINE_MODE:
        return evaluate_human_statistical(
            mart_path, candidate, temporal_result, bootstrap_samples=bootstrap_samples
        )
    return _ORIG_EVALUATE(
        mart_path, candidate, temporal_result, bootstrap_samples=bootstrap_samples
    )


guard_base.evaluate_candidate = _evaluate_v02


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mart", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--registry-audit", required=True)
    parser.add_argument("--bootstrap-samples", type=int, default=stats.DEFAULT_BOOTSTRAP_SAMPLES)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--audit-json", required=True)
    parser.add_argument("--export-jsonl")
    parser.add_argument("--export-csv")
    args = parser.parse_args()
    rows, summary = guard_base.apply_guard(
        args.mart, args.registry, args.registry_audit,
        bootstrap_samples=args.bootstrap_samples,
    )
    summary["v02_wrapper_version"] = VERSION
    summary["human_residual_guard"] = "HUMAN_PRE_IDM_EXPANDING_V1"
    with Path(args.output_jsonl).open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    if bool(args.export_jsonl) != bool(args.export_csv):
        raise ValueError("--export-jsonl and --export-csv must be specified together")
    if args.export_jsonl and args.export_csv:
        summary["export"] = export_registry(args.registry, args.export_jsonl, args.export_csv)
    Path(args.audit_json).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
