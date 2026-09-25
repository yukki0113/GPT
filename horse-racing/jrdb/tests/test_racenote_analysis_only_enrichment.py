import sqlite3

import racenote_history_engine as engine


def test_prior_and_target_year_stats_read_analysis_only():
    analysis = sqlite3.connect(":memory:")
    analysis.row_factory = sqlite3.Row
    analysis.execute(
        """
        CREATE TABLE fact_entry_result_lite (
            year INTEGER,
            race_date TEXT,
            venue_code TEXT,
            track_type TEXT,
            distance INTEGER,
            sire_name TEXT,
            finish INTEGER
        )
        """
    )
    analysis.executemany(
        "INSERT INTO fact_entry_result_lite VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (2024, "2024-05-01", "06", "1", 1600, "Sire-A", 1),
            (2024, "2024-06-01", "06", "1", 1600, "Sire-A", 4),
            (2025, "2025-05-01", "06", "1", 1600, "Sire-A", 2),
            (2025, "2025-07-01", "06", "1", 1600, "Sire-A", 1),
        ],
    )
    analysis.commit()

    result = engine.as_of_summary(
        analysis=analysis,
        analysis_column="sire_name",
        dimension_value="Sire-A",
        race_date="2025-06-01",
        venue_code="06",
        track_type="1",
        distance_where_sql="distance=?",
        distance_parameters=[1600],
        years=5,
    )

    assert result["starts"] == 3
    assert result["wins"] == 1
    assert result["top3"] == 2
    assert result["source"] == "JRDB Analysis canonical (as-of-exclusive)"
    analysis.close()

def test_running_style_race_trends_are_asof_safe_and_target_independent():
    analysis = sqlite3.connect(":memory:")
    analysis.row_factory = sqlite3.Row
    analysis.execute(
        """
        CREATE TABLE fact_entry_result_lite (
            year INTEGER,
            race_date TEXT,
            venue_code TEXT,
            race_no INTEGER,
            track_type TEXT,
            distance INTEGER,
            horse_no INTEGER,
            horse_id TEXT,
            frame_no INTEGER,
            sire_name TEXT,
            jockey_name TEXT,
            running_style TEXT,
            finish INTEGER
        )
        """
    )
    analysis.executemany(
        "INSERT INTO fact_entry_result_lite VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (2024, "2024-04-01", "06", 1, "1", 1600, 1, None, 2, None, None, "1", 1),
            (2024, "2024-05-01", "06", 2, "1", 1600, 2, None, 4, None, None, "1", 4),
            (2024, "2024-06-01", "06", 3, "1", 1600, 3, None, 6, None, None, "3", 2),
            (2025, "2025-06-01", "06", 11, "1", 1600, 1, None, 2, None, None, "4", 1),
        ],
    )
    analysis.commit()

    base = {
        "race": {
            "date": "2025-06-01",
            "venue": "中山",
            "race_no": 11,
            "surface": "芝",
            "distance_m": 1600,
        },
        "horses": [
            {
                "basic": {
                    "horse_no": 1,
                    "horse_name": "Target",
                    "jockey": "J",
                    "trainer_base": "美浦",
                },
                "recent_runs": [],
            }
        ],
    }

    enriched, warnings = engine.enrich(
        base,
        analysis,
        older_limit=3,
        years=5,
    )

    assert warnings == []
    styles = enriched["race"]["race_trends"]["running_style"]
    assert styles["1"]["label"] == "逃げ"
    assert styles["1"]["starts"] == 2
    assert styles["1"]["wins"] == 1
    assert styles["1"]["top3"] == 1
    assert styles["3"]["label"] == "差し"
    assert styles["3"]["starts"] == 1
    assert "4" not in styles
    analysis.close()

