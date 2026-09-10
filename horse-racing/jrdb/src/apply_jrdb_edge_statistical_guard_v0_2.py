#!/usr/bin/env python3
"""Apply v0.2 statistical guard with HUMAN residual-aware evaluation.

v0.2 keeps temporal WATCH as WATCH, but maps candidates that were temporally
ACTIVE/PROVISIONAL and then fail the statistical guard to final Registry
REJECTED. The underlying statistical_status remains WATCH for compatibility
with the v0.1 statistical-guard contract and audit history.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import jrdb_edge_statistical_guard as stats
import apply_jrdb_edge_statistical_guard as guard_base
from build_jrdb_edge_registry import export_registry
from jrdb_edge_human_residual_v0_2 import BASELINE_MODE as HUMAN_BASELINE_MODE, evaluate_human_statistical

VERSION = "0.2.3"
STATISTICAL_REJECT_REASON = "STATISTICAL_GUARD_REJECTED"
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


def reclassify_statistical_rejects(registry_path: str | Path) -> dict[str, int | str]:
    """Map v0.2 statistical downgrades to final Registry REJECTED.

    The base v0.1 guard remains unchanged. This v0.2-only post-processing keeps
    the guard row's statistical_status=WATCH while making the final Registry
    state explicit and appending a REJECT validation event.
    """
    con = sqlite3.connect(registry_path)
    con.row_factory = sqlite3.Row
    now = datetime.now(timezone.utc).isoformat()
    try:
        policy_row = con.execute(
            "SELECT policy_version FROM edge_registry_meta ORDER BY generated_at DESC LIMIT 1"
        ).fetchone()
        if policy_row is None:
            raise ValueError("edge_registry_meta is missing")
        policy_version = str(policy_row["policy_version"])
        rows = con.execute(
            """
            SELECT d.edge_id, d.policy_id, g.evidence_json
            FROM edge_definition AS d
            JOIN edge_statistical_guard AS g ON g.edge_id=d.edge_id
            WHERE d.status='WATCH'
              AND g.temporal_status IN ('ACTIVE','PROVISIONAL')
              AND g.statistical_status='WATCH'
            ORDER BY d.edge_id
            """
        ).fetchall()
        for row in rows:
            evidence = {
                "source": "v0.2_statistical_guard_final_status_mapping",
                "reason": STATISTICAL_REJECT_REASON,
                "guard": json.loads(str(row["evidence_json"])),
            }
            con.execute(
                """UPDATE edge_definition
                   SET status='REJECTED', confidence_band='R', updated_at=?
                   WHERE edge_id=?""",
                (now, row["edge_id"]),
            )
            con.execute(
                """INSERT INTO edge_validation_event(
                     edge_id,evaluated_at,policy_id,policy_version,decision,failure_reason,evidence_json
                   ) VALUES(?,?,?,?,?,?,?)""",
                (
                    row["edge_id"], now, row["policy_id"], policy_version,
                    "REJECT", STATISTICAL_REJECT_REASON,
                    json.dumps(evidence, ensure_ascii=False, sort_keys=True),
                ),
            )
        con.commit()
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError(f"Edge Registry integrity_check failed after v0.2 status mapping: {integrity}")
        final_watch = int(con.execute(
            "SELECT COUNT(*) FROM edge_definition WHERE status='WATCH'"
        ).fetchone()[0])
        final_rejected = int(con.execute(
            "SELECT COUNT(*) FROM edge_definition WHERE status='REJECTED'"
        ).fetchone()[0])
        return {
            "statistical_rejected": len(rows),
            "final_watch": final_watch,
            "final_rejected": final_rejected,
            "integrity_check": integrity,
        }
    finally:
        con.close()


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
    status_mapping = reclassify_statistical_rejects(args.registry)
    summary["v02_wrapper_version"] = VERSION
    summary["human_residual_guard"] = "HUMAN_PRE_IDM_EXPANDING_V1"
    summary["final_status_mapping"] = "TEMPORAL_WATCH_STAYS_WATCH__STATISTICAL_DOWNGRADE_TO_REJECTED"
    summary.update(status_mapping)
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
