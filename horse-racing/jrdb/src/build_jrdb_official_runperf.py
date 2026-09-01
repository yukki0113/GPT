#!/usr/bin/env python3
"""Materialize the frozen official ``T1|EXPANDING|RAW`` RunPerf history.

This builder consumes the audited candidate-feature database.  It deliberately does
not choose a model: the only materialized score is the already promoted v0.1
specification.  Every score retains its inputs, coefficient snapshot, and provenance
so an Ability builder can use the history without reconstructing opaque values.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Any

from fit_jrdb_runperf_coefficient_snapshot import fit_snapshot

VERSION = "0.1.0"
SCHEMA_VERSION = "0.1"
OFFICIAL_CANDIDATE = "T1|EXPANDING|RAW"
BASELINE_METHOD = "EXPANDING"
FIRST_MODEL_YEAR = 2013


def _sha256(path: Path) -> str:
    """Return the SHA-256 of a local SQLite source."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_finite(value: Any) -> bool:
    """Return whether a nullable SQLite value is a finite numeric value."""
    if value is None:
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _snapshot_year_for_run(year: int) -> int:
    """Return the only allowed snapshot target year for one materialized run."""
    if year < FIRST_MODEL_YEAR:
        return FIRST_MODEL_YEAR
    return year


def _score_provenance(year: int) -> str:
    """Describe whether a row follows annual as-of or permitted warm-up scoring."""
    if year < FIRST_MODEL_YEAR:
        return "WARMUP_RETROSPECTIVE_2013_SNAPSHOT"
    return "ANNUAL_ASOF_LITERAL_NEXT_START"


def _load_source_years(connection: sqlite3.Connection) -> tuple[int, int, int]:
    """Return source range and row count, failing when no EXPANDING source exists."""
    row = connection.execute(
        """
        SELECT MIN(o.year),MAX(o.year),COUNT(*)
        FROM runner_runperf_features f
        JOIN race_runperf_observation o ON o.race_key=f.race_key
        WHERE f.baseline_method=?
        """,
        (BASELINE_METHOD,),
    ).fetchone()
    if row is None or row[0] is None or row[1] is None or int(row[2]) == 0:
        raise ValueError("source has no EXPANDING RunPerf runner rows")
    return int(row[0]), int(row[1]), int(row[2])


def _build_snapshots(source_db: Path, source_year_max: int) -> dict[int, dict[str, Any]]:
    """Fit every annual snapshot required by the source range using strict as-of years."""
    snapshots: dict[int, dict[str, Any]] = {}
    for target_year in range(FIRST_MODEL_YEAR, source_year_max + 1):
        asof_year = target_year - 1
        snapshot = fit_snapshot(
            source_db,
            "T1",
            BASELINE_METHOD,
            "RAW",
            asof_year,
            target_year,
        )
        coefficients = snapshot.get("coefficients", {})
        values = (
            snapshot.get("intercept"),
            coefficients.get("time_raw_bias"),
            coefficients.get("prev_margin_score"),
        )
        if snapshot.get("status") != "PASS" or not all(_is_finite(value) for value in values):
            raise ValueError(f"invalid non-finite coefficient snapshot for {target_year}")
        snapshots[target_year] = snapshot
    return snapshots


def _insert_snapshots(target: sqlite3.Connection, snapshots: dict[int, dict[str, Any]]) -> None:
    """Persist immutable annual coefficient snapshots before scoring any runner."""
    created_at = dt.datetime.now().isoformat(timespec="seconds")
    rows: list[tuple[Any, ...]] = []
    for target_year, snapshot in snapshots.items():
        coefficients = snapshot["coefficients"]
        rows.append(
            (
                target_year,
                snapshot["coefficient_asof_through_year"],
                snapshot["training_pair_count"],
                json.dumps(snapshot["pair_count_by_target_year"], sort_keys=True),
                snapshot["intercept"],
                coefficients["time_raw_bias"],
                coefficients["prev_margin_score"],
                snapshot["snapshot_fitter_version"],
                created_at,
            )
        )
    target.executemany(
        """
        INSERT INTO runperf_coefficient_snapshot(
          target_year,coefficient_asof_through_year,training_pair_count,
          pair_count_by_target_year_json,intercept,beta_time_raw_bias,
          beta_margin_score,fitter_version,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        rows,
    )


def _materialize_rows(
    source: sqlite3.Connection,
    target: sqlite3.Connection,
    snapshots: dict[int, dict[str, Any]],
) -> tuple[int, int]:
    """Copy every EXPANDING source row and score only eligible finite components."""
    cursor = source.execute(
        """
        SELECT
          o.race_key,o.race_date,o.year,f.horse_no,f.horse_id,
          f.calculation_status AS source_calculation_status,
          f.expected_time_sec,f.day_bias_raw_sec,f.time_residual_raw_bias_sec,
          f.margin_per_1000m_sec
        FROM runner_runperf_features f
        JOIN race_runperf_observation o ON o.race_key=f.race_key
        WHERE f.baseline_method=?
        ORDER BY o.race_date,o.race_key,f.horse_no
        """,
        (BASELINE_METHOD,),
    )
    insert_sql = """
        INSERT INTO official_runperf(
          race_key,race_date,year,horse_no,horse_id,source_calculation_status,
          score_status,expected_time_sec,day_bias_raw_sec,time_raw_bias_sec,margin_score,
          runperf_raw,coefficient_snapshot_target_year,coefficient_asof_through_year,
          coefficient_intercept,coefficient_beta_time,coefficient_beta_margin,score_provenance
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """
    rows: list[tuple[Any, ...]] = []
    materialized = 0
    scored = 0
    for row in cursor:
        materialized += 1
        source_status = str(row["source_calculation_status"])
        expected_time = row["expected_time_sec"]
        day_bias = row["day_bias_raw_sec"]
        time_raw = row["time_residual_raw_bias_sec"]
        margin_score = None
        if _is_finite(row["margin_per_1000m_sec"]):
            margin_score = -float(row["margin_per_1000m_sec"])

        score_status = "EXCLUDED_SOURCE_CALCULATION_STATUS"
        runperf_raw = None
        snapshot_target_year = None
        snapshot_asof_year = None
        intercept = None
        beta_time = None
        beta_margin = None
        provenance = "EXCLUDED_SOURCE_CALCULATION_STATUS"
        if source_status == "OK":
            components = (expected_time, day_bias, time_raw, margin_score)
            if not all(_is_finite(value) for value in components):
                score_status = "EXCLUDED_NONFINITE_COMPONENT"
                provenance = "EXCLUDED_NONFINITE_COMPONENT"
            else:
                snapshot_target_year = _snapshot_year_for_run(int(row["year"]))
                snapshot = snapshots.get(snapshot_target_year)
                if snapshot is None:
                    raise ValueError(f"missing required coefficient snapshot {snapshot_target_year}")
                coefficients = snapshot["coefficients"]
                snapshot_asof_year = int(snapshot["coefficient_asof_through_year"])
                intercept = float(snapshot["intercept"])
                beta_time = float(coefficients["time_raw_bias"])
                beta_margin = float(coefficients["prev_margin_score"])
                runperf_raw = intercept + beta_time * float(time_raw) + beta_margin * float(margin_score)
                if not _is_finite(runperf_raw):
                    raise ValueError("RunPerf arithmetic produced a non-finite result")
                score_status = "OK"
                provenance = _score_provenance(int(row["year"]))
                scored += 1

        rows.append(
            (
                row["race_key"], row["race_date"], row["year"], row["horse_no"], row["horse_id"],
                source_status, score_status, expected_time, day_bias, time_raw, margin_score,
                runperf_raw, snapshot_target_year, snapshot_asof_year, intercept, beta_time,
                beta_margin, provenance,
            )
        )
        if len(rows) >= 10000:
            target.executemany(insert_sql, rows)
            rows.clear()
    if rows:
        target.executemany(insert_sql, rows)
    return materialized, scored


def build(source_db: Path, output_db: Path, schema_path: Path) -> dict[str, Any]:
    """Build one official v0.1 SQLite database from an audited candidate DB."""
    if output_db.exists():
        output_db.unlink()
    started_at = dt.datetime.now().isoformat(timespec="seconds")
    source = sqlite3.connect(f"file:{source_db}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    target = sqlite3.connect(output_db)
    try:
        year_min, year_max, source_count = _load_source_years(source)
        target.executescript(schema_path.read_text(encoding="utf-8"))
        target.execute(
            """
            INSERT INTO meta_official_runperf_build(
              build_id,builder_version,schema_version,source_runperf_db_path,
              source_runperf_db_sha256,official_candidate,baseline_method,first_model_year,
              started_at,status,source_year_min,source_year_max,source_runner_count
            ) VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                VERSION, SCHEMA_VERSION, str(source_db), _sha256(source_db), OFFICIAL_CANDIDATE,
                BASELINE_METHOD, FIRST_MODEL_YEAR, started_at, "RUNNING", year_min, year_max, source_count,
            ),
        )
        snapshots = _build_snapshots(source_db, year_max)
        _insert_snapshots(target, snapshots)
        materialized_count, scored_count = _materialize_rows(source, target, snapshots)
        target.execute(
            """
            UPDATE meta_official_runperf_build
            SET finished_at=?,status='SUCCESS',materialized_runner_count=?,scored_runner_count=?,message=?
            WHERE build_id=1
            """,
            (
                dt.datetime.now().isoformat(timespec="seconds"), materialized_count, scored_count,
                "Materialized frozen T1|EXPANDING|RAW with annual as-of snapshots and explicit exclusions.",
            ),
        )
        target.commit()
        return {
            "status": "SUCCESS",
            "official_candidate": OFFICIAL_CANDIDATE,
            "source_year_min": year_min,
            "source_year_max": year_max,
            "source_runner_count": source_count,
            "materialized_runner_count": materialized_count,
            "scored_runner_count": scored_count,
            "snapshot_count": len(snapshots),
        }
    except Exception as exc:
        target.rollback()
        try:
            target.execute(
                "UPDATE meta_official_runperf_build SET status='FAILED',finished_at=?,message=? WHERE build_id=1",
                (dt.datetime.now().isoformat(timespec="seconds"), str(exc)),
            )
            target.commit()
        except sqlite3.Error:
            pass
        raise
    finally:
        source.close()
        target.close()


def _default_schema_path() -> Path:
    """Return the repository schema path for normal CLI operation."""
    return Path(__file__).resolve().parents[1] / "schema" / "jrdb_official_runperf_schema_v0_1.sql"


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--runperf-db", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=_default_schema_path())
    args = parser.parse_args()
    print(json.dumps(build(args.runperf_db, args.out, args.schema), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
