from __future__ import annotations

import hashlib
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "horse-racing/jrdb/src/jrdb_edge_v04_preflight.py"
SPEC = importlib.util.spec_from_file_location("jrdb_edge_v04_preflight", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class EdgeV04FamilyPreflightTest(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = [
            {"template_id": "t1", "search_lane": "PEDIGREE_BASELINE", "family": "PEDIGREE_CROSS", "depth": 2, "estimated_group_upper_bound": 10},
            {"template_id": "t2", "search_lane": "PEDIGREE_BASELINE", "family": "TRANSITION_CROSS", "depth": 2, "estimated_group_upper_bound": 20},
            {"template_id": "t3", "search_lane": "PEDIGREE_INTERACTION", "family": "PEDIGREE_CROSS", "depth": 3, "estimated_group_upper_bound": 30},
            {"template_id": "t4", "search_lane": "TRANSITION_PRIORITY", "family": "PEDIGREE_TRANSITION_CROSS", "depth": 3, "estimated_group_upper_bound": 40},
            {"template_id": "t5", "search_lane": "TRANSITION_PRIORITY", "family": "PEDIGREE_CROSS", "depth": 4, "estimated_group_upper_bound": 50},
        ]

    def test_family_filter_applies_before_partition(self) -> None:
        plan = MODULE.build_plan(
            self.rows,
            source_catalog_sha256="catalog-sha",
            search_lanes=["PEDIGREE_BASELINE", "PEDIGREE_INTERACTION", "TRANSITION_PRIORITY"],
            families=["PEDIGREE_CROSS"],
            min_depth=2,
            max_depth=3,
        )
        self.assertEqual(plan["source_template_count"], 5)
        self.assertEqual(plan["template_count"], 2)
        self.assertEqual(plan["requested_families"], ["PEDIGREE_CROSS"])
        self.assertEqual(plan["selected_template_counts_by_family"], {"PEDIGREE_CROSS": 2})
        self.assertEqual(plan["selected_template_counts_by_depth"], {"2": 1, "3": 1})
        self.assertEqual(
            plan["selected_template_counts_by_lane"],
            {"PEDIGREE_BASELINE": 1, "PEDIGREE_INTERACTION": 1},
        )
        assigned = sorted(
            template_id
            for shard in plan["shards"]
            for template_id in shard["template_ids"]
        )
        self.assertEqual(assigned, ["t1", "t3"])
        expected = hashlib.sha256("t1\nt3".encode()).hexdigest()
        self.assertEqual(plan["selected_template_ids_sha256"], expected)
        self.assertTrue(plan["selection_applied_before_partition"])
        self.assertFalse(plan["uses_results"])
        self.assertFalse(plan["uses_roi"])
        self.assertFalse(plan["uses_odds_or_popularity"])

    def test_family_filter_is_deterministic(self) -> None:
        kwargs = dict(
            source_catalog_sha256="catalog-sha",
            search_lanes=["PEDIGREE_INTERACTION", "PEDIGREE_BASELINE"],
            families=["PEDIGREE_CROSS"],
            min_depth=2,
            max_depth=3,
        )
        first = MODULE.build_plan(list(self.rows), **kwargs)
        second = MODULE.build_plan(list(reversed(self.rows)), **kwargs)
        self.assertEqual(first, second)

    def test_unknown_family_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "template selection is empty"):
            MODULE.build_plan(
                self.rows,
                source_catalog_sha256="catalog-sha",
                families=["DOES_NOT_EXIST"],
                min_depth=2,
                max_depth=3,
            )


if __name__ == "__main__":
    unittest.main()
