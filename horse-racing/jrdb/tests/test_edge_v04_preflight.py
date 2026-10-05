from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "horse-racing" / "jrdb" / "src"
sys.path.insert(0, str(SRC))

from jrdb_edge_v04_preflight import (  # noqa: E402
    build_plan,
    date_in_window,
    resolve_date_window,
    select_templates,
)

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:  # Pure date/planner tests remain runnable without Arrow installed.
    pa = None
    pq = None


class PlannerAndWindowUnitTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"template_id": "t1", "search_lane": "TRANSITION_PRIORITY", "depth": 2, "estimated_group_upper_bound": 100},
            {"template_id": "t2", "search_lane": "TRANSITION_PRIORITY", "depth": 3, "estimated_group_upper_bound": 200},
            {"template_id": "t3", "search_lane": "PEDIGREE_INTERACTION", "depth": 3, "estimated_group_upper_bound": 300},
            {"template_id": "t4", "search_lane": "PEDIGREE_BASELINE", "depth": 2, "estimated_group_upper_bound": 400},
            {"template_id": "t5", "search_lane": "TRANSITION_PRIORITY", "depth": 4, "estimated_group_upper_bound": 500},
            {"template_id": "t6", "search_lane": "STATIC_CROSS", "depth": 2, "estimated_group_upper_bound": 600},
        ]

    def test_wave_a_selection_and_one_assignment_per_selected_template(self):
        lanes = ["TRANSITION_PRIORITY", "PEDIGREE_INTERACTION", "PEDIGREE_BASELINE"]
        plan = build_plan(
            self.rows,
            source_catalog_sha256="source-sha",
            search_lanes=lanes,
            min_depth=2,
            max_depth=3,
            max_templates_per_shard=2,
            target_estimated_cost=10_000,
        )
        assigned = [template_id for shard in plan["shards"] for template_id in shard["template_ids"]]
        self.assertCountEqual(assigned, ["t1", "t2", "t3", "t4"])
        self.assertEqual(len(assigned), len(set(assigned)))
        self.assertNotIn("t5", assigned)
        self.assertNotIn("t6", assigned)
        self.assertEqual(plan["source_template_catalog_sha256"], "source-sha")
        self.assertEqual(plan["selected_template_counts_by_lane"], {
            "PEDIGREE_BASELINE": 1,
            "PEDIGREE_INTERACTION": 1,
            "TRANSITION_PRIORITY": 2,
        })
        self.assertEqual(plan["selected_template_counts_by_depth"], {"2": 2, "3": 2})
        self.assertFalse(plan["uses_results"])
        self.assertFalse(plan["uses_roi"])
        self.assertFalse(plan["uses_odds_or_popularity"])

    def test_empty_or_invalid_planner_selection_fails(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            select_templates(self.rows, ["TRANSITION_PRIORITY"], 5, 6)
        with self.assertRaisesRegex(ValueError, "unknown search lane"):
            select_templates(self.rows, ["STATIC_CROSS"], 2, 3)

    def test_plan_and_assignments_are_deterministic(self):
        kwargs = dict(
            source_catalog_sha256="source-sha",
            search_lanes=["TRANSITION_PRIORITY", "PEDIGREE_INTERACTION"],
            min_depth=2,
            max_depth=3,
            max_templates_per_shard=1,
        )
        first = build_plan(self.rows, **kwargs)
        second = build_plan(list(reversed(self.rows)), **kwargs)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_as_of_window_is_inclusive_and_excludes_rows_after_endpoint(self):
        as_of, start, source_max = resolve_date_window(
            ["2021-12-31", "2022-01-01", "2024-12-31", "2025-01-02"], 3, "2025-01-01"
        )
        self.assertEqual((as_of, start, source_max), (date(2025, 1, 1), date(2022, 1, 1), date(2025, 1, 2)))
        self.assertTrue(date_in_window("2022-01-01", start, as_of))
        self.assertTrue(date_in_window("2025-01-01", start, as_of))
        self.assertFalse(date_in_window("2021-12-31", start, as_of))
        self.assertFalse(date_in_window("2025-01-02", start, as_of))

    def test_default_as_of_and_february_29_fallback_are_stable(self):
        self.assertEqual(resolve_date_window(["2021-03-01", "2024-02-29"], 3),
                         (date(2024, 2, 29), date(2021, 2, 28), date(2024, 2, 29)))
        first = resolve_date_window(["2021-03-01", "2024-02-29"], 3, "2024-02-29")
        second = resolve_date_window(["2021-03-01", "2024-02-29"], 3, "2024-02-29")
        self.assertEqual(first, second)

    def test_bad_discovery_years_and_malformed_or_empty_date_domain_fail(self):
        for years in (0, -1):
            with self.subTest(years=years), self.assertRaisesRegex(ValueError, "positive"):
                resolve_date_window(["2024-01-01"], years)
        for values, message in (([], "no non-null"), ([None, None], "no non-null"), (["0000-00-00"], "malformed"), (["2024-1-01"], "malformed")):
            with self.subTest(values=values), self.assertRaisesRegex(ValueError, message):
                resolve_date_window(values, 3)
        with self.assertRaisesRegex(ValueError, "exceeds maximum"):
            resolve_date_window(["2024-01-01"], 3, "2024-01-02")


@unittest.skipUnless(pa is not None, "pyarrow is required for synthetic Parquet integration tests")
class ParquetIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.work = Path(self.temp.name)
        self.feature_path = self.work / "feature.parquet"
        self.template_path = self.work / "templates.parquet"

    def tearDown(self):
        self.temp.cleanup()

    def _write_feature_fixture(self):
        dims = [
            "venue_code", "distance_m", "surface_code", "turn_code", "inner_outer_code",
            "race_condition_code", "grade_code", "track_condition_bucket", "frame_zone",
            "sex_code", "horse_age", "running_style_code", "condition_class_code", "sire_name",
            "sire_line_code", "broodmare_sire_name", "broodmare_sire_line_code", "prev1_venue_code",
            "prev1_turn_code", "distance_change_bucket", "surface_transition", "frame_transition",
        ]
        rows = []
        for index in range(15):
            row = {dim: f"v-{dim}" for dim in dims}
            row.update({
                "venue_code": "01", "distance_m": "1600", "race_date": "2022-01-01" if index == 0 else "2024-12-31",
                "label_win_hit": 1 if index in (13, 14) else 0,
                "label_place_hit": 0,
                "label_win_payout": 1000.0 if index in (13, 14) else 0.0,
                "label_place_payout": 0.0,
            })
            rows.append(row)
        for race_date in ("2021-12-31", "2025-01-02"):
            row = {dim: f"v-{dim}" for dim in dims}
            row.update({
                "venue_code": "01", "distance_m": "1600", "race_date": race_date,
                "label_win_hit": 1, "label_place_hit": 1,
                "label_win_payout": 100_000.0, "label_place_payout": 100_000.0,
            })
            rows.append(row)
        pq.write_table(pa.Table.from_pylist(rows), self.feature_path)
        return rows

    def _run(self, script: str, *args: str):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
        return subprocess.run(
            [sys.executable, str(SRC / script), *args], cwd=ROOT, env=env,
            text=True, capture_output=True, check=False,
        )

    def test_planner_cli_filters_before_sharding_and_records_catalog_hash(self):
        templates = [
            {"template_id": "t-transition", "search_lane": "TRANSITION_PRIORITY", "depth": 2, "estimated_group_upper_bound": 10},
            {"template_id": "t-interaction", "search_lane": "PEDIGREE_INTERACTION", "depth": 3, "estimated_group_upper_bound": 20},
            {"template_id": "t-baseline", "search_lane": "PEDIGREE_BASELINE", "depth": 2, "estimated_group_upper_bound": 30},
            {"template_id": "t-depth4", "search_lane": "TRANSITION_PRIORITY", "depth": 4, "estimated_group_upper_bound": 40},
            {"template_id": "t-static", "search_lane": "STATIC_CROSS", "depth": 2, "estimated_group_upper_bound": 50},
        ]
        pq.write_table(pa.Table.from_pylist(templates), self.template_path)
        outputs = [self.work / "plan-one.json", self.work / "plan-two.json"]
        for output in outputs:
            result = self._run(
                "plan_jrdb_edge_v04_stage_c1_shards.py",
                "--template-parquet", str(self.template_path), "--output", str(output),
                "--search-lane", "TRANSITION_PRIORITY", "--search-lane", "PEDIGREE_INTERACTION",
                "--search-lane", "PEDIGREE_BASELINE", "--min-depth", "2", "--max-depth", "3",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        one = json.loads(outputs[0].read_text())
        two = json.loads(outputs[1].read_text())
        self.assertEqual(one, two)
        self.assertEqual(one["source_template_catalog_sha256"], hashlib.sha256(self.template_path.read_bytes()).hexdigest())
        assigned = [tid for shard in one["shards"] for tid in shard["template_ids"]]
        self.assertCountEqual(assigned, ["t-transition", "t-interaction", "t-baseline"])
        self.assertEqual(len(assigned), len(set(assigned)))
        empty = self._run(
            "plan_jrdb_edge_v04_stage_c1_shards.py", "--template-parquet", str(self.template_path),
            "--output", str(self.work / "empty.json"), "--search-lane", "TRANSITION_PRIORITY",
            "--min-depth", "5", "--max-depth", "6",
        )
        self.assertNotEqual(empty.returncode, 0)
        self.assertIn("empty", empty.stderr)

    def test_c1_and_c2b_share_explicit_window_and_exclude_outside_metrics(self):
        self._write_feature_fixture()
        template_id = "tpl-transition-2"
        dimensions = ["venue_code", "distance_m"]
        template = {
            "template_id": template_id, "depth": 2, "search_lane": "TRANSITION_PRIORITY",
            "family": "TRANSITION_CROSS", "dimensions_json": json.dumps(dimensions),
        }
        pq.write_table(pa.Table.from_pylist([template]), self.template_path)
        plan_path = self.work / "plan.json"
        plan = {
            "shards": [{
                "shard_id": "transition_priority-d2-s000", "search_lane": "TRANSITION_PRIORITY",
                "depth": 2, "template_ids": [template_id],
                "template_ids_sha256": hashlib.sha256(template_id.encode()).hexdigest(),
            }]
        }
        plan_path.write_text(json.dumps(plan))
        c1_out = self.work / "c1"
        c1 = self._run(
            "evaluate_jrdb_edge_v04_stage_c1_shard.py", "--feature-parquet", str(self.feature_path),
            "--template-parquet", str(self.template_path), "--shard-plan", str(plan_path),
            "--shard-id", "transition_priority-d2-s000", "--output-dir", str(c1_out),
            "--discovery-years", "3", "--as-of-date", "2025-01-01",
        )
        self.assertEqual(c1.returncode, 0, c1.stderr)
        c1_audit = json.loads((c1_out / "stage_c_shard_audit_transition_priority-d2-s000.json").read_text())
        c1_rows = pq.read_table(c1_out / "research_candidates_shard_transition_priority-d2-s000.parquet").to_pylist()
        self.assertEqual(c1_audit["requested_as_of_date"], "2025-01-01")
        self.assertEqual(c1_audit["resolved_as_of_date"], "2025-01-01")
        self.assertEqual(c1_audit["discovery_start_date"], "2022-01-01")
        self.assertEqual(c1_audit["discovery_end_date"], "2025-01-01")
        self.assertEqual(c1_audit["source_rows_all_history"], 17)
        self.assertEqual(c1_audit["source_rows"], 15)
        self.assertEqual(len(c1_rows), 1)
        self.assertEqual(c1_rows[0]["n"], 15)
        self.assertAlmostEqual(c1_rows[0]["win_roi"], 133.3333, places=3)
        self.assertEqual(c1_rows[0]["n_365"], 14)

        request_path = self.work / "requests.parquet"
        conditions = [
            {"feature": "venue_code", "value": "01"},
            {"feature": "distance_m", "value": "1600"},
        ]
        pq.write_table(pa.Table.from_pylist([{
            "metric_request_id": "v04m_00synthetic", "conditions_json": json.dumps(conditions), "depth": 2,
        }]), request_path)
        c2_out = self.work / "c2b"
        c2b = self._run(
            "evaluate_jrdb_edge_v04_stage_c2b_shard.py", "--feature-parquet", str(self.feature_path),
            "--request-parquet", str(request_path), "--output-dir", str(c2_out),
            "--shard-index", "0", "--shard-count", "1", "--discovery-years", "3",
            "--as-of-date", "2025-01-01",
        )
        self.assertEqual(c2b.returncode, 0, c2b.stderr)
        c2_audit = json.loads((c2_out / "stage_c2b_shard_audit_00.json").read_text())
        c2_rows = pq.read_table(c2_out / "metric_results_shard_00.parquet").to_pylist()
        self.assertEqual((c2_audit["discovery_start_date"], c2_audit["discovery_end_date"]),
                         (c1_audit["discovery_start_date"], c1_audit["discovery_end_date"]))
        self.assertEqual(c2_audit["feature_rows_discovery"], c1_audit["source_rows"])
        self.assertEqual(c2_rows[0]["n"], 15)
        self.assertAlmostEqual(c2_rows[0]["win_roi"], 2000 / 15)


if __name__ == "__main__":
    unittest.main()
