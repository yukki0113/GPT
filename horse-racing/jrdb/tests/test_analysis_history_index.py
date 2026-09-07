from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path


SCHEMA = (
    Path(__file__).resolve().parents[1]
    / "schema"
    / "jrdb_analysis_schema_v1_2.sql"
)


class AnalysisHistoryIndexTest(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.executescript(SCHEMA.read_text(encoding="utf-8"))
        self.connection.executemany(
            """
            INSERT INTO fact_entry_result_lite(
                race_date, race_key, race_no, horse_no, horse_id
            ) VALUES(?,?,?,?,?)
            """,
            [
                ("2024-01-01", "R1", 1, 1, "H1"),
                ("2024-02-01", "R2", 2, 1, "H1"),
                ("2024-02-01", "R3", 3, 2, "H2"),
            ],
        )

    def tearDown(self) -> None:
        self.connection.close()

    def test_schema_contains_horse_history_index(self) -> None:
        indexes = {
            row[1]
            for row in self.connection.execute(
                "PRAGMA index_list(fact_entry_result_lite)"
            )
        }
        self.assertIn("ix_analysis_horse_history", indexes)

    def test_horse_history_queries_use_dedicated_index(self) -> None:
        summary_plan = " ".join(
            str(row[3])
            for row in self.connection.execute(
                """
                EXPLAIN QUERY PLAN
                SELECT count(*)
                FROM fact_entry_result_lite
                WHERE horse_id=? AND race_date<?
                """,
                ("H1", "2024-03-01"),
            )
        )
        older_plan = " ".join(
            str(row[3])
            for row in self.connection.execute(
                """
                EXPLAIN QUERY PLAN
                SELECT race_date, race_no
                FROM fact_entry_result_lite
                WHERE horse_id=? AND race_date<?
                ORDER BY race_date DESC, race_no DESC
                LIMIT 3
                """,
                ("H1", "2024-03-01"),
            )
        )

        self.assertIn("ix_analysis_horse_history", summary_plan)
        self.assertIn("ix_analysis_horse_history", older_plan)

    def test_index_preserves_expected_history_order(self) -> None:
        rows = self.connection.execute(
            """
            SELECT race_date, race_no
            FROM fact_entry_result_lite
            WHERE horse_id=? AND race_date<?
            ORDER BY race_date DESC, race_no DESC
            """,
            ("H1", "2024-03-01"),
        ).fetchall()
        self.assertEqual(rows, [("2024-02-01", 2), ("2024-01-01", 1)])


if __name__ == "__main__":
    unittest.main()
