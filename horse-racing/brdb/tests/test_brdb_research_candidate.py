from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import build_brdb_research_candidate as candidate  # noqa: E402
from brdb_research_reader import ResearchPedigreeReader  # noqa: E402
from brdb_pedigree_reader import BloodReviewReader, BloodReviewReaderError  # noqa: E402


def observation(horse_id: str, data_date: str, archive_date: str, semantic_hash: str):
    return {"record": {"horse_id": horse_id, "data_date": data_date,
                       "horse_name": horse_id, "sire_name": "S",
                       "dam_name": "D", "broodmare_sire_name": "B",
                       "sire_line_code": "1206", "broodmare_sire_line_code": "1503"},
            "semantic_hash": semantic_hash, "archive_date": archive_date,
            "archive": f"PACI{archive_date[2:]}.zip", "archive_sha256": "a" * 64,
            "member": f"UKC{archive_date[2:]}.txt", "line_number": 1}


class CandidateSelectionTest(unittest.TestCase):
    def test_new_paci_can_extend_but_not_change_fixed_baseline(self):
        baseline = [{"name": f"PACI26{n:04d}.zip", "sha256": str(n)}
                    for n in range(91)]
        added = {"name": "PACI270101.zip", "sha256": "new"}
        candidate.checked_inventory(baseline + [added], baseline)
        changed = [dict(x) for x in baseline] + [added]
        changed[0]["sha256"] = "changed"
        with self.assertRaisesRegex(ValueError, "baseline PACI changed"):
            candidate.checked_inventory(changed, baseline)

    def test_latest_profile_and_history_are_deterministic(self):
        old = observation("12345678", "20260101", "20260104", "old")
        new = observation("12345678", "20260102", "20260111", "new")
        left = candidate.select_daily({"12345678": [new, old]}, "generation")
        right = candidate.select_daily({"12345678": [old, new]}, "generation")
        self.assertEqual(left, right)
        self.assertEqual(left[0][0]["profile_data_date"], "20260102")
        self.assertEqual(sum(row["selected"] for row in left[1]), 1)
        self.assertEqual(len(left[2]), 1)

    def test_same_date_conflict_fails_closed(self):
        a = observation("12345678", "20260102", "20260104", "a")
        b = observation("12345678", "20260102", "20260111", "b")
        with self.assertRaisesRegex(ValueError, "same-date semantic conflict"):
            candidate.select_daily({"12345678": [a, b]}, "generation")


class ResearchReaderTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        payloads = {name: b"fixture" for name in (
            "pedigree_fact.parquet", "parent_relation.parquet",
            "pedigree_name_alias.parquet", "lineage_code_master.parquet")}
        payloads["audit.json"] = b"{}"
        payloads["added_104.json"] = json.dumps([
            {"horse_id": f"{n:08d}", "first_observed_archive_date": "20260104"}
            for n in range(104)]).encode()
        for name, value in payloads.items():
            (self.root / name).write_bytes(value)
        manifest = {"artifact_type": "brdb_pedigree", "generation_id": "abc123",
                    "schema_version": "v0.1", "builder_version": "research-paci-v0.1",
                    "alias_version": "v0.1", "source_min_data_date": "19990101",
                    "source_max_data_date": "20261001", "validation_status": "PASS",
                    "research_only": True,
                    "row_counts": {"pedigree_fact": 104, "parent_relation": 312},
                    "output_sha256": {name: hashlib.sha256(value).hexdigest()
                                      for name, value in payloads.items()}}
        (self.root / "manifest.json").write_text(json.dumps(manifest))

    def test_explicit_reader_requires_as_of_and_never_changes_current(self):
        with self.assertRaises(BloodReviewReaderError):
            BloodReviewReader(self.root)
        reader = ResearchPedigreeReader(self.root)
        self.assertIsNone(reader.horse_pedigree("00000000", as_of="20251231"))
        reader._reader.horse_pedigree = lambda horse_id: {"horse_id": horse_id}
        self.assertEqual(reader.horse_pedigree("00000000", as_of="20260104"),
                         {"horse_id": "00000000"})
        with self.assertRaises(ValueError):
            reader.horse_pedigree("00000000", as_of="99999999")


if __name__ == "__main__":
    unittest.main()
