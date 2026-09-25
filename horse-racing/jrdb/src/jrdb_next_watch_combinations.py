#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RaceReviewDB Next-Watch Turn 5: interpretable Discovery combinations.

Only Discovery rows are used. Holdout rows are never read by this builder.
Candidate thresholds are frozen into JSON before any Holdout validation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import duckdb


ARTIFACT_TYPE = "jrdb_next_watch_candidate_rules"
RULE_VERSION = "next-watch-rules-discovery-v0.1"


class Turn5Error(RuntimeError):
    """Raised when Turn-5 candidate rule freezing fails."""


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
        raise Turn5Error(f"JSON object required: {path}")
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
        raise Turn5Error("unique Turn3 fact/audit required")
    audit = _json(audits[0])
    if audit.get("status") != "PASS":
        raise Turn5Error("Turn3 checkpoint is not PASS")
    return facts[0], audit


def _metrics(connection: duckdb.DuckDBPyConnection, where: str) -> dict[str, float | int]:
    row = connection.execute(f"""
    SELECT
      COUNT(*) AS n,
      AVG(CASE WHEN next_win THEN 1.0 ELSE 0.0 END) AS win_rate,
      AVG(CASE WHEN next_top3 THEN 1.0 ELSE 0.0 END) AS top3_rate,
      AVG(CASE WHEN next_top5 THEN 1.0 ELSE 0.0 END) AS top5_rate,
      AVG(CAST(next_finish AS DOUBLE)) AS avg_next_finish,
      MEDIAN(CAST(next_finish AS DOUBLE)) AS median_next_finish,
      AVG(CAST(finish_improvement AS DOUBLE)) AS avg_finish_improvement,
      MEDIAN(CAST(finish_improvement AS DOUBLE)) AS median_finish_improvement
    FROM discovery
    WHERE {where}
    """).fetchone()
    if row is None:
        raise Turn5Error("metric query returned no row")
    names = [
        "n", "win_rate", "top3_rate", "top5_rate",
        "avg_next_finish", "median_next_finish",
        "avg_finish_improvement", "median_finish_improvement",
    ]
    result: dict[str, float | int] = {}
    for name, value in zip(names, row):
        if name == "n":
            result[name] = int(value or 0)
        else:
            result[name] = float(value) if value is not None else float("nan")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--turn3-zip", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--result-output", type=Path, required=True)
    parser.add_argument("--rules-output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    args.work_root.mkdir(parents=True, exist_ok=True)
    args.result_output.parent.mkdir(parents=True, exist_ok=True)

    fact_path, turn3_audit = _find_turn3(args.turn3_zip, args.work_root)
    fact_sql = _literal(fact_path)

    connection = duckdb.connect(":memory:")
    try:
        connection.execute(f"""
        CREATE TEMP VIEW discovery AS
        SELECT *
        FROM read_parquet('{fact_sql}')
        WHERE evaluation_period = 'DISCOVERY'
          AND phase1_eligible = TRUE
        """)

        discovery_n = connection.execute(
            "SELECT COUNT(*) FROM discovery"
        ).fetchone()[0]
        if int(discovery_n) != 8619:
            raise Turn5Error(f"unexpected Discovery population: {discovery_n}")

        perf_q80, perf_q90 = connection.execute("""
        SELECT
          quantile_cont(performance_signal, 0.80),
          quantile_cont(performance_signal, 0.90)
        FROM discovery
        WHERE performance_signal IS NOT NULL
        """).fetchone()

        baselines = {
            "ALL": _metrics(connection, "TRUE"),
            "FINISH_GE4": _metrics(connection, "finish >= 4"),
            "FINISH_GE6": _metrics(connection, "finish >= 6"),
            "FINISH_LE3": _metrics(connection, "finish <= 3"),
        }

        q80 = float(perf_q80)
        q90 = float(perf_q90)

        rules = [
            {
                "rule_id": "HV01",
                "track": "hidden_value",
                "baseline": "FINISH_GE4",
                "condition": f"finish >= 4 AND performance_signal >= {q80!r}",
                "description": "4着以下 + performance_signal 上位20%",
            },
            {
                "rule_id": "HV02",
                "track": "hidden_value",
                "baseline": "FINISH_GE6",
                "condition": f"finish >= 6 AND performance_signal >= {q80!r}",
                "description": "6着以下 + performance_signal 上位20%",
            },
            {
                "rule_id": "HV03",
                "track": "hidden_value",
                "baseline": "FINISH_GE4",
                "condition": "finish >= 4 AND last3f_speed_percentile >= 90",
                "description": "4着以下 + 上がり速度percentile 90以上",
            },
            {
                "rule_id": "HV04",
                "track": "hidden_value",
                "baseline": "FINISH_GE6",
                "condition": "finish >= 6 AND last3f_speed_percentile >= 90",
                "description": "6着以下 + 上がり速度percentile 90以上",
            },
            {
                "rule_id": "HV05",
                "track": "hidden_value",
                "baseline": "FINISH_GE4",
                "condition": f"finish >= 4 AND performance_signal >= {q80!r} AND last3f_speed_percentile >= 80",
                "description": "4着以下 + performance上位20% + 上がり80以上",
            },
            {
                "rule_id": "HV06",
                "track": "hidden_value",
                "baseline": "FINISH_GE6",
                "condition": f"finish >= 6 AND performance_signal >= {q80!r} AND last3f_speed_percentile >= 80",
                "description": "6着以下 + performance上位20% + 上がり80以上",
            },
            {
                "rule_id": "HV07",
                "track": "hidden_value",
                "baseline": "FINISH_GE4",
                "condition": "finish >= 4 AND overall_position_gain >= 0.25 AND last3f_speed_percentile >= 80",
                "description": "4着以下 + 強い位置取り改善 + 上がり80以上",
            },
            {
                "rule_id": "HV08",
                "track": "hidden_value",
                "baseline": "FINISH_GE6",
                "condition": "finish >= 6 AND overall_position_gain >= 0.25 AND last3f_speed_percentile >= 80",
                "description": "6着以下 + 強い位置取り改善 + 上がり80以上",
            },
            {
                "rule_id": "HV09",
                "track": "hidden_value",
                "baseline": "FINISH_GE4",
                "condition": "finish >= 4 AND last3f_pct_vs_prior3 >= 10 AND last3f_speed_percentile >= 80",
                "description": "4着以下 + 自身過去3走比で上がり+10以上 + 絶対上がり80以上",
            },
            {
                "rule_id": "HV10",
                "track": "hidden_value",
                "baseline": "FINISH_GE6",
                "condition": "finish >= 6 AND last3f_pct_vs_prior3 >= 10 AND last3f_speed_percentile >= 80",
                "description": "6着以下 + 自身過去3走比で上がり+10以上 + 絶対上がり80以上",
            },
            {
                "rule_id": "HV11",
                "track": "hidden_value",
                "baseline": "FINISH_GE4",
                "condition": f"finish >= 4 AND performance_signal >= {q80!r} AND performance_vs_prior3 >= 0.5",
                "description": "4着以下 + performance上位20% + 自身過去3走比改善",
            },
            {
                "rule_id": "HV12",
                "track": "hidden_value",
                "baseline": "FINISH_GE6",
                "condition": f"finish >= 6 AND performance_signal >= {q80!r} AND performance_vs_prior3 >= 0.5",
                "description": "6着以下 + performance上位20% + 自身過去3走比改善",
            },
            {
                "rule_id": "HV13",
                "track": "hidden_value",
                "baseline": "FINISH_GE4",
                "condition": f"finish >= 4 AND performance_signal >= {q90!r} AND last3f_speed_percentile >= 90",
                "description": "4着以下 + performance上位10% + 上がり90以上",
            },
            {
                "rule_id": "HV14",
                "track": "hidden_value",
                "baseline": "FINISH_GE6",
                "condition": f"finish >= 6 AND performance_signal >= {q90!r} AND last3f_speed_percentile >= 90",
                "description": "6着以下 + performance上位10% + 上がり90以上",
            },
            {
                "rule_id": "HV15",
                "track": "hidden_value",
                "baseline": "FINISH_GE4",
                "condition": "finish >= 4 AND jrdb_trouble_score >= 2 AND last3f_speed_percentile >= 80",
                "description": "4着以下 + JRDB強い不利 + 上がり80以上",
            },
            {
                "rule_id": "P01",
                "track": "persistence",
                "baseline": "FINISH_LE3",
                "condition": f"finish <= 3 AND performance_signal >= {q80!r}",
                "description": "1-3着 + performance上位20%",
            },
            {
                "rule_id": "P02",
                "track": "persistence",
                "baseline": "FINISH_LE3",
                "condition": "finish <= 3 AND last3f_speed_percentile >= 90",
                "description": "1-3着 + 上がり90以上",
            },
            {
                "rule_id": "P03",
                "track": "persistence",
                "baseline": "FINISH_LE3",
                "condition": f"finish <= 3 AND performance_signal >= {q80!r} AND last3f_speed_percentile >= 80",
                "description": "1-3着 + performance上位20% + 上がり80以上",
            },
        ]

        result_rows: list[dict[str, object]] = []
        frozen: list[dict[str, object]] = []
        for rule in rules:
            metrics = _metrics(connection, str(rule["condition"]))
            base = baselines[str(rule["baseline"])]
            top3_lift = float(metrics["top3_rate"]) - float(base["top3_rate"])
            top5_lift = float(metrics["top5_rate"]) - float(base["top5_rate"])
            status = "REJECTED_LOW_LIFT"
            if int(metrics["n"]) < 30:
                status = "INSUFFICIENT_SAMPLE"
            elif top3_lift >= 0.05 and top5_lift >= 0.03:
                status = "HOLDOUT_CANDIDATE"
            elif top3_lift >= 0.04 and float(metrics["avg_finish_improvement"]) > float(base["avg_finish_improvement"]):
                status = "HOLDOUT_CANDIDATE"
            result = {
                **rule,
                "n": int(metrics["n"]),
                "win_rate": float(metrics["win_rate"]),
                "top3_rate": float(metrics["top3_rate"]),
                "top5_rate": float(metrics["top5_rate"]),
                "avg_next_finish": float(metrics["avg_next_finish"]),
                "avg_finish_improvement": float(metrics["avg_finish_improvement"]),
                "baseline_n": int(base["n"]),
                "baseline_top3_rate": float(base["top3_rate"]),
                "baseline_top5_rate": float(base["top5_rate"]),
                "baseline_avg_finish_improvement": float(base["avg_finish_improvement"]),
                "top3_lift_vs_matched_baseline": top3_lift,
                "top5_lift_vs_matched_baseline": top5_lift,
                "status": status,
            }
            result_rows.append(result)
            if status == "HOLDOUT_CANDIDATE":
                frozen.append({
                    "rule_id": rule["rule_id"],
                    "track": rule["track"],
                    "condition": rule["condition"],
                    "description": rule["description"],
                    "matched_baseline": rule["baseline"],
                    "discovery_n": int(metrics["n"]),
                    "discovery_top3_rate": float(metrics["top3_rate"]),
                    "discovery_top3_lift_vs_matched_baseline": top3_lift,
                    "discovery_top5_rate": float(metrics["top5_rate"]),
                    "discovery_top5_lift_vs_matched_baseline": top5_lift,
                    "status": "HOLDOUT_PENDING",
                })

        connection.execute("""
        CREATE TABLE rule_result (
          rule_id VARCHAR,
          track VARCHAR,
          baseline VARCHAR,
          condition VARCHAR,
          description VARCHAR,
          n BIGINT,
          win_rate DOUBLE,
          top3_rate DOUBLE,
          top5_rate DOUBLE,
          avg_next_finish DOUBLE,
          avg_finish_improvement DOUBLE,
          baseline_n BIGINT,
          baseline_top3_rate DOUBLE,
          baseline_top5_rate DOUBLE,
          baseline_avg_finish_improvement DOUBLE,
          top3_lift_vs_matched_baseline DOUBLE,
          top5_lift_vs_matched_baseline DOUBLE,
          status VARCHAR
        )
        """)
        connection.executemany(
            "INSERT INTO rule_result VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [[
                r["rule_id"], r["track"], r["baseline"], r["condition"], r["description"],
                r["n"], r["win_rate"], r["top3_rate"], r["top5_rate"],
                r["avg_next_finish"], r["avg_finish_improvement"],
                r["baseline_n"], r["baseline_top3_rate"], r["baseline_top5_rate"],
                r["baseline_avg_finish_improvement"],
                r["top3_lift_vs_matched_baseline"],
                r["top5_lift_vs_matched_baseline"], r["status"],
            ] for r in result_rows],
        )
        connection.execute(
            f"COPY rule_result TO '{_literal(args.result_output)}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )

        frozen_contract = {
            "artifact_type": ARTIFACT_TYPE,
            "rule_version": RULE_VERSION,
            "status": "CANDIDATE_RULES_FROZEN",
            "source_turn3_run_id": 36109088127,
            "source_generation_id": turn3_audit.get("source_generation_id"),
            "discovery_only": True,
            "holdout_consulted": False,
            "thresholds": {
                "performance_signal_q80": q80,
                "performance_signal_q90": q90,
                "last3f_pct_strong": 80,
                "last3f_pct_elite": 90,
                "position_gain_strong": 0.25,
                "last3f_vs_prior3_improvement": 10,
                "performance_vs_prior3_improvement": 0.5,
                "trouble_score_strong": 2,
            },
            "promotion_guardrails": {
                "minimum_discovery_n": 30,
                "candidate_primary": "top3 lift >= 0.05 and top5 lift >= 0.03 vs matched source-finish baseline",
                "candidate_secondary": "top3 lift >= 0.04 and avg finish improvement better than matched baseline",
            },
            "baselines": baselines,
            "frozen_rules": frozen,
            "all_rule_count": len(result_rows),
            "frozen_rule_count": len(frozen),
        }
        args.rules_output.write_text(
            json.dumps(frozen_contract, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        sorted_rules = sorted(
            result_rows,
            key=lambda r: (
                float(r["top3_lift_vs_matched_baseline"]),
                int(r["n"]),
            ),
            reverse=True,
        )
        summary = {
            "status": "PASS",
            "artifact_type": ARTIFACT_TYPE,
            "rule_version": RULE_VERSION,
            "discovery_n": int(discovery_n),
            "holdout_consulted": False,
            "thresholds": frozen_contract["thresholds"],
            "baselines": baselines,
            "tested_rule_count": len(result_rows),
            "frozen_rule_count": len(frozen),
            "frozen_rule_ids": [r["rule_id"] for r in frozen],
            "top_rules_by_matched_top3_lift": [
                {
                    "rule_id": r["rule_id"],
                    "track": r["track"],
                    "description": r["description"],
                    "n": r["n"],
                    "top3_rate": r["top3_rate"],
                    "baseline_top3_rate": r["baseline_top3_rate"],
                    "top3_lift": r["top3_lift_vs_matched_baseline"],
                    "top5_rate": r["top5_rate"],
                    "top5_lift": r["top5_lift_vs_matched_baseline"],
                    "avg_finish_improvement": r["avg_finish_improvement"],
                    "status": r["status"],
                }
                for r in sorted_rules[:12]
            ],
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
    summary["rules_file"] = args.rules_output.name
    summary["rules_sha256"] = _sha256(args.rules_output)
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
