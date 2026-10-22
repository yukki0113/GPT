import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from brdb_ancestor_graph import ancestor_graph
from brdb_ancestor_evidence import (
    AncestorEvidenceError, summarize_graph, describe_crosses,
    compare_observed_ancestors,
)


def relation(role, parent=None):
    return {
        "role": role,
        "resolved_parent_horse_id": parent,
        "resolution_status": "RESOLVED_EXACT" if parent else "NO_CANDIDATE",
    }


class AncestorEvidenceTest(unittest.TestCase):
    def test_observed_3_by_4_notation(self):
        data = {
            "A": [relation("sire", "B")],
            "B": [relation("sire", "C")],
            "C": [relation("sire", "X"), relation("dam", "D")],
            "D": [relation("dam", "X")],
        }
        graph = ancestor_graph("A", lambda key: data.get(key, []), max_depth=4)
        crosses = describe_crosses(graph)
        self.assertEqual(crosses["crosses"][0]["notation"], "3×4")
        self.assertFalse(crosses["absence_proven"])

    def test_missing_ancestors_are_not_negative_evidence(self):
        graph = ancestor_graph("A", lambda _: [], max_depth=5)
        result = describe_crosses(graph)
        self.assertEqual(result["observed_cross_count"], 0)
        self.assertFalse(result["absence_proven"])
        self.assertEqual(result["coverage"]["generation_coverage"][4]["expected_paths"], 32)

    def test_full_two_generation_tree(self):
        data = {
            "A": [relation("sire", "B"), relation("dam", "C")],
            "B": [relation("sire", "D"), relation("dam", "E")],
            "C": [relation("sire", "F"), relation("dam", "G")],
        }
        graph = ancestor_graph("A", lambda key: data.get(key, []), max_depth=2)
        self.assertTrue(summarize_graph(graph)["complete"])
        self.assertTrue(describe_crosses(graph)["absence_proven"])

    def test_partial_similarity_not_rankable(self):
        a = ancestor_graph("A", lambda _: [relation("sire", "X")], max_depth=1)
        b = ancestor_graph("B", lambda _: [relation("dam", "X")], max_depth=1)
        result = compare_observed_ancestors(a, b)
        self.assertEqual(result["observed_jaccard"], 1.0)
        self.assertFalse(result["can_rank_similarity"])

    def test_duplicate_paths_rejected(self):
        graph = ancestor_graph("A", lambda _: [], max_depth=1)
        graph["paths"].append(dict(graph["paths"][0]))
        with self.assertRaises(AncestorEvidenceError):
            summarize_graph(graph)


    def test_missing_intermediate_path_is_not_full(self):
        graph = {
            "horse_id": "A", "max_depth": 2,
            "paths": [
                {"path": "S", "horse_id": "B"},
                {"path": "D", "horse_id": "C"},
                {"path": "SS", "horse_id": "E"},
                {"path": "SD", "horse_id": "F"},
                {"path": "DS", "horse_id": "G"},
            ],
        }
        result = summarize_graph(graph)
        self.assertFalse(result["complete"])
        self.assertEqual(result["generation_coverage"][1]["unresolved_paths"], 1)

    def test_unknown_graph_does_not_create_similarity_rank(self):
        a = ancestor_graph("A", lambda _: [], max_depth=2)
        b = ancestor_graph("B", lambda _: [], max_depth=2)
        result = compare_observed_ancestors(a, b)
        self.assertIsNone(result["observed_jaccard"])
        self.assertFalse(result["can_rank_similarity"])


if __name__ == "__main__":
    unittest.main()
