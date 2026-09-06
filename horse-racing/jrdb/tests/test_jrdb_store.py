from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import sys

TEST_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(TEST_ROOT))

from jrdb_store import (  # noqa: E402
    StoreError,
    StoreManifest,
    StoreResolver,
    default_cache_root,
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def artifact(
    logical_name: str,
    storage_path: Path,
    storage_bytes: bytes,
    payload_bytes: bytes | None = None,
    compression: str = "none",
    member: str | None = None,
    status: str = "FINAL",
) -> dict:
    if payload_bytes is None:
        payload_bytes = storage_bytes
    payload_filename = storage_path.name
    if compression == "zip":
        payload_filename = "payload.sqlite"
    return {
        "logical_name": logical_name,
        "artifact_type": "test",
        "schema_version": "v1",
        "data_version": "test",
        "period_from": "2024-01-01",
        "period_to": "2024-12-31",
        "status": status,
        "storage": {
            "provider": "google_drive",
            "file_id": "drive-test-id",
            "filename": storage_path.name,
            "size": len(storage_bytes),
            "sha256": digest(storage_bytes),
        },
        "payload": {
            "compression": compression,
            "member": member,
            "filename": payload_filename,
            "size": len(payload_bytes),
            "sha256": digest(payload_bytes),
        },
    }


class StoreResolverTest(unittest.TestCase):
    def test_manifest_rejects_duplicate_logical_name(self) -> None:
        row = artifact("analysis/current", Path("a.sqlite"), b"abc")
        data = {
            "manifest_version": "1.0",
            "updated_at": "",
            "artifacts": [row, row],
        }
        with self.assertRaisesRegex(StoreError, "Duplicate logical artifact"):
            StoreManifest.from_dict(data)

    def test_uncompressed_artifact_fetches_once_and_reuses_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "analysis.sqlite"
            source.write_bytes(b"verified-analysis")
            raw = artifact(
                "analysis/current",
                source,
                source.read_bytes(),
                status="YTD",
            )
            manifest = StoreManifest.from_dict(
                {"manifest_version": "1.0", "updated_at": "", "artifacts": [raw]}
            )
            calls = 0

            def fetcher(_artifact, destination: Path) -> None:
                nonlocal calls
                calls += 1
                shutil.copyfile(source, destination)

            resolver = StoreResolver(manifest, root / "cache", fetcher=fetcher)
            first = resolver.resolve("jrdb://analysis/current")
            second = resolver.resolve("analysis/current")
            self.assertEqual(first, second)
            self.assertEqual(first.read_bytes(), b"verified-analysis")
            self.assertEqual(calls, 1)

    def test_corrupt_cached_object_is_refetched(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "stats.sqlite"
            source.write_bytes(b"stats-data")
            raw = artifact("stats/current", source, source.read_bytes())
            manifest = StoreManifest.from_dict(
                {"manifest_version": "1.0", "updated_at": "", "artifacts": [raw]}
            )
            calls = 0

            def fetcher(_artifact, destination: Path) -> None:
                nonlocal calls
                calls += 1
                shutil.copyfile(source, destination)

            resolver = StoreResolver(manifest, root / "cache", fetcher=fetcher)
            resolved = resolver.resolve("stats/current")
            resolved.write_bytes(b"bad")
            repaired = resolver.resolve("stats/current")
            self.assertEqual(repaired.read_bytes(), b"stats-data")
            self.assertEqual(calls, 2)

    def test_zip_payload_is_materialized_and_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload = b"sqlite-payload-data"
            source = root / "canonical_2024.sqlite.zip"
            with zipfile.ZipFile(source, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("canonical_2024.sqlite", payload)
            raw = artifact(
                "canonical/2024",
                source,
                source.read_bytes(),
                payload_bytes=payload,
                compression="zip",
                member="canonical_2024.sqlite",
            )
            manifest = StoreManifest.from_dict(
                {"manifest_version": "1.0", "updated_at": "", "artifacts": [raw]}
            )
            calls = 0

            def fetcher(_artifact, destination: Path) -> None:
                nonlocal calls
                calls += 1
                shutil.copyfile(source, destination)

            resolver = StoreResolver(manifest, root / "cache", fetcher=fetcher)
            resolved = resolver.resolve_year(2024)
            self.assertEqual(resolved.read_bytes(), payload)
            self.assertEqual(calls, 1)
            again = resolver.resolve("jrdb://canonical/2024", offline=True)
            self.assertEqual(again, resolved)
            self.assertEqual(calls, 1)

    def test_candidate_is_rejected_by_default(self) -> None:
        raw = artifact(
            "canonical/2025",
            Path("candidate.sqlite"),
            b"abc",
            status="CANDIDATE",
        )
        manifest = StoreManifest.from_dict(
            {"manifest_version": "1.0", "updated_at": "", "artifacts": [raw]}
        )
        resolver = StoreResolver(manifest, Path("cache"), fetcher=lambda _a, _p: None)
        with self.assertRaisesRegex(StoreError, "not resolvable"):
            resolver.resolve("canonical/2025")

    def test_offline_missing_artifact_fails_without_fetch(self) -> None:
        raw = artifact("analysis/current", Path("a.sqlite"), b"abc")
        manifest = StoreManifest.from_dict(
            {"manifest_version": "1.0", "updated_at": "", "artifacts": [raw]}
        )
        resolver = StoreResolver(
            manifest,
            Path("missing-cache"),
            fetcher=lambda _a, _p: None,
        )
        with self.assertRaisesRegex(StoreError, "offline cache"):
            resolver.resolve("analysis/current", offline=True)

    def test_cache_root_environment_override(self) -> None:
        with patch.dict(
            os.environ,
            {"JRDB_STORE_CACHE": "/tmp/jrdb-cache-test"},
            clear=False,
        ):
            self.assertEqual(default_cache_root(), Path("/tmp/jrdb-cache-test"))


if __name__ == "__main__":
    unittest.main()
