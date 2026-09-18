from __future__ import annotations

import unittest
from pathlib import Path


class PostRaceParquetDryRunWorkflowTest(unittest.TestCase):
    def test_dry_run_never_promotes_or_publishes_downstream(self) -> None:
        root = Path(__file__).resolve().parents[3]
        workflow = (root / ".github/workflows/jrdb_post_race_parquet_dry_run_issue.yml").read_text(encoding="utf-8")
        self.assertIn("[JRDB_POST_RACE_PARQUET_DRY_RUN]", workflow)
        self.assertIn("run_jrdb_analysis_post_race_incremental.py", workflow)
        self.assertIn("build_jrdb_analysis_post_race_parquet_candidate.py", workflow)
        self.assertIn("non-promoted candidate only", workflow)
        self.assertIn("if-no-files-found: error", workflow)
        self.assertIn(".postrace/handoff", workflow)
        self.assertNotIn("publish_jrdb_analysis_parquet_drive_generation.py", workflow)
        self.assertNotIn("publish_jrdb_fact_lite_parquet.py", workflow)


if __name__ == "__main__":
    unittest.main()
