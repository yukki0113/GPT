"""Deterministic read-only runtime dependency monitoring contract."""
import importlib.util
from pathlib import Path
import sys
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts/check_runtime_dependency_updates.py"
spec = importlib.util.spec_from_file_location("check_runtime_dependency_updates", SOURCE)
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)


def fake_project(releases):
    return {"releases": {version: [
        {"packagetype": "bdist_wheel",
         "filename": f"pkg-{version}-cp313-cp313-manylinux_2_28_x86_64.whl",
         "yanked": yanked}
    ] for version, yanked in releases.items()}}


class DependencyWatchTest(unittest.TestCase):
    def setUp(self):
        self.registry = {"packages": [
            {"package": "duckdb", "version": "2.0.1"},
            {"package": "pyarrow", "version": "25.0.1"},
            {"package": "numpy", "version": "2.2.4"}]}
        self.pypi = {"duckdb": fake_project({"2.0.1": False}),
                     "pyarrow": fake_project({"25.0.1": False}),
                     "numpy": fake_project({"2.2.4": False})}

    def test_no_updates(self):
        out = watch.inspect(self.registry, self.pypi, "2026-11-23T00:00:00Z")
        self.assertEqual(out["status"], "NO_UPDATES")
        self.assertTrue(all(not x["newer_available"] for x in out["components"]))
        self.assertEqual(out["promotion"], "NEVER_AUTOMATIC")

    def test_stable_release_drives_review_not_promotion(self):
        self.pypi["duckdb"]["releases"]["2.0.2"] = fake_project(
            {"2.0.2": False})["releases"]["2.0.2"]
        out = watch.inspect(self.registry, self.pypi, "2026-11-23T00:00:00Z")
        self.assertEqual(out["status"], "REVIEW_REQUIRED")
        self.assertEqual(out["components"][0]["change_type"], "patch")
        self.assertIn("LTS eligibility", out["components"][0]["source_notes"])

    def test_no_prerelease_and_no_yanked(self):
        self.pypi["duckdb"] = fake_project({
            "2.0.1": False, "2.0.9rc1": False, "2.0.3": True, "2.0.2": False})
        report = watch.inspect(self.registry, self.pypi, "2026-11-23T00:00:00Z")
        self.assertEqual(report["components"][0]["latest_stable_with_non_yanked_wheel"], "2.0.2")

    def test_newer_major_and_minor(self):
        self.assertEqual(watch.classify("2.0.1", "3.0.0"), "major")
        self.assertEqual(watch.classify("2.0.1", "2.1.0"), "minor")

    def test_no_download_or_install_in_monitor(self):
        self.assertEqual(watch.MONITORED, ("duckdb", "pyarrow", "numpy"))

    def test_invalid_registry_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "INVALID_REGISTRY"):
            watch.inspect({"packages": []}, self.pypi, "2026-11-23T00:00:00Z")

    def test_missing_pypi_releases_fails_closed(self):
        self.pypi["duckdb"] = {"releases": {}}
        with self.assertRaisesRegex(ValueError, "INVALID_PYPI"):
            watch.inspect(self.registry, self.pypi, "2026-11-23T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
