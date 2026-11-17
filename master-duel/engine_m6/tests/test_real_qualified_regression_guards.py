"""Synthetic-only safety checks for the private-real qualified audit entrypoint."""
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from engine_m6.real_qualified_regression import audit_real_qualified_eligibility


class RealQualifiedRegressionGuards(unittest.TestCase):
    def test_sha_pin_rejects_missing_or_wrong_source(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "fictional.sqlite"
            sqlite3.connect(path).close()
            with self.assertRaisesRegex(ValueError, "REAL_QUALIFIED_MASTER_SHA_MISMATCH"):
                audit_real_qualified_eligibility(
                    path, expected_sqlite_sha256="f" * 64)

    def test_requires_real_source_schema_and_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "fictional.sqlite"
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE card_extra_material_requirements "
                         "(card_id TEXT,summon_method TEXT,material_header TEXT,"
                         "material_header_sha256 TEXT,source_text_sha256 TEXT,grammar TEXT)")
            conn.execute("CREATE TABLE card_texts(card_id TEXT,language TEXT,body TEXT)")
            conn.commit()
            conn.close()
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "REAL_QUALIFIED_EXPECTED_COVERAGE_MISMATCH"):
                audit_real_qualified_eligibility(
                    path, expected_sqlite_sha256=hashlib.sha256(before).hexdigest())
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
