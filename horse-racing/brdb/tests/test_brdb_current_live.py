"""A02: live BRDB CURRENT discovery, refresh, integrity and rollback regressions."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
from test_brdb_current import make_generation  # noqa: E402
import brdb_current as current  # noqa: E402
import brdb_current_live as live  # noqa: E402
import build_brdb_current_bundle as bundle  # noqa: E402

FOLDER = live.DEFAULT_DRIVE_FOLDER_ID


class FakeFiles:
    def __init__(self, drive):
        self.drive = drive

    def list(self, **kwargs):
        drive = self.drive
        class Request:
            def execute(self):
                # Include exact filename only and honor canonical parent.
                found = [dict(f["meta"]) for f in drive.objects.values()
                         if f["meta"]["name"] == live.EXPECTED_CURRENT_FILENAME
                         and FOLDER in f["meta"]["parents"]]
                return {"files": found}
        return Request()


class FakeService:
    def __init__(self, drive):
        self.drive = drive

    def files(self):
        return FakeFiles(self.drive)


class FakeDrive:
    def __init__(self):
        self.objects = {}
        self.service = FakeService(self)
        self.download_calls = 0
        self.mutate_after_download = None

    def load_service(self, folder_id):
        assert folder_id == FOLDER
        return self.service, folder_id

    def add(self, file_id, path, *, version=1, name=live.EXPECTED_CURRENT_FILENAME):
        size = path.stat().st_size
        self.objects[file_id] = {
            "zip": path,
            "meta": {
                "id": file_id, "name": name, "mimeType": "application/zip",
                "size": str(size), "md5Checksum": hashlib.md5(path.read_bytes()).hexdigest(),
                "version": str(version), "modifiedTime": f"2026-11-02T00:00:{version:02d}Z",
                "parents": [FOLDER], "trashed": False,
            },
        }

    def metadata(self, service, file_id):
        assert service is self.service
        return dict(self.objects[file_id]["meta"])

    def download(self, service, file_id, destination):
        assert service is self.service
        self.download_calls += 1
        src = self.objects[file_id]["zip"]
        shutil.copyfile(src, destination)
        if self.mutate_after_download:
            self.mutate_after_download(self, file_id)
        return {"sha256": hashlib.sha256(destination.read_bytes()).hexdigest()}


class LiveResolverTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.cache = self.root / "cache"
        self.drive = FakeDrive()
        self.id1 = "1f_q_current_brdb_20261102_A"
        self.id2 = "1f_q_current_brdb_20261102_B"
        self.g1 = self.bundle_zip("0123456789abcdef", "one")
        self.g2 = self.bundle_zip("fedcba9876543210", "two")
        self.drive.add(self.id1, self.g1, version=1)

    def bundle_zip(self, gen_id, suffix):
        folder = self.root / f"gen-{suffix}"
        folder.mkdir()
        make_generation(folder)
        manifest_path = folder / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["generation_id"] = gen_id
        manifest_path.write_text(json.dumps(manifest))
        out = self.root / f"source-{suffix}.zip"
        bundle.build_current_bundle(folder, out)
        return out

    def resolve(self, *, refresh=False):
        return current.resolve_brdb_current(
            self.cache, drive_folder_id=FOLDER, drive_service=self.drive.service,
            drive_api=self.drive, force_refresh=refresh,
        )

    def state(self):
        return json.loads((self.cache / current.STATE_FILENAME).read_text())

    def test_cold_warm_and_same_id_update(self):
        first = self.resolve()
        self.assertEqual(first.provenance["cache_status"], "REFRESHED")
        self.assertEqual(first.reader.generation_id, "0123456789abcdef")
        self.assertEqual(self.state()["drive"]["version"], "1")
        second = self.resolve()
        self.assertEqual(second.provenance["cache_status"], "HIT")
        self.assertEqual(self.drive.download_calls, 1)
        self.drive.add(self.id1, self.g2, version=2)
        third = self.resolve()
        self.assertEqual(third.provenance["cache_status"], "REFRESHED")
        self.assertEqual(third.reader.generation_id, "fedcba9876543210")
        self.assertEqual(self.state()["drive"]["version"], "2")
        self.assertEqual(self.resolve().provenance["cache_status"], "HIT")
        self.assertTrue((self.cache / "generations" / "0123456789abcdef").is_dir())

    def test_new_id_same_name_switches_without_git_update(self):
        self.resolve()
        old = self.state()
        self.drive.objects[self.id1]["meta"]["name"] = "BRDB_OLD_SNAPSHOT.zip"
        self.drive.add(self.id2, self.g2, version=3)
        updated = self.resolve()
        self.assertEqual(updated.reader.generation_id, "fedcba9876543210")
        self.assertEqual(self.state()["drive"]["file_id"], self.id2)
        self.assertNotEqual(old["zip_sha256"], self.state()["zip_sha256"])

    def test_duplicate_candidates_fail_and_preserve_cache(self):
        self.resolve()
        old = self.state()
        self.drive.add(self.id2, self.g2, version=3)
        with self.assertRaisesRegex(current.BRDBCurrentResolverError, "ambiguous"):
            self.resolve()
        self.assertEqual(self.state(), old)

    def test_missing_current_fails_closed_and_preserves_cache(self):
        self.resolve()
        old = self.state()
        self.drive.objects[self.id1]["meta"]["name"] = "removed.zip"
        with self.assertRaisesRegex(current.BRDBCurrentResolverError, "not found"):
            self.resolve()
        self.assertEqual(self.state(), old)

    def test_change_during_download_fails_and_preserves_cache(self):
        self.resolve()
        old = self.state()
        self.drive.add(self.id1, self.g2, version=2)
        def mutate(drive, file_id):
            drive.objects[file_id]["meta"]["version"] = "3"
        self.drive.mutate_after_download = mutate
        with self.assertRaisesRegex(current.BRDBCurrentResolverError, "changed during download"):
            self.resolve()
        self.assertEqual(self.state(), old)

    def test_corrupt_download_fails_without_cache_loss(self):
        self.resolve()
        old = self.state()
        self.drive.add(self.id1, self.g2, version=2)
        def corrupted(service, file_id, destination):
            destination.write_bytes(b"X" * self.drive.objects[file_id]["meta"]["size"].__len__())
            return {}
        original = self.drive.download
        self.drive.download = corrupted
        try:
            with self.assertRaisesRegex(current.BRDBCurrentResolverError, "size mismatch"):
                self.resolve()
        finally:
            self.drive.download = original
        self.assertEqual(self.state(), old)

    def test_same_generation_modified_data_refused(self):
        self.resolve()
        old = self.state()
        variant_folder = self.root / "gen-one-again"
        variant_folder.mkdir()
        make_generation(variant_folder)
        (variant_folder / "audit.json").write_bytes(b'{"repackaged":true}\n')
        manifest_path = variant_folder / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["output_sha256"]["audit.json"] = hashlib.sha256(
            (variant_folder / "audit.json").read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        variant = self.root / "source-one-again.zip"
        bundle.build_current_bundle(variant_folder, variant)
        self.drive.add(self.id1, variant, version=2)
        with self.assertRaisesRegex(current.BRDBCurrentResolverError, "generation payload conflict"):
            self.resolve()
        self.assertEqual(self.state(), old)

    def test_metadata_change_with_identical_bytes_revalidates(self):
        self.resolve()
        self.drive.add(self.id1, self.g1, version=2)
        updated = self.resolve()
        self.assertEqual(updated.provenance["cache_status"], "REFRESHED")
        self.assertEqual(self.state()["drive"]["version"], "2")

    def test_missing_md5_or_revision_fails_closed(self):
        self.resolve()
        old = self.state()
        for key in ("md5Checksum", "version"):
            before = self.drive.objects[self.id1]["meta"].pop(key)
            with self.assertRaisesRegex(current.BRDBCurrentResolverError, "incomplete"):
                self.resolve()
            self.drive.objects[self.id1]["meta"][key] = before
        self.assertEqual(self.state(), old)

    def test_no_authenticated_bridge_fails_instead_of_pinned_fallback(self):
        class NoAuth(FakeDrive):
            def load_service(self, folder_id):
                raise RuntimeError("missing credentials")
        with self.assertRaisesRegex(current.BRDBCurrentResolverError, "authenticated"):
            current.resolve_brdb_current(self.root / "no-auth", drive_api=NoAuth())

    def test_explicit_pinned_mode_keeps_legacy_contract(self):
        from test_brdb_current import make_transport
        pinned = self.root / "pinned.json"
        make_transport(pinned, self.g1)
        def fetcher(manifest, output_root):
            path = output_root / live.EXPECTED_CURRENT_FILENAME
            shutil.copyfile(self.g1, path)
            return path
        resolved = current.resolve_brdb_current(
            self.root / "pinned-cache", transport_manifest=pinned, fetcher=fetcher)
        self.assertEqual(resolved.reader.generation_id, "0123456789abcdef")
        self.assertEqual(resolved.provenance["cache_status"], "REFRESHED")


if __name__ == "__main__":
    unittest.main()
