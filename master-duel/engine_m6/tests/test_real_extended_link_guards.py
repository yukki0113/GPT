"""Fictional-only safety checks for the private real-extended LINK auditor."""
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from engine_m6.real_extended_link_regression import audit_real_extended_link


class ExtendedRealGuards(unittest.TestCase):
    def test_sha_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fiction.sqlite"
            sqlite3.connect(path).close()
            with self.assertRaisesRegex(ValueError, "EXTENDED_REAL_MASTER_SHA_MISMATCH"):
                audit_real_extended_link(path, expected_sqlite_sha256="0"*64)

    def test_requires_real_coverage_without_modifying_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fiction.sqlite"
            con = sqlite3.connect(path)
            con.execute("CREATE TABLE card_extra_material_requirements "
                        "(card_id TEXT,summon_method TEXT,grammar TEXT,"
                        "material_header TEXT,material_header_sha256 TEXT,"
                        "source_text_sha256 TEXT)")
            con.execute("CREATE TABLE card_texts (card_id TEXT,language TEXT,body TEXT)")
            con.commit()
            con.close()
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "EXTENDED_REAL_COVERAGE_MISMATCH"):
                audit_real_extended_link(
                    path, expected_sqlite_sha256=hashlib.sha256(before).hexdigest())
            self.assertEqual(before,path.read_bytes())


if __name__ == "__main__":
    unittest.main()
