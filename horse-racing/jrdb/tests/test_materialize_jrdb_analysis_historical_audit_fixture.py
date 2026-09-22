from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import materialize_jrdb_analysis_historical_audit_fixture as fixture  # noqa: E402
from update_jrdb_analysis_incremental import FACT_COLUMNS  # noqa: E402


class AuditFixtureTest(unittest.TestCase):
    def test_fixture_month_rejects_2026(self) -> None:
        with self.assertRaises(fixture.AuditFixtureError):
            fixture.parse_month("2026-01")

    def test_fixture_requires_five_analysis_relations(self) -> None:
        with self.assertRaises(fixture.AuditFixtureError):
            fixture.parse_asset_roots(["BAC=/tmp/bac"])
        roots = fixture.parse_asset_roots([
            "BAC=/tmp/bac", "KYI=/tmp/kyi", "SED=/tmp/sed", "CYB=/tmp/cyb", "UKC=/tmp/ukc",
        ])
        self.assertEqual(set(roots), {"BAC", "KYI", "SED", "CYB", "UKC"})

    def test_logical_hash_is_independent_of_insert_order(self) -> None:
        first = sqlite3.connect(":memory:")
        second = sqlite3.connect(":memory:")
        columns = ",".join(f'"{name}" TEXT' for name in FACT_COLUMNS)
        for connection in (first, second):
            connection.execute(f"CREATE TABLE fact_entry_result_lite({columns})")
        one = tuple(["2018-12-01", "2018", "05", "1", "", "", "", "", "", "", "05120101", "1"] + [""] * (len(FACT_COLUMNS) - 12))
        two = tuple(["2018-12-01", "2018", "05", "2", "", "", "", "", "", "", "05120102", "1"] + [""] * (len(FACT_COLUMNS) - 12))
        placeholders = ",".join("?" for _ in FACT_COLUMNS)
        first.executemany(f"INSERT INTO fact_entry_result_lite VALUES({placeholders})", [one, two])
        second.executemany(f"INSERT INTO fact_entry_result_lite VALUES({placeholders})", [two, one])
        self.assertEqual(fixture.logical_hash(first), fixture.logical_hash(second))


if __name__ == "__main__":
    unittest.main()
