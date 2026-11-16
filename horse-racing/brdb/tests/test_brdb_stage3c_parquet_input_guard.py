"""Regression tests for the real JRDB mixed-role and malformed-key input."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from run_brdb_stage3c_direct_parent_graph import read_verified_parent_candidates


class RealInputGuardTests(unittest.TestCase):
    """Confirm invalid UKC keys cannot enter the typed parent graph."""

    def create_fixture(self, database: duckdb.DuckDBPyConnection,
                       root: Path, *, resolved_invalid: bool = False) -> Path:
        """Create a small research-like mixed-role Parquet fixture."""
        bad_status = "RESOLVED_EXACT" if resolved_invalid else "NO_CANDIDATE"
        rows = [
            ("00000001", "sire", "00000002", "RESOLVED_EXACT", "father", 1999),
            ("00000001", "dam", None, "NO_CANDIDATE", "mother", 2001),
            ("00000001", "broodmare_sire", None, "NO_CANDIDATE", "bms", 1989),
            ("000K0002", "sire", None, bad_status, "unknown", 2000),
            ("000k0003", "dam", None, "INSUFFICIENT_KEY", "unknown", 2000),
        ]
        database.execute(
            "CREATE TABLE sample(child_horse_id VARCHAR, role VARCHAR,"
            " resolved_parent_horse_id VARCHAR, resolution_status VARCHAR,"
            " parent_name VARCHAR, parent_birth_year INTEGER)"
        )
        database.executemany("INSERT INTO sample VALUES (?, ?, ?, ?, ?, ?)", rows)
        filepath = root / "relations.parquet"
        database.execute("COPY sample TO ? (FORMAT PARQUET)", [str(filepath)])
        return filepath

    def test_keeps_only_sire_dam_with_canonical_child(self):
        with tempfile.TemporaryDirectory() as directory:
            db = duckdb.connect(":memory:")
            file = self.create_fixture(db, Path(directory))
            rows, exclusions = read_verified_parent_candidates(db, file)
            self.assertEqual(len(rows), 2)
            self.assertEqual({x["role"] for x in rows}, {"sire", "dam"})
            self.assertEqual(exclusions,
                             {"NO_CANDIDATE": 1, "INSUFFICIENT_KEY": 1})

    def test_fails_if_noncanonical_child_has_resolved_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            db = duckdb.connect(":memory:")
            file = self.create_fixture(db, Path(directory), resolved_invalid=True)
            with self.assertRaisesRegex(ValueError, "Noncanonical JRDB child ID"):
                read_verified_parent_candidates(db, file)


if __name__ == "__main__":
    unittest.main()
