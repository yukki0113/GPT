from __future__ import annotations

import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BUILDER_PATH = ROOT / "horse-racing/jrdb/src/build_jrdb_pwa_fact_lite.py"
SCHEMA_V14 = ROOT / "horse-racing/jrdb/schema/jrdb_analysis_schema_v1_4.sql"

SPEC = importlib.util.spec_from_file_location("fact_lite_builder", BUILDER_PATH)
BUILDER = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(BUILDER)


class FactLiteFromAnalysisV14Test(unittest.TestCase):
    def test_v14_extra_context_columns_do_not_change_fact_lite_v03_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            analysis = root / "analysis-v1_4.sqlite"
            connection = sqlite3.connect(analysis)
            try:
                connection.executescript(SCHEMA_V14.read_text(encoding="utf-8"))
                connection.execute(
                    """
                    INSERT INTO meta_analysis_build(
                      builder_version,schema_version,started_at,status,row_count
                    ) VALUES('test','v1.4','x','SUCCESS',2)
                    """
                )
                rows = [
                    (
                        "2025-08-17", 2025, "01", 2, 4, 11, "1", 2000,
                        "OP", "10", "2", "札幌記念", "1", None,
                        "01252411", 1, 1, "H1", "Horse1", "1", 5,
                        "Sire1", "Bms1", "10", "20", "Jockey1", "2",
                        "3", "3", 50.0, 1, "0", 3.5, 1, 350, 160,
                        None, None,
                    ),
                    (
                        "2025-08-17", 2025, "01", 2, 4, 11, "1", 2000,
                        "OP", "10", "2", "札幌記念", "1", None,
                        "01252411", 2, 2, "H2", "Horse2", "2", 4,
                        "Sire2", "Bms2", "11", "21", "Jockey2", "3",
                        "2", "2", 45.0, 2, "0", 5.0, 2, 0, 190,
                        None, None,
                    ),
                ]
                connection.executemany(
                    """
                    INSERT INTO fact_entry_result_lite(
                      race_date,year,venue_code,meeting_no,meeting_day,race_no,
                      track_type,distance,race_condition_code,track_condition_code,
                      grade_code,race_name,course_code,win5_leg_no,race_key,horse_no,
                      frame_no,horse_id,horse_name,sex_code,age,sire_name,
                      broodmare_sire_name,sire_line_code,broodmare_sire_line_code,
                      jockey_name,running_style,distance_aptitude,uptrend,
                      training_index,finish,abnormal_code,final_win_odds,
                      final_win_popularity,win_payout,place_payout,
                      prev_result_key_1,prev_race_key_1
                    ) VALUES(
                      ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,
                      ?,?,?,?,?,?,?,?
                    )
                    """,
                    rows,
                )
                connection.commit()
            finally:
                connection.close()

            output = root / "fact.sqlite"
            result = BUILDER.build(
                analysis,
                output,
                race_names=None,
                schema=ROOT / "horse-racing/jrdb/schema/jrdb_pwa_fact_lite_schema_v0_3.sql",
            )
            self.assertEqual(result["rows"], 2)

            connection = sqlite3.connect(output)
            try:
                columns = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(fact_stats_entry)"
                    )
                }
                self.assertIn("win5_leg_no", columns)
                self.assertNotIn("meeting_no", columns)
                self.assertNotIn("meeting_day", columns)
                self.assertNotIn("course_code", columns)
                self.assertEqual(
                    connection.execute(
                        "SELECT COUNT(*) FROM fact_stats_entry"
                    ).fetchone()[0],
                    2,
                )
                self.assertEqual(
                    connection.execute(
                        "PRAGMA integrity_check"
                    ).fetchone()[0],
                    "ok",
                )
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
