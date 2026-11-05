"""D2 deterministic synthetic tests; no licensed pedigree data."""
from __future__ import annotations

import copy
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from brdb_ancestor_graph import ancestor_graph
from brdb_d1_catalog import load_catalog
from brdb_d2_ancestry_positions import (
    PositionError, describe_positions, from_relations, VERSION,
)

REGIONS = ROOT / "taxonomy" / "regional_roots_candidate_v0_1.json"
BLOOD = ROOT / "taxonomy" / "embedded_blood_hypotheses_candidate_v0_1.json"


def relation(role, parent=None):
    return {"role": role, "resolved_parent_horse_id": parent,
            "resolution_status": "RESOLVED_EXACT" if parent else "NO_CANDIDATE"}


class D2PositionsTest(unittest.TestCase):
    def setUp(self):
        self.data = {
            "A": [relation("sire", "F"), relation("dam", "M")],
            "F": [relation("sire", "FF"), relation("dam", "FM")],
            "M": [relation("sire", "BMS"), relation("dam", "MM")],
            "FF": [relation("sire", "X")],
            "BMS": [relation("sire", "X")],
        }
        self.catalogs = load_catalog(REGIONS), load_catalog(BLOOD)

    def build(self, depth=3, data=None, **kw):
        return from_relations("A", lambda h: (data or self.data).get(h, []),
                              source_generation="SYNTHETIC-GEN",
                              target_date="2026-11-01",
                              source_profile_as_of="2026-10-31",
                              max_depth=depth, candidate_catalogs=self.catalogs, **kw)

    def test_parent_position_and_bms_ds_distinguished(self):
        r = self.build(depth=3)
        by = {v["ancestor_horse_id"]: v for v in r["ancestors"]}
        self.assertEqual(by["F"]["paths"], ["S"])
        self.assertEqual(by["F"]["roles"], ["SIRE_EXACT"])
        self.assertEqual(by["M"]["paths"], ["D"])
        self.assertEqual(by["BMS"]["paths"], ["DS"])
        self.assertEqual(by["BMS"]["roles"], ["BMS_EXACT"])
        self.assertEqual(by["FF"]["paths"], ["SS"])
        self.assertEqual(by["X"]["paths"], ["SSS", "DSS"])
        self.assertEqual(by["X"]["observed_occurrences"], 2)
        self.assertEqual(by["X"]["sides"], ["MATERNAL", "SIRE"])

    def test_cross_is_same_id_two_paths_not_name(self):
        r = self.build(depth=3)
        self.assertEqual(r["observed_cross_count"], 1)
        cross = r["observed_crosses"][0]
        self.assertEqual(cross["ancestor_horse_id"], "X")
        self.assertEqual(cross["notation"], "3×3")
        self.assertEqual(cross["paths"], ["DSS", "SSS"])
        self.assertFalse(r["no_observed_cross_absence_proven"])

    def test_partial_graph_unknown_not_negative(self):
        r = self.build(depth=5, data={"A": [relation("sire", "F")]})
        self.assertFalse(r["complete"])
        self.assertEqual(r["max_depth"], 5)
        self.assertEqual(sum(v["expected_paths"] for v in r["generation_coverage"]), 62)
        self.assertEqual(sum(v["resolved_paths"] for v in r["generation_coverage"]), 1)
        self.assertEqual(r["side_coverage"]["MATERNAL"]["unknown_paths"], 31)
        self.assertTrue(r["unresolved_is_unknown"])
        self.assertEqual(r["observed_crosses"], [])
        self.assertFalse(r["no_observed_cross_absence_proven"])

    def test_complete_one_generation_proves_only_depth_one(self):
        r = self.build(depth=1)
        self.assertTrue(r["complete"])
        self.assertTrue(r["no_observed_cross_absence_proven"])
        self.assertEqual(r["max_depth"], 1)
        self.assertEqual(r["generation_coverage"][0]["expected_paths"], 2)

    def test_d1_names_not_mapped_to_ids_or_regions(self):
        r = self.build()
        self.assertEqual(r["candidate_catalog_status"], "D1_CANDIDATE_UNBOUND")
        self.assertEqual(r["candidate_bloodline_matches"], [])
        self.assertEqual(r["regional_root_assignments"], [])
        self.assertEqual(r["aptitude_claims"], [])
        self.assertFalse(r["can_change_primary_review"])
        self.assertTrue(all(v["identity_binding"] == "CANONICAL_GRAPH_ONLY"
                            for v in r["ancestors"]))

    def test_future_profile_rejected(self):
        with self.assertRaises(PositionError):
            from_relations("A", lambda h: self.data.get(h, []),
                           source_generation="SYNTH", target_date="2026-11-01",
                           source_profile_as_of="2026-11-02")
        graph = ancestor_graph("A", lambda h: self.data.get(h, []), max_depth=2)
        with self.assertRaises(PositionError):
            describe_positions(graph, source_generation="SYNTH",
                               target_date="2026-11-01",
                               profile_timing_verified=True)

    def test_asof_remains_unverified_by_date_only(self):
        r = self.build()
        self.assertEqual(r["historical_asof_status"], "AS_OF_UNVERIFIED")
        self.assertFalse(r["prediction_safe"])
        self.assertTrue(r["research_only"])

    def test_tampered_graph_unresolved_id_rejected(self):
        graph = ancestor_graph("A", lambda h: self.data.get(h, []), max_depth=3)
        graph["paths"][0]["resolution_status"] = "NO_CANDIDATE"
        with self.assertRaises(PositionError):
            describe_positions(graph, source_generation="SYNTH",
                               target_date="2026-11-01")

    def test_tampered_graph_orphan_path_rejected(self):
        graph = ancestor_graph("A", lambda h: self.data.get(h, []), max_depth=3)
        for row in graph["paths"]:
            if row["path"] == "S":
                row["horse_id"] = None
                row["status"] = "NO_CANDIDATE"
                break
        graph["resolved_paths"] -= 1
        with self.assertRaises(PositionError):
            describe_positions(graph, source_generation="SYNTH",
                               target_date="2026-11-01")

    def test_bad_d1_approval_rejected(self):
        regions, blood = copy.deepcopy(self.catalogs)
        blood["hypotheses"][0]["review_status"] = "REVIEWED"
        graph = ancestor_graph("A", lambda h: self.data.get(h, []), max_depth=2)
        with self.assertRaises(ValueError):
            describe_positions(graph, source_generation="SYNTH",
                               target_date="2026-11-01",
                               candidate_catalogs=(regions, blood))


if __name__ == "__main__":
    unittest.main()
