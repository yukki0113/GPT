"""Unit tests for Stage 3-C pinned real-data acceptance constraints."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import verify_brdb_stage3c_direct_parent_graph as acceptance


class Stage3CIndependentAcceptanceTests(unittest.TestCase):
    """Synthetic direct-parent proof; only counts are relaxed via patch."""

    def setUp(self):
        self.graph = {
            "schema_version": "brdb-stage3c-direct-parent-v0.1",
            "graph_kind": "SOURCE_VERIFIED_DIRECT_PARENT",
            "source_generation": "5279af0bd8226cde",
            "research_only": True,
            "prediction_safe": False,
            "supports_production_cross_detection": False,
            "historical_asof_status": "AS_OF_UNVERIFIED",
            "verified_root_count": 2,
            "root_person_keys": ["JRDB:00000001", "JRDB:00000002"],
            "nodes": [
                {"person_key": "JRDB:00000001"},
                {"person_key": "JRDB:00000002"},
                {"person_key": "JRDB:00000003"},
                {"person_key": "JBIS:0000000001"},
            ],
            "edges": [
                {"child_person_key": "JRDB:00000001",
                 "parent_person_key": "JRDB:00000003", "role": "sire",
                 "source": "JRDB_PARENT_RELATION",
                 "evidence_kind": "DIRECT_PARENT_EDGE"},
                {"child_person_key": "JRDB:00000002",
                 "parent_person_key": "JBIS:0000000001", "role": "dam",
                 "source": "STAGE3B_MULTI_GUARD_JRDB_JBIS_BRIDGE",
                 "evidence_kind": "DIRECT_PARENT_EDGE"},
            ],
            "shared_ancestor_candidates": [],
            "stats": {
                "unverified_name_only_edges_added": 0,
                "unverified_identity_merges": 0,
                "parallel_unmerged_claims": 0,
            },
            "source_sha256": {
                "top50": acceptance.EXPECTED["top50_sha256"],
                "pedigree": acceptance.EXPECTED["pedigree_sha256"],
                "relations": acceptance.EXPECTED["parent_relation_sha256"],
            },
        }
        self.demo_counts = {
            **acceptance.EXPECTED,
            "verified_root_count": 2,
            "node_count": 4,
            "total_direct_parent_edges": 2,
            "jrdb_edges": 1,
            "jbis_bridge_edges": 1,
            "shared_ancestor_candidate_count": 0,
        }

    def verify(self):
        """Run acceptance logic using the synthetic expected counts."""
        with patch.object(acceptance, "EXPECTED", self.demo_counts):
            return acceptance.verify_graph(self.graph)

    def test_accepts_matching_source_evidence(self):
        self.assertEqual(self.verify()["status"], "PASS")

    def test_unaudited_jbis_key_cannot_be_cast_as_jrdb(self):
        self.graph["edges"][1]["parent_person_key"] = "JRDB:00000004"
        self.graph["nodes"][3]["person_key"] = "JRDB:00000004"
        with self.assertRaises(acceptance.AcceptanceError):
            self.verify()

    def test_name_only_edges_not_accepted(self):
        self.graph["stats"]["unverified_name_only_edges_added"] = 1
        with self.assertRaises(acceptance.AcceptanceError):
            self.verify()

    def test_research_only_asof_must_stay_unverified(self):
        self.graph["prediction_safe"] = True
        with self.assertRaises(acceptance.AcceptanceError):
            self.verify()

    def test_unexpected_direct_parent_count_rejected(self):
        self.graph["edges"].pop()
        with self.assertRaises(acceptance.AcceptanceError):
            self.verify()

    def test_duplicate_child_role_rejected(self):
        duplicate = copy.deepcopy(self.graph["edges"][0])
        duplicate["parent_person_key"] = "JBIS:0000000001"
        duplicate["source"] = "STAGE3B_MULTI_GUARD_JRDB_JBIS_BRIDGE"
        self.graph["edges"].append(duplicate)
        self.demo_counts["total_direct_parent_edges"] = 3
        self.demo_counts["jbis_bridge_edges"] = 2
        with self.assertRaises(acceptance.AcceptanceError):
            self.verify()

    def test_drifted_parquet_sha_fails(self):
        self.graph["source_sha256"]["relations"] = "0" * 64
        with self.assertRaises(acceptance.AcceptanceError):
            self.verify()


if __name__ == "__main__":
    unittest.main()
