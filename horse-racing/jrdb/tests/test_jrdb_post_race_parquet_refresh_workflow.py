from __future__ import annotations

import unittest
from pathlib import Path


class PostRaceParquetRefreshWorkflowTest(unittest.TestCase):
    def test_refresh_uses_v14_native_candidate_and_stable_bundle(self) -> None:
        root = Path(__file__).resolve().parents[3]
        workflow = (
            root / ".github/workflows/jrdb_post_race_parquet_refresh_issue.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("[JRDB_POST_RACE_PARQUET_REFRESH]", workflow)
        self.assertIn("source_run_id", workflow)
        self.assertIn("artifact_name", workflow)
        self.assertIn("expected_source_generation", workflow)
        self.assertIn('gh run download "$SOURCE_RUN_ID"', workflow)
        self.assertIn("analysis-parquet-candidate.tar.xz", workflow)
        self.assertIn(
            "build_jrdb_analysis_post_race_parquet_native_v1_4.py",
            workflow,
        )
        self.assertIn("schema_version') != 'v1.4'", workflow)
        self.assertIn("native_parquet_update", workflow)
        self.assertIn("full_sqlite_materialization", workflow)
        self.assertIn("analysis-parquet-candidate.tar.xz", workflow)
        self.assertIn("if-no-files-found: error", workflow)

        self.assertNotIn("update_jrdb_analysis_incremental.py", workflow)
        self.assertNotIn("run_jrdb_analysis_post_race_incremental.py", workflow)
        self.assertNotIn("materialize_jrdb_analysis_sqlite.py", workflow)
        self.assertNotIn("publish_jrdb_analysis_parquet_drive_generation.py", workflow)
        self.assertNotIn("refresh_jrdb_stats_mart_year.py", workflow)
        self.assertNotIn("drive.usercontent.google.com", workflow)
        self.assertNotIn("drive.google.com", workflow)


if __name__ == "__main__":
    unittest.main()
