from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


class FactLiteSqlitePublishWorkflowTest(unittest.TestCase):
    def test_publisher_uses_current_analysis_manifest_and_sqlite_only_release(self) -> None:
        workflow = (ROOT / ".github/workflows/jrdb_pwa_fact_lite_publish.yml").read_text(encoding="utf-8")
        self.assertIn("Analysis Parquet current manifest has no partitions", workflow)
        self.assertIn("analysis-current-parquet", workflow)
        self.assertIn("build_jrdb_pwa_fact_lite.py", workflow)
        self.assertIn("jrdb_pwa_fact_lite.sqlite", workflow)
        self.assertIn("meta_pwa_fact_build", workflow)
        self.assertIn("PRAGMA integrity_check", workflow)
        self.assertNotIn("build_jrdb_pwa_fact_lite_dual.py", workflow)
        self.assertNotIn("audit_jrdb_pwa_fact_lite_dual.py", workflow)
        self.assertNotIn("FACT_PARQUET_RELEASE_TAG", workflow)
        self.assertNotIn("actions/deploy-pages", workflow)

    def test_full_pages_follows_successful_fact_lite_publish(self) -> None:
        workflow = (ROOT / ".github/workflows/jrdb_pwa_pages.yml").read_text(encoding="utf-8")
        self.assertIn('"JRDB PWA Fact Lite Publish"', workflow)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", workflow)
        self.assertIn("Fact Lite SQLite SHA-256 mismatch", workflow)
        self.assertIn("download_release_assets", workflow)
        self.assertIn("sleep $((attempt * 10))", workflow)
        self.assertNotIn("FACT_PARQUET_RELEASE_TAG", workflow)
        self.assertNotIn("fact-lite-parquet", workflow)


if __name__ == "__main__":
    unittest.main()
