"""A06: approved RRDB CURRENT ID rotation with no new Drive API or auth."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
import rrdb_current_source_contract as pointer
import racenote_fetch_rrdb_current as fetcher
import racenote_racereview_current as legacy

OLD_ID = "1UwNfrupMTHRPhkzULPvClGre4MWz2TFg"
NEW_ID = "1Replacement_CurrentRRDB_20261102"
GEN1 = "jrdb_race_review_v0_1_incremental_20261101_01"
GEN2 = "jrdb_race_review_v0_1_incremental_20261108_01"


def make_zip(path: Path, generation: str, period: str, *, corrupt_manifest=False):
    root = "postrace_review/v0_1/"
    current = {
        "status": "CURRENT", "artifact_type": "jrdb_postrace_review",
        "generation_id": generation, "manifest": f"generations/{generation}/manifest.json",
    }
    manifest = {
        "artifact_type": "jrdb_postrace_review",
        "validation_status": "FAIL" if corrupt_manifest else "PASS",
        "generation_id": generation, "period_from": "2010-01-05", "period_to": period,
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(root+"current.json", json.dumps(current))
        z.writestr(root+current["manifest"], json.dumps(manifest))
        z.writestr(root+"objects/valid.parquet", b"p"*2048)


class CurrentSourceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.config = self.root / "source.json"
        self.source = json.loads(pointer.DEFAULT_SOURCE.read_text())
        self.config.write_text(json.dumps(self.source))
        self.z1 = self.root / "gen1.zip"
        self.z2 = self.root / "gen2.zip"
        make_zip(self.z1, GEN1, "2026-11-01")
        make_zip(self.z2, GEN2, "2026-11-08")
        self.downloads = []

    def edit(self, **fields):
        self.source.update(fields)
        self.config.write_text(json.dumps(self.source))

    def fake_download(self, path):
        def downloader(file_id, output):
            self.downloads.append(file_id)
            shutil.copyfile(path, output)
            return str(output)
        return downloader

    def fetch(self, label, zip_file=None, **kw):
        return fetcher.fetch(
            self.root / (label+".zip"), self.root / (label+".json"),
            source_config=self.config, downloader=self.fake_download(zip_file or self.z1),
            **kw,
        )

    def test_default_approved_pointer_matches_existing_main_id(self):
        data = pointer.approved_source()
        self.assertEqual(data["file_id"], OLD_ID)
        self.assertEqual(data["canonical_folder_id"], pointer.CANONICAL_FOLDER_ID)
        self.assertEqual(data["file_name"], "RaceReviewDB_CURRENT.zip")
        self.assertRegex(data["source_contract_sha256"], r"^[0-9a-f]{64}$")

    def test_same_id_weekly_update_no_git_source_change(self):
        a = self.fetch("first")
        b = self.fetch("second",self.z2)
        self.assertEqual(self.downloads, [OLD_ID, OLD_ID])
        self.assertEqual(a["source_contract_sha256"], b["source_contract_sha256"])
        self.assertNotEqual(a["sha256"], b["sha256"])
        self.assertEqual(b["generation_id"], GEN2)
        self.assertEqual(b["period_to"], "2026-11-08")
        self.assertEqual(json.loads((self.root/"second.json").read_text()), b)

    def test_new_id_requires_reviewed_git_pointer_and_expected_identity(self):
        self.edit(file_id=NEW_ID, source_revision=2, approval_reference="GH-PR-reviewed-rotation-123")
        b = self.fetch("new", self.z2, expected_file_id=NEW_ID)
        self.assertEqual(self.downloads,[NEW_ID])
        self.assertEqual(b["file_id"],NEW_ID)
        self.assertEqual(b["source_revision"],2)
        self.assertEqual(b["generation_id"],GEN2)

    def test_old_id_is_rejected_after_pointer_promoted(self):
        self.edit(file_id=NEW_ID,source_revision=2,approval_reference="GH-PR-reviewed-rotation-123")
        with self.assertRaisesRegex(ValueError,"differs from approved"):
            self.fetch("stale", expected_file_id=OLD_ID)
        self.assertEqual(self.downloads,[])
        self.assertFalse((self.root/"stale.zip").exists())

    def test_expected_sha_rejects_wrong_actual_bytes(self):
        with self.assertRaisesRegex(ValueError,"expected SHA mismatch"):
            self.fetch("bad-sha", expected_sha256="a"*64)
        self.assertFalse((self.root/"bad-sha.zip").exists())
        self.assertFalse((self.root/"bad-sha.json").exists())

    def test_fail_closed_on_corrupt_generation_and_no_outputs(self):
        invalid=self.root/"invalid.zip"
        make_zip(invalid,GEN1,"2026-11-01",corrupt_manifest=True)
        with self.assertRaisesRegex(ValueError,"not PASS"):
            self.fetch("bad-manifest",invalid)
        self.assertFalse((self.root/"bad-manifest.zip").exists())

    def test_missing_and_unreviewed_pointer_rejected(self):
        for changes in [
            {"status":"DRAFT"},
            {"file_name":"RaceReviewDB_CURRENT_OLD.zip"},
            {"canonical_folder_id":"1WRONGFOLDER_A06"},
            {"approval_method":"service_account"},
            {"sha_policy":"pinned_historical_sha"},
        ]:
            self.edit(**changes)
            with self.assertRaises(pointer.RRDBCurrentSourceError):
                self.fetch("not-approved")
            self.source=json.loads(pointer.DEFAULT_SOURCE.read_text())
            self.edit(**self.source)
        self.assertEqual(self.downloads,[])

    def test_pointer_change_during_download_fails_closed(self):
        def flip(file_id,output):
            shutil.copyfile(self.z1,output)
            self.edit(file_id=NEW_ID,source_revision=2,approval_reference="GH-PR-reviewed-rotation-123")
            return str(output)
        with self.assertRaisesRegex(ValueError,"changed during download"):
            fetcher.fetch(self.root/"race.zip",self.root/"race.json",
                          source_config=self.config,downloader=flip)
        self.assertFalse((self.root/"race.zip").exists())

    def test_legacy_resolver_uses_same_promoted_pointer_without_new_api(self):
        from test_racenote_racereview_current import _FakeDriveApi, _FakeReader, _build_archive
        fixture=self.root/"legacy.zip"
        _build_archive(fixture, "rr-test-id2")
        api=_FakeDriveApi(fixture)
        self.edit(file_id=NEW_ID,source_revision=2,approval_reference="GH-PR-reviewed-rotation-123")
        with patch.object(legacy,"approved_source",return_value=pointer.approved_source(self.config)), \
             patch.object(legacy,"_drive_api",return_value=api), \
             patch.object(legacy,"RaceReviewReader",_FakeReader):
            resolved=legacy.resolve_racereview_current(
                self.root/"cache",service=object(),automation_root_id="root")
            self.assertEqual(resolved.provenance["drive"]["file_id"],NEW_ID)
            with self.assertRaisesRegex(legacy.RaceReviewCurrentResolverError,"differs from approved"):
                legacy.resolve_racereview_current(
                    self.root/"cache",file_id=OLD_ID,service=object(),automation_root_id="root")


if __name__ == "__main__":
    unittest.main()
