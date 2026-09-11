#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from project_training_edge_v0_2_input import project  # noqa: E402


class TrainingEdgeV02InputProjectorTest(unittest.TestCase):
    def _sources(self, root: Path) -> tuple[Path, Path]:
        index = root / "index.sqlite"
        official = root / "official.sqlite"

        idx = sqlite3.connect(index)
        idx.executescript((ROOT / "schema/jrdb_index_base_schema_v0_1.sql").read_text(encoding="utf-8"))
        races = [
            ("05250101", "2025-01-05", 2025, "CHA250103.txt"),
            ("05260101", "2026-01-11", 2026, "CHA260109.txt"),
        ]
        for sequence, (race_key, race_date, year, cha_member) in enumerate(races, start=1):
            idx.execute(
                """INSERT INTO race_context(
                  race_key,race_date,year,venue_code,race_no,source_kind,availability_class,record_hash
                ) VALUES(?,?,?,?,1,'BAC','PRE_RACE',?)""",
                (race_key, race_date, year, "05", f"r{year}"),
            )
            idx.execute(
                """INSERT INTO runner_pre(
                  race_key,horse_no,horse_id,horse_name,trainer_code,trainer_name,
                  jockey_code,jockey_name,training_score,training_arrow_code,source_member,record_hash
                ) VALUES(?,1,'HORSE001','Horse','TR001','Trainer','JK001','Jockey',50,'1',?,?)""",
                (race_key, f"KYI{year}.txt", f"k{year}"),
            )
            idx.execute(
                """INSERT INTO workout_main(
                  race_key,horse_no,training_date,workout_count,course_code,effort_code,
                  chase_state_code,rider_type_code,furlong_count,final_segment_sec,
                  pair_result_code,pair_effort_code,pair_class_code,jrdb_final_segment_index,
                  jrdb_workout_index,source_member,record_hash
                ) VALUES(?,1,?,1,'12','1','1','1',6,11.5,'1','1','01',55,60,?,?)""",
                (race_key, cha_member[3:9][:2] and ("2025-01-03" if year == 2025 else "2026-01-09"), cha_member, f"w{year}"),
            )
            idx.execute(
                """INSERT INTO training_analysis(
                  race_key,horse_no,training_type_code,training_course_type_code,
                  used_slope,used_wood,used_dirt,used_turf,used_pool,used_jump,used_polytrack,
                  training_distance_code,training_focus_code,training_volume_code,
                  week_ago_course_code,finish_index,source_member,record_hash
                ) VALUES(?,1,'01','W',0,1,0,0,0,0,0,'1','1','A','12',58,?,?)""",
                (race_key, f"CYB{year}.txt", f"y{year}"),
            )
        idx.commit()
        idx.close()

        off = sqlite3.connect(official)
        off.executescript((ROOT / "schema/jrdb_official_runperf_schema_v0_1.sql").read_text(encoding="utf-8"))
        for race_key, race_date, year, _ in races:
            off.execute(
                """INSERT INTO official_runperf(
                  race_key,race_date,year,horse_no,horse_id,source_calculation_status,
                  score_status,runperf_raw,score_provenance
                ) VALUES(?,?,?,?,?,'OK','OK',?,'test')""",
                (race_key, race_date, year, 1, "HORSE001", 0.5 + (year - 2025) * 0.1),
            )
        off.commit()
        off.close()
        return index, official

    def test_projection_supports_2026_without_mutating_v01_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index, official = self._sources(root)
            output = root / "training_edge_v02_input.sqlite"
            result = project(
                index_db=index,
                official_db=official,
                output_db=output,
                from_year=2025,
                to_year=2026,
                source_git_commit="a" * 40,
            )

            self.assertEqual(result["status"], "success")
            self.assertEqual(result["row_count"], 2)
            self.assertEqual(result["by_year"], {"2025": 1, "2026": 1})
            self.assertEqual(result["duplicate_business_keys"], 0)
            self.assertEqual(result["future_training_rows"], 0)
            self.assertEqual(result["integrity_check"], "ok")

            db = sqlite3.connect(output)
            row = db.execute(
                """SELECT year,days_since_last_run,days_before_race,course_code,
                          official_runperf_raw
                   FROM training_edge_input WHERE year=2026"""
            ).fetchone()
            db.close()
            self.assertEqual(row[0], 2026)
            self.assertEqual(row[1], 371)
            self.assertEqual(row[2], 2)
            self.assertEqual(row[3], "12")
            self.assertAlmostEqual(row[4], 0.6)

            source_tables = {
                name
                for (name,) in sqlite3.connect(index).execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            self.assertNotIn("training_edge_input", source_tables)


if __name__ == "__main__":
    unittest.main()
