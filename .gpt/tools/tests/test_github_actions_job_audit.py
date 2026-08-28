import importlib.util
import json
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "github_actions_job_audit.py"
SPEC = importlib.util.spec_from_file_location("github_actions_job_audit", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load module: {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GitHubActionsJobAuditTests(unittest.TestCase):
    """Unit tests for job duration, runner classification, and filtering."""

    def test_resolve_month_range(self) -> None:
        """Month shorthand must expand to the exact calendar month."""
        date_range = MODULE.resolve_date_range("2026-09", None, None)
        self.assertEqual("2026-09-01", date_range.start.isoformat())
        self.assertEqual("2026-09-30", date_range.end.isoformat())

    def test_rounds_four_minutes_thirty_seconds_to_five(self) -> None:
        """Private job estimate must round each started job up to a whole minute."""
        job = {
            "started_at": "2026-08-28T01:12:42Z",
            "completed_at": "2026-08-28T01:17:12Z",
            "conclusion": "failure",
        }
        duration_seconds = MODULE.calculate_duration_seconds(job)
        rounded_minutes = MODULE.calculate_rounded_job_minutes(job, duration_seconds)
        self.assertEqual(270, duration_seconds)
        self.assertEqual(5, rounded_minutes)

    def test_skipped_job_has_zero_rounded_minutes(self) -> None:
        """Skipped jobs must not be treated as one-minute runner executions."""
        job = {
            "started_at": "2026-08-28T01:00:00Z",
            "completed_at": "2026-08-28T01:00:00Z",
            "conclusion": "skipped",
        }
        self.assertEqual(0, MODULE.calculate_rounded_job_minutes(job, 0))

    def test_self_hosted_job_is_excluded_from_private_estimate(self) -> None:
        """Self-hosted runner jobs must not consume private GitHub-hosted minutes."""
        run = {
            "id": 1,
            "name": "sample",
            "path": ".github/workflows/sample.yml",
            "event": "push",
            "conclusion": "success",
            "created_at": "2026-09-01T00:00:00Z",
            "html_url": "https://example.invalid/run/1",
        }
        job = {
            "id": 10,
            "name": "test",
            "conclusion": "success",
            "started_at": "2026-09-01T00:00:00Z",
            "completed_at": "2026-09-01T00:01:01Z",
            "labels": ["self-hosted", "linux"],
            "runner_name": "local-runner",
        }
        row = MODULE.build_job_row(run, job)
        self.assertEqual("self-hosted", row.runner_type)
        self.assertEqual(2, row.rounded_job_minutes)
        self.assertEqual(0, row.private_estimated_minutes)

    def test_github_hosted_ubuntu_job_is_included(self) -> None:
        """GitHub-hosted Ubuntu jobs must contribute rounded private minutes."""
        run = {
            "id": 1,
            "name": "sample",
            "path": ".github/workflows/sample.yml",
            "event": "push",
            "conclusion": "success",
            "created_at": "2026-09-01T00:00:00Z",
            "html_url": "https://example.invalid/run/1",
        }
        job = {
            "id": 10,
            "name": "test",
            "conclusion": "success",
            "started_at": "2026-09-01T00:00:00Z",
            "completed_at": "2026-09-01T00:00:22Z",
            "labels": ["ubuntu-latest"],
            "runner_name": "GitHub Actions 1000000000",
            "runner_group_name": "GitHub Actions",
        }
        row = MODULE.build_job_row(run, job)
        self.assertEqual("github-hosted", row.runner_type)
        self.assertEqual("linux", row.runner_os)
        self.assertEqual(1, row.private_estimated_minutes)

    def test_paginated_response_is_flattened(self) -> None:
        """All pages returned by gh --slurp must be merged into one record list."""
        response = json.dumps(
            [
                {"workflow_runs": [{"id": 1}]},
                {"workflow_runs": [{"id": 2}, {"id": 3}]},
            ]
        )
        runs = MODULE.flatten_paginated_response(response, "workflow_runs")
        self.assertEqual([1, 2, 3], [run["id"] for run in runs])

    def test_exclude_workflow_regex_matches_name_or_path(self) -> None:
        """Workflow exclusion must work against both display name and YAML path."""
        patterns = MODULE.compile_patterns([r"Pages|deploy_pages"])
        named_run = {"name": "JRDB PWA Pages", "path": ".github/workflows/a.yml"}
        path_run = {"name": "other", "path": ".github/workflows/deploy_pages.yml"}
        self.assertTrue(MODULE.run_matches_patterns(named_run, patterns))
        self.assertTrue(MODULE.run_matches_patterns(path_run, patterns))


if __name__ == "__main__":
    unittest.main()
