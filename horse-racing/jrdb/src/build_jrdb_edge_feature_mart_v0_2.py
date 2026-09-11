#!/usr/bin/env python3
"""Build JRDB Edge Feature Mart v0.2 from Index Base v0.1.

Most condition fields are pre-race. Historical track condition is the explicit
exception: it is read first from ``race_result_context`` (SED-derived race
context) into an isolated race-level snapshot, then result labels are joined in
a separate query. This supports historical discovery such as sire x going
without exposing finish/payout columns to the condition-extraction step.

v0.2 flat-racing Edge discovery is explicitly scoped to turf/dirt. Obstacle
(surface_code=3) rows are retained for audit but marked ineligible so they do
not enter either candidate samples or their baselines.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
from pathlib import Path
from typing import Any

from jrdb_edge_canonical import (
    distance_bucket as _distance_bucket,
    frame_zone as _frame_zone,
    transition as _transition,
)
from jrdb_edge_v02_canonical import (
    canonical_stable_evaluation_code,
    canonical_training_arrow_code,
    canonical_uptrend_code,
    horse_age_at_race,
    track_condition_bucket,
)

VERSION = "0.2.4"
SCHEMA_VERSION = "v0.2"
DEFAULT_SCHEMA = Path(__file__).resolve().parents[1] / "schema/jrdb_edge_feature_mart_schema_v0_2.sql"


def _status(row: sqlite3.Row | dict[str, Any]) -> str:
    if row["source_availability_class"] != "PRE_RACE":
        return "SOURCE_NOT_PRE_RACE"
    if str(row["surface_code"] or "").strip() == "3":
        return "EXCLUDED_OBSTACLE"
    if row["label_finish"] is None:
        return "NO_RESULT"
    abnormal = (row["label_abnormal_code"] or "").strip()
    if abnormal not in {"", "0"}:
        return "ABNORMAL"
    return "ELIGIBLE"


def _required_tables(connection: sqlite3.Connection) -> None:
    required = {
        "race_context",
        "race_result_context",
        "runner_pre",
        "runner_previous_link",
        "runner_result",
        "horse_profile_observation",
    }
    existing = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    missing = required - existing
    if missing:
        raise ValueError(f"Index Base is missing required table(s): {sorted(missing)}")


def _historical_track_condition_snapshot(connection: sqlite3.Connection) -> dict[str, tuple[str, str]]:
    """Read only SED-derived race condition context, without runner results."""
    snapshot: dict[str, tuple[str, str]] = {}
    for row in connection.execute(
        "SELECT race_key, track_condition_code FROM race_result_context ORDER BY race_key"
    ):
        raw = str(row[1] or "").strip()
        bucket = track_condition_bucket(raw)
        if raw and bucket is not None:
            snapshot[str(row[0])] = (raw, bucket)
    return snapshot


def build(source: str | Path, output: str | Path, schema: str | Path = DEFAULT_SCHEMA) -> dict[str, int | float | str]:
    source_path = Path(source)
    output_path = Path(output)
    schema_path = Path(schema)
    if output_path.exists():
        output_path.unlink()

    src = sqlite3.connect(source_path)
    src.row_factory = sqlite3.Row
    out = sqlite3.connect(output_path)
    try:
        _required_tables(src)
        out.executescript(schema_path.read_text(encoding="utf-8"))
        track_snapshot = _historical_track_condition_snapshot(src)

        query = """
        SELECT
          r.race_key, p.horse_no, r.race_date, r.venue_code, r.race_no,
          r.distance_m, r.surface_code, r.turn_code, r.inner_outer_code,
          r.race_condition_code, r.grade_code, r.declared_field_size,
          r.availability_class AS source_availability_class,
          p.frame_no, p.horse_id, p.horse_name, p.sex_code,
          p.jockey_code, p.jockey_name, p.trainer_code, p.trainer_name,
          p.carried_weight_kg, p.running_style_code, p.rotation_interval,
          p.pre_idm, p.training_score, p.stable_score, p.uptrend_code,
          p.training_arrow_code, p.stable_evaluation_code,
          p.body_weight_pre_kg, p.body_weight_change_pre_kg,
          p.condition_class_code,
          hp.data_date AS profile_asof_date, hp.birth_date,
          hp.sire_name, hp.sire_line_code,
          hp.broodmare_sire_name, hp.broodmare_sire_line_code,
          pl.prev_result_key AS prev1_result_key, pl.prev_race_key AS prev1_race_key,
          prc.race_date AS prev1_race_date, prc.venue_code AS prev1_venue_code,
          prc.distance_m AS prev1_distance_m, prc.surface_code AS prev1_surface_code,
          prc.turn_code AS prev1_turn_code, pp.frame_no AS prev1_frame_no,
          pres.finish AS prev1_finish,
          res.finish AS label_finish, res.abnormal_code AS label_abnormal_code,
          res.win_payout AS label_win_payout, res.place_payout AS label_place_payout,
          res.final_win_odds AS label_final_win_odds,
          res.final_win_popularity AS label_final_win_popularity
        FROM race_context r
        JOIN runner_pre p ON p.race_key = r.race_key
        LEFT JOIN runner_result res
          ON res.race_key = p.race_key AND res.horse_no = p.horse_no
        LEFT JOIN runner_previous_link pl
          ON pl.race_key = p.race_key AND pl.horse_no = p.horse_no AND pl.sequence = 1
        LEFT JOIN runner_result pres ON pres.result_key = pl.prev_result_key
        LEFT JOIN race_context prc ON prc.race_key = pres.race_key
        LEFT JOIN runner_pre pp
          ON pp.race_key = pres.race_key AND pp.horse_no = pres.horse_no
        LEFT JOIN horse_profile_observation hp
          ON hp.rowid = (
            SELECT hp2.rowid
            FROM horse_profile_observation hp2
            WHERE hp2.horse_id = p.horse_id AND hp2.data_date <= r.race_date
            ORDER BY hp2.data_date DESC, hp2.rowid DESC
            LIMIT 1
          )
        ORDER BY r.race_date, r.race_key, p.horse_no
        """

        columns = [row[1] for row in out.execute("PRAGMA table_info(edge_runner_fact)")]
        insert_sql = (
            f"INSERT INTO edge_runner_fact ({','.join(columns)}) "
            f"VALUES ({','.join('?' for _ in columns)})"
        )

        rows = pre_race_eligible = result_labeled = anomalies = 0
        historical_track_condition_rows = excluded_obstacle_count = 0
        eligible_labels = win_hits = place_hits = 0
        for row in src.execute(query):
            if row["profile_asof_date"] and row["profile_asof_date"] > row["race_date"]:
                raise ValueError("profile observation leaks from the future")
            if row["prev1_race_date"] and row["prev1_race_date"] >= row["race_date"]:
                anomalies += 1
                raise ValueError(
                    f"previous race is not strictly prior: {row['race_key']} horse {row['horse_no']}"
                )

            current_zone = _frame_zone(row["frame_no"])
            prev_zone = _frame_zone(row["prev1_frame_no"])
            delta = None
            if row["distance_m"] is not None and row["prev1_distance_m"] is not None:
                delta = int(row["distance_m"]) - int(row["prev1_distance_m"])

            if row["label_finish"] is None:
                win_hit = place_hit = None
            else:
                win_hit = int(int(row["label_finish"]) == 1)
                place_hit = int((row["label_place_payout"] or 0) > 0)

            status = _status(row)
            excluded_obstacle_count += int(status == "EXCLUDED_OBSTACLE")
            is_pre = int(row["source_availability_class"] == "PRE_RACE")
            track = track_snapshot.get(str(row["race_key"]))
            raw_track = track[0] if track else None
            track_bucket = track[1] if track else None
            track_source = "HISTORICAL_RESULT_CONTEXT" if track else None
            historical_track_condition_rows += int(track is not None)

            values: dict[str, Any] = {
                "race_key": row["race_key"],
                "horse_no": row["horse_no"],
                "race_date": row["race_date"],
                "venue_code": row["venue_code"],
                "race_no": row["race_no"],
                "distance_m": row["distance_m"],
                "surface_code": row["surface_code"],
                "turn_code": row["turn_code"],
                "inner_outer_code": row["inner_outer_code"],
                "race_condition_code": row["race_condition_code"],
                "grade_code": row["grade_code"],
                "declared_field_size": row["declared_field_size"],
                "source_availability_class": row["source_availability_class"],
                "is_pre_race_eligible": is_pre,
                "track_condition_code": raw_track,
                "track_condition_bucket": track_bucket,
                "track_condition_source_class": track_source,
                "frame_no": row["frame_no"],
                "frame_zone": current_zone,
                "horse_id": row["horse_id"],
                "horse_name": row["horse_name"],
                "sex_code": row["sex_code"],
                "horse_age": horse_age_at_race(row["race_date"], row["birth_date"]),
                "jockey_code": row["jockey_code"],
                "jockey_name": row["jockey_name"],
                "trainer_code": row["trainer_code"],
                "trainer_name": row["trainer_name"],
                "carried_weight_kg": row["carried_weight_kg"],
                "running_style_code": row["running_style_code"],
                "rotation_interval": row["rotation_interval"],
                "pre_idm": row["pre_idm"],
                "training_score": row["training_score"],
                "stable_score": row["stable_score"],
                "uptrend_code": canonical_uptrend_code(row["uptrend_code"]),
                "training_arrow_code": canonical_training_arrow_code(row["training_arrow_code"]),
                "stable_evaluation_code": canonical_stable_evaluation_code(row["stable_evaluation_code"]),
                "body_weight_pre_kg": row["body_weight_pre_kg"],
                "body_weight_change_pre_kg": row["body_weight_change_pre_kg"],
                "condition_class_code": row["condition_class_code"],
                "horse_quality_rank_pct": None,
                "horse_quality_bucket": None,
                "horse_quality_expected_place": None,
                "horse_quality_place_residual": None,
                "horse_quality_model_version": None,
                "horse_quality_model_cutoff_year": None,
                "profile_asof_date": row["profile_asof_date"],
                "birth_date": row["birth_date"],
                "sire_name": row["sire_name"],
                "sire_line_code": row["sire_line_code"],
                "broodmare_sire_name": row["broodmare_sire_name"],
                "broodmare_sire_line_code": row["broodmare_sire_line_code"],
                "prev1_result_key": row["prev1_result_key"],
                "prev1_race_key": row["prev1_race_key"],
                "prev1_race_date": row["prev1_race_date"],
                "prev1_venue_code": row["prev1_venue_code"],
                "prev1_distance_m": row["prev1_distance_m"],
                "prev1_surface_code": row["prev1_surface_code"],
                "prev1_turn_code": row["prev1_turn_code"],
                "prev1_frame_no": row["prev1_frame_no"],
                "prev1_finish": row["prev1_finish"],
                "distance_change_m": delta,
                "distance_change_bucket": _distance_bucket(delta),
                "surface_transition": _transition(row["prev1_surface_code"], row["surface_code"]),
                "frame_transition": _transition(prev_zone, current_zone),
                "label_finish": row["label_finish"],
                "label_abnormal_code": row["label_abnormal_code"],
                "label_win_hit": win_hit,
                "label_place_hit": place_hit,
                "label_win_payout": row["label_win_payout"],
                "label_place_payout": row["label_place_payout"],
                "label_final_win_odds": row["label_final_win_odds"],
                "label_final_win_popularity": row["label_final_win_popularity"],
                "calculation_status": status,
            }
            out.execute(insert_sql, tuple(values[c] for c in columns))
            rows += 1
            pre_race_eligible += is_pre
            result_labeled += int(row["label_finish"] is not None)
            if status == "ELIGIBLE":
                eligible_labels += 1
                win_hits += int(win_hit or 0)
                place_hits += int(place_hit or 0)

        win_hit_rate = win_hits / eligible_labels if eligible_labels else 0.0
        place_hit_rate = place_hits / eligible_labels if eligible_labels else 0.0
        if eligible_labels >= 1000:
            if not (0.0 < win_hit_rate < 0.25):
                raise ValueError(f"implausible overall win hit rate: {win_hit_rate:.6f}")
            if not (win_hit_rate < place_hit_rate < 0.60):
                raise ValueError(f"implausible overall place hit rate: {place_hit_rate:.6f}")

        built_at = dt.datetime.now(dt.timezone.utc).isoformat()
        out.execute(
            """INSERT INTO meta_edge_feature_mart_build(
              builder_version,schema_version,source_path,built_at,row_count,
              pre_race_eligible_count,result_labeled_count,historical_track_condition_count,
              excluded_obstacle_count,anomaly_count,status,message
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                VERSION, SCHEMA_VERSION, str(source_path), built_at, rows,
                pre_race_eligible, result_labeled, historical_track_condition_rows,
                excluded_obstacle_count, anomalies, "VALID", None,
            ),
        )
        out.commit()
        integrity = out.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError(f"Edge Feature Mart integrity_check failed: {integrity}")
        return {
            "status": "PASS",
            "rows": rows,
            "pre_race_eligible": pre_race_eligible,
            "result_labeled": result_labeled,
            "historical_track_condition_rows": historical_track_condition_rows,
            "historical_track_condition_races": len(track_snapshot),
            "excluded_obstacle": excluded_obstacle_count,
            "eligible_labels": eligible_labels,
            "win_hits": win_hits,
            "place_hits": place_hits,
            "win_hit_rate": win_hit_rate,
            "place_hit_rate": place_hit_rate,
            "anomalies": anomalies,
        }
    finally:
        src.close()
        out.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="JRDB Index Base v0.1 SQLite")
    parser.add_argument("--output", required=True)
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    args = parser.parse_args()
    print(build(args.source, args.output, args.schema))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
