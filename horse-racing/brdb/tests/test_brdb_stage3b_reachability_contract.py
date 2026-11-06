"""Research reachability must never be treated as direct pedigree edges."""
import copy
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from brdb_stage3b_reachability_contract import (
    ReachabilityContractError, validate_reachability,
)


class ReachabilityContractTests(unittest.TestCase):
    """Use two subject roots and three source-identified ancestry positions."""

    def setUp(self):
        self.graph = {
            "schema_version": "brdb-stage3b-reachability-v0.1",
            "graph_kind": "ROOT_TO_ANCESTOR_REACHABILITY",
            "direct_parent_edge_count": 0,
            "supports_cross_detection": False,
            "research_only": True,
            "prediction_safe": False,
            "historical_asof_status": "AS_OF_UNVERIFIED",
            "nodes": [
                {"id": "JRDB:00000001", "kind": "ENTRY", "names": ["horse1"]},
                {"id": "JBIS:0000000001", "kind": "ANCESTOR", "names": ["ancestor1"]},
                {"id": "JRDB:00000002", "kind": "ENTRY", "names": ["horse2"]},
                {"id": "JRDB:00000003", "kind": "ANCESTOR", "names": ["ancestor2"]},
            ],
            "paths": [
                {"root_id": "JRDB:00000001",
                 "ancestor_id": "JBIS:0000000001", "path": "SSS",
                 "status": "JBIS_SOURCE_QUALIFIED",
                 "source_url": "https://www.jbis.or.jp/horse/0000000001/"},
                {"root_id": "JRDB:00000002",
                 "ancestor_id": "JRDB:00000003", "path": "S",
                 "status": "JRDB_CANONICAL",
                 "source_url": "JRDB_PARENT_RELATION"},
            ],
        }

    def test_path_counts_not_direct_parent_edge_counts(self):
        stats = validate_reachability(self.graph)
        self.assertEqual(stats["reachability_path_count"], 2)
        self.assertEqual(stats["direct_parent_edge_count"], 0)
        self.assertFalse(stats["supports_cross_detection"])
        self.assertEqual(stats["source_lane_counts"], {"jrdb": 1, "jbis": 1})

    def test_disallow_cross_detection_promotion(self):
        altered = copy.deepcopy(self.graph)
        altered["supports_cross_detection"] = True
        with self.assertRaises(ReachabilityContractError):
            validate_reachability(altered)

    def test_disallow_direct_parent_edge_promotion(self):
        altered = copy.deepcopy(self.graph)
        altered["direct_parent_edge_count"] = 2
        with self.assertRaises(ReachabilityContractError):
            validate_reachability(altered)

    def test_dangling_ancestor_id_fails(self):
        altered = copy.deepcopy(self.graph)
        altered["paths"][0]["ancestor_id"] = "JBIS:9999999999"
        with self.assertRaises(ReachabilityContractError):
            validate_reachability(altered)

    def test_name_only_status_cannot_be_an_edge(self):
        altered = copy.deepcopy(self.graph)
        altered["paths"][0]["status"] = "NAME_OBSERVED"
        with self.assertRaises(ReachabilityContractError):
            validate_reachability(altered)

    def test_namespace_must_match_source(self):
        altered = copy.deepcopy(self.graph)
        altered["paths"][0]["status"] = "JRDB_CANONICAL"
        with self.assertRaises(ReachabilityContractError):
            validate_reachability(altered)

    def test_same_root_path_cannot_be_double_counted(self):
        altered = copy.deepcopy(self.graph)
        altered["paths"].append(copy.deepcopy(altered["paths"][0]))
        with self.assertRaises(ReachabilityContractError):
            validate_reachability(altered)

    def test_three_generation_path_is_not_a_direct_parent(self):
        stats = validate_reachability(self.graph)
        self.assertEqual(stats["reachability_path_count"], 2)
        self.assertEqual(stats["direct_parent_edge_count"], 0)

    def test_asof_unknown_cannot_become_prediction_ready(self):
        altered = copy.deepcopy(self.graph)
        altered["prediction_safe"] = True
        with self.assertRaises(ReachabilityContractError):
            validate_reachability(altered)


if __name__ == "__main__":
    unittest.main()
