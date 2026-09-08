#!/usr/bin/env python3
"""Build leakage-safe Phase1 Edge Feature Mart from JRDB Index Base v0.1."""
from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
from pathlib import Path
from typing import Any

VERSION = "0.1.0"
SCHEMA_VERSION = "v0.1"


def _frame_zone(frame_no: int | None) -> str | None:
    if frame_no is None:
        return None
    if frame_no <= 3:
        return "INNER"
    if frame_no <= 6:
        return "MIDDLE"
    return "OUTER"


def _distance_bucket(delta: int | None) -> str | None:
    if delta is None:
        return None
    if delta <= -400:
        return "LARGE_SHORTEN"
    if delta <= -200:
        return "SHORTEN"
    if delta < 200:
        return "SAME_BAND"
    if delta < 400:
        return "EXTEND"
    return "LARGE_EXTEND"


def _transition(before: str | None, after: str | None) -> str | None:
    if not before or not after:
        return None
    return f"{before}->{after}"


def _status(row: sqlite3.Row) -> str:
    if row["source_availability_class"] != "PRE_RACE":
        return "SOURCE_NOT_PRE_RACE"
    if row["label_finish"] is None:
        return "NO_RESULT"
    abnormal = (row["label_abnormal_code"] or "").strip()
    if abnormal not in {"", "0"}:
        return "ABNORMAL"
    return "ELIGIBLE"


def _required_tables(connection: sqlite3.Connection) -> None:
    required = {
        "race_context",
        "runner_pre",
        "runner_previous_link",
        "runner_result",
        "horse_profile_observation",
    }
    existing = {
        row[0]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    missing = required - existing
    if missing:
        raise ValueError(f"Index Base is missing required table(s): {sorted(missing)}")


def build(source: str | Path, output: str | Path, schema: str | Path) -> dict[str, int | str]:
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
        query = """
        SELECT
          r.race_key, p.horse_no, r.race_date, r.venue_code, r.race_no,
          r.distance_m, r.surface_code, r.turn_code, r.inner_outer_code,
          r.race_condition_code, r.grade_code, r.declared_field_size,
          r.availability_class AS source_availability_class,
          p.frame_no, p.horse_id, p.horse_name, p.sex_code,
          p.jockey_code, p.jockey_name, p.trainer_code, p.trainer_name,
          p.carried_weight_kg, p.running_style_code, p.rotation_interval,
          p.condition_class_code,
          hp.data_date AS profile_asof_date, hp.sire_name, hp.sire_line_code,
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
        insert_sql = """
        INSERT INTO edge_runner_fact VALUES (
          ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
        )
        """
        rows = 0
        pre_race_eligible = 0
        result_labeled = 0
        anomalies = 0
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
            win_hit = None if row["label_win_payout"] is None else int(row["label_win_payout"] > 0)
            place_hit = None if row["label_place_payout"] is None else int(row["label_place_payout"] > 0)
            status = _status(row)
            is_pre = int(row["source_availability_class"] == "PRE_RACE")
            values: tuple[Any, ...] = (
                row["race_key"], row["horse_no"], row["race_date"], row["venue_code"], row["race_no"],
                row["distance_m"], row["surface_code"], row["turn_code"], row["inner_outer_code"],
                row["race_condition_code"], row["grade_code"], row["declared_field_size"],
                row["source_availability_class"], is_pre,
                row["frame_no"], current_zone, row["horse_id"], row["horse_name"], row["sex_code"],
                row["jockey_code"], row["jockey_name"], row["trainer_code"], row["trainer_name"],
                row["carried_weight_kg"], row["running_style_code"], row["rotation_interval"],
                row["condition_class_code"], row["profile_asof_date"], row["sire_name"], row["sire_line_code"],
                row["broodmare_sire_name"], row["broodmare_sire_line_code"],
                row["prev1_result_key"], row["prev1_race_key"], row["prev1_race_date"],
                row["prev1_venue_code"], row["prev1_distance_m"], row["prev1_surface_code"], row["prev1_turn_code"],
                row["prev1_frame_no"], row["prev1_finish"], delta, _distance_bucket(delta),
                _transition(row["prev1_surface_code"], row["surface_code"]), _transition(prev_zone, current_zone),
                row["label_finish"], row["label_abnormal_code"], win_hit, place_hit,
                row["label_win_payout"], row["label_place_payout"], row["label_final_win_odds"],
                row["label_final_win_popularity"], status,
            )
            out.execute(insert_sql, values)
            rows += 1
            pre_race_eligible += is_pre
            result_labeled += int(row["label_finish"] is not None)
        built_at = dt.datetime.now(dt.timezone.utc).isoformat()
        out.execute(
            """INSERT INTO meta_edge_feature_mart_build(
              builder_version,schema_version,source_path,built_at,row_count,
              pre_race_eligible_count,result_labeled_count,anomaly_count,status,message
            ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                VERSION, SCHEMA_VERSION, str(source_path), built_at, rows,
                pre_race_eligible, result_labeled, anomalies, "VALID", None,
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
            "anomalies": anomalies,
        }
    finally:
        src.close()
        out.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="JRDB Index Base v0.1 SQLite")
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--schema",
        default=str(Path(__file__).resolve().parents[1] / "schema/jrdb_edge_feature_mart_schema_v0_1.sql"),
    )
    args = parser.parse_args()
    print(build(args.source, args.output, args.schema))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
