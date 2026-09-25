#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RaceReviewDB Next-Watch historical OOS validation for 2024-2025.

The frozen 2026 Discovery rules are applied unchanged.
Source features use the same definitions as Turn 2 and only preceding horse
history. Next starts use the same stable horse_id ordering as Turn 3.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import duckdb


SOURCE_FROM = "2024-01-01"
SOURCE_TO = "2025-12-31"
ARTIFACT_TYPE = "jrdb_next_watch_historical_oos"
VERSION = "next-watch-historical-oos-v0.1"


class HistoricalOOSError(RuntimeError):
    """Raised when the historical OOS contract cannot be satisfied."""


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
        raise HistoricalOOSError(f"JSON object required: {path}")
    return value


def _extract(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    with zipfile.ZipFile(source) as archive:
        archive.extractall(target)


def _race_review_root(current_zip: Path, work_root: Path) -> Path:
    target = work_root / "current"
    _extract(current_zip, target)
    roots: list[Path] = []
    for pointer in target.rglob("current.json"):
        current = _json(pointer)
        if current.get("artifact_type") == "jrdb_postrace_review":
            roots.append(pointer.parent)
    if len(roots) != 1:
        raise HistoricalOOSError(f"unique RaceReviewDB root required: {roots}")
    return roots[0]


def _turn5_contract(turn5_zip: Path, work_root: Path) -> dict[str, object]:
    target = work_root / "turn5"
    _extract(turn5_zip, target)
    rules = list(target.rglob("next_watch_candidate_rules_frozen.json"))
    if len(rules) != 1:
        raise HistoricalOOSError("unique frozen rule contract required")
    contract = _json(rules[0])
    if contract.get("status") != "CANDIDATE_RULES_FROZEN":
        raise HistoricalOOSError("Turn5 rule contract is not frozen")
    if contract.get("holdout_consulted") is not False:
        raise HistoricalOOSError("frozen contract indicates Holdout consultation")
    return contract


def _relation_paths(
    root: Path,
    manifest: dict[str, object],
    relation: str,
) -> list[Path]:
    relations = manifest.get("relations")
    if not isinstance(relations, dict):
        raise HistoricalOOSError("manifest relations missing")
    meta = relations.get(relation)
    if not isinstance(meta, dict):
        raise HistoricalOOSError(f"relation missing: {relation}")
    paths: list[Path] = []
    for partition in meta.get("partitions") or []:
        if not isinstance(partition, dict):
            continue
        relative = partition.get("relative_path")
        if not isinstance(relative, str):
            continue
        path = root / relative
        if not path.is_file():
            raise HistoricalOOSError(f"missing Parquet object: {path}")
        paths.append(path)
    if not paths:
        raise HistoricalOOSError(f"no Parquet objects for {relation}")
    return paths


def _table_sql(paths: list[Path]) -> tuple[str, list[str]]:
    marks = ", ".join("?" for _ in paths)
    return (
        "read_parquet([" + marks + "], union_by_name=true, hive_partitioning=false)",
        [str(path) for path in paths],
    )


def _metrics(
    connection: duckdb.DuckDBPyConnection,
    view: str,
    condition: str,
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
    WHERE {condition}
    """).fetchone()
    if row is None:
        raise HistoricalOOSError("metrics query returned no row")
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
    *,
    block_count: int,
    positive_blocks: int,
    full_n: int,
    full_top3_lift: float,
    full_top5_lift: float,
) -> str:
    """Historical OOS grading fixed before execution."""
    if full_n < 30:
        return "INSUFFICIENT_SAMPLE"
    if (
        block_count == 4
        and positive_blocks >= 3
        and full_top3_lift >= 0.05
        and full_top5_lift >= 0.03
    ):
        return "HISTORICAL_S_SUPPORTED"
    if (
        positive_blocks >= 3
        and full_top3_lift >= 0.03
        and full_top5_lift >= 0.00
    ):
        return "HISTORICAL_A_SUPPORTED"
    if positive_blocks >= 2 and full_top3_lift > 0.0:
        return "DIRECTION_PARTIAL"
    return "HISTORICAL_REJECTED"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-zip", type=Path, required=True)
    parser.add_argument("--turn5-zip", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--fact-output", type=Path, required=True)
    parser.add_argument("--result-output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    args.work_root.mkdir(parents=True, exist_ok=True)
    args.fact_output.parent.mkdir(parents=True, exist_ok=True)

    current_root = _race_review_root(args.current_zip, args.work_root)
    contract = _turn5_contract(args.turn5_zip, args.work_root)

    current = _json(current_root / "current.json")
    manifest_ref = current.get("manifest")
    if not isinstance(manifest_ref, str):
        raise HistoricalOOSError("CURRENT manifest missing")
    manifest = _json(current_root / manifest_ref)
    if manifest.get("validation_status") != "PASS":
        raise HistoricalOOSError("CURRENT manifest is not PASS")
    if str(manifest.get("period_from") or "") > SOURCE_FROM:
        raise HistoricalOOSError("CURRENT does not cover OOS start")
    if str(manifest.get("period_to") or "") <= SOURCE_TO:
        raise HistoricalOOSError("CURRENT does not extend beyond OOS end")

    hp_paths = _relation_paths(current_root, manifest, "fact_horse_performance")
    rr_paths = _relation_paths(current_root, manifest, "fact_race_review")
    rc_paths = _relation_paths(current_root, manifest, "fact_race_context")
    hp_sql, hp_params = _table_sql(hp_paths)
    rr_sql, rr_params = _table_sql(rr_paths)
    rc_sql, rc_params = _table_sql(rc_paths)

    fact_sql = _literal(args.fact_output)
    result_sql = _literal(args.result_output)

    connection = duckdb.connect(":memory:")
    try:
        query = f"""
        COPY (
          WITH hp_valid AS (
            SELECT
              *,
              -horse_adjusted_delta_per_1000m AS performance_signal
            FROM {hp_sql}
            WHERE horse_id IS NOT NULL
              AND TRIM(horse_id) <> ''
              AND COALESCE(finish, 0) > 0
              AND COALESCE(time_sec, 0) > 0
              AND COALESCE(surface_code, '') <> '3'
          ),
          hp_history AS (
            SELECT
              *,
              LAG(race_date, 1) OVER horse_order AS previous_start_date,
              COUNT(*) OVER (
                PARTITION BY horse_id
                ORDER BY race_date, race_key, horse_no
                ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
              ) AS prior_start_count,
              AVG(performance_signal) OVER (
                PARTITION BY horse_id
                ORDER BY race_date, race_key, horse_no
                ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
              ) AS prior3_performance_mean,
              AVG(performance_signal) OVER (
                PARTITION BY horse_id
                ORDER BY race_date, race_key, horse_no
                ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
              ) AS prior5_performance_mean,
              MAX(performance_signal) OVER (
                PARTITION BY horse_id
                ORDER BY race_date, race_key, horse_no
                ROWS BETWEEN 5 PRECEDING AND 1 PRECEDING
              ) AS prior5_performance_best,
              AVG(last3f_speed_percentile) OVER (
                PARTITION BY horse_id
                ORDER BY race_date, race_key, horse_no
                ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
              ) AS prior3_last3f_pct_mean
            FROM hp_valid
            WINDOW horse_order AS (
              PARTITION BY horse_id
              ORDER BY race_date, race_key, horse_no
            )
          ),
          source AS (
            SELECT
              h.*,
              h.performance_signal - h.prior3_performance_mean
                AS performance_vs_prior3,
              h.last3f_speed_percentile - h.prior3_last3f_pct_mean
                AS last3f_pct_vs_prior3,
              CASE
                WHEN h.race_date < DATE '2024-07-01' THEN '2024H1'
                WHEN h.race_date < DATE '2025-01-01' THEN '2024H2'
                WHEN h.race_date < DATE '2025-07-01' THEN '2025H1'
                ELSE '2025H2'
              END AS oos_block
            FROM hp_history h
            WHERE h.race_date BETWEEN DATE '{SOURCE_FROM}' AND DATE '{SOURCE_TO}'
          ),
          source_enriched AS (
            SELECT
              s.*,
              r.time_delta_sec AS race_time_delta_sec,
              r.time_delta_per_1000m AS race_time_delta_per_1000m,
              c.race_pace_code,
              c.pace_balance_sec,
              c.pace_balance_percentile
            FROM source s
            JOIN {rr_sql} r USING (race_key)
            JOIN {rc_sql} c USING (race_key)
          ),
          all_starts AS (
            SELECT
              race_horse_key,
              race_key,
              horse_no,
              horse_id,
              horse_name,
              race_date,
              finish,
              time_sec,
              surface_code,
              venue_code,
              distance_m,
              declared_class_group
            FROM {hp_sql}
            WHERE horse_id IS NOT NULL
              AND TRIM(horse_id) <> ''
          ),
          ranked AS (
            SELECT
              s.*,
              t.race_horse_key AS next_race_horse_key,
              t.race_key AS next_race_key,
              t.horse_no AS next_horse_no,
              t.horse_name AS next_horse_name,
              t.race_date AS next_date,
              t.finish AS next_finish_raw,
              t.time_sec AS next_time_sec,
              t.surface_code AS next_surface_code,
              t.venue_code AS next_venue_code,
              t.distance_m AS next_distance_m,
              t.declared_class_group AS next_declared_class_group,
              ROW_NUMBER() OVER (
                PARTITION BY s.race_horse_key
                ORDER BY t.race_date, t.race_key, t.horse_no
              ) AS next_rank
            FROM source_enriched s
            LEFT JOIN all_starts t
              ON t.horse_id = s.horse_id
             AND t.race_date > s.race_date
          ),
          chosen AS (
            SELECT * FROM ranked WHERE next_rank = 1
          )
          SELECT
            *,
            CASE
              WHEN next_date IS NOT NULL
               AND COALESCE(next_surface_code, '') <> '3'
               AND COALESCE(next_finish_raw, 0) > 0
               AND COALESCE(next_time_sec, 0) > 0
              THEN TRUE ELSE FALSE
            END AS phase1_eligible,
            CASE
              WHEN next_date IS NOT NULL
               AND COALESCE(next_surface_code, '') <> '3'
               AND COALESCE(next_finish_raw, 0) > 0
               AND COALESCE(next_time_sec, 0) > 0
              THEN next_finish_raw ELSE NULL
            END AS next_finish,
            CASE
              WHEN next_date IS NOT NULL
               AND COALESCE(next_surface_code, '') <> '3'
               AND COALESCE(next_finish_raw, 0) = 1
               AND COALESCE(next_time_sec, 0) > 0
              THEN TRUE
              WHEN next_date IS NOT NULL
               AND COALESCE(next_surface_code, '') <> '3'
               AND COALESCE(next_finish_raw, 0) > 1
               AND COALESCE(next_time_sec, 0) > 0
              THEN FALSE ELSE NULL
            END AS next_win,
            CASE
              WHEN next_date IS NOT NULL
               AND COALESCE(next_surface_code, '') <> '3'
               AND COALESCE(next_finish_raw, 0) BETWEEN 1 AND 3
               AND COALESCE(next_time_sec, 0) > 0
              THEN TRUE
              WHEN next_date IS NOT NULL
               AND COALESCE(next_surface_code, '') <> '3'
               AND COALESCE(next_finish_raw, 0) > 3
               AND COALESCE(next_time_sec, 0) > 0
              THEN FALSE ELSE NULL
            END AS next_top3,
            CASE
              WHEN next_date IS NOT NULL
               AND COALESCE(next_surface_code, '') <> '3'
               AND COALESCE(next_finish_raw, 0) BETWEEN 1 AND 5
               AND COALESCE(next_time_sec, 0) > 0
              THEN TRUE
              WHEN next_date IS NOT NULL
               AND COALESCE(next_surface_code, '') <> '3'
               AND COALESCE(next_finish_raw, 0) > 5
               AND COALESCE(next_time_sec, 0) > 0
              THEN FALSE ELSE NULL
            END AS next_top5,
            CASE
              WHEN next_date IS NOT NULL
               AND COALESCE(next_surface_code, '') <> '3'
               AND COALESCE(next_finish_raw, 0) > 0
               AND COALESCE(next_time_sec, 0) > 0
              THEN finish - next_finish_raw ELSE NULL
            END AS finish_improvement,
            date_diff('day', race_date, next_date) AS days_to_next_start,
            '{VERSION}' AS historical_oos_version,
            '{manifest.get("generation_id")}' AS source_generation_id
          FROM chosen
          ORDER BY race_date, race_key, horse_no
        ) TO '{fact_sql}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """
        connection.execute(query, [*hp_params, *rr_params, *rc_params, *hp_params])

        source_audit = connection.execute(f"""
        SELECT
          COUNT(*),
          COUNT(DISTINCT race_horse_key),
          SUM(CASE WHEN phase1_eligible THEN 1 ELSE 0 END),
          SUM(CASE WHEN next_date IS NULL THEN 1 ELSE 0 END),
          SUM(CASE WHEN next_date IS NOT NULL AND next_date <= race_date
                   THEN 1 ELSE 0 END)
        FROM read_parquet('{fact_sql}')
        """).fetchone()

        block_counts = connection.execute(f"""
        SELECT
          oos_block,
          COUNT(*) AS source_n,
          SUM(CASE WHEN phase1_eligible THEN 1 ELSE 0 END) AS eligible_n
        FROM read_parquet('{fact_sql}')
        GROUP BY oos_block
        ORDER BY oos_block
        """).fetchall()

        connection.execute(f"""
        CREATE TEMP VIEW oos AS
        SELECT *
        FROM read_parquet('{fact_sql}')
        WHERE phase1_eligible = TRUE
        """)

        frozen_rules = contract.get("frozen_rules")
        if not isinstance(frozen_rules, list) or not frozen_rules:
            raise HistoricalOOSError("frozen rule list missing")

        periods = ["ALL", "2024H1", "2024H2", "2025H1", "2025H2"]
        rows: list[dict[str, object]] = []
        final_rules: list[dict[str, object]] = []

        for rule in frozen_rules:
            if not isinstance(rule, dict):
                continue
            rule_id = str(rule["rule_id"])
            condition = str(rule["condition"])
            baseline_key = str(rule["matched_baseline"])
            baseline_condition = {
                "ALL": "TRUE",
                "FINISH_GE4": "finish >= 4",
                "FINISH_GE6": "finish >= 6",
                "FINISH_LE3": "finish <= 3",
            }[baseline_key]

            block_positive = 0
            block_valid = 0
            full_n = 0
            full_top3_lift = 0.0
            full_top5_lift = 0.0

            for period in periods:
                period_filter = "TRUE" if period == "ALL" else f"oos_block = '{period}'"
                metrics = _metrics(
                    connection,
                    "oos",
                    f"({period_filter}) AND ({condition})",
                )
                baseline = _metrics(
                    connection,
                    "oos",
                    f"({period_filter}) AND ({baseline_condition})",
                )
                top3_lift = float(metrics["top3_rate"]) - float(baseline["top3_rate"])
                top5_lift = float(metrics["top5_rate"]) - float(baseline["top5_rate"])

                rows.append({
                    "rule_id": rule_id,
                    "track": str(rule["track"]),
                    "description": str(rule["description"]),
                    "period": period,
                    "n": int(metrics["n"]),
                    "top3_rate": float(metrics["top3_rate"]),
                    "top5_rate": float(metrics["top5_rate"]),
                    "avg_finish_improvement": float(metrics["avg_finish_improvement"]),
                    "baseline_n": int(baseline["n"]),
                    "baseline_top3_rate": float(baseline["top3_rate"]),
                    "baseline_top5_rate": float(baseline["top5_rate"]),
                    "top3_lift": top3_lift,
                    "top5_lift": top5_lift,
                })

                if period == "ALL":
                    full_n = int(metrics["n"])
                    full_top3_lift = top3_lift
                    full_top5_lift = top5_lift
                else:
                    if int(metrics["n"]) >= 20:
                        block_valid += 1
                        if top3_lift > 0.0 and top5_lift >= 0.0:
                            block_positive += 1

            status = _status(
                block_count=block_valid,
                positive_blocks=block_positive,
                full_n=full_n,
                full_top3_lift=full_top3_lift,
                full_top5_lift=full_top5_lift,
            )
            final_rules.append({
                "rule_id": rule_id,
                "track": str(rule["track"]),
                "description": str(rule["description"]),
                "historical_oos_n": full_n,
                "positive_blocks": block_positive,
                "valid_blocks": block_valid,
                "full_top3_lift": full_top3_lift,
                "full_top5_lift": full_top5_lift,
                "status": status,
            })

        connection.execute("""
        CREATE TABLE result (
          rule_id VARCHAR,
          track VARCHAR,
          description VARCHAR,
          period VARCHAR,
          n BIGINT,
          top3_rate DOUBLE,
          top5_rate DOUBLE,
          avg_finish_improvement DOUBLE,
          baseline_n BIGINT,
          baseline_top3_rate DOUBLE,
          baseline_top5_rate DOUBLE,
          top3_lift DOUBLE,
          top5_lift DOUBLE
        )
        """)
        connection.executemany(
            "INSERT INTO result VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [[
                r["rule_id"], r["track"], r["description"], r["period"], r["n"],
                r["top3_rate"], r["top5_rate"], r["avg_finish_improvement"],
                r["baseline_n"], r["baseline_top3_rate"],
                r["baseline_top5_rate"], r["top3_lift"], r["top5_lift"],
            ] for r in rows],
        )
        connection.execute(
            f"COPY result TO '{result_sql}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )

        status_counts: dict[str, int] = {}
        for rule in final_rules:
            status = str(rule["status"])
            status_counts[status] = status_counts.get(status, 0) + 1

        summary = {
            "status": "PASS",
            "artifact_type": ARTIFACT_TYPE,
            "version": VERSION,
            "source_generation_id": manifest.get("generation_id"),
            "source_period_from": SOURCE_FROM,
            "source_period_to": SOURCE_TO,
            "rule_version": contract.get("rule_version"),
            "frozen_rule_count": len(frozen_rules),
            "thresholds_reoptimized": False,
            "source_rows": int(source_audit[0] or 0),
            "distinct_source_keys": int(source_audit[1] or 0),
            "phase1_eligible_rows": int(source_audit[2] or 0),
            "no_next_start_rows": int(source_audit[3] or 0),
            "nonfuture_target_rows": int(source_audit[4] or 0),
            "blocks": [
                {
                    "block": row[0],
                    "source_n": int(row[1]),
                    "eligible_n": int(row[2] or 0),
                }
                for row in block_counts
            ],
            "grading_policy": {
                "block_minimum_n": 20,
                "historical_s_supported": (
                    "all 4 blocks valid, >=3 positive blocks, "
                    "full-period top3 lift>=0.05 and top5 lift>=0.03"
                ),
                "historical_a_supported": (
                    ">=3 positive blocks, full-period top3 lift>=0.03 "
                    "and top5 lift>=0"
                ),
            },
            "status_counts": status_counts,
            "rules": final_rules,
            "period_results": rows,
            "hard_errors": [],
        }
        if int(source_audit[0]) != int(source_audit[1]):
            summary["hard_errors"].append("duplicate source keys")
        if int(source_audit[4] or 0) != 0:
            summary["hard_errors"].append("nonfuture target rows")
        if summary["hard_errors"]:
            summary["status"] = "FAIL"

        args.summary.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    finally:
        connection.close()

    summary["fact_file"] = args.fact_output.name
    summary["fact_sha256"] = _sha256(args.fact_output)
    summary["result_file"] = args.result_output.name
    summary["result_sha256"] = _sha256(args.result_output)
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
