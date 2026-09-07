#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jrdb_raw import BODY_LENGTHS  # noqa: E402
from upgrade_jrdb_analysis_v1_1_to_v1_2 import upgrade_database  # noqa: E402


def put(row: bytearray, start: int, width: int, value: str) -> None:
    encoded = value.encode("cp932")
    if len(encoded) > width:
        raise ValueError(value)
    offset = start - 1
    row[offset : offset + width] = encoded.ljust(width, b" ")


def make_kyi(
    race_key: str,
    horse_no: int,
    prev_result_key: str,
    prev_race_key: str,
) -> bytes:
    row = bytearray(b" " * BODY_LENGTHS["KYI"])
    put(row, 1, 8, race_key)
    put(row, 9, 2, f"{horse_no:02d}")
    put(row, 11, 8, "20231001")
    put(row, 19, 36, "テストホース")
    put(row, 204, 16, prev_result_key)
    put(row, 284, 8, prev_race_key)
    return bytes(row)


def write_kyi_year(root: Path, year: int, rows: list[bytes]) -> None:
    kyi_dir = root / "KYI"
    kyi_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        kyi_dir / f"KYI_{year}.zip",
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr(
            f"KYI{str(year)[2:]}0101.txt",
            b"".join(row + b"\r\n" for row in rows),
        )


class AnalysisUpgradeCommonReaderTest(unittest.TestCase):
    def test_upgrade_backfills_prev1_from_common_kyi(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_path = root / "analysis.sqlite"
            raw_root = root / "raw"
            race_key = "0524A101"
            horse_no = 3
            prev_result = "2023100120231201"
            prev_race = "05249011"

            connection = sqlite3.connect(db_path)
            try:
                connection.execute(
                    "CREATE TABLE fact_entry_result_lite("
                    "race_key TEXT NOT NULL, horse_no INTEGER NOT NULL)"
                )
                connection.execute(
                    "INSERT INTO fact_entry_result_lite(race_key, horse_no) "
                    "VALUES(?, ?)",
                    (race_key, horse_no),
                )
                connection.commit()
            finally:
                connection.close()

            write_kyi_year(
                raw_root,
                2024,
                [make_kyi(race_key, horse_no, prev_result, prev_race)],
            )

            report = upgrade_database(db_path, raw_root, [2024])

            connection = sqlite3.connect(db_path)
            try:
                row = connection.execute(
                    "SELECT prev_result_key_1, prev_race_key_1 "
                    "FROM fact_entry_result_lite "
                    "WHERE race_key=? AND horse_no=?",
                    (race_key, horse_no),
                ).fetchone()
                columns = {
                    item[1]
                    for item in connection.execute(
                        "PRAGMA table_info(fact_entry_result_lite)"
                    )
                }
            finally:
                connection.close()

            self.assertEqual(row, (prev_result, prev_race))
            self.assertIn("prev_result_key_1", columns)
            self.assertIn("prev_race_key_1", columns)
            self.assertEqual(report["updated_candidates"], 1)
            self.assertEqual(report["filled_rows"], 1)
            self.assertEqual(report["integrity_check"], "ok")


if __name__ == "__main__":
    unittest.main()
