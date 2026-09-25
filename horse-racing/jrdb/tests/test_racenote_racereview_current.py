#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

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

import racenote_racereview_current as current  # noqa: E402


class _FakeReader:
    def __init__(self, root: Path) -> None:
        root = Path(root)
        pointer = json.loads(
            (root / "current.json").read_text(encoding="utf-8")
        )
        manifest = json.loads(
            (root / pointer["manifest"]).read_text(encoding="utf-8")
        )
        if pointer.get("status") != "CURRENT":
            raise RuntimeError("not current")
        if manifest.get("validation_status") != "PASS":
            raise RuntimeError("manifest not pass")
        if manifest.get("generation_id") != pointer.get("generation_id"):
            raise RuntimeError("generation mismatch")
        self.generation_id = manifest["generation_id"]
        self.period_from = manifest.get("period_from", "")
        self.period_to = manifest.get("period_to", "")
        self.review_schema_version = manifest.get("schema_version", "")
        self.review_logic_version = manifest.get("review_logic_version", "")
        self.baseline_version = manifest.get("baseline_version", "")


class _FakeDriveApi:
    def __init__(
        self,
        archive: Path,
        *,
        name: str = current.EXPECTED_CURRENT_FILENAME,
        modified_time: str = "2026-09-25T05:00:00Z",
    ) -> None:
        self.archive = Path(archive)
        self.name = name
        self.modified_time = modified_time
        self.download_count = 0

    def load_service(self, root_id: str | None = None):
        return object(), root_id or "root"

    def assert_under_root(self, service, file_id: str, root_id: str) -> None:
        if root_id != "root":
            raise RuntimeError("wrong root")

    def metadata(self, service, file_id: str):
        return {
            "id": file_id,
            "name": self.name,
            "modifiedTime": self.modified_time,
            "size": str(self.archive.stat().st_size),
            "md5Checksum": "fake-md5",
        }

    def download(
        self,
        service,
        file_id: str,
        destination: Path,
        force: bool = False,
    ):
        self.download_count += 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.archive, destination)
        return {
            **self.metadata(service, file_id),
            "size_bytes": destination.stat().st_size,
            "sha256": current._sha256(destination),
        }


def _build_archive(
    path: Path,
    generation_id: str = "rr-test-g1",
    *,
    unsafe_member: bool = False,
) -> None:
    pointer = {
        "status": "CURRENT",
        "artifact_type": "jrdb_postrace_review",
        "generation_id": generation_id,
        "manifest": "manifest.json",
    }
    manifest = {
        "validation_status": "PASS",
        "generation_id": generation_id,
        "period_from": "2010-01-05",
        "period_to": "2026-09-22",
        "schema_version": "RaceReviewDB-v0.1",
        "review_logic_version": "Review-v0.1",
        "baseline_version": "Baseline-v0.1",
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "snapshot/current.json",
            json.dumps(pointer),
        )
        archive.writestr(
            "snapshot/manifest.json",
            json.dumps(manifest),
        )
        if unsafe_member:
            archive.writestr("../escape.txt", "unsafe")


class RaceReviewCurrentResolverTest(unittest.TestCase):
    def test_refresh_then_cache_hit_uses_stable_drive_object(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / "current.zip"
            cache = root / "cache"
            _build_archive(archive)
            api = _FakeDriveApi(archive)

            with patch.object(
                current,
                "_drive_api",
                return_value=api,
            ), patch.object(
                current,
                "RaceReviewReader",
                _FakeReader,
            ):
                first = current.resolve_racereview_current(
                    cache,
                    service=object(),
                    automation_root_id="root",
                )
                second = current.resolve_racereview_current(
                    cache,
                    service=object(),
                    automation_root_id="root",
                )

            self.assertEqual(
                first.provenance["cache_status"],
                "REFRESHED",
            )
            self.assertEqual(
                second.provenance["cache_status"],
                "HIT",
            )
            self.assertEqual(api.download_count, 1)
            self.assertEqual(
                first.reader.generation_id,
                "rr-test-g1",
            )
            self.assertTrue(
                (
                    cache
                    / current.STATE_FILENAME
                ).is_file()
            )

    def test_unexpected_stable_filename_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / "current.zip"
            _build_archive(archive)
            api = _FakeDriveApi(
                archive,
                name="wrong.zip",
            )

            with patch.object(
                current,
                "_drive_api",
                return_value=api,
            ), patch.object(
                current,
                "RaceReviewReader",
                _FakeReader,
            ):
                with self.assertRaises(
                    current.RaceReviewCurrentResolverError
                ):
                    current.resolve_racereview_current(
                        root / "cache",
                        service=object(),
                        automation_root_id="root",
                    )

            self.assertEqual(api.download_count, 0)

    def test_zip_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / "current.zip"
            _build_archive(
                archive,
                unsafe_member=True,
            )
            api = _FakeDriveApi(archive)

            with patch.object(
                current,
                "_drive_api",
                return_value=api,
            ), patch.object(
                current,
                "RaceReviewReader",
                _FakeReader,
            ):
                with self.assertRaises(
                    current.RaceReviewCurrentResolverError
                ):
                    current.resolve_racereview_current(
                        root / "cache",
                        service=object(),
                        automation_root_id="root",
                    )

            self.assertFalse(
                (root / "escape.txt").exists()
            )

    def test_failed_refresh_does_not_replace_accepted_cache_state(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            good_archive = root / "good.zip"
            bad_archive = root / "bad.zip"
            cache = root / "cache"
            _build_archive(good_archive)
            bad_archive.write_bytes(b"not-a-zip")

            good_api = _FakeDriveApi(good_archive)
            with patch.object(
                current,
                "_drive_api",
                return_value=good_api,
            ), patch.object(
                current,
                "RaceReviewReader",
                _FakeReader,
            ):
                accepted = current.resolve_racereview_current(
                    cache,
                    service=object(),
                    automation_root_id="root",
                )

            state_before = (
                cache
                / current.STATE_FILENAME
            ).read_bytes()

            bad_api = _FakeDriveApi(
                bad_archive,
                modified_time="2026-09-25T06:00:00Z",
            )
            with patch.object(
                current,
                "_drive_api",
                return_value=bad_api,
            ), patch.object(
                current,
                "RaceReviewReader",
                _FakeReader,
            ):
                with self.assertRaises(
                    current.RaceReviewCurrentResolverError
                ):
                    current.resolve_racereview_current(
                        cache,
                        service=object(),
                        automation_root_id="root",
                    )

            state_after = (
                cache
                / current.STATE_FILENAME
            ).read_bytes()
            self.assertEqual(state_after, state_before)
            self.assertTrue(accepted.root.is_dir())


if __name__ == "__main__":
    unittest.main()
