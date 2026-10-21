from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import brdb_pedigree_reader as reader  # noqa: E402
import build_brdb_current_bundle as bundle  # noqa: E402


class FakeCursor:
    def __init__(self, rows):
        self.description = [(name,) for name in rows[0].keys()] if rows else [("horse_id",)]
        self._rows = [tuple(row[name[0]] for name in self.description) for row in rows]

    def fetchall(self):
        return self._rows


class FakeConnection:
    def __init__(self, responses):
        self.responses = list(responses)
        self.closed = False

    def execute(self, sql, params):
        return FakeCursor(self.responses.pop(0))

    def close(self):
        self.closed = True


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_root(root: Path) -> None:
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
    current = {
        "status": "CURRENT",
        "artifact_type": "brdb_pedigree",
        "generation_id": "0123456789abcdef",
        "manifest": "manifest.json",
        "reader_contract_version": "v0.1",
    }
    (root / "current.json").write_text(json.dumps(current), encoding="utf-8")


class BloodReviewReaderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        make_root(self.root)

    def test_valid_current_metadata(self):
        got = reader.BloodReviewReader(self.root)
        self.assertEqual(got.generation_id, "0123456789abcdef")
        self.assertFalse(got.metadata()["name_fallback"])
        self.assertEqual(got.metadata()["row_counts"]["parent_relation"], 3)

    def test_generation_mismatch_fails_closed(self):
        current = json.loads((self.root / "current.json").read_text())
        current["generation_id"] = "fedcba9876543210"
        (self.root / "current.json").write_text(json.dumps(current))
        with self.assertRaisesRegex(reader.BloodReviewReaderError, "generation mismatch"):
            reader.BloodReviewReader(self.root)

    def test_hash_mismatch_fails_closed(self):
        (self.root / "pedigree_fact.parquet").write_bytes(b"tampered")
        with self.assertRaisesRegex(reader.BloodReviewReaderError, "SHA-256 mismatch"):
            reader.BloodReviewReader(self.root)

    def test_parent_relation_cardinality_contract(self):
        manifest = json.loads((self.root / "manifest.json").read_text())
        manifest["row_counts"]["parent_relation"] = 2
        (self.root / "manifest.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(reader.BloodReviewReaderError, "3 x pedigree_fact"):
            reader.BloodReviewReader(self.root, verify_hashes=False)

    def test_horse_pedigree_projection_uses_horse_id_only(self):
        got = reader.BloodReviewReader(self.root)
        responses = [
            [{
                "horse_id": "H1",
                "horse_name": "馬",
                "birth_date": "20220101",
                "sire_name": "父",
                "sire_birth_year": 2010,
                "dam_name": "母",
                "dam_birth_year": 2015,
                "broodmare_sire_name": "母父",
                "broodmare_sire_birth_year": 2008,
                "sire_line_code": "1206",
                "broodmare_sire_line_code": "1503",
            }],
            [
                {"role": "sire", "resolution_status": "RESOLVED_EXACT"},
                {"role": "dam", "resolution_status": "RESOLVED_EXACT"},
                {"role": "broodmare_sire", "resolution_status": "NO_CANDIDATE"},
            ],
            [{"lineage_code": "1206", "major_name": "大", "minor_name": "小"}],
            [{"lineage_code": "1503", "major_name": "大2", "minor_name": "小2"}],
        ]
        connections = [FakeConnection([response]) for response in responses]
        got._connect = lambda: connections.pop(0)
        projection = got.horse_pedigree("H1")
        self.assertEqual(projection["horse_id"], "H1")
        self.assertEqual(projection["sire"]["lineage"]["lineage_code"], "1206")
        self.assertEqual(
            projection["broodmare_sire"]["relation"]["resolution_status"],
            "NO_CANDIDATE",
        )
        with self.assertRaisesRegex(ValueError, "horse_id is required"):
            got.horse_profile("")

    def test_current_bundle_is_deterministic(self):
        generation = self.root / "generation"
        generation.mkdir()
        for name in ("manifest.json", *reader.REQUIRED_FILES):
            (generation / name).write_bytes((self.root / name).read_bytes())
        first = self.root / "one.zip"
        second = self.root / "two.zip"
        result1 = bundle.build_current_bundle(generation, first)
        result2 = bundle.build_current_bundle(generation, second)
        self.assertEqual(result1["generation_id"], "0123456789abcdef")
        self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == "__main__":
    unittest.main()
