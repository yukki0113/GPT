"""A02 native-connector handoff: no Drive API, no public gdown CURRENT."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
from test_brdb_current import make_generation, make_transport
import brdb_current as current
import brdb_current_connector as connector
import build_brdb_current_bundle as builder


class ConnectorCurrentTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.cache = self.root / "cache"
        self.current_zip = self.root / "BloodReviewDB_CURRENT.zip"
        self.receipt = self.root / "handoff.json"
        self.g1 = self.bundle("0123456789abcdef", "gen1")
        self.g2 = self.bundle("fedcba9876543210", "gen2")
        shutil.copyfile(self.g1, self.current_zip)
        self.t1 = "2026-10-22T00:00:13.522Z"
        self.t2 = "2026-11-02T10:00:00.000Z"

    def bundle(self, generation_id, label):
        path = self.root / label
        path.mkdir()
        make_generation(path)
        mf = path / "manifest.json"
        manifest = json.loads(mf.read_text())
        manifest["generation_id"] = generation_id
        mf.write_text(json.dumps(manifest))
        out = self.root / (label + ".zip")
        builder.build_current_bundle(path, out)
        return out

    def handoff(self, *, file_id="1fvqJgMMf1KUNL0Zr_GVnUAC6FyU8rMVz",
                modified=None, count=1, observed_offset=0, source_size=None):
        observed = datetime.now(timezone.utc) + timedelta(seconds=observed_offset)
        obj = {
            "schema_version": 1, "transport": connector.TRANSPORT,
            "folder_id": connector.CANONICAL_FOLDER_ID,
            "candidate_count": count, "file_id": file_id,
            "file_name": "BloodReviewDB_CURRENT.zip",
            "source_size_bytes": (self.current_zip.stat().st_size
                                  if source_size is None else source_size),
            "source_modified_time": modified or self.t1,
            "observed_at_utc": observed.isoformat(),
        }
        self.receipt.write_text(json.dumps(obj))
        return obj

    def resolve(self, **kwargs):
        return current.resolve_brdb_current(
            self.cache, current_zip=self.current_zip,
            connector_receipt=self.receipt, **kwargs,
        )

    def state(self):
        return json.loads((self.cache / current.STATE_FILENAME).read_text())

    def test_requires_fresh_handoff_not_old_git_manifest(self):
        with self.assertRaisesRegex(current.BRDBCurrentResolverError, "current_zip and connector_receipt"):
            current.resolve_brdb_current(self.cache)
        self.assertFalse((self.cache / current.STATE_FILENAME).exists())

    def test_warm_hit_and_same_id_updated_content(self):
        self.handoff()
        first = self.resolve()
        self.assertEqual(first.provenance["cache_status"], "REFRESHED")
        self.assertEqual(first.reader.generation_id, "0123456789abcdef")
        # A newly observed, identical source must reuse the verified generation.
        self.handoff()
        second = self.resolve()
        self.assertEqual(second.provenance["cache_status"], "HIT")
        shutil.copyfile(self.g2, self.current_zip)
        self.handoff(modified=self.t2)
        third = self.resolve()
        self.assertEqual(third.reader.generation_id, "fedcba9876543210")
        self.assertEqual(third.provenance["cache_status"], "REFRESHED")
        self.assertTrue((self.cache / "generations" / "0123456789abcdef").exists())
        self.assertEqual(self.state()["source"]["file_id"], self.handoff()["file_id"])

    def test_new_file_id_without_git_update(self):
        self.handoff()
        self.resolve()
        shutil.copyfile(self.g2, self.current_zip)
        self.handoff(file_id="1f_other_current_file_2026", modified=self.t2)
        updated = self.resolve()
        self.assertEqual(updated.reader.generation_id, "fedcba9876543210")
        self.assertEqual(self.state()["source"]["file_id"], "1f_other_current_file_2026")

    def test_size_mismatch_preserves_prior_current(self):
        self.handoff()
        self.resolve()
        old = self.state()
        shutil.copyfile(self.g2, self.current_zip)
        self.handoff(modified=self.t2, source_size=123)
        with self.assertRaisesRegex(current.BRDBCurrentResolverError, "size mismatch"):
            self.resolve()
        self.assertEqual(old, self.state())

    def test_tampered_zip_preserves_prior_cache(self):
        self.handoff()
        self.resolve()
        old = self.state()
        self.current_zip.write_bytes(b"x" * 500)
        self.handoff(modified=self.t2)
        with self.assertRaises(current.BRDBCurrentResolverError):
            self.resolve()
        self.assertEqual(old, self.state())

    def test_conflicting_same_generation_rejected(self):
        self.handoff()
        self.resolve()
        old = self.state()
        folder = self.root / "altered"
        folder.mkdir()
        make_generation(folder)
        (folder / "audit.json").write_text('{"altered":true}')
        manifest_path = folder / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["output_sha256"]["audit.json"] = hashlib.sha256(
            (folder / "audit.json").read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        alternate = self.root / "alternate.zip"
        builder.build_current_bundle(folder, alternate)
        shutil.copyfile(alternate, self.current_zip)
        self.handoff(modified=self.t2)
        with self.assertRaisesRegex(current.BRDBCurrentResolverError, "content conflict"):
            self.resolve()
        self.assertEqual(old, self.state())

    def test_duplicate_listing_fails_closed(self):
        self.handoff(count=2)
        with self.assertRaisesRegex(current.BRDBCurrentResolverError, "unique"):
            self.resolve()

    def test_stale_receipt_rejected(self):
        self.handoff(observed_offset=-7200)
        with self.assertRaisesRegex(current.BRDBCurrentResolverError, "stale"):
            self.resolve()

    def test_wrong_folder_rejected(self):
        obj = self.handoff()
        obj["folder_id"] = "some-other-folder-12345"
        self.receipt.write_text(json.dumps(obj))
        with self.assertRaisesRegex(current.BRDBCurrentResolverError, "canonical folder"):
            self.resolve()

    def test_older_revision_does_not_replace_cache(self):
        self.handoff(modified=self.t2)
        self.resolve()
        old = self.state()
        shutil.copyfile(self.g2, self.current_zip)
        self.handoff(modified=self.t1)
        with self.assertRaisesRegex(current.BRDBCurrentResolverError, "regressed"):
            self.resolve()
        self.assertEqual(self.state(), old)

    def test_concurrent_cache_lock_fails_without_state_change(self):
        self.handoff()
        self.cache.mkdir()
        (self.cache / ".brdb-current-connector.lock").mkdir()
        with patch.object(connector, "LOCK_WAIT_SECONDS", 0):
            with self.assertRaisesRegex(current.BRDBCurrentResolverError, "lock busy"):
                self.resolve()
        self.assertFalse((self.cache / current.STATE_FILENAME).exists())

    def test_explicit_historical_pinned_replay_remains_supported(self):
        pinned = self.root / "pinned.json"
        make_transport(pinned, self.g1)
        def fetcher(_, destination):
            dest = destination / "BloodReviewDB_CURRENT.zip"
            shutil.copyfile(self.g1, dest)
            return dest
        result = current.resolve_brdb_current(
            self.root / "historical", transport_manifest=pinned, fetcher=fetcher)
        self.assertEqual(result.reader.generation_id, "0123456789abcdef")
        with self.assertRaisesRegex(current.BRDBCurrentResolverError, "cannot mix"):
            current.resolve_brdb_current(
                self.root / "historical", transport_manifest=pinned,
                current_zip=self.current_zip, connector_receipt=self.receipt)


if __name__ == "__main__":
    unittest.main()
