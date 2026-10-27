from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from audit_daily_paci_ukc_missing import fixed_ids, scan_one


class PACIMissingAuditTest(unittest.TestCase):
    def test_denominator_requires_108_unique_canonical_ids(self):
        document = {"missing_in_all_ukc_years_count": 108,
                    "missing_horses": [{"horse_id": f"{i:08d}"} for i in range(108)]}
        self.assertEqual(len(fixed_ids(document)), 108)
        document["missing_horses"][-1]["horse_id"] = "00000000"
        with self.assertRaises(ValueError):
            fixed_ids(document)

    def test_ukc_parser_exact_id_and_provenance(self):
        record = bytearray(b" " * 290)
        record[0:8] = b"23100017"
        record[268:276] = b"20260104"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "PACI260104.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("UKC260104.txt", bytes(record) + b"\r\n")
            file = {"id": "drive-id", "name": path.name, "path": str(path),
                    "expected_bytes": path.stat().st_size}
            inspected, matches = scan_one(file, {"23100017", "23100018"})
            self.assertEqual(inspected["status"], "SCANNED")
            self.assertEqual(inspected["ukc_record_count"], 1)
            self.assertEqual(len(matches), 1)
            self.assertEqual(matches[0]["record"]["horse_id"], "23100017")
            self.assertEqual(matches[0]["source_zip_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_parse_error_does_not_claim_clean_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "PACI260104.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("UKC260104.txt", b"bad\r\n")
            file = {"id": "drive-id", "name": path.name, "path": str(path),
                    "expected_bytes": path.stat().st_size}
            inspected, matches = scan_one(file, {"23100017"})
            self.assertEqual(inspected["status"], "PARSE_ERROR")
            self.assertEqual(inspected["parse_errors"], 1)
            self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main()
