#!/usr/bin/env python3
"""Apply Phase1 statistical guard to a temporally validated JRDB Edge Registry."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from build_jrdb_edge_registry import export_registry
from jrdb_edge_statistical_guard import (
    DEFAULT_BOOTSTRAP_SAMPLES,
    apply_fdr,
    assign_lineage,
    evaluate_candidate,
    finalize_gate,
)

VERSION = "0.1.0"


def _edge_id(candidate_id: str) -> str:
    if candidate_id.startswith("EDGE-CAND-"):
        return candidate_id.replace("EDGE-CAND-", "EDGE-", 1)
    return "EDGE-" + hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()[:20].upper()


def _q_prepass(record: dict[str, Any]) -> bool:
    status = record["temporal_status"]
    if status not in {"ACTIVE", "PROVISIONAL"}:
        return False
    threshold = 0.05 if status == "ACTIVE" else 0.10
    for signal in ("performance", "value"):
        if record.get(f"{signal}_signal") == "NEUTRAL":
            continue
        q = record.get(f"{signal}_q_value")
        if q is not None and float(q) <= threshold:
            return True
    return False


def apply_guard(
    mart_path: str | Path,
    registry_path: str | Path,
    registry_audit_path: str | Path,
    *,
    bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    audit = json.loads(Path(registry_audit_path).read_text(encoding="utf-8"))
    validation_rows = audit.get("validation_rows")
    if not isinstance(validation_rows, list):
        raise ValueError("registry audit has no validation_rows")

    candidates_by_id: dict[str, dict[str, Any]] = {}
    temporal_by_id: dict[str, dict[str, Any]] = {}
    stat_rows: list[dict[str, Any]] = []
    for temporal in validation_rows:
        candidate = temporal.get("candidate")
        if not isinstance(candidate, dict) or "candidate_id" not in candidate:
            raise ValueError("validation row is missing candidate")
        cid = str(candidate["candidate_id"])
        candidates_by_id[cid] = candidate
        temporal_by_id[cid] = temporal
        stat_rows.append(evaluate_candidate(mart_path, candidate, temporal, bootstrap_samples=0))

    apply_fdr(stat_rows)
    bootstrap_evaluated = 0
    for index, row in enumerate(stat_rows):
        if not _q_prepass(row):
            stat_rows[index] = finalize_gate(row)
            continue
        cid = str(row["candidate_id"])
        detailed = evaluate_candidate(
            mart_path,
            candidates_by_id[cid],
            temporal_by_id[cid],
            bootstrap_samples=bootstrap_samples,
        )
        detailed["performance_q_value"] = row.get("performance_q_value")
        detailed["value_q_value"] = row.get("value_q_value")
        stat_rows[index] = finalize_gate(detailed)
        bootstrap_evaluated += 1

    assign_lineage(stat_rows, candidates_by_id)

    con = sqlite3.connect(registry_path)
    try:
        con.execute("""
          CREATE TABLE IF NOT EXISTS edge_statistical_guard(
            edge_id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            hypothesis_family TEXT NOT NULL,
            temporal_status TEXT NOT NULL,
            statistical_status TEXT NOT NULL,
            performance_p_value REAL,
            performance_q_value REAL,
            value_p_value REAL,
            value_q_value REAL,
            performance_ci_low REAL,
            performance_ci_high REAL,
            value_ci_low REAL,
            value_ci_high REAL,
            performance_stat_pass INTEGER NOT NULL,
            value_stat_pass INTEGER NOT NULL,
            parent_candidate_id TEXT,
            redundancy_group_id TEXT,
            multiple_testing_version TEXT NOT NULL,
            bootstrap_samples INTEGER NOT NULL,
            evidence_json TEXT NOT NULL,
            FOREIGN KEY(edge_id) REFERENCES edge_definition(edge_id)
          )
        """)
        existing = {r[0] for r in con.execute("SELECT edge_id FROM edge_definition")}
        downgraded = 0
        stored_guard_rows = 0
        for row in stat_rows:
            edge_id = _edge_id(str(row["candidate_id"]))
            if edge_id not in existing:
                continue
            con.execute(
                """INSERT OR REPLACE INTO edge_statistical_guard(
                  edge_id,candidate_id,hypothesis_family,temporal_status,statistical_status,
                  performance_p_value,performance_q_value,value_p_value,value_q_value,
                  performance_ci_low,performance_ci_high,value_ci_low,value_ci_high,
                  performance_stat_pass,value_stat_pass,parent_candidate_id,redundancy_group_id,
                  multiple_testing_version,bootstrap_samples,evidence_json
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    edge_id,
                    row["candidate_id"],
                    row["hypothesis_family"],
                    row["temporal_status"],
                    row["statistical_status"],
                    row.get("performance_p_value"),
                    row.get("performance_q_value"),
                    row.get("value_p_value"),
                    row.get("value_q_value"),
                    row.get("performance_ci_low"),
                    row.get("performance_ci_high"),
                    row.get("value_ci_low"),
                    row.get("value_ci_high"),
                    int(bool(row.get("performance_stat_pass"))),
                    int(bool(row.get("value_stat_pass"))),
                    row.get("parent_candidate_id"),
                    row.get("redundancy_group_id"),
                    row["multiple_testing_version"],
                    int(row.get("bootstrap_samples") or 0),
                    json.dumps(row, ensure_ascii=False, sort_keys=True),
                ),
            )
            if (
                row["temporal_status"] in {"ACTIVE", "PROVISIONAL"}
                and row["statistical_status"] == "WATCH"
            ):
                con.execute("UPDATE edge_definition SET status='WATCH' WHERE edge_id=?", (edge_id,))
                downgraded += 1
            stored_guard_rows += 1
        con.commit()
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError(
                f"Edge Registry integrity_check failed after statistical guard: {integrity}"
            )
    finally:
        con.close()

    temporal_counts = Counter(str(row["temporal_status"]) for row in stat_rows)
    statistical_counts = Counter(str(row["statistical_status"]) for row in stat_rows)
    summary = {
        "status": "PASS",
        "guard_version": VERSION,
        "validated_candidates": len(stat_rows),
        "stored_guard_rows": stored_guard_rows,
        "bootstrap_evaluated": bootstrap_evaluated,
        "downgraded_to_watch": downgraded,
        "temporal_counts": dict(sorted(temporal_counts.items())),
        "statistical_counts": dict(sorted(statistical_counts.items())),
        "performance_stat_pass": sum(
            bool(row.get("performance_stat_pass")) for row in stat_rows
        ),
        "value_stat_pass": sum(bool(row.get("value_stat_pass")) for row in stat_rows),
        "integrity_check": integrity,
    }
    return stat_rows, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mart", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--registry-audit", required=True)
    parser.add_argument(
        "--bootstrap-samples", type=int, default=DEFAULT_BOOTSTRAP_SAMPLES
    )
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--audit-json", required=True)
    parser.add_argument("--export-jsonl")
    parser.add_argument("--export-csv")
    args = parser.parse_args()

    rows, summary = apply_guard(
        args.mart,
        args.registry,
        args.registry_audit,
        bootstrap_samples=args.bootstrap_samples,
    )
    with Path(args.output_jsonl).open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    if bool(args.export_jsonl) != bool(args.export_csv):
        raise ValueError("--export-jsonl and --export-csv must be specified together")
    if args.export_jsonl and args.export_csv:
        summary["export"] = export_registry(
            args.registry, args.export_jsonl, args.export_csv
        )
    Path(args.audit_json).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
