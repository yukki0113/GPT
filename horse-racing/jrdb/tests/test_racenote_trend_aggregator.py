from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from racenote.src.racenote_trend_aggregator import attach_trends


SCHEMA = """
CREATE TABLE fact_entry_result_lite(
  race_date TEXT,
  year INTEGER,
  venue_code TEXT,
  meeting_no INTEGER,
  meeting_day INTEGER,
  race_no INTEGER,
  track_type TEXT,
  distance INTEGER,
  race_condition_code TEXT,
  track_condition_code TEXT,
  grade_code TEXT,
  race_name TEXT,
  course_code TEXT,
  race_key TEXT,
  frame_no INTEGER,
  sex_code TEXT,
  age INTEGER,
  sire_name TEXT,
  jockey_name TEXT,
  running_style TEXT,
  final_win_popularity INTEGER,
  finish INTEGER,
  win_payout INTEGER,
  place_payout INTEGER,
  prev_race_key_1 TEXT
);
"""


def _note() -> dict:
    return {
        "schema_version": "RaceNote-Evidence-1.0",
        "metadata": {
            "note_kind": "EVIDENCE_NOTE",
            "as_of": "2026-08-16",
        },
        "race": {
            "date": "2026-08-16",
            "venue": "札幌",
            "race_no": 11,
            "race_name": "札幌記念",
            "surface": "芝",
            "distance_m": 2000,
            "class": "オープン",
            "grade": "G2",
            "course_rail": "A",
            "meeting_day": 4,
            "source_codes": {
                "venue_code": "01",
                "surface_code": "1",
                "race_class_code": "OP",
                "grade_code": "2",
                "course_code": "1",
            },
        },
        "coverage": {"missing_families": ["named_race_trend", "local_context_trend"]},
        "provenance": [],
    }


def _insert(
    conn: sqlite3.Connection,
    *,
    race_date: str,
    venue_code: str,
    distance: int,
    grade_code: str,
    race_name: str,
    course_code: str,
    race_key: str,
    finish: int,
    win_payout: int = 0,
    place_payout: int = 0,
    popularity: int = 1,
) -> None:
    conn.execute(
        """
        INSERT INTO fact_entry_result_lite VALUES(
          ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
        )
        """,
        (
            race_date,
            int(race_date[:4]),
            venue_code,
            2,
            4,
            11,
            "1",
            distance,
            "OP",
            "10",
            grade_code,
            race_name,
            course_code,
            race_key,
            1,
            "1",
            5,
            "Test Sire",
            "Test Jockey",
            "2",
            popularity,
            finish,
            win_payout,
            place_payout,
            None,
        ),
    )


def test_named_scope_requires_name_and_current_conditions(tmp_path: Path) -> None:
    db = tmp_path / "analysis.db"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)

    # Exact comparable Sapporo Kinen: winner.
    _insert(
        conn,
        race_date="2025-08-17",
        venue_code="01",
        distance=2000,
        grade_code="2",
        race_name="札幌記念",
        course_code="1",
        race_key="01252411",
        finish=1,
        win_payout=350,
        place_payout=160,
    )
    # Same race name, wrong venue: must not enter Named exact.
    _insert(
        conn,
        race_date="2024-08-18",
        venue_code="05",
        distance=2000,
        grade_code="2",
        race_name="札幌記念",
        course_code="1",
        race_key="05242411",
        finish=2,
        place_payout=150,
    )
    # Same race name, wrong distance: must not enter Named exact.
    _insert(
        conn,
        race_date="2023-08-20",
        venue_code="01",
        distance=1800,
        grade_code="2",
        race_name="札幌記念",
        course_code="1",
        race_key="01232411",
        finish=3,
        place_payout=180,
    )
    conn.commit()
    conn.close()

    out = attach_trends(_note(), db)
    named = out["trend_context"]["named_race"]
    assert named["status"] == "AVAILABLE"
    assert named["selected_level"] == "NAMED_EXACT"
    assert named["sample"]["starts"] == 1

    popularity = named["dimensions"]["popularity"]["rows"][0]
    assert popularity["finish_record"]["compact"] == "(1-0-0-0)"
    assert popularity["win_roi"] == 350.0
    assert popularity["place_roi"] == 160.0


def test_local_graded_scope_uses_op_plus_support(tmp_path: Path) -> None:
    db = tmp_path / "analysis.db"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)

    # Comparable G3 at the same course/month should enter Local OP+.
    _insert(
        conn,
        race_date="2025-08-10",
        venue_code="01",
        distance=2000,
        grade_code="3",
        race_name="別の重賞",
        course_code="1",
        race_key="01252311",
        finish=2,
        place_payout=210,
    )
    # Ordinary 2-win race should not enter graded Local OP+.
    conn.execute(
        """
        INSERT INTO fact_entry_result_lite VALUES(
          '2025-08-09',2025,'01',2,4,10,'1',2000,'08','10','0',
          '条件戦','1','01252310',2,'1',4,'Other Sire','Other Jockey','3',
          2,1,500,190,NULL
        )
        """
    )
    conn.commit()
    conn.close()

    out = attach_trends(_note(), db)
    local = out["trend_context"]["local_context"]
    assert local["status"] == "AVAILABLE"
    assert local["scope"]["class_scope"] == "OP+"
    assert local["sample"]["starts"] == 1
