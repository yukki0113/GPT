#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RaceReviewDB Next-Watch Turn 6 frozen-rule Holdout validation."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import shutil
import zipfile
from pathlib import Path

import duckdb

ARTIFACT_TYPE = "jrdb_next_watch_holdout_validation"
VALIDATION_VERSION = "next-watch-holdout-v0.1"


class Turn6Error(RuntimeError):
    """Raised when Holdout validation violates the frozen contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _literal(path: Path) -> str:
    return str(path).replace("'", "''")


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Turn6Error(f"JSON object required: {path}")
    return value


def _extract(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    with zipfile.ZipFile(source) as archive:
        archive.extractall(target)


def _find_turn3(turn3_zip: Path, work_root: Path) -> tuple[Path, dict[str, object]]:
    target = work_root / "turn3"
    _extract(turn3_zip, target)
    facts = list(target.rglob("next_watch_backtest_fact.parquet"))
    audits = list(target.rglob("next_start_audit.json"))
    if len(facts) != 1 or len(audits) != 1:
        raise Turn6Error("unique Turn3 fact/audit required")
    audit = _json(audits[0])
    if audit.get("status") != "PASS":
        raise Turn6Error("Turn3 checkpoint is not PASS")
    return facts[0], audit


def _find_turn5(turn5_zip: Path, work_root: Path) -> dict[str, object]:
    target = work_root / "turn5"
    _extract(turn5_zip, target)
    rules = list(target.rglob("next_watch_candidate_rules_frozen.json"))
    if len(rules) != 1:
        raise Turn6Error("unique Turn5 frozen-rule contract required")
    contract = _json(rules[0])
    if contract.get("status") != "CANDIDATE_RULES_FROZEN":
        raise Turn6Error("Turn5 rules are not frozen")
    if contract.get("holdout_consulted") is not False:
        raise Turn6Error("Turn5 contract indicates Holdout was consulted")
    return contract


def _metrics(
    connection: duckdb.DuckDBPyConnection,
    view: str,
    where: str,
) -> dict[str, float | int]:
    row = connection.execute(f"""
    SELECT
      COUNT(*) AS n,
      AVG(CASE WHEN next_win THEN 1.0 ELSE 0.0 END) AS win_rate,
      AVG(CASE WHEN next_top3 THEN 1.0 ELSE 0.0 END) AS top3_rate,
      AVG(CASE WHEN next_top5 THEN 1.0 ELSE 0.0 END) AS top5_rate,
      AVG(CAST(next_finish AS DOUBLE)) AS avg_next_finish,
      AVG(CAST(finish_improvement AS DOUBLE)) AS avg_finish_improvement
    FROM {view}
    WHERE {where}
    """).fetchone()
    if row is None:
        raise Turn6Error("metric query returned no row")
    names = [
        "n", "win_rate", "top3_rate", "top5_rate",
        "avg_next_finish", "avg_finish_improvement",
    ]
    result: dict[str, float | int] = {}
    for name, value in zip(names, row):
        if name == "n":
            result[name] = int(value or 0)
        else:
            result[name] = float(value) if value is not None else float("nan")
    return result


def _status(
    track: str,
    n: int,
    top3_lift: float,
    top5_lift: float,
    discovery_top3_lift: float,
) -> str:
    if n < 20:
        return "INSUFFICIENT_SAMPLE"
    if (
        track == "hidden_value"
        and n >= 30
        and top3_lift >= 0.05
        and top5_lift >= 0.03
        and top3_lift >= discovery_top3_lift * 0.35
    ):
        return "ACCEPTED_S"
    if top3_lift >= 0.03 and top5_lift >= 0.0:
        return "ACCEPTED_A"
    if top3_lift > 0.0 and top5_lift >= 0.0:
        return "DIRECTION_RETAINED_WEAK"
    return "REJECTED"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--turn3-zip", type=Path, required=True)
    parser.add_argument("--turn5-zip", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--result-output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    args.work_root.mkdir(parents=True, exist_ok=True)
    args.result_output.parent.mkdir(parents=True, exist_ok=True)

    fact_path, turn3_audit = _find_turn3(args.turn3_zip, args.work_root)
    contract = _find_turn5(args.turn5_zip, args.work_root)
    frozen_rules = contract.get("frozen_rules")
    if not isinstance(frozen_rules, list) or not frozen_rules:
        raise Turn6Error("frozen rule list missing")

    fact_sql = _literal(fact_path)
    horizon_text = str(turn3_audit.get("observation_horizon") or "")
    horizon = dt.date.fromisoformat(horizon_text)

    connection = duckdb.connect(":memory:")
    try:
        connection.execute(f"""
        CREATE TEMP VIEW all_fact AS
        SELECT *
        FROM read_parquet('{fact_sql}')
        """)

        maturity_row = connection.execute("""
        SELECT
          quantile_cont(CAST(days_to_next_start AS DOUBLE), 0.90),
          quantile_cont(CAST(days_to_next_start AS DOUBLE), 0.95)
        FROM all_fact
        WHERE evaluation_period = 'DISCOVERY'
          AND phase1_eligible = TRUE
          AND days_to_next_start IS NOT NULL
        """).fetchone()
        if maturity_row is None or maturity_row[0] is None:
            raise Turn6Error("Discovery maturity distribution unavailable")

        q90 = float(maturity_row[0])
        q95 = float(maturity_row[1])
        maturity_days = int(math.ceil(q90))
        mature_cutoff = horizon - dt.timedelta(days=maturity_days)

        connection.execute(f"""
        CREATE TEMP VIEW holdout_source AS
        SELECT *
        FROM all_fact
        WHERE evaluation_period = 'HOLDOUT'
          AND race_date <= DATE '{mature_cutoff.isoformat()}'
        """)

        source_counts = connection.execute("""
        SELECT
          COUNT(*),
          SUM(CASE WHEN phase1_eligible THEN 1 ELSE 0 END),
          SUM(CASE WHEN next_start_status = 'NO_NEXT_START_BY_HORIZON'
                   THEN 1 ELSE 0 END),
          SUM(CASE WHEN next_start_status = 'RESOLVED_JUMP'
                   THEN 1 ELSE 0 END),
          SUM(CASE WHEN next_start_status = 'RESOLVED_INVALID_RESULT'
                   THEN 1 ELSE 0 END)
        FROM holdout_source
        """).fetchone()

        connection.execute("""
        CREATE TEMP VIEW holdout AS
        SELECT *
        FROM holdout_source
        WHERE phase1_eligible = TRUE
        """)

        baselines = {
            "ALL": _metrics(connection, "holdout", "TRUE"),
            "FINISH_GE4": _metrics(connection, "holdout", "finish >= 4"),
            "FINISH_GE6": _metrics(connection, "holdout", "finish >= 6"),
            "FINISH_LE3": _metrics(connection, "holdout", "finish <= 3"),
        }

        rows: list[dict[str, object]] = []
        for rule in frozen_rules:
            if not isinstance(rule, dict):
                continue
            condition = str(rule["condition"])
            baseline_key = str(rule["matched_baseline"])
            track = str(rule["track"])
            metrics = _metrics(connection, "holdout", condition)
            baseline = baselines[baseline_key]
            top3_lift = float(metrics["top3_rate"]) - float(baseline["top3_rate"])
            top5_lift = float(metrics["top5_rate"]) - float(baseline["top5_rate"])
            discovery_lift = float(rule["discovery_top3_lift_vs_matched_baseline"])
            status = _status(
                track,
                int(metrics["n"]),
                top3_lift,
                top5_lift,
                discovery_lift,
            )
            rows.append({
                "rule_id": str(rule["rule_id"]),
                "track": track,
                "description": str(rule["description"]),
                "condition": condition,
                "baseline": baseline_key,
                "discovery_n": int(rule["discovery_n"]),
                "discovery_top3_rate": float(rule["discovery_top3_rate"]),
                "discovery_top3_lift": discovery_lift,
                "holdout_n": int(metrics["n"]),
                "holdout_win_rate": float(metrics["win_rate"]),
                "holdout_top3_rate": float(metrics["top3_rate"]),
                "holdout_top5_rate": float(metrics["top5_rate"]),
                "holdout_avg_finish_improvement": float(metrics["avg_finish_improvement"]),
                "holdout_baseline_n": int(baseline["n"]),
                "holdout_baseline_top3_rate": float(baseline["top3_rate"]),
                "holdout_baseline_top5_rate": float(baseline["top5_rate"]),
                "holdout_baseline_avg_finish_improvement": float(
                    baseline["avg_finish_improvement"]
                ),
                "holdout_top3_lift": top3_lift,
                "holdout_top5_lift": top5_lift,
                "lift_retention_ratio": (
                    top3_lift / discovery_lift
                    if discovery_lift != 0.0 else float("nan")
                ),
                "status": status,
            })

        connection.execute("""
        CREATE TABLE result (
          rule_id VARCHAR, track VARCHAR, description VARCHAR, condition VARCHAR,
          baseline VARCHAR, discovery_n BIGINT, discovery_top3_rate DOUBLE,
          discovery_top3_lift DOUBLE, holdout_n BIGINT, holdout_win_rate DOUBLE,
          holdout_top3_rate DOUBLE, holdout_top5_rate DOUBLE,
          holdout_avg_finish_improvement DOUBLE, holdout_baseline_n BIGINT,
          holdout_baseline_top3_rate DOUBLE, holdout_baseline_top5_rate DOUBLE,
          holdout_baseline_avg_finish_improvement DOUBLE,
          holdout_top3_lift DOUBLE, holdout_top5_lift DOUBLE,
          lift_retention_ratio DOUBLE, status VARCHAR
        )
        """)
        connection.executemany(
            "INSERT INTO result VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [[
                r["rule_id"], r["track"], r["description"], r["condition"],
                r["baseline"], r["discovery_n"], r["discovery_top3_rate"],
                r["discovery_top3_lift"], r["holdout_n"], r["holdout_win_rate"],
                r["holdout_top3_rate"], r["holdout_top5_rate"],
                r["holdout_avg_finish_improvement"], r["holdout_baseline_n"],
                r["holdout_baseline_top3_rate"], r["holdout_baseline_top5_rate"],
                r["holdout_baseline_avg_finish_improvement"],
                r["holdout_top3_lift"], r["holdout_top5_lift"],
                r["lift_retention_ratio"], r["status"],
            ] for r in rows],
        )
        connection.execute(
            f"COPY result TO '{_literal(args.result_output)}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )

        status_counts = connection.execute(
            "SELECT status, COUNT(*) FROM result GROUP BY status ORDER BY status"
        ).fetchall()

        summary = {
            "status": "PASS",
            "artifact_type": ARTIFACT_TYPE,
            "validation_version": VALIDATION_VERSION,
            "source_turn3_run_id": 36109088127,
            "source_turn5_run_id": 36110362625,
            "rule_version": contract.get("rule_version"),
            "maturity_policy": {
                "basis": "Discovery-only q90 of observed days_to_next_start",
                "discovery_q90_days": q90,
                "discovery_q95_days": q95,
                "maturity_days": maturity_days,
                "observation_horizon": horizon_text,
                "mature_source_cutoff": mature_cutoff.isoformat(),
            },
            "grading_policy": {
                "minimum_holdout_n": 20,
                "accepted_s": "hidden_value, N>=30, top3 lift>=0.05, top5 lift>=0.03, retain >=35% of Discovery top3 lift",
                "accepted_a": "N>=20, top3 lift>=0.03, top5 lift>=0",
                "weak": "N>=20, top3 lift>0, top5 lift>=0",
            },
            "mature_holdout_source_rows": int(source_counts[0] or 0),
            "mature_holdout_phase1_eligible": int(source_counts[1] or 0),
            "mature_holdout_censored": int(source_counts[2] or 0),
            "mature_holdout_jump": int(source_counts[3] or 0),
            "mature_holdout_invalid": int(source_counts[4] or 0),
            "mature_resolution_rate": (
                float(source_counts[1] or 0) / float(source_counts[0] or 1)
            ),
            "holdout_baselines": baselines,
            "validated_rule_count": len(rows),
            "status_counts": {str(k): int(v) for k, v in status_counts},
            "results": rows,
            "hard_errors": [],
        }
        args.summary.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    finally:
        connection.close()

    summary["result_file"] = args.result_output.name
    summary["result_sha256"] = _sha256(args.result_output)
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
