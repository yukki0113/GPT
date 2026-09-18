from __future__ import annotations

import unittest
from pathlib import Path


class FactLiteParquetWorkflowTest(unittest.TestCase):
    def test_publish_workflow_has_no_analysis_sqlite_input(self) -> None:
        root = Path(__file__).resolve().parents[3]
        workflow = (root / ".github/workflows/jrdb_pwa_fact_lite_publish.yml").read_text(encoding="utf-8")
        self.assertIn('required = ["analysis_parquet_bundle_file_id", "data_version"]', workflow)
        self.assertIn("--analysis-root .fact_publish/analysis-parquet", workflow)
        self.assertIn("source_analysis_generation", workflow)
        self.assertIn("analysis-current-parquet", workflow)
        self.assertNotIn("analysis-parquet/objects/fact_entry_result_lite/**/*.parquet", workflow)
        self.assertNotIn('required = ["drive_file_id", "source_filename", "data_version"]', workflow)
        self.assertNotIn("DRIVE_FILE_ID", workflow)
        self.assertNotIn("SOURCE_FILENAME", workflow)


if __name__ == "__main__":
    unittest.main()
