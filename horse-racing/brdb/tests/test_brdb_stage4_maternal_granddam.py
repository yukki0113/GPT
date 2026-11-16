"""Contract tests for Stage 4 optional maternal-granddam research."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import brdb_stage4_maternal_granddam as stage4


class Stage4MaternalGranddamTests(unittest.TestCase):
    """Use synthetic parents to test proof depth and fail-closed guards."""

    def setUp(self):
        self.subjects = [
            {"rank": rank, "name": "H" + str(rank),
             "jrdb_horse_id": f"{rank:08d}" if rank <= 37 else None,
             "paths": []}
            for rank in range(1, 51)
        ]
        self.top50 = {
            "research_only": True, "prediction_safe": False,
            "source_generation": stage4.GENERATION, "subjects": self.subjects,
        }
        self.sources = {
            "version": "brdb-stage3b-jbis-observations-v0.1",
            "historical_asof_status": "AS_OF_UNVERIFIED",
            "research_only": True, "prediction_safe": False,
            "pedigrees": [
                {"rank": rank, "name": "H" + str(rank),
                 "jbis_subject_id": f"{rank:010d}",
                 "source_url":
                 f"https://www.jbis.or.jp/horse/{rank:010d}/pedigree/",
                 "paths": {
                     key: {"label": key + str(rank), "year": 1980}
                     for key in ("DD", "DDS", "DDD")
                 }}
                for rank in range(1, 51)
            ],
        }
        self.graph = {
            "schema_version": "brdb-stage3c-direct-parent-v0.1",
            "graph_kind": "SOURCE_VERIFIED_DIRECT_PARENT",
            "research_only": True, "prediction_safe": False,
            "historical_asof_status": "AS_OF_UNVERIFIED",
            "source_generation": stage4.GENERATION,
            "supports_production_cross_detection": False,
            "source_sha256": {"top50": stage4.TOP50_SHA},
            "root_person_keys": [f"JRDB:{rank:08d}" for rank in range(1, 38)],
            "nodes": [],
            "edges": [],
        }
        self.approved = {rank: True for rank in range(1, 51)}
        self.approved[50] = False
        self.set_edge("JRDB:00000001", "dam", "JRDB:00000101")
        self.set_edge("JRDB:00000101", "dam", "JRDB:00000102")

    def set_edge(self, child, role, parent):
        self.graph["edges"].append({
            "child_person_key": child, "role": role,
            "parent_person_key": parent,
            "source": "JRDB_PARENT_RELATION",
            "evidence_kind": "DIRECT_PARENT_EDGE",
        })
        for key in (child, parent):
            if not any(x["person_key"] == key for x in self.graph["nodes"]):
                self.graph["nodes"].append({"person_key": key})

    def run_builder(self):
        # Synthetic graph has fewer than 46 edges; independent real graph
        # size and source pins are instead verified by the actual E2E.
        with patch.object(stage4, "_validate_sources"):
            return stage4.build_maternal_observations(
                self.top50, self.sources, self.graph, self.approved)

    def test_one_hundred_fifty_unique_paths(self):
        result = self.run_builder()
        self.assertEqual(len(result["rows"]), 150)
        self.assertEqual(
            {path: result["counts"][path] for path in stage4.PATHS},
            {"DD": 50, "DDS": 50, "DDD": 50})

    def test_two_verified_steps_certify_dd_only(self):
        rows = [x for x in self.run_builder()["rows"] if x["rank"] == 1]
        dd = next(x for x in rows if x["path"] == "DD")
        self.assertEqual(dd["ancestor_person_key"], "JRDB:00000102")
        self.assertEqual(dd["identity_status"], "CERTIFIED_DIRECT_PARENT_CHAIN")
        self.assertEqual(len(dd["direct_parent_provenance"]), 2)
        self.assertTrue(all(x["ancestor_person_key"] is None
                            for x in rows if x["path"] != "DD"))

    def test_third_step_requires_separate_certified_edge(self):
        self.set_edge("JRDB:00000102", "sire", "JRDB:00000103")
        rows = [x for x in self.run_builder()["rows"] if x["rank"] == 1]
        dds = next(x for x in rows if x["path"] == "DDS")
        self.assertEqual(dds["ancestor_person_key"], "JRDB:00000103")
        self.assertEqual(len(dds["direct_parent_provenance"]), 3)

    def test_unreviewed_root_is_observation_only(self):
        row = next(x for x in self.run_builder()["rows"]
                   if x["rank"] == 50 and x["path"] == "DD")
        self.assertEqual(row["identity_status"], "ROOT_IDENTITY_REVIEW_REQUIRED")
        self.assertIsNone(row["ancestor_person_key"])

    def test_unreviewed_external_root_does_not_invalidate_jrdb_chain(self):
        self.approved[1] = False
        row = next(x for x in self.run_builder()["rows"]
                   if x["rank"] == 1 and x["path"] == "DD")
        self.assertEqual(row["identity_status"],
                         "JRDB_CHAIN_VERIFIED_EXTERNAL_ROOT_UNREVIEWED")

    def test_conflicting_existing_jrdb_person_id_rejected(self):
        self.subjects[0]["paths"] = [{
            "path": "DD", "id": "99999999", "name": "conflict",
        }]
        with self.assertRaisesRegex(stage4.MaternalGranddamError,
                                    "canonical person disagrees"):
            self.run_builder()

    def test_duplicate_rank_source_rejected(self):
        self.sources["pedigrees"][1]["rank"] = 1
        with self.assertRaisesRegex(stage4.MaternalGranddamError,
                                    "duplicate"):
            self.run_builder()

    def test_ancestor_source_names_never_create_person_keys(self):
        output = self.run_builder()
        self.assertEqual(
            sum(x["ancestor_person_key"] is not None for x in output["rows"]), 1)
        self.assertFalse(output["prediction_safe"])
        self.assertEqual(output["historical_asof_status"], "AS_OF_UNVERIFIED")

    def test_no_partial_path_is_proclaimed_verified(self):
        self.graph["edges"].pop()
        self.graph["nodes"] = [
            x for x in self.graph["nodes"]
            if x["person_key"] != "JRDB:00000102"
        ]
        rows = [x for x in self.run_builder()["rows"] if x["rank"] == 1]
        self.assertTrue(all(x["ancestor_person_key"] is None for x in rows))

    def test_reject_mixed_source_generation(self):
        self.graph["source_generation"] = "wrong"
        with self.assertRaisesRegex(stage4.MaternalGranddamError,
                                    "cannot trust"):
            stage4._validate_sources(self.top50, self.sources, self.graph)


if __name__ == "__main__":
    unittest.main()
