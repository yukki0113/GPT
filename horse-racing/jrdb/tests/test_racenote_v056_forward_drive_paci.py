"""Drive PACI transport regression tests. Never performs network access."""
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from racenote_v056_forward_drive_paci import materialize, CANONICAL_FOLDER_ID

ID = "1ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"

class DrivePaciTransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.dest = self.base / "PACI261031.zip"
        self.receipt = self.base / "drive_receipt.json"

    def fake_gdown(self, argv, check):
        self.assertTrue(check)
        self.assertEqual(argv, ["gdown", ID, "-O", str(self.dest)])
        with zipfile.ZipFile(self.dest, "w") as zf:
            zf.writestr("safe/KYI261031.TXT", b"fictional-test")
        return None

    def test_accepts_drive_zip_and_records_sha(self):
        with patch("racenote_v056_forward_drive_paci.subprocess.run", side_effect=self.fake_gdown) as run:
            d = materialize("2026-10-31", ID, self.dest, self.receipt)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(d["source"], "GOOGLE_DRIVE_CANONICAL_PACI")
        self.assertFalse(d["jrdb_direct_fetch"])
        self.assertEqual(d["canonical_folder_id"], CANONICAL_FOLDER_ID)
        self.assertEqual(d["sha256"], hashlib.sha256(self.dest.read_bytes()).hexdigest())
        self.assertEqual(json.loads(self.receipt.read_text())["drive_file_id"], ID)

    def test_expected_sha_rejection_discards_download(self):
        with patch("racenote_v056_forward_drive_paci.subprocess.run", side_effect=self.fake_gdown), self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            materialize("2026-10-31", ID, self.dest, self.receipt, expected_sha256="0"*64)
        self.assertFalse(self.dest.exists())
        self.assertFalse(self.receipt.exists())

    def test_existing_download_never_overwritten(self):
        self.dest.write_bytes(b"existing")
        with self.assertRaises(FileExistsError):
            materialize("2026-10-31", ID, self.dest, self.receipt)
        self.assertEqual(self.dest.read_bytes(), b"existing")

    def test_date_mismatch_never_downloads(self):
        with patch("racenote_v056_forward_drive_paci.subprocess.run") as run, self.assertRaisesRegex(ValueError, "exact target-day"):
            materialize("2026-11-01", ID, self.dest, self.receipt)
        run.assert_not_called()

    def test_reject_missing_target_day_kyi(self):
        def wrong(argv, check):
            with zipfile.ZipFile(self.dest, "w") as zf:
                zf.writestr("KYI261030.TXT", b"wrong date")
        with patch("racenote_v056_forward_drive_paci.subprocess.run", side_effect=wrong), self.assertRaisesRegex(ValueError, "target-date KYI"):
            materialize("2026-10-31", ID, self.dest, self.receipt)
        self.assertFalse(self.dest.exists())

    def test_downloader_failure_has_no_jrdb_fallback(self):
        def broken(argv, check):
            raise RuntimeError("Drive unavailable")
        with patch("racenote_v056_forward_drive_paci.subprocess.run", side_effect=broken) as run, self.assertRaisesRegex(RuntimeError, "Drive unavailable"):
            materialize("2026-10-31", ID, self.dest, self.receipt)
        run.assert_called_once()
        self.assertFalse(self.receipt.exists())


if __name__ == "__main__":
    unittest.main()
