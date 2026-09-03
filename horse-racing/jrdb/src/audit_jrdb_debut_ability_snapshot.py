#!/usr/bin/env python3
"""Audit Debut/no-scored-history Ability snapshot chronology and structural coverage."""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any


def _date_token(value: Any) -> str | None:
    """Normalize date-like values to YYYYMMDD."""
    if value is None:
        return None
    text = str(value).strip().replace("-", "").replace("/", "")
    if len(text) < 8 or not text[:8].isdigit():
        return None
    return text[:8]


def _columns(connection: sqlite3.Connection, table: str) -> list[str]:
    """Return table column names."""
    return [str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")]


def _history_maps(
    index_connection: sqlite3.Connection,
    official_connection: sqlite3.Connection,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Load chronological all-start and scored-RunPerf history dates by horse."""
    starts: dict[str, list[str]] = defaultdict(list)
    for horse_id, race_date in index_connection.execute(
        """
        SELECT p.horse_id,r.race_date
        FROM runner_pre p JOIN race_context r ON r.race_key=p.race_key
        WHERE p.horse_id IS NOT NULL AND p.horse_id<>''
        ORDER BY p.horse_id,r.race_date
        """
    ):
        token = _date_token(race_date)
        if token is not None:
            starts[str(horse_id)].append(token)

    scored: dict[str, list[str]] = defaultdict(list)
    for horse_id, race_date in official_connection.execute(
        """
        SELECT horse_id,race_date
        FROM official_runperf
        WHERE horse_id IS NOT NULL AND horse_id<>''
          AND score_status='OK' AND runperf_raw IS NOT NULL
        ORDER BY horse_id,race_date
        """
    ):
        token = _date_token(race_date)
        if token is not None:
            scored[str(horse_id)].append(token)
    return dict(starts), dict(scored)


def _count_prior(dates: list[str] | None, target: str) -> int:
    """Count dates strictly earlier than target without treating same-day as prior."""
    if not dates:
        return 0
    count = 0
    for value in dates:
        if value < target:
            count += 1
        else:
            break
    return count


def audit(database: Path, index_db: Path, official_runperf_db: Path) -> dict[str, Any]:
    """Run structural and chronology gates without predictive model evaluation."""
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    index_connection = sqlite3.connect(f"file:{index_db}?mode=ro", uri=True)
    official_connection = sqlite3.connect(f"file:{official_runperf_db}?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        target_rows = connection.execute(
            """
            SELECT race_date,race_key,horse_no,horse_id,year,prior_start_count,is_true_first_start,
                   race_context_availability,profile_data_date,profile_prior_day_available,
                   profile_same_day_observation_exists,validation_status
            FROM debut_target_runner ORDER BY race_date,race_key,horse_no
            """
        ).fetchall()
        starts, scored = _history_maps(index_connection, official_connection)

        duplicate_count = connection.execute(
            """
            SELECT COUNT(*) FROM (
              SELECT race_key,horse_no,COUNT(*) n
              FROM debut_target_runner GROUP BY race_key,horse_no HAVING n<>1
            )
            """
        ).fetchone()[0]
        pedigree_count = connection.execute("SELECT COUNT(*) FROM debut_pedigree_feature").fetchone()[0]
        training_count = connection.execute("SELECT COUNT(*) FROM debut_training_feature").fetchone()[0]
        people_count = connection.execute("SELECT COUNT(*) FROM debut_people_prior_feature").fetchone()[0]
        result_count = connection.execute("SELECT COUNT(*) FROM debut_current_result").fetchone()[0]

        target_definition_violation = 0
        prior_start_count_violation = 0
        true_first_flag_violation = 0
        profile_future_use = 0
        profile_availability_contract_violation = 0
        missing_horse_identity = 0
        fallback_target_count = 0
        for (
            race_date,race_key,horse_no,horse_id,year,stored_prior_starts,stored_true_first,
            availability,profile_date,profile_prior_day_available,same_day_exists,validation_status,
        ) in target_rows:
            target = _date_token(race_date)
            if target is None:
                target_definition_violation += 1
                continue
            horse_key = str(horse_id) if horse_id not in (None, "") else ""
            if not horse_key:
                missing_horse_identity += 1
            else:
                actual_prior_scored = _count_prior(scored.get(horse_key), target)
                if actual_prior_scored != 0:
                    target_definition_violation += 1
                actual_prior_starts = _count_prior(starts.get(horse_key), target)
                if int(stored_prior_starts) != actual_prior_starts:
                    prior_start_count_violation += 1
                expected_true_first = 1 if actual_prior_starts == 0 else 0
                if int(stored_true_first) != expected_true_first:
                    true_first_flag_violation += 1
            if profile_date is not None:
                profile_token = _date_token(profile_date)
                if profile_token is None:
                    profile_availability_contract_violation += 1
                elif profile_token > target:
                    profile_future_use += 1
                elif profile_token < target and int(profile_prior_day_available) != 1:
                    profile_availability_contract_violation += 1
                elif profile_token == target and int(same_day_exists) != 1:
                    profile_availability_contract_violation += 1
            elif int(profile_prior_day_available) != 0 or int(same_day_exists) != 0:
                profile_availability_contract_violation += 1
            if availability != "PRE_RACE":
                fallback_target_count += 1

        evidence_contract_violation = 0
        nonfinite_feature_count = 0
        pedigree_rows = connection.execute("SELECT * FROM debut_pedigree_feature").fetchall()
        pedigree_columns = _columns(connection, "debut_pedigree_feature")
        for row in pedigree_rows:
            values = dict(zip(pedigree_columns, row))
            for prefix in (
                "sire_debut","broodmare_sire_debut","sire_line_debut","broodmare_sire_line_debut",
                "sire_surface_debut","broodmare_sire_surface_debut",
            ):
                n = int(values[f"{prefix}_n"])
                missing = int(values[f"{prefix}_missing"])
                raw = values[f"{prefix}_runperf_raw"]
                if (n == 0) != (missing == 1):
                    evidence_contract_violation += 1
                if n == 0 and raw is not None:
                    evidence_contract_violation += 1
                if raw is not None and not math.isfinite(float(raw)):
                    nonfinite_feature_count += 1
            for base in ("sire_distance", "broodmare_sire_distance"):
                for bandwidth in (200,400,600,800):
                    prefix = f"{base}_d{bandwidth}"
                    n = int(values[f"{prefix}_n"])
                    neff = values[f"{prefix}_neff"]
                    missing = int(values[f"{prefix}_missing"])
                    raw = values[f"{prefix}_raw"]
                    if (n == 0) != (missing == 1):
                        evidence_contract_violation += 1
                    if n == 0:
                        if raw is not None or neff is not None:
                            evidence_contract_violation += 1
                    else:
                        if raw is None or neff is None:
                            evidence_contract_violation += 1
                        elif float(neff) <= 0 or float(neff) > n + 1e-9:
                            evidence_contract_violation += 1
                    for numeric in (raw, neff):
                        if numeric is not None and not math.isfinite(float(numeric)):
                            nonfinite_feature_count += 1

        people_contract_violation = 0
        people_rows = connection.execute("SELECT * FROM debut_people_prior_feature").fetchall()
        people_columns = _columns(connection, "debut_people_prior_feature")
        for row in people_rows:
            values = dict(zip(people_columns, row))
            for prefix in ("jockey_debut", "trainer_debut"):
                n = int(values[f"{prefix}_n"])
                missing = int(values[f"{prefix}_missing"])
                raw = values[f"{prefix}_runperf_raw"]
                if (n == 0) != (missing == 1):
                    people_contract_violation += 1
                if n == 0 and raw is not None:
                    people_contract_violation += 1
                if raw is not None and not math.isfinite(float(raw)):
                    nonfinite_feature_count += 1

        table_names = (
            "debut_target_runner","debut_pedigree_feature","debut_training_feature",
            "debut_people_prior_feature","debut_current_result",
        )
        forbidden_markers = ("odds", "popularity", "market")
        market_columns = [
            f"{table}.{column}"
            for table in table_names
            for column in _columns(connection, table)
            if any(marker in column.lower() for marker in forbidden_markers)
        ]

        target_count = len(target_rows)
        count_reconciliation_violation = sum(
            1 for value in (pedigree_count,training_count,people_count,result_count) if int(value) != target_count
        )

        annual = []
        for year in sorted({int(row[4]) for row in target_rows}):
            summary = connection.execute(
                """
                SELECT
                  COUNT(*),
                  SUM(is_true_first_start),
                  SUM(profile_prior_day_available),
                  SUM(profile_same_day_observation_exists),
                  SUM(CASE WHEN profile_data_date IS NOT NULL THEN 1 ELSE 0 END),
                  SUM(CASE WHEN profile_data_date=race_date THEN 1 ELSE 0 END)
                FROM debut_target_runner WHERE year=?
                """,
                (year,),
            ).fetchone()
            coverage = connection.execute(
                """
                SELECT
                  SUM(CASE WHEN p.sire_debut_missing=0 THEN 1 ELSE 0 END),
                  SUM(CASE WHEN p.broodmare_sire_debut_missing=0 THEN 1 ELSE 0 END),
                  SUM(CASE WHEN p.sire_line_debut_missing=0 THEN 1 ELSE 0 END),
                  SUM(CASE WHEN p.broodmare_sire_line_debut_missing=0 THEN 1 ELSE 0 END),
                  SUM(CASE WHEN tr.cha_missing=0 THEN 1 ELSE 0 END),
                  SUM(CASE WHEN tr.cyb_missing=0 THEN 1 ELSE 0 END),
                  SUM(CASE WHEN pe.jockey_debut_missing=0 THEN 1 ELSE 0 END),
                  SUM(CASE WHEN pe.trainer_debut_missing=0 THEN 1 ELSE 0 END)
                FROM debut_target_runner t
                JOIN debut_pedigree_feature p USING(race_key,horse_no)
                JOIN debut_training_feature tr USING(race_key,horse_no)
                JOIN debut_people_prior_feature pe USING(race_key,horse_no)
                WHERE t.year=?
                """,
                (year,),
            ).fetchone()
            count = int(summary[0] or 0)
            annual.append(
                {
                    "year":year,
                    "target_count":count,
                    "true_first_start_count":int(summary[1] or 0),
                    "profile_prior_day_coverage":float(summary[2] or 0)/count if count else 0.0,
                    "profile_same_day_observation_rate":float(summary[3] or 0)/count if count else 0.0,
                    "profile_selected_pre_race_coverage":float(summary[4] or 0)/count if count else 0.0,
                    "profile_same_day_selected_rate":float(summary[5] or 0)/count if count else 0.0,
                    "sire_prior_coverage":float(coverage[0] or 0)/count if count else 0.0,
                    "broodmare_sire_prior_coverage":float(coverage[1] or 0)/count if count else 0.0,
                    "sire_line_prior_coverage":float(coverage[2] or 0)/count if count else 0.0,
                    "broodmare_sire_line_prior_coverage":float(coverage[3] or 0)/count if count else 0.0,
                    "cha_coverage":float(coverage[4] or 0)/count if count else 0.0,
                    "cyb_coverage":float(coverage[5] or 0)/count if count else 0.0,
                    "jockey_prior_coverage":float(coverage[6] or 0)/count if count else 0.0,
                    "trainer_prior_coverage":float(coverage[7] or 0)/count if count else 0.0,
                }
            )

        violations = {
            "integrity_failure":0 if integrity == "ok" else 1,
            "duplicate_target_key":int(duplicate_count),
            "target_definition_violation":target_definition_violation,
            "prior_start_count_violation":prior_start_count_violation,
            "true_first_flag_violation":true_first_flag_violation,
            "missing_horse_identity_count":missing_horse_identity,
            "profile_future_use":profile_future_use,
            "profile_availability_contract_violation":profile_availability_contract_violation,
            "count_reconciliation_violation":count_reconciliation_violation,
            "pedigree_evidence_contract_violation":evidence_contract_violation,
            "people_evidence_contract_violation":people_contract_violation,
            "nonfinite_feature_count":nonfinite_feature_count,
            "market_column_count":len(market_columns),
        }
        total_violations = sum(int(value) for value in violations.values())
        return {
            "status":"PASS" if total_violations == 0 else "FAIL",
            "target_runner_count":target_count,
            "missing_horse_identity_count":missing_horse_identity,
            "fallback_target_count":fallback_target_count,
            "violations":violations,
            "market_columns":market_columns,
            "annual":annual,
            "2024_2025_predictive_metrics_inspected":False,
            "model_selected":False,
        }
    finally:
        official_connection.close()
        index_connection.close()
        connection.close()


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--db",required=True,type=Path)
    parser.add_argument("--index-db",required=True,type=Path)
    parser.add_argument("--official-runperf-db",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    args = parser.parse_args()
    report = audit(args.db,args.index_db,args.official_runperf_db)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps({"status":report["status"],"violations":report["violations"]},ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
