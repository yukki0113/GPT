from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


stub = types.ModuleType("update_jrdb_analysis_incremental")
stub.ensure_v13 = lambda _: None
stub.parse_paci_sed = lambda *_: None
stub.sha256_file = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
stub.update_rows = lambda *_: None
sys.modules["update_jrdb_analysis_incremental"] = stub
sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_jrdb_analysis_post_race_incremental as target  # noqa: E402


class IncrementalAuditTest(unittest.TestCase):
    def make_db(self, root: Path) -> Path:
        db = root / "analysis.sqlite"
        with sqlite3.connect(db) as connection:
            connection.executescript(
                """
                CREATE TABLE fact_entry_result_lite(
                  race_date TEXT, race_key TEXT, horse_no INTEGER, prev_result_key_1 TEXT
                );
                CREATE TABLE meta_analysis_ingest_batch(
                  target_date TEXT, status TEXT, batch_id INTEGER, row_count INTEGER, source_sha256s TEXT
                );
                """
            )
            connection.executemany(
                "INSERT INTO fact_entry_result_lite VALUES(?,?,?,?)",
                [
                    ("2026-09-12", "A", 1, "horse20260905"),
                    ("2026-09-13", "B", 1, "horse20260906"),
                ],
            )
        return db

    def test_replaces_target_and_preserves_all_other_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            db = self.make_db(root)
            paci, sed = root / "PACI260913.zip", root / "SED260913.zip"
            paci.write_bytes(b"paci"); sed.write_bytes(b"sed")
            metadata = {"source_sha256s": {"PACI": target.sha256_file(paci), "SED": target.sha256_file(sed)}}

            def replace(connection, day, rows, meta):
                connection.execute("DELETE FROM fact_entry_result_lite WHERE race_date=?", (day.isoformat(),))
                connection.executemany("INSERT INTO fact_entry_result_lite VALUES(?,?,?,?)", rows)
                connection.execute(
                    "INSERT INTO meta_analysis_ingest_batch VALUES(?,?,?,?,?)",
                    (day.isoformat(), "SUCCESS", 1, len(rows), json.dumps(meta["source_sha256s"])),
                )
                connection.commit()
                return {"date": day.isoformat()}

            with patch.object(target, "parse_paci_sed", return_value=(
                __import__("datetime").date(2026, 9, 13),
                [("2026-09-13", "C", 1, "horse20260907")],
                metadata,
            )), patch.object(target, "update_rows", replace):
                result = target.update_paci_sed(db, paci, sed)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["target_rows"], 1)
            with sqlite3.connect(db) as connection:
                self.assertEqual(connection.execute("SELECT race_key FROM fact_entry_result_lite WHERE race_date='2026-09-12'").fetchone()[0], "A")
                self.assertEqual(connection.execute("SELECT race_key FROM fact_entry_result_lite WHERE race_date='2026-09-13'").fetchone()[0], "C")

    def test_rejects_as_of_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            db = self.make_db(root)
            with sqlite3.connect(db) as connection:
                connection.execute("UPDATE fact_entry_result_lite SET prev_result_key_1='horse20260913' WHERE race_date='2026-09-13'")
                with self.assertRaisesRegex(RuntimeError, "as-of violation"):
                    target._audit_as_of(connection, "2026-09-13")

    def test_rejects_any_non_target_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            db = self.make_db(root)
            paci, sed = root / "PACI260913.zip", root / "SED260913.zip"
            paci.write_bytes(b"paci"); sed.write_bytes(b"sed")
            metadata = {"source_sha256s": {"PACI": target.sha256_file(paci), "SED": target.sha256_file(sed)}}

            def corrupt_non_target(connection, day, rows, meta):
                connection.execute("UPDATE fact_entry_result_lite SET race_key='BROKEN' WHERE race_date='2026-09-12'")
                connection.commit()
                return {}

            with patch.object(target, "parse_paci_sed", return_value=(
                __import__("datetime").date(2026, 9, 13),
                [("2026-09-13", "C", 1, "horse20260907")],
                metadata,
            )), patch.object(target, "update_rows", corrupt_non_target):
                with self.assertRaisesRegex(RuntimeError, "non-target Analysis rows changed"):
                    target.update_paci_sed(db, paci, sed)
