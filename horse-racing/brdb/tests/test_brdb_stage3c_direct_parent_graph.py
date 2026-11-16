"""Fail-closed tests for the new Stage 3-C direct parent edge model."""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from brdb_stage3c_direct_parent_graph import (
    ParentGraphError, build_graph, inspect_shared_ancestor_candidates,
    person_key,
)


class Stage3CDirectParentGraphTests(unittest.TestCase):
    """Use 37 JRDB roots and 13 JBIS-only roots like the fixed cohort."""

    def setUp(self):
        subjects = []
        for index in range(1, 51):
            horse_id = str(index).zfill(8) if index <= 37 else None
            subjects.append({
                "name": "horse" + str(index),
                "jrdb_horse_id": horse_id,
            })
        self.top50 = {
            "research_only": True,
            "prediction_safe": False,
            "source_generation": "5279af0bd8226cde",
            "subjects": subjects,
        }
        self.crosswalk = {
            "schema_version": "brdb-stage3b-person-identity-crosswalk-candidate-v0.1",
            "source_generation": "5279af0bd8226cde",
            "prediction_safe": False,
            "historical_asof_status": "AS_OF_UNVERIFIED",
            "approved_research_crosswalks": [
                {
                    "jrdb_horse_id": str(index).zfill(8),
                    "person_resolution_status": "RESEARCH_MULTI_GUARD_VERIFIED",
                    "source_time_asof_verified": False,
                    "parent_links": [
                        {"path": "S",
                         "external_ancestor_key": "JBIS:" + str(index * 2).zfill(10)},
                        {"path": "D",
                         "external_ancestor_key": "JBIS:" + str(index * 2 + 1).zfill(10)},
                    ],
                }
                for index in (1, 2)
            ],
        }
        self.bridge = {
            "source_generation": "5279af0bd8226cde",
            "prediction_safe": False,
        }
        self.audit = {
            "status": "RESEARCH_CHILD_IDENTITY_CROSSWALK_VALID",
            "matched_child_identities": 2,
            "source_verified_parent_edges": 4,
            "external_parent_edges": [
                {
                    "jrdb_child_horse_id": str(index).zfill(8),
                    "path": role,
                    "external_ancestor_key": "JBIS:" + str(number).zfill(10),
                    "status": "SOURCE_VERIFIED_PARENT_EDGE_NO_JRDB_ANCESTOR_ID",
                }
                for index in (1, 2)
                for role, number in (("S", index * 2), ("D", index * 2 + 1))
            ],
        }
        self.relations = [
            {
                "child_horse_id": "00000003",
                "role": "sire",
                "resolved_parent_horse_id": "00000050",
                "resolution_status": "RESOLVED_EXACT",
            },
            {
                "child_horse_id": "00000004",
                "role": "sire",
                "resolved_parent_horse_id": "00000050",
                "resolution_status": "RESOLVED_ALIAS",
            },
            {
                "child_horse_id": "00000050",
                "role": "sire",
                "resolved_parent_horse_id": "00000060",
                "resolution_status": "RESOLVED_EXACT",
            },
            {
                "child_horse_id": "00000003",
                "role": "dam",
                "resolved_parent_horse_id": None,
                "resolution_status": "NAME_ONLY",
            },
        ]

    def graph(self):
        """Compute a synthetic instance with known edge provenance."""
        return build_graph(self.top50, self.relations, self.crosswalk,
                           self.bridge, self.audit)

    def test_requires_valid_8_digit_jrdb_person_key(self):
        self.assertEqual(person_key("JRDB", "00000003"), "JRDB:00000003")
        with self.assertRaises(ParentGraphError):
            person_key("JRDB", "000000003")

    def test_requires_valid_10_digit_jbis_person_key(self):
        self.assertEqual(person_key("JBIS", "0000000002"), "JBIS:0000000002")
        with self.assertRaises(ParentGraphError):
            person_key("JBIS", "00000002")

    def test_only_canonical_resolved_jrdb_edges_admitted(self):
        graph = self.graph()
        self.assertEqual(graph["stats"]["jrdb_edges"], 3)
        self.assertEqual(graph["stats"]["jbis_bridge_edges"], 4)
        self.assertEqual(graph["stats"]["unverified_name_only_edges_added"], 0)
        self.assertEqual(graph["verified_root_count"], 37)
        self.assertEqual(len(graph["edges"]), 7)
        self.assertFalse(graph["supports_production_cross_detection"])

    def test_shared_ancestor_candidates_use_verified_roots_only(self):
        candidates = inspect_shared_ancestor_candidates(self.graph())
        by_ancestor = {x["ancestor_person_key"]: x for x in candidates}
        self.assertEqual(
            by_ancestor["JRDB:00000050"]["reachable_jrdb_root_count"], 2)
        self.assertEqual(
            by_ancestor["JRDB:00000060"]["reachable_jrdb_root_count"], 2)

    def test_unverified_name_only_parent_cannot_enter_graph(self):
        graph = self.graph()
        parents = [
            edge for edge in graph["edges"]
            if edge["child_person_key"] == "JRDB:00000003"
            and edge["role"] == "dam"
        ]
        self.assertEqual(parents, [])

    def test_cycle_is_rejected(self):
        self.relations.append({
            "child_horse_id": "00000060", "role": "dam",
            "resolved_parent_horse_id": "00000003",
            "resolution_status": "RESOLVED_EXACT",
        })
        with self.assertRaisesRegex(ParentGraphError, "cycle"):
            self.graph()

    def test_duplicate_parent_role_is_rejected(self):
        self.relations.append(copy.deepcopy(self.relations[0]))
        with self.assertRaisesRegex(ParentGraphError, "duplicate"):
            self.graph()

    def test_external_and_jrdb_competing_sources_are_not_person_merged(self):
        self.relations.append({
            "child_horse_id": "00000001", "role": "sire",
            "resolved_parent_horse_id": "00000070",
            "resolution_status": "RESOLVED_EXACT",
        })
        graph = self.graph()
        self.assertEqual(graph["stats"]["parallel_unmerged_claims"], 1)
        self.assertEqual(graph["stats"]["jbis_bridge_edges"], 3)
        self.assertFalse(any(
            edge["child_person_key"] == "JRDB:00000001"
            and edge["parent_person_key"] == "JBIS:0000000002"
            for edge in graph["edges"]
        ))

    def test_rejects_unapproved_crosswalk(self):
        self.crosswalk["approved_research_crosswalks"][0][
            "person_resolution_status"] = "CANDIDATE"
        with self.assertRaises(ParentGraphError):
            self.graph()

    def test_rejects_asof_publication(self):
        self.top50["prediction_safe"] = True
        with self.assertRaises(ParentGraphError):
            self.graph()

    def test_does_not_infer_person_identity_from_shared_name(self):
        graph = self.graph()
        self.assertEqual(graph["stats"]["unverified_identity_merges"], 0)


if __name__ == "__main__":
    unittest.main()
