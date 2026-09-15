#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evaluate_training_edge_v0_2_oot import SOURCE_COLUMNS  # noqa: E402
from score_training_edge_v0_2_daily import _display_index, score_day  # noqa: E402
from training_edge_v0_2_core import VERSION as CORE_VERSION  # noqa: E402


def _row(
    race_date: str,
    year: int,
    race_key: str,
    horse_no: int,
    horse_id: str,
    sequence: int,
) -> dict[str, object]:
    row = {column: None for column in SOURCE_COLUMNS}
    row.update(
        {
            "race_date": race_date,
            "year": year,
            "race_key": race_key,
            "horse_no": horse_no,
            "horse_id": horse_id,
            "trainer_code": "00001",
            "trainer_name": "trainer",
            "days_since_last_run": 90,
            "days_before_race": 3,
            "workout_count": 2,
            "course_code": "12",
            "effort_code": "1",
            "chase_state_code": "00",
            "rider_type_code": "1",
            "furlong_count": 5,
            "final_segment_sec": 12.8 - (sequence % 7) * 0.05 - horse_no * 0.01,
            "pair_result_code": "1",
            "pair_effort_code": "1",
            "pair_class_code": "03",
            "jrdb_final_segment_index": 50 + (sequence % 5) + horse_no,
            "jrdb_workout_index_cha": 48 + (sequence % 4) + horse_no,
            "training_type_code": "01",
            "training_course_type_code": "1",
            "used_slope": 0,
            "used_wood": 1,
            "used_dirt": 0,
            "used_turf": 0,
            "used_pool": 0,
            "used_jump": 0,
            "used_polytrack": 0,
            "training_distance_code": "2",
            "training_focus_code": "1",
            "training_volume_code": "2",
            "week_ago_course_code": "12",
            "finish_index": 52 + (sequence % 6) + horse_no,
            "kyi_training_score": 55.0 + (sequence % 8) + horse_no,
            "kyi_training_arrow_code": "2",
            "official_runperf_raw": 0.01 * ((sequence % 9) - 4) + horse_no * 0.002,
            "runperf_score_status": "OK",
        }
    )
    return row


def _build_projection(path: Path) -> str:
    rows: list[dict[str, object]] = []
    sequence = 0
    for year in range(2010, 2026):
        for month, day in ((1, 10), (4, 10), (7, 10), (10, 10)):
            sequence += 1
            race_date = f"{year:04d}-{month:02d}-{day:02d}"
            race_key = f"06{sequence:06d}"
            for horse_no in range(1, 4):
                rows.append(
                    _row(
                        race_date,
                        year,
                        race_key,
                        horse_no,
                        f"H{horse_no:07d}",
                        sequence,
                    )
                )

    target_key = "06999999"
    for horse_no in range(1, 4):
        row = _row(
            "2026-09-19",
            2026,
            target_key,
            horse_no,
            f"H{horse_no:07d}",
            sequence + 1,
        )
        row["official_runperf_raw"] = None
        row["runperf_score_status"] = None
        rows.append(row)

    newcomer = _row(
        "2026-09-19",
        2026,
        target_key,
        4,
        "NEW00001",
        sequence + 1,
    )
    newcomer["official_runperf_raw"] = None
    newcomer["runperf_score_status"] = None
    rows.append(newcomer)

    frame = pd.DataFrame(rows, columns=list(SOURCE_COLUMNS))
    connection = sqlite3.connect(path)
    try:
        frame.to_sql("training_edge_input", connection, index=False)
    finally:
        connection.close()
    return target_key


def _build_index(path: Path, target_key: str) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE TABLE race_context("
            "race_key TEXT,race_date TEXT,venue_code TEXT,race_no INTEGER)"
        )
        connection.execute(
            "INSERT INTO race_context VALUES(?,?,?,?)",
            (target_key, "2026-09-19", "06", 1),
        )
        connection.commit()
    finally:
        connection.close()


def _build_calibration(path: Path) -> None:
    knots = {str(value): -1.0 + value * 0.02 for value in range(101)}
    path.write_text(
        json.dumps(
            {
                "schema": "training-edge-v0.2-calibration",
                "version": CORE_VERSION,
                "percentile_knots": knots,
            }
        ),
        encoding="utf-8",
    )


def test_display_index_uses_one_decimal_half_up() -> None:
    assert _display_index(12.34) == "12.3"
    assert _display_index(12.35) == "12.4"
    assert _display_index(100.0) == "100.0"


def test_score_day_outputs_complete_five_column_population(tmp_path: Path) -> None:
    input_db = tmp_path / "input.sqlite"
    index_db = tmp_path / "index.sqlite"
    calibration = tmp_path / "calibration.json"
    target_key = _build_projection(input_db)
    _build_index(index_db, target_key)
    _build_calibration(calibration)

    rows, audit = score_day(
        input_db=input_db,
        index_db=index_db,
        calibration_path=calibration,
        target_date="20260919",
    )

    assert len(rows) == 4
    assert list(rows[0]) == [
        "date",
        "venue_code",
        "race_no",
        "horse_no",
        "training_edge_index",
    ]
    assert all(row["date"] == "2026-09-19" for row in rows)
    assert all(row["venue_code"] == "06" for row in rows)
    assert all(row["race_no"] == "1" for row in rows)
    assert all(row["training_edge_index"].count(".") == 1 for row in rows[:3])
    assert rows[3]["training_edge_index"] == ""
    assert audit["target_runner_n"] == 4
    assert audit["target_eligible_n"] == 3
    assert audit["target_ineligible_n"] == 1
    assert audit["guard"]["fit_max_year"] == 2025
    assert audit["guard"]["target_result_required"] is False
    assert audit["display_contract"]["decimal_places"] == 1
