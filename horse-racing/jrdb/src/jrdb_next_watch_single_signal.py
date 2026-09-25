#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RaceReviewDB Next-Watch Turn 4: Discovery single-signal screening."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import zipfile
from pathlib import Path

import duckdb


ARTIFACT_TYPE = "jrdb_next_watch_single_signal_screen"
SCREEN_VERSION = "next-watch-single-signal-v0.1"


class SingleSignalError(RuntimeError):
    """Raised when Turn-4 screening cannot satisfy its contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_zip(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    with zipfile.ZipFile(source) as archive:
        archive.extractall(target)


def _literal(path: Path) -> str:
    return str(path).replace("'", "''")


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SingleSignalError(f"JSON object required: {path}")
    return value


def _find_turn3(turn3_zip: Path, work_root: Path) -> tuple[Path, dict[str, object]]:
    target = work_root / "turn3"
    _extract_zip(turn3_zip, target)
    facts = list(target.rglob("next_watch_backtest_fact.parquet"))
    audits = list(target.rglob("next_start_audit.json"))
    if len(facts) != 1 or len(audits) != 1:
        raise SingleSignalError(f"unique Turn3 fact/audit required: {facts} / {audits}")
    audit = _json(audits[0])
    if audit.get("status") != "PASS":
        raise SingleSignalError("Turn3 checkpoint is not PASS")
    return facts[0], audit


def _metrics_sql(condition: str) -> str:
    return f"""
      COUNT(*) AS n,
      AVG(CASE WHEN next_win THEN 1.0 ELSE 0.0 END) AS win_rate,
      AVG(CASE WHEN next_top3 THEN 1.0 ELSE 0.0 END) AS top3_rate,
      AVG(CASE WHEN next_top5 THEN 1.0 ELSE 0.0 END) AS top5_rate,
      AVG(CAST(next_finish AS DOUBLE)) AS avg_next_finish,
      MEDIAN(CAST(next_finish AS DOUBLE)) AS median_next_finish,
      AVG(CAST(finish_improvement AS DOUBLE)) AS avg_finish_improvement,
      MEDIAN(CAST(finish_improvement AS DOUBLE)) AS median_finish_improvement
    FROM discovery
    WHERE {condition}
    """


def build(
    *,
    turn3_zip: Path,
    work_root: Path,
    result_path: Path,
    summary_path: Path,
) -> dict[str, object]:
    fact_path, turn3_audit = _find_turn3(turn3_zip, work_root)
    fact_sql = _literal(fact_path)
    result_path.parent.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect(":memory:")
    try:
        connection.execute(f"""
        CREATE TEMP VIEW discovery AS
        SELECT *
        FROM read_parquet('{fact_sql}')
        WHERE evaluation_period = 'DISCOVERY'
          AND phase1_eligible = TRUE
        """)

        baseline = connection.execute(
            "SELECT " + _metrics_sql("TRUE")
        ).fetchone()
        baseline_cols = [
            "n","win_rate","top3_rate","top5_rate","avg_next_finish",
            "median_next_finish","avg_finish_improvement","median_finish_improvement"
        ]
        baseline_map = dict(zip(baseline_cols, baseline))

        specs = [
            ("finish_band",
             """CASE
                  WHEN finish <= 3 THEN 'F01_03'
                  WHEN finish <= 5 THEN 'F04_05'
                  WHEN finish <= 8 THEN 'F06_08'
                  ELSE 'F09_PLUS'
                END"""),
            ("performance_signal_q",
             "NTILE(5) OVER (ORDER BY performance_signal)"),
            ("last3f_pct_band",
             """CASE
                  WHEN last3f_speed_percentile < 20 THEN 'P00_20'
                  WHEN last3f_speed_percentile < 40 THEN 'P20_40'
                  WHEN last3f_speed_percentile < 60 THEN 'P40_60'
                  WHEN last3f_speed_percentile < 80 THEN 'P60_80'
                  WHEN last3f_speed_percentile < 90 THEN 'P80_90'
                  ELSE 'P90_100'
                END"""),
            ("overall_position_gain_band",
             """CASE
                  WHEN overall_position_gain IS NULL THEN 'MISSING'
                  WHEN overall_position_gain <= -0.25 THEN 'NEG_STRONG'
                  WHEN overall_position_gain < 0 THEN 'NEG'
                  WHEN overall_position_gain = 0 THEN 'ZERO'
                  WHEN overall_position_gain < 0.25 THEN 'POS'
                  ELSE 'POS_STRONG'
                END"""),
            ("late_position_gain_band",
             """CASE
                  WHEN late_position_gain IS NULL THEN 'MISSING'
                  WHEN late_position_gain <= -0.25 THEN 'NEG_STRONG'
                  WHEN late_position_gain < 0 THEN 'NEG'
                  WHEN late_position_gain = 0 THEN 'ZERO'
                  WHEN late_position_gain < 0.25 THEN 'POS'
                  ELSE 'POS_STRONG'
                END"""),
            ("trouble_score_band",
             """CASE
                  WHEN jrdb_trouble_score IS NULL THEN 'MISSING'
                  WHEN jrdb_trouble_score <= 0 THEN 'LE_0'
                  WHEN jrdb_trouble_score < 1 THEN 'GT0_LT1'
                  WHEN jrdb_trouble_score < 2 THEN '1_2'
                  ELSE 'GE_2'
                END"""),
            ("late_break_score_band",
             """CASE
                  WHEN jrdb_late_break_score IS NULL THEN 'MISSING'
                  WHEN jrdb_late_break_score <= 0 THEN 'LE_0'
                  WHEN jrdb_late_break_score < 1 THEN 'GT0_LT1'
                  WHEN jrdb_late_break_score < 2 THEN '1_2'
                  ELSE 'GE_2'
                END"""),
            ("performance_vs_prior3_band",
             """CASE
                  WHEN performance_vs_prior3 IS NULL THEN 'MISSING'
                  WHEN performance_vs_prior3 <= -1.0 THEN 'LE_M1'
                  WHEN performance_vs_prior3 < 0 THEN 'M1_0'
                  WHEN performance_vs_prior3 < 0.5 THEN '0_0P5'
                  WHEN performance_vs_prior3 < 1.0 THEN '0P5_1'
                  ELSE 'GE_1'
                END"""),
            ("last3f_vs_prior3_band",
             """CASE
                  WHEN last3f_pct_vs_prior3 IS NULL THEN 'MISSING'
                  WHEN last3f_pct_vs_prior3 <= -20 THEN 'LE_M20'
                  WHEN last3f_pct_vs_prior3 < 0 THEN 'M20_0'
                  WHEN last3f_pct_vs_prior3 < 10 THEN '0_10'
                  WHEN last3f_pct_vs_prior3 < 20 THEN '10_20'
                  ELSE 'GE_20'
                END"""),
            ("recent5_best_flag",
             """CASE
                  WHEN is_recent5_performance_best IS NULL THEN 'MISSING'
                  WHEN is_recent5_performance_best THEN 'TRUE'
                  ELSE 'FALSE'
                END"""),
            ("pace_shape",
             """COALESCE(pace_shape, 'MISSING')"""),
            ("race_pace_code",
             """COALESCE(race_pace_code, 'MISSING')"""),
            ("corner4_frontness_band",
             """CASE
                  WHEN corner4_frontness IS NULL THEN 'MISSING'
                  WHEN corner4_frontness < 0.25 THEN 'BACK'
                  WHEN corner4_frontness < 0.5 THEN 'MID_BACK'
                  WHEN corner4_frontness < 0.75 THEN 'MID_FRONT'
                  ELSE 'FRONT'
                END"""),
        ]

        rows: list[dict[str, object]] = []
        for signal_name, bucket_expr in specs:
            if signal_name == "performance_signal_q":
                query = f"""
                WITH x AS (
                  SELECT *, {bucket_expr} AS bucket_num
                  FROM discovery
                  WHERE performance_signal IS NOT NULL
                )
                SELECT
                  CAST(bucket_num AS VARCHAR) AS bucket,
                  COUNT(*) AS n,
                  AVG(CASE WHEN next_win THEN 1.0 ELSE 0.0 END) AS win_rate,
                  AVG(CASE WHEN next_top3 THEN 1.0 ELSE 0.0 END) AS top3_rate,
                  AVG(CASE WHEN next_top5 THEN 1.0 ELSE 0.0 END) AS top5_rate,
                  AVG(CAST(next_finish AS DOUBLE)) AS avg_next_finish,
                  MEDIAN(CAST(next_finish AS DOUBLE)) AS median_next_finish,
                  AVG(CAST(finish_improvement AS DOUBLE)) AS avg_finish_improvement,
                  MEDIAN(CAST(finish_improvement AS DOUBLE)) AS median_finish_improvement
                FROM x
                GROUP BY bucket_num
                ORDER BY bucket_num
                """
            else:
                query = f"""
                SELECT
                  CAST({bucket_expr} AS VARCHAR) AS bucket,
                  COUNT(*) AS n,
                  AVG(CASE WHEN next_win THEN 1.0 ELSE 0.0 END) AS win_rate,
                  AVG(CASE WHEN next_top3 THEN 1.0 ELSE 0.0 END) AS top3_rate,
                  AVG(CASE WHEN next_top5 THEN 1.0 ELSE 0.0 END) AS top5_rate,
                  AVG(CAST(next_finish AS DOUBLE)) AS avg_next_finish,
                  MEDIAN(CAST(next_finish AS DOUBLE)) AS median_next_finish,
                  AVG(CAST(finish_improvement AS DOUBLE)) AS avg_finish_improvement,
                  MEDIAN(CAST(finish_improvement AS DOUBLE)) AS median_finish_improvement
                FROM discovery
                GROUP BY 1
                ORDER BY 1
                """
            cur = connection.execute(query)
            cols = [d[0] for d in cur.description]
            for vals in cur.fetchall():
                item = dict(zip(cols, vals))
                item["signal"] = signal_name
                item["top3_lift_vs_baseline"] = (
                    float(item["top3_rate"]) - float(baseline_map["top3_rate"])
                )
                item["top5_lift_vs_baseline"] = (
                    float(item["top5_rate"]) - float(baseline_map["top5_rate"])
                )
                rows.append(item)

        # closing_gain: available-evidence population only
        cur = connection.execute("""
        SELECT
          CASE
            WHEN closing_gain_sec < -0.5 THEN 'LT_M0P5'
            WHEN closing_gain_sec < 0 THEN 'M0P5_0'
            WHEN closing_gain_sec < 0.5 THEN '0_0P5'
            ELSE 'GE_0P5'
          END AS bucket,
          COUNT(*) AS n,
          AVG(CASE WHEN next_win THEN 1.0 ELSE 0.0 END) AS win_rate,
          AVG(CASE WHEN next_top3 THEN 1.0 ELSE 0.0 END) AS top3_rate,
          AVG(CASE WHEN next_top5 THEN 1.0 ELSE 0.0 END) AS top5_rate,
          AVG(CAST(next_finish AS DOUBLE)) AS avg_next_finish,
          MEDIAN(CAST(next_finish AS DOUBLE)) AS median_next_finish,
          AVG(CAST(finish_improvement AS DOUBLE)) AS avg_finish_improvement,
          MEDIAN(CAST(finish_improvement AS DOUBLE)) AS median_finish_improvement
        FROM discovery
        WHERE closing_gain_sec IS NOT NULL
        GROUP BY 1
        ORDER BY 1
        """)
        cols = [d[0] for d in cur.description]
        closing_n = 0
        for vals in cur.fetchall():
            item = dict(zip(cols, vals))
            closing_n += int(item["n"])
            item["signal"] = "closing_gain_available_only"
            item["top3_lift_vs_baseline"] = (
                float(item["top3_rate"]) - float(baseline_map["top3_rate"])
            )
            item["top5_lift_vs_baseline"] = (
                float(item["top5_rate"]) - float(baseline_map["top5_rate"])
            )
            rows.append(item)

        connection.execute("""
        CREATE TABLE result (
          signal VARCHAR,
          bucket VARCHAR,
          n BIGINT,
          win_rate DOUBLE,
          top3_rate DOUBLE,
          top5_rate DOUBLE,
          avg_next_finish DOUBLE,
          median_next_finish DOUBLE,
          avg_finish_improvement DOUBLE,
          median_finish_improvement DOUBLE,
          top3_lift_vs_baseline DOUBLE,
          top5_lift_vs_baseline DOUBLE
        )
        """)
        connection.executemany(
            "INSERT INTO result VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [[
                r["signal"], str(r["bucket"]), int(r["n"]),
                float(r["win_rate"]), float(r["top3_rate"]), float(r["top5_rate"]),
                float(r["avg_next_finish"]), float(r["median_next_finish"]),
                float(r["avg_finish_improvement"]),
                float(r["median_finish_improvement"]),
                float(r["top3_lift_vs_baseline"]),
                float(r["top5_lift_vs_baseline"])
            ] for r in rows]
        )
        connection.execute(
            f"COPY result TO '{_literal(result_path)}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )

        # stable compact top buckets; descriptive only, not yet candidate rules
        top = connection.execute("""
        SELECT signal, bucket, n, top3_rate, top3_lift_vs_baseline,
               top5_rate, top5_lift_vs_baseline, avg_finish_improvement
        FROM result
        WHERE n >= 30
        ORDER BY top3_lift_vs_baseline DESC, n DESC
        LIMIT 20
        """).fetchall()

        signal_counts = connection.execute("""
        SELECT signal, COUNT(*) AS bucket_count, SUM(n) AS represented_n
        FROM result
        GROUP BY signal
        ORDER BY signal
        """).fetchall()

        summary = {
            "status": "PASS",
            "artifact_type": ARTIFACT_TYPE,
            "screen_version": SCREEN_VERSION,
            "source_turn3_run_id": 36109088127,
            "source_generation_id": turn3_audit.get("source_generation_id"),
            "discovery_phase1_eligible": int(baseline_map["n"]),
            "baseline": {k: (int(v) if k == "n" else float(v)) for k,v in baseline_map.items()},
            "closing_gain_available_n": closing_n,
            "signal_bucket_counts": [
                {"signal": r[0], "bucket_count": int(r[1]), "represented_n": int(r[2])}
                for r in signal_counts
            ],
            "top20_descriptive_buckets_n30": [
                {
                    "signal": r[0],
                    "bucket": r[1],
                    "n": int(r[2]),
                    "top3_rate": float(r[3]),
                    "top3_lift_vs_baseline": float(r[4]),
                    "top5_rate": float(r[5]),
                    "top5_lift_vs_baseline": float(r[6]),
                    "avg_finish_improvement": float(r[7]),
                }
                for r in top
            ],
            "result_rows": len(rows),
            "hard_errors": [],
        }

        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return summary
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--turn3-zip", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--result-output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    args.work_root.mkdir(parents=True, exist_ok=True)
    args.result_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)

    summary = build(
        turn3_zip=args.turn3_zip,
        work_root=args.work_root,
        result_path=args.result_output,
        summary_path=args.summary,
    )
    summary["result_file"] = args.result_output.name
    summary["result_size_bytes"] = args.result_output.stat().st_size
    summary["result_sha256"] = _sha256(args.result_output)
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
