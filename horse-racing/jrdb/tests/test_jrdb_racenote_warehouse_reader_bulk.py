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

import jrdb_racenote_warehouse_reader as reader_module  # noqa: E402
from jrdb_racenote_warehouse_reader import WarehouseRaceNoteReader  # noqa: E402


class FakeConnection:
    """Minimal connection used to verify one-build DuckDB orchestration."""

    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, object]] = []
        self.executemany_calls: list[tuple[str, list[tuple[str]]]] = []
        self.closed = False

    def execute(self, query: str, params: object = None) -> "FakeConnection":
        self.execute_calls.append((query, params))
        return self

    def executemany(self, query: str, rows: list[tuple[str]]) -> None:
        self.executemany_calls.append((query, list(rows)))

    def close(self) -> None:
        self.closed = True


class FakeDuckDB(types.ModuleType):
    """Module-shaped fake that counts connect calls."""

    def __init__(self) -> None:
        super().__init__("duckdb")
        self.connections: list[FakeConnection] = []

    def connect(self, _database: str) -> FakeConnection:
        connection = FakeConnection()
        self.connections.append(connection)
        return connection


class FakeAudit:
    """Bundle audit stub with no semantic errors."""

    def __init__(self) -> None:
        self.bundle_errors: list[str] = []


class FakeBundleBuilder:
    """Bundle builder stub preserving only orchestration-visible fields."""

    def __init__(self, parsed: dict, _audit: FakeAudit) -> None:
        self.parsed = parsed
        self.join = {"stub": len(parsed)}

    def build(self, race: dict, horses: list[dict]) -> dict:
        return {
            "race": dict(race),
            "horses": list(horses),
        }


def synthetic_rows() -> dict[str, list[dict[str, object]]]:
    """Return one target race with two historical previous-result years."""
    return {
        "bac": [{
            "race_key_raw": "RACE0001",
            "race_date": "2025-01-05",
            "source_member_date": "2025-01-05",
            "source_member": "BAC250105.txt",
            "source_record_ordinal": 1,
        }],
        "kyi": [{
            "race_key_raw": "RACE0001",
            "source_member_date": "2025-01-05",
            "source_member": "KYI250105.txt",
            "source_record_ordinal": 1,
        }],
        "cha": [{
            "race_horse_key": "RACE000101",
            "year": 2025,
            "source_member": "CHA250105.txt",
            "source_record_ordinal": 1,
        }],
        "cyb": [{
            "race_horse_key": "RACE000101",
            "year": 2025,
            "source_member": "CYB250105.txt",
            "source_record_ordinal": 1,
        }],
        "zed": [{
            "result_key": "HORSE00120240101",
            "source_member": "ZED240101.txt",
            "source_record_ordinal": 1,
        }],
        "zkb": [{
            "result_key": "HORSE00220230102",
            "source_member": "ZKB230102.txt",
            "source_record_ordinal": 1,
        }],
    }


class WarehouseRaceNoteBulkReadTest(unittest.TestCase):
    def make_reader(
        self,
    ) -> tuple[
        WarehouseRaceNoteReader,
        list[tuple[str, tuple[int, ...], str, list[object]]],
    ]:
        reader = WarehouseRaceNoteReader.__new__(WarehouseRaceNoteReader)
        reader.covered_years = {2023, 2024, 2025}
        reader.manifest = {"generation_id": "warehouse-test"}
        data = synthetic_rows()
        calls: list[tuple[str, tuple[int, ...], str, list[object]]] = []

        def fake_rows_on(
            _self: WarehouseRaceNoteReader,
            _connection: object,
            relation: str,
            years: list[int],
            where: str = "",
            params: list[object] | None = None,
        ) -> list[dict[str, object]]:
            calls.append(
                (
                    relation,
                    tuple(years),
                    where,
                    list(params or []),
                )
            )
            return list(data[relation])

        reader._rows_on = MethodType(fake_rows_on, reader)
        return reader, calls

    @staticmethod
    def fake_unflatten(family: str, row: dict) -> dict:
        if family == "KYI":
            return {
                "race_key_raw": row["race_key_raw"],
                "previous": [
                    {"result_key": "HORSE00120240101"},
                    {"result_key": "HORSE00220230102"},
                ],
            }
        return dict(row)

    def run_build(
        self,
        reader: WarehouseRaceNoteReader,
        fake_duckdb: FakeDuckDB,
        source_member_date: dt.date | None,
    ) -> tuple[dict, dict]:
        with (
            patch.dict(sys.modules, {"duckdb": fake_duckdb}),
            patch.object(reader_module, "Audit", FakeAudit),
            patch.object(reader_module, "BundleBuilder", FakeBundleBuilder),
            patch.object(
                reader_module,
                "unflatten_parser_row",
                side_effect=self.fake_unflatten,
            ),
            patch.object(
                reader_module,
                "out_of_warehouse_previous_keys",
                return_value=[],
            ),
            patch.object(
                reader_module,
                "select_raw_compatible_rows",
                side_effect=lambda _family, rows: [dict(row) for row in rows],
            ),
        ):
            return reader.build(
                dt.date(2025, 1, 5),
                source_member_date=source_member_date,
            )

    def test_build_uses_one_connection_and_bulk_previous_year_reads(self) -> None:
        reader, calls = self.make_reader()
        fake_duckdb = FakeDuckDB()

        bundles, evidence = self.run_build(
            reader,
            fake_duckdb,
            dt.date(2025, 1, 5),
        )

        self.assertEqual(len(fake_duckdb.connections), 1)
        self.assertTrue(fake_duckdb.connections[0].closed)
        self.assertEqual(set(bundles), {"RACE0001"})
        self.assertEqual(evidence["previous_result_years"], [2023, 2024])

        by_relation = {
            relation: (years, where, params)
            for relation, years, where, params in calls
        }
        self.assertEqual(by_relation["bac"][0], (2025,))
        self.assertEqual(by_relation["kyi"][0], (2025,))
        self.assertIn("source_member_date", by_relation["bac"][1])
        self.assertIn("source_member_date", by_relation["kyi"][1])
        self.assertIn("target_race_keys", by_relation["cha"][1])
        self.assertIn("target_race_keys", by_relation["cyb"][1])

        self.assertEqual(by_relation["zed"][0], (2023, 2024))
        self.assertEqual(by_relation["zkb"][0], (2023, 2024))
        self.assertIn("target_result_keys", by_relation["zed"][1])
        self.assertIn("target_result_keys", by_relation["zkb"][1])

        relation_names = [item[0] for item in calls]
        self.assertEqual(relation_names.count("zed"), 1)
        self.assertEqual(relation_names.count("zkb"), 1)

        inserts = fake_duckdb.connections[0].executemany_calls
        self.assertTrue(
            any(rows == [("RACE0001",)] for _, rows in inserts)
        )
        self.assertTrue(
            any(
                rows
                == [
                    ("HORSE00120240101",),
                    ("HORSE00220230102",),
                ]
                for _, rows in inserts
            )
        )

    def test_without_member_date_pushes_day_and_race_keys_into_duckdb(self) -> None:
        reader, calls = self.make_reader()
        fake_duckdb = FakeDuckDB()

        self.run_build(reader, fake_duckdb, None)

        by_relation = {
            relation: (years, where, params)
            for relation, years, where, params in calls
        }
        self.assertEqual(
            by_relation["bac"],
            ((2025,), "race_date = ?", ["2025-01-05"]),
        )
        self.assertIn("target_race_keys", by_relation["kyi"][1])


if __name__ == "__main__":
    unittest.main()
