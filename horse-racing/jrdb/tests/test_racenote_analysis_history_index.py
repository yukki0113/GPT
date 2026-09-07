from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[1] / "schema" / "jrdb_analysis_schema_v1_2.sql"
TABLE = "fact_entry_result_lite"


class RaceNoteAnalysisHistoryIndexTest(unittest.TestCase):
    def make_db(self) -> sqlite3.Connection:
        connection = sqlite3.connect(":memory:")
        connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        rows = [
            ("2024-12-28", 2024, "06", 11, "1", 2000, "OP", "10", "1", "06245911", 1, 1, "H001", "A", "1", 2, "SIRE", "BMS", None, None, "J", None, None, None, None, 1, "0", 1.5, 1, 100, 110, None, None),
            ("2024-10-01", 2024, "05", 8, "1", 2000, "OP", "10", "5", "05240808", 4, 2, "H001", "A", "1", 2, "SIRE", "BMS", None, None, "J", None, None, None, None, 2, "0", 2.5, 2, 0, 120, None, None),
            ("2024-08-01", 2024, "04", 7, "1", 1800, "OP", "10", "5", "04240707", 3, 2, "H001", "A", "1", 2, "SIRE", "BMS", None, None, "J", None, None, None, None, 3, "0", 3.5, 3, 0, 130, None, None),
        ]
        placeholders = ",".join("?" for _ in range(33))
        connection.executemany(f"INSERT INTO {TABLE} VALUES({placeholders})", rows)
        connection.commit()
        return connection

    def test_schema_contains_horse_history_index(self) -> None:
        connection = self.make_db()
        try:
            indexes = {
                row[1]: row
                for row in connection.execute(f"PRAGMA index_list({TABLE})")
            }
            self.assertIn("ix_analysis_horse_history", indexes)
        finally:
            connection.close()

    def test_planner_uses_horse_history_index_for_summary(self) -> None:
        connection = self.make_db()
        try:
            plan = connection.execute(
                f"EXPLAIN QUERY PLAN SELECT count(*) FROM {TABLE} WHERE horse_id=? AND race_date<?",
                ("H001", "2024-12-28"),
            ).fetchall()
            text = " ".join(str(item[-1]) for item in plan)
            self.assertIn("ix_analysis_horse_history", text)
        finally:
            connection.close()

    def test_planner_uses_horse_history_index_for_older_runs_and_keeps_order(self) -> None:
        connection = self.make_db()
        try:
            plan = connection.execute(
                f"EXPLAIN QUERY PLAN SELECT race_date,race_no FROM {TABLE} WHERE horse_id=? AND race_date<? ORDER BY race_date DESC,race_no DESC LIMIT 3",
                ("H001", "2024-12-28"),
            ).fetchall()
            text = " ".join(str(item[-1]) for item in plan)
            self.assertIn("ix_analysis_horse_history", text)
            rows = connection.execute(
                f"SELECT race_date,race_no FROM {TABLE} WHERE horse_id=? AND race_date<? ORDER BY race_date DESC,race_no DESC LIMIT 3",
                ("H001", "2024-12-28"),
            ).fetchall()
            self.assertEqual(rows, [("2024-10-01", 8), ("2024-08-01", 7)])
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
