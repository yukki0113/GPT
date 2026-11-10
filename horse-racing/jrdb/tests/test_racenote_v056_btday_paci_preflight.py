import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from racenote_v056_btday_paci_preflight import validate_paci
from racenote_v056_forward_drive_paci import CANONICAL_FOLDER_ID, VERSION


class PaciPreflightTest(unittest.TestCase):
    def test_valid_and_digest_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "PACI261031.zip"
            bac = bytearray(b" " * 182)
            bac[:16] = b"0526110120261031"
            kyi = bytearray(b" " * 1022)
            kyi[:10] = b"0526110101"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("BAC261031.txt", bytes(bac) + b"\r\n")
                z.writestr("KYI261031.txt", bytes(kyi) + b"\r\n")
            receipt = root / "receipt.json"
            payload = {"schema_version": VERSION, "status": "DRIVE_PACI_VERIFIED",
                       "source": "GOOGLE_DRIVE_CANONICAL_PACI", "canonical_folder_id": CANONICAL_FOLDER_ID,
                       "target_date": "2026-10-31", "filename": archive.name,
                       "drive_file_id": "fixture", "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                       "jrdb_direct_fetch": False}
            receipt.write_text(json.dumps(payload))
            self.assertEqual(validate_paci("2026-10-31", archive, receipt)["horse_count"], 1)
            payload["sha256"] = "0" * 64
            receipt.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "receipt mismatch"):
                validate_paci("2026-10-31", archive, receipt)


if __name__ == "__main__":
    unittest.main()
