import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from brdb_ancestor_graph import ancestor_graph, ancestor_crosses, pedigree_similarity, PedigreeGraphError

def row(role, parent=None, status="NO_CANDIDATE"):
    return {"role": role, "resolved_parent_horse_id": parent, "resolution_status": status}

class AncestorGraphTest(unittest.TestCase):
    def test_cross_detected_by_ids_not_names(self):
        graph = {
            "A": [row("sire", "B", "RESOLVED_EXACT"), row("dam", "C", "RESOLVED_ALIAS")],
            "B": [row("sire", "X", "RESOLVED_EXACT"), row("dam")],
            "C": [row("sire", "X", "RESOLVED_EXACT"), row("dam")],
        }
        result = ancestor_graph("A", lambda x: graph.get(x, []), max_depth=2)
        crosses = ancestor_crosses(result)["crosses"]
        self.assertEqual(crosses[0]["ancestor_horse_id"], "X")
        self.assertEqual(crosses[0]["paths"], ["DS", "SS"])
        self.assertEqual(result["coverage"], "PARTIAL")

    def test_same_unresolved_name_does_not_create_cross(self):
        root = {"A": [row("sire"), row("dam")]}
        result = ancestor_graph("A", lambda x: root.get(x, []), max_depth=3)
        self.assertEqual(ancestor_crosses(result)["crosses"], [])
        self.assertFalse(ancestor_crosses(result)["absence_is_proven"])

    def test_cycle_fails_closed(self):
        graph = {"A": [row("sire", "A", "RESOLVED_EXACT"), row("dam")]}
        result = ancestor_graph("A", lambda x: graph.get(x, []), max_depth=2)
        self.assertEqual(result["paths"][0]["status"], "CYCLE")
        self.assertIsNone(result["paths"][0]["horse_id"])

    def test_unresolved_with_id_rejected(self):
        with self.assertRaises(PedigreeGraphError):
            ancestor_graph("A", lambda _: [row("sire", "B", "CONFLICT")])

    def test_duplicate_role_rejected(self):
        with self.assertRaises(PedigreeGraphError):
            ancestor_graph("A", lambda _: [row("sire"), row("sire")])

    def test_depth_guard(self):
        with self.assertRaises(PedigreeGraphError):
            ancestor_graph("A", lambda _: [], max_depth=6)

    def test_similarity_is_observed_only(self):
        graph = {
            "A": [row("sire", "X", "RESOLVED_EXACT")],
            "B": [row("dam", "X", "RESOLVED_EXACT")],
        }
        a = ancestor_graph("A", lambda x: graph.get(x, []), max_depth=1)
        b = ancestor_graph("B", lambda x: graph.get(x, []), max_depth=1)
        result = pedigree_similarity(a, b)
        self.assertEqual(result["shared_ancestor_ids"], ["X"])
        self.assertEqual(result["observed_jaccard"], 1.0)
        self.assertEqual(result["coverage"], "PARTIAL")

if __name__ == "__main__":
    unittest.main()
