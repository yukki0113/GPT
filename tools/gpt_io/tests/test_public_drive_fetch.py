"""Offline regression tests for pinned public download transport."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.gpt_io.public_drive.fetch import FetchError, fetch, read_manifest


class PublicDriveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = b"verified public input"
        self.row = dict(artifact_id="sample", file_id="AbCdEfGhIjKlMnOpQrSt",
                        destination="nested/sample.bin", expected_name="sample.bin",
                        expected_size=len(self.payload), sha256=hashlib.sha256(self.payload).hexdigest())
        self.manifest = self.root / "manifest.json"
        self.save()

    def save(self):
        self.manifest.write_text(json.dumps(dict(schema_version=1, transport="public_google_drive",
                                                 artifacts=[self.row])), encoding="utf-8")

    def test_fetch_and_reuse_without_redownload(self):
        calls = []
        def downloader(file_id, output):
            calls.append(file_id)
            output.write_bytes(self.payload)
            return str(output)
        output = self.root / "data"
        self.assertTrue(fetch(self.manifest, output, downloader=downloader)["artifacts"][0]["verified"])
        fetch(self.manifest, output, downloader=downloader)
        self.assertEqual(calls, [self.row["file_id"]])

    def test_sha_failure_no_promotion(self):
        def corrupted(file_id, output):
            output.write_bytes(b"not the payload")
            return str(output)
        with self.assertRaises(FetchError):
            fetch(self.manifest, self.root / "data", downloader=corrupted)
        self.assertFalse((self.root / "data/nested/sample.bin").exists())

    def test_traversal_rejected(self):
        self.row["destination"] = "../sample.bin"
        self.save()
        with self.assertRaises(FetchError):
            read_manifest(self.manifest)

    def test_symlink_rejected(self):
        output = self.root / "data"
        output.mkdir()
        (output / "nested").symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(FetchError):
            fetch(self.manifest, output, downloader=lambda *_: None)

    def test_duplicate_keys_rejected(self):
        self.manifest.write_text('{"schema_version":1,"schema_version":1,"transport":"public_google_drive","artifacts":[]}')
        with self.assertRaises(FetchError):
            read_manifest(self.manifest)

    def test_duplicate_destination_rejected(self):
        row2 = {**self.row, "artifact_id": "second"}
        self.manifest.write_text(json.dumps({"schema_version":1,"transport":"public_google_drive",
                                              "artifacts":[self.row, row2]}))
        with self.assertRaises(FetchError):
            read_manifest(self.manifest)

    def test_existing_unverified_not_overwritten(self):
        path = self.root / "data/nested/sample.bin"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"wrong")
        with self.assertRaises(FetchError):
            fetch(self.manifest, self.root / "data", downloader=lambda *_: None)
        self.assertEqual(path.read_bytes(), b"wrong")


if __name__ == "__main__":
    unittest.main()
