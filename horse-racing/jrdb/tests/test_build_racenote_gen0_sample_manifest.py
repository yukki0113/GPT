from __future__ import annotations

import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import build_racenote_gen0_sample_manifest as sampler  # noqa: E402


def _database() -> sqlite3.Connection:
    """Build an Analysis-Lite-like in-memory fixture with flat and obstacle races."""
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE fact_entry_result_lite(
            race_date TEXT,
            venue_code TEXT,
            race_no INTEGER,
            track_type TEXT,
            distance INTEGER,
            race_condition_code TEXT,
            grade_code TEXT,
            race_key TEXT,
            horse_no INTEGER,
            finish INTEGER,
            final_win_odds REAL,
            final_win_popularity INTEGER,
            win_payout INTEGER,
            place_payout INTEGER
        )
        """
    )

    race_index = 0
    for day in range(1, 31):
        race_date = f"2025-06-{day:02d}"
        for race_no in range(1, 5):
            race_index += 1
            venue_code = f"{((day - 1) % 10) + 1:02d}"
            surface_code = "1" if race_index % 2 else "2"
            meeting = ((day - 1) // 8) + 1
            meeting_day = ((day - 1) % 8) + 1
            race_key = f"{venue_code}25{meeting}{meeting_day:X}{race_no:02d}"
            for horse_no in range(1, 7):
                connection.execute(
                    """
                    INSERT INTO fact_entry_result_lite(
                        race_date, venue_code, race_no, track_type, distance,
                        race_condition_code, grade_code, race_key, horse_no,
                        finish, final_win_odds, final_win_popularity,
                        win_payout, place_payout
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        race_date,
                        venue_code,
                        race_no,
                        surface_code,
                        1200 + race_no * 200,
                        "10",
                        "",
                        race_key,
                        horse_no,
                        horse_no,
                        20.0 + horse_no,
                        horse_no,
                        100 if horse_no == 1 else 0,
                        110 if horse_no <= 3 else 0,
                    ),
                )

    for race_no in range(1, 6):
        race_key = f"052511{race_no:02d}"
        for horse_no in range(1, 7):
            connection.execute(
                """
                INSERT INTO fact_entry_result_lite(
                    race_date, venue_code, race_no, track_type, distance,
                    race_condition_code, grade_code, race_key, horse_no,
                    finish, final_win_odds, final_win_popularity,
                    win_payout, place_payout
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "2025-07-01",
                    "05",
                    race_no,
                    "3",
                    3000,
                    "20",
                    "",
                    race_key,
                    horse_no,
                    horse_no,
                    10.0,
                    horse_no,
                    0,
                    0,
                ),
            )
    connection.commit()
    return connection


def test_load_candidates_excludes_obstacles_and_result_values() -> None:
    """Candidate selection reads flat-race structure, not result values."""
    connection = _database()
    before = sampler.load_candidates(connection)
    connection.execute(
        """
        UPDATE fact_entry_result_lite
        SET finish=99, final_win_odds=9999, final_win_popularity=99,
            win_payout=999999, place_payout=999999
        """
    )
    after = sampler.load_candidates(connection)
    connection.close()

    assert before == after
    assert len(before) == 120
    assert {row["surface_code"] for row in before} == {"1", "2"}
    assert all(row["runner_count"] == 6 for row in before)


def test_same_seed_reproduces_same_manifest() -> None:
    """Generation problem set is fully reproducible from seed and candidate pool."""
    connection = _database()
    candidates = sampler.load_candidates(connection)
    connection.close()

    first = sampler.build_manifest(candidates, "Gen0-G000", "GEN0-SEED-001")
    second = sampler.build_manifest(candidates, "Gen0-G000", "GEN0-SEED-001")

    assert first == second
    assert first["primary_count"] == 50
    assert first["reserve_count"] == 20
    assert len(first["races"]) == 70
    assert len(first["manifest_sha256"]) == 64


def test_primary_and_reserve_are_separate_and_mildly_stratified() -> None:
    """Primary 50R itself satisfies date concentration and turf/dirt guards."""
    connection = _database()
    candidates = sampler.load_candidates(connection)
    connection.close()
    manifest = sampler.build_manifest(candidates, "Gen0-G000", "GEN0-SEED-002")

    primary = [row for row in manifest["races"] if row["sample_role"] == "PRIMARY"]
    reserve = [row for row in manifest["races"] if row["sample_role"] == "RESERVE"]
    assert len(primary) == 50
    assert len(reserve) == 20
    assert all(row["queue_status"] == "READY" for row in primary)
    assert all(row["queue_status"] == "RESERVE" for row in reserve)
    assert not ({row["race_key"] for row in primary} & {row["race_key"] for row in reserve})

    primary_surface = Counter(row["surface_code"] for row in primary)
    assert primary_surface["1"] >= 15
    assert primary_surface["2"] >= 15
    primary_dates = Counter(row["race_date"] for row in primary)
    reserve_dates = Counter(row["race_date"] for row in reserve)
    assert max(primary_dates.values()) <= 3
    assert max(reserve_dates.values()) <= 3


def test_different_seed_changes_problem_set() -> None:
    """Changing only the seed changes the deterministic pseudo-random sample."""
    connection = _database()
    candidates = sampler.load_candidates(connection)
    connection.close()

    first = sampler.build_manifest(candidates, "Gen0-G000", "GEN0-SEED-A")
    second = sampler.build_manifest(candidates, "Gen0-G000", "GEN0-SEED-B")
    first_keys = [row["race_key"] for row in first["races"][:50]]
    second_keys = [row["race_key"] for row in second["races"][:50]]
    assert first_keys != second_keys


def test_queue_projection_keeps_manifest_identity() -> None:
    """Every queue row is traceable to one immutable generation manifest."""
    connection = _database()
    candidates = sampler.load_candidates(connection)
    connection.close()
    manifest = sampler.build_manifest(candidates, "Gen0-G000", "GEN0-SEED-003")
    rows = sampler.queue_rows(manifest)

    assert len(rows) == 70
    assert {row["manifest_id"] for row in rows} == {manifest["manifest_id"]}
    assert {row["manifest_sha256"] for row in rows} == {manifest["manifest_sha256"]}
    assert rows[0]["source_ready_status"] == "UNRESOLVED"
