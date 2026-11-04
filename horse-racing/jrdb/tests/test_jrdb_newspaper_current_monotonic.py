"""T7 regression: no stale or equal-revision Current cache publication."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "horse-racing/jrdb/src"))

from jrdb_newspaper_current_monotonic import assert_current_advances, release_identity


PERSONAL = "jrdb_newspaper_current_cache"
MOMOTARO = "jrdb_momotaro_newspaper_current_cache"


class CurrentMonotonicTest(unittest.TestCase):
    def current(self, kind=PERSONAL):
        return {"release_kind": kind, "date": "2026-11-01", "revision": 9}

    def test_stale_git_request_cannot_roll_back_current(self):
        request = json.loads(
            (ROOT / "horse-racing/jrdb/newspaper/publish/current.json").read_text()
        )
        with self.assertRaisesRegex(ValueError, "stale Current publication"):
            assert_current_advances(request, self.current(), PERSONAL)

    def test_equal_revision_cannot_replace_release(self):
        with self.assertRaisesRegex(ValueError, "stale Current publication"):
            assert_current_advances(
                {"date": "2026-11-01", "revision": 9},
                self.current(), PERSONAL
            )

    def test_older_date_with_higher_revision_is_stale(self):
        with self.assertRaisesRegex(ValueError, "stale Current publication"):
            assert_current_advances(
                {"date": "2026-10-31", "revision": 99},
                self.current(), PERSONAL
            )

    def test_new_revision_same_day_allowed(self):
        incoming, current = assert_current_advances(
            {"date": "2026-11-01", "revision": 10}, self.current(), PERSONAL
        )
        self.assertEqual((incoming[1], current[1]), (10, 9))

    def test_later_date_new_revision_one_allowed(self):
        assert_current_advances(
            {"date": "2026-11-07", "revision": 1}, self.current(), PERSONAL
        )

    def test_momotaro_kind_must_match(self):
        with self.assertRaisesRegex(ValueError, "release_kind mismatch"):
            assert_current_advances(
                {"date": "2026-11-07", "revision": 1},
                self.current(), MOMOTARO
            )
        assert_current_advances(
            {"date": "2026-11-07", "revision": 1},
            self.current(MOMOTARO), MOMOTARO
        )

    def test_invalid_identity_fails_closed(self):
        for obj in (
            {"date": "2026-11-01", "revision": True},
            {"date": "2026-11-01", "revision": 0},
            {"date": "2026-11-01", "revision": "9"},
            {"date": "2026-11-33", "revision": 9},
            {"date": "20261101", "revision": 9},
        ):
            with self.subTest(obj=obj):
                with self.assertRaises(ValueError):
                    release_identity(obj, "candidate")

    def test_guard_is_wired_before_mutable_publication(self):
        import yaml

        for name in (
            "jrdb_newspaper_publish_current.yml",
            "jrdb_newspaper_skeleton_publish_issue.yml",
            "jrdb_momotaro_newspaper_publish_issue.yml",
        ):
            path = ROOT / ".github/workflows" / name
            workflow = yaml.safe_load(path.read_text())
            job = next(iter(workflow["jobs"].values()))
            names = [step.get("name", "") for step in job["steps"]]
            gates = [
                i for i, step in enumerate(job["steps"])
                if "jrdb_newspaper_current_monotonic.py" in step.get("run", "")
            ]
            publishers = [
                i for i, step in enumerate(job["steps"])
                if "gh release" in step.get("run", "")
                and ("gh release upload" in step["run"] or "gh release create" in step["run"])
            ]
            with self.subTest(workflow=name):
                self.assertEqual(len(gates), 1)
                self.assertTrue(publishers)
                self.assertLess(gates[0], min(publishers))


    def test_all_current_release_writers_are_serialized(self):
        import yaml

        group = "jrdb-newspaper-current-publish"
        root = ROOT / ".github/workflows"
        cases = (
            ("jrdb_newspaper_publish_current.yml", "workflow"),
            ("jrdb_newspaper_skeleton_publish_issue.yml", "job"),
            ("jrdb_momotaro_newspaper_publish_issue.yml", "job"),
            ("jrdb_newspaper_kensho_merge_issue.yml", "job"),
        )
        for name, owner in cases:
            with self.subTest(workflow=name):
                workflow = yaml.safe_load((root / name).read_text())
                if owner == "workflow":
                    concurrency = workflow.get("concurrency") or {}
                else:
                    job = next(iter(workflow["jobs"].values()))
                    concurrency = job.get("concurrency") or {}
                self.assertEqual(concurrency.get("group"), group)
                self.assertFalse(concurrency.get("cancel-in-progress", True))


if __name__ == "__main__":
    unittest.main()
