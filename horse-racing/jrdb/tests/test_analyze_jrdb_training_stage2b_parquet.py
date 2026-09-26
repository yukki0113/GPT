#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT.parents[1] / "tools" / "data-storage"))

from analyze_jrdb_training_stage2b import REQUIRED_SOURCE_COLUMNS, _load_source


class Stage2bParquetReaderTest(unittest.TestCase):
    def _create_sqlite(self, path: Path) -> None:
        connection = sqlite3.connect(path)
        definitions = []
        for name in REQUIRED_SOURCE_COLUMNS:
            if name in {"year", "horse_no"}:
                definitions.append(f'"{name}" INTEGER')
            elif name in {
                "days_since_last_run",
                "days_before_race",
                "workout_count",
                "furlong_count",
                "used_slope",
                "used_wood",
                "used_dirt",
                "used_turf",
                "used_pool",
                "used_jump",
                "used_polytrack",
            }:
                definitions.append(f'"{name}" INTEGER')
            elif name in {
                "final_segment_sec",
                "jrdb_workout_index_cha",
                "jrdb_final_segment_index",
                "finish_index",
                "kyi_training_score",
                "official_runperf_raw",
            }:
                definitions.append(f'"{name}" REAL')
            else:
                definitions.append(f'"{name}" TEXT')
        connection.execute(f"CREATE TABLE training_runner ({','.join(definitions)})")

        names = list(REQUIRED_SOURCE_COLUMNS)
        placeholders = ",".join("?" for _ in names)
        quoted_names = ",".join(f'"{name}"' for name in names)
        for year in (2010, 2023, 2024):
            values = []
            for name in names:
                if name == "race_date":
                    values.append(f"{year}-01-01")
                elif name == "year":
                    values.append(year)
                elif name == "race_key":
                    values.append(f"05{year % 100:02d}0101")
                elif name == "horse_no":
                    values.append(1)
                elif name == "horse_id":
                    values.append("HORSE001")
                elif name in {"trainer_code", "trainer_name"}:
                    values.append("T")
                elif name in {
                    "days_since_last_run",
                    "days_before_race",
                    "workout_count",
                    "furlong_count",
                    "used_slope",
                    "used_wood",
                    "used_dirt",
                    "used_turf",
                    "used_pool",
                    "used_jump",
                    "used_polytrack",
                }:
                    values.append(1)
                elif name in {
                    "final_segment_sec",
                    "jrdb_workout_index_cha",
                    "jrdb_final_segment_index",
                    "finish_index",
                    "kyi_training_score",
                    "official_runperf_raw",
                }:
                    values.append(1.0)
                else:
                    values.append("X")
            connection.execute(
                f"INSERT INTO training_runner ({quoted_names}) VALUES ({placeholders})",
                values,
            )
        connection.commit()
        connection.close()

    def test_legacy_sqlite_is_filtered_to_development_period(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "training.sqlite"
            self._create_sqlite(path)
            frame, audit = _load_source(path, "sqlite")
            self.assertEqual(list(frame["year"]), [2010, 2023])
            self.assertEqual(audit["source_format"], "sqlite")
            self.assertEqual(audit["source_max_year"], 2024)
            self.assertEqual(audit["selected_max_year"], 2023)
            self.assertEqual(audit["holdout_rows_selected"], 0)

    def test_canonical_parquet_is_read_with_duckdb(self) -> None:
        try:
            import duckdb
        except ImportError:
            self.skipTest("duckdb is not installed")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sqlite_path = root / "training.sqlite"
            parquet_path = root / "training_development.parquet"
            self._create_sqlite(sqlite_path)

            sqlite_connection = sqlite3.connect(sqlite_path)
            frame = pd.read_sql_query(
                "SELECT * FROM training_runner WHERE year BETWEEN 2010 AND 2023 "
                "ORDER BY race_date,race_key,horse_no",
                sqlite_connection,
            )
            sqlite_connection.close()

            duck = duckdb.connect()
            try:
                duck.register("source_frame", frame)
                duck.execute(
                    f"COPY source_frame TO '{parquet_path.as_posix()}' "
                    "(FORMAT PARQUET, COMPRESSION ZSTD)"
                )
            finally:
                duck.close()

            parquet_frame, audit = _load_source(parquet_path, "parquet")
            self.assertEqual(list(parquet_frame["year"]), [2010, 2023])
            self.assertEqual(audit["source_format"], "parquet")
            self.assertEqual(audit["source_max_year"], 2023)
            self.assertEqual(audit["selected_max_year"], 2023)
            self.assertEqual(audit["holdout_rows_selected"], 0)
            self.assertEqual(audit["missing_required_columns"], [])


if __name__ == "__main__":
    unittest.main()
