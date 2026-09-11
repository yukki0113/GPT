#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused regression tests for Analysis Lite v1.3 WIN5 support."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from jrdb_analysis_raw_adapter import parse_bac  # noqa: E402
from jrdb_raw import BODY_LENGTHS, Parser  # noqa: E402
from upgrade_jrdb_analysis_v1_2_to_v1_3 import migrate  # noqa: E402


def put(row: bytearray, start: int, width: int, value: str) -> None:
    """Write one CP932 fixed-width fixture field."""
    encoded = value.encode("cp932")
    if len(encoded) > width:
        raise ValueError(value)
    offset = start - 1
    row[offset : offset + width] = encoded.ljust(width, b" ")


def make_bac(race_key: str, date: str, leg: int | None) -> bytes:
    """Create a minimal BAC body containing one optional WIN5 leg."""
    row = bytearray(b" " * BODY_LENGTHS["BAC"])
    put(row, 1, 8, race_key)
    put(row, 9, 8, date)
    put(row, 21, 4, "1600")
    put(row, 25, 1, "1")
    put(row, 30, 2, "OP")
    put(row, 36, 1, "3")
    if leg is not None:
        put(row, 177, 1, str(leg))
    return bytes(row)


class AnalysisWin5Test(unittest.TestCase):
    """Pin Raw parsing, Analysis projection, schema, and migration behavior."""

    def test_common_reader_and_adapter_preserve_leg_number(self) -> None:
        record = make_bac("05259010", "20250101", 4)
        parsed = Parser().bac(record)
        projected = parse_bac(record, "2025-01-01", 2025)
        self.assertEqual(parsed["win5_leg_no"], 4)
        self.assertEqual(projected["win5_leg_no"], 4)

    def test_blank_win5_field_is_none(self) -> None:
        record = make_bac("05259009", "20250101", None)
        self.assertIsNone(Parser().bac(record)["win5_leg_no"])
        self.assertIsNone(parse_bac(record, "2025-01-01", 2025)["win5_leg_no"])

    def test_v13_schema_has_constrained_win5_column(self) -> None:
        schema = ROOT / "schema" / "jrdb_analysis_schema_v1_3.sql"
        connection = sqlite3.connect(":memory:")
        try:
            connection.executescript(schema.read_text(encoding="utf-8"))
            columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(fact_entry_result_lite)"
                )
            }
            self.assertIn("win5_leg_no", columns)
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO fact_entry_result_lite(race_key,horse_no,win5_leg_no) "
                    "VALUES('05259001',1,6)"
                )
        finally:
            connection.close()

    def test_v12_migration_backfills_all_five_legs_without_row_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw_root = root / "raw"
            bac_dir = raw_root / "BAC"
            bac_dir.mkdir(parents=True)
            archive = bac_dir / "BAC_2025.zip"

            records = []
            race_keys = []
            for leg in range(1, 6):
                race_key = f"052590{9 + leg:02d}"
                race_keys.append(race_key)
                records.append(make_bac(race_key, "20250101", leg))
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.writestr("BAC250101.txt", b"\r\n".join(records) + b"\r\n")

            db = root / "analysis.sqlite"
            schema_v12 = ROOT / "schema" / "jrdb_analysis_schema_v1_2.sql"
            connection = sqlite3.connect(db)
            try:
                connection.executescript(schema_v12.read_text(encoding="utf-8"))
                for horse_no, race_key in enumerate(race_keys, start=1):
                    connection.execute(
                        "INSERT INTO fact_entry_result_lite("
                        "race_date,year,race_key,horse_no"
                        ") VALUES(?,?,?,?)",
                        ("2025-01-01", 2025, race_key, horse_no),
                    )
                connection.commit()
            finally:
                connection.close()

            result = migrate(db, raw_root)
            self.assertEqual(result["rows_before"], 5)
            self.assertEqual(result["rows_after"], 5)
            self.assertEqual(result["win5_dates"], 1)
            self.assertEqual(result["win5_races"], 5)
            self.assertEqual(result["integrity_check"], "ok")
            self.assertEqual(result["sequence_anomalies"], [])
            self.assertEqual(result["incomplete_sequences"], [])
            self.assertEqual(
                result["leg_distribution_races"],
                {1: 1, 2: 1, 3: 1, 4: 1, 5: 1},
            )

            connection = sqlite3.connect(db)
            try:
                rows = connection.execute(
                    "SELECT race_key,win5_leg_no FROM fact_entry_result_lite "
                    "ORDER BY win5_leg_no"
                ).fetchall()
            finally:
                connection.close()
            self.assertEqual([row[1] for row in rows], [1, 2, 3, 4, 5])

    def test_v12_migration_accepts_incomplete_sequence_as_audit_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            raw_root = root / "raw"
            bac_dir = raw_root / "BAC"
            bac_dir.mkdir(parents=True)
            archive = bac_dir / "BAC_2025.zip"

            records = [
                make_bac("05259010", "20250101", 1),
                make_bac("06259011", "20250101", 4),
            ]
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.writestr("BAC250101.txt", b"\r\n".join(records) + b"\r\n")

            db = root / "analysis.sqlite"
            schema_v12 = ROOT / "schema" / "jrdb_analysis_schema_v1_2.sql"
            connection = sqlite3.connect(db)
            try:
                connection.executescript(schema_v12.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO fact_entry_result_lite("
                    "race_date,year,race_key,horse_no"
                    ") VALUES(?,?,?,?)",
                    ("2025-01-01", 2025, "05259010", 1),
                )
                connection.execute(
                    "INSERT INTO fact_entry_result_lite("
                    "race_date,year,race_key,horse_no"
                    ") VALUES(?,?,?,?)",
                    ("2025-01-01", 2025, "06259011", 2),
                )
                connection.commit()
            finally:
                connection.close()

            result = migrate(db, raw_root)
            self.assertEqual(result["rows_before"], 2)
            self.assertEqual(result["rows_after"], 2)
            self.assertEqual(result["sequence_anomalies"], [])
            self.assertEqual(
                result["incomplete_sequences"],
                [
                    {
                        "race_date": "2025-01-01",
                        "present_legs": [1, 4],
                        "missing_legs": [2, 3, 5],
                    }
                ],
            )
            self.assertEqual(result["integrity_check"], "ok")


if __name__ == "__main__":
    unittest.main()
