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

import brdb_current as current  # noqa: E402
import brdb_pedigree_reader as reader  # noqa: E402
import build_brdb_current_bundle as bundle  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_generation(root: Path) -> None:
    payloads = {
        "pedigree_fact.parquet": b"pedigree",
        "parent_relation.parquet": b"relation",
        "pedigree_name_alias.parquet": b"alias",
        "lineage_code_master.parquet": b"lineage",
        "audit.json": b"{}\n",
    }
    for name, data in payloads.items():
        (root / name).write_bytes(data)
    manifest = {
        "artifact_type": "brdb_pedigree",
        "generation_id": "0123456789abcdef",
        "schema_version": "v0.1",
        "builder_version": "0.1.0",
        "source_family": "UKC",
        "source_archive_count": 1,
        "source_min_data_date": "20250101",
        "source_max_data_date": "20251231",
        "source_archives": [],
        "row_counts": {
            "pedigree_fact": 1,
            "parent_relation": 3,
            "pedigree_name_alias": 0,
            "lineage_code_master": 1,
        },
        "canonical_keys": {
            "pedigree_fact": ["horse_id"],
            "parent_relation": ["child_horse_id", "role"],
        },
        "alias_version": "v0.1",
        "lineage_source_version": ["test"],
        "validation_status": "PASS",
        "output_sha256": {name: sha256(root / name) for name in payloads},
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def make_transport(path: Path, zip_path: Path) -> None:
    data = {
        "schema_version": 1,
        "transport": "public_google_drive",
        "artifacts": [{
            "artifact_id": "brdb_current",
            "file_id": "1234567890ABCDEFGHIJ",
            "destination": "BloodReviewDB_CURRENT.zip",
            "expected_name": "BloodReviewDB_CURRENT.zip",
            "expected_size": zip_path.stat().st_size,
            "sha256": sha256(zip_path),
        }],
    }
    path.write_text(json.dumps(data), encoding="utf-8")


class BRDBCurrentResolverTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.generation = self.root / "generation"
        self.generation.mkdir()
        make_generation(self.generation)
        self.zip = self.root / "BloodReviewDB_CURRENT.zip"
        bundle.build_current_bundle(self.generation, self.zip)
        self.transport = self.root / "transport.json"
        make_transport(self.transport, self.zip)

    def fetcher(self, manifest_path: Path, output_root: Path) -> Path:
        target = output_root / "BloodReviewDB_CURRENT.zip"
        shutil.copy2(self.zip, target)
        return target

    def test_resolve_then_cache_hit(self):
        cache = self.root / "cache"
        first = current.resolve_brdb_current(
            cache, transport_manifest=self.transport, fetcher=self.fetcher
        )
        self.assertEqual(first.reader.generation_id, "0123456789abcdef")
        self.assertEqual(first.provenance["cache_status"], "REFRESHED")

        second = current.resolve_brdb_current(
            cache,
            transport_manifest=self.transport,
            fetcher=lambda *_: self.fail("cache hit should not fetch"),
        )
        self.assertEqual(second.provenance["cache_status"], "HIT")

    def test_bad_download_hash_does_not_replace_cache(self):
        cache = self.root / "cache"
        current.resolve_brdb_current(
            cache, transport_manifest=self.transport, fetcher=self.fetcher
        )
        accepted = cache / "generations" / "0123456789abcdef"
        self.assertTrue(accepted.is_dir())

        def bad_fetcher(_manifest, output_root):
            target = output_root / "BloodReviewDB_CURRENT.zip"
            target.write_bytes(b"tampered")
            return target

        with self.assertRaisesRegex(current.BRDBCurrentResolverError, "size mismatch"):
            current.resolve_brdb_current(
                cache,
                transport_manifest=self.transport,
                force_refresh=True,
                fetcher=bad_fetcher,
            )
        self.assertTrue(accepted.is_dir())
        reader.BloodReviewReader(accepted)

    def test_transport_filename_mismatch_fails(self):
        data = json.loads(self.transport.read_text())
        data["artifacts"][0]["expected_name"] = "wrong.zip"
        self.transport.write_text(json.dumps(data))
        with self.assertRaisesRegex(current.BRDBCurrentResolverError, "filename mismatch"):
            current.resolve_brdb_current(
                self.root / "cache",
                transport_manifest=self.transport,
                fetcher=self.fetcher,
            )


if __name__ == "__main__":
    unittest.main()
