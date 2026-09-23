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
        mart=None,
        mart_table="ignored_legacy_table",
        mart_column="ignored_legacy_column",
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
