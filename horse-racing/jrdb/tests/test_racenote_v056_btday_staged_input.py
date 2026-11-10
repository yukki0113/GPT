import hashlib
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from racenote_v056_btday_staged_input import extract


class StagedInputTest(unittest.TestCase):
    def test_verified_bundle_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "staged.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("inputs/source_row.json", "{}")
                z.writestr("horse-racing/jrdb/backtests/BTDAY-9999/selection.json", "{}")
            sha = hashlib.sha256(archive.read_bytes()).hexdigest()
            extract(archive, root / "out", sha)
            self.assertEqual((root / "out/inputs/source_row.json").read_text(), "{}")
            with self.assertRaises(ValueError):
                extract(archive, root / "out", sha)

    def test_bad_digest_and_traversal_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "staged.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("../outside", "bad")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                extract(archive, root / "out", "0" * 64)
            sha = hashlib.sha256(archive.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "unsafe"):
                extract(archive, root / "out", sha)
            self.assertFalse((root / "out").exists())


if __name__ == "__main__":
    unittest.main()
