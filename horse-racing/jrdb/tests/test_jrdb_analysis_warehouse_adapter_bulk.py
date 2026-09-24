#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt
import sys
import types
import unittest
from pathlib import Path
from types import MethodType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jrdb_analysis_warehouse_adapter import WarehouseAnalysisReader  # noqa: E402


class FakeConnection:
    """Minimal DuckDB connection used to verify query orchestration."""

    def __init__(self) -> None:
        self.execute_calls: list[str] = []
        self.executemany_calls: list[tuple[str, list[tuple[str]]]] = []
        self.closed = False

    def execute(self, query: str, params: object = None) -> "FakeConnection":
        self.execute_calls.append(query)
        return self

    def executemany(self, query: str, rows: list[tuple[str]]) -> None:
        self.executemany_calls.append((query, list(rows)))

    def close(self) -> None:
        self.closed = True


class FakeDuckDB(types.ModuleType):
    """Module-shaped fake that counts connections."""

    def __init__(self) -> None:
        super().__init__("duckdb")
        self.connections: list[FakeConnection] = []

    def connect(self, _database: str) -> FakeConnection:
        connection = FakeConnection()
        self.connections.append(connection)
        return connection


def relation_rows() -> dict[str, list[dict[str, object]]]:
    """Return one fully joinable synthetic race across Warehouse relations."""
    return {
        "bac": [{
            "race_key_raw": "0526A101",
            "race_date": "2026-09-20",
            "source_member_date": "2026-09-20",
            "source_member": "BAC260920.txt",
            "source_record_ordinal": 1,
            "surface_code": "1",
            "race_class_code": "05",
            "grade_code": "0",
            "win5_leg_no": None,
            "distance_raw": "1800",
        }],
        "sed": [{
            "race_key_raw": "0526A101",
            "horse_no": 3,
            "race_date": "2026-09-20",
            "source_member_date": "2026-09-20",
            "source_member": "SED260920.txt",
            "source_record_ordinal": 1,
            "finish": "1",
            "abnormal_code": "0",
            "final_win_odds": "25",
            "final_popularity": "2",
            "win_payout": "250",
            "place_payout": "130",
            "distance_m": "1800",
            "surface_code": "1",
            "track_condition_code": "10",
        }],
        "kyi": [{
            "race_key_raw": "0526A101",
            "horse_no": 3,
            "source_member_date": "2026-09-20",
            "source_member": "KYI260920.txt",
            "source_record_ordinal": 1,
            "frame_no": "2",
            "blood_registration_no": "H001",
            "horse_name": "TEST HORSE",
            "jockey": "TEST JOCKEY",
            "running_style_code": "2",
            "distance_fit_code": "2",
            "improvement_code": "3",
            "prev_result_key_1": "HISTORY000000001",
            "prev_race_key_1": "0526A011",
        }],
        "cyb": [{
            "race_horse_key": "0526A10103",
            "source_member_date": "2026-09-20",
            "source_member": "CYB260920.txt",
            "source_record_ordinal": 1,
            "training_index": "55",
        }],
        "ukc": [{
            "horse_id": "H001",
            "source_member_date": "2026-09-20",
            "source_member": "UKC260920.txt",
            "source_record_ordinal": 1,
            "birth_date": "20200101",
            "sex_code": "1",
            "sire_name": "SIRE",
            "broodmare_sire_name": "BMS",
            "sire_line_code": "1101",
            "broodmare_sire_line_code": "1201",
            "data_date": "2026-09-20",
        }],
    }


class WarehouseAnalysisBulkReadTest(unittest.TestCase):
    def make_reader(self) -> tuple[WarehouseAnalysisReader, list[tuple[str, str, list[object]]]]:
        reader = WarehouseAnalysisReader.__new__(WarehouseAnalysisReader)
        reader.covered_years = {2026}
        reader.current = {"generation_id": "warehouse-test"}
        calls: list[tuple[str, str, list[object]]] = []
        data = relation_rows()

        def fake_relation(
            self: WarehouseAnalysisReader,
            connection: object,
            relation: str,
            year: int,
            where: str = "",
            params: list[object] | None = None,
        ) -> list[dict[str, object]]:
            self.assert_year_for_test(year)
            calls.append((relation, where, list(params or [])))
            return list(data[relation])

        def fake_paths(
            _self: WarehouseAnalysisReader,
            relation: str,
            year: int,
        ) -> list[Path]:
            return [Path(f"/warehouse/{relation}/{year}.parquet")]

        def fake_hashes(
            _self: WarehouseAnalysisReader,
            relation: str,
            year: int,
        ) -> list[str]:
            return [relation[0] * 64]

        def assert_year_for_test(_self: WarehouseAnalysisReader, year: int) -> None:
            self.assertEqual(year, 2026)

        reader.assert_year_for_test = MethodType(assert_year_for_test, reader)
        reader._relation_rows_on = MethodType(fake_relation, reader)
        reader._paths = MethodType(fake_paths, reader)
        reader._asset_sha256s = MethodType(fake_hashes, reader)
        return reader, calls

    def test_parse_day_uses_one_connection_and_bulk_key_filters(self) -> None:
        reader, calls = self.make_reader()
        fake_duckdb = FakeDuckDB()
        with patch.dict(sys.modules, {"duckdb": fake_duckdb}):
            rows, metadata = reader.parse_day(dt.date(2026, 9, 20))

        self.assertEqual(len(fake_duckdb.connections), 1)
        self.assertTrue(fake_duckdb.connections[0].closed)
        self.assertEqual(len(rows), 1)
        self.assertEqual(metadata["row_count"], 1)

        by_relation = {relation: (where, params) for relation, where, params in calls}
        self.assertEqual(by_relation["bac"], ("race_date = ?", ["2026-09-20"]))
        self.assertEqual(by_relation["sed"], ("race_date = ?", ["2026-09-20"]))
        self.assertIn("target_race_keys", by_relation["kyi"][0])
        self.assertIn("target_race_keys", by_relation["cyb"][0])
        self.assertIn("target_horse_ids", by_relation["ukc"][0])

        inserts = fake_duckdb.connections[0].executemany_calls
        self.assertTrue(any(rows_value == [("0526A101",)] for _, rows_value in inserts))
        self.assertTrue(any(rows_value == [("H001",)] for _, rows_value in inserts))

    def test_strict_member_mode_pushes_member_date_before_python_filter(self) -> None:
        reader, calls = self.make_reader()
        fake_duckdb = FakeDuckDB()
        with patch.dict(sys.modules, {"duckdb": fake_duckdb}):
            rows, _ = reader.parse_day(
                dt.date(2026, 9, 20),
                source_member_date=dt.date(2026, 9, 20),
            )

        self.assertEqual(len(rows), 1)
        by_relation = {relation: (where, params) for relation, where, params in calls}
        for relation in ("kyi", "cyb", "ukc"):
            self.assertIn("source_member_date", by_relation[relation][0])
            self.assertEqual(by_relation[relation][1], ["20260920"])


if __name__ == "__main__":
    unittest.main()
