import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
HTML = ROOT / "horse-racing/jrdb/pwa/fact-lite.html"
RUNTIME = ROOT / "horse-racing/jrdb/pwa/fact-lite-duckdb.js"
STATUS = ROOT / "horse-racing/jrdb/pwa/fact-lite-parquet-status.mjs"
SERVICE_WORKER = ROOT / "horse-racing/jrdb/pwa/service-worker.js"


class FactLiteParquetStatusTest(unittest.TestCase):
    def test_diagnostic_ui_exposes_cache_engine_remote_and_actions(self) -> None:
        html = HTML.read_text(encoding="utf-8")
        for identifier in (
            "fact-parquet-cache-status",
            "fact-parquet-engine-status",
            "fact-parquet-remote-status",
            "fact-btn-parquet-check",
            "fact-btn-parquet-sync",
            "fact-parquet-progress",
        ):
            self.assertIn(identifier, html)

    def test_status_controller_reports_validation_and_offline_reuse(self) -> None:
        source = STATUS.read_text(encoding="utf-8")
        self.assertIn("Parquet manifest確認中", source)
        self.assertIn("SHA-256検証中", source)
        self.assertIn("DuckDB初期化・schema/行数検証中", source)
        self.assertIn("オフラインで検証済みローカルcacheを利用できます", source)
        self.assertIn("既存cacheは利用可能です", source)
        self.assertIn("FactLiteDuckDb.synchronizeCache(fetch, reportStage)", source)

    def test_runtime_emits_progress_without_changing_cache_pointer_order(self) -> None:
        source = RUNTIME.read_text(encoding="utf-8")
        self.assertIn('onProgress("manifest")', source)
        self.assertIn('onProgress("download", table)', source)
        self.assertIn('onProgress("duckdb")', source)
        self.assertLess(
            source.index("await validateDuckDbCachedGeneration(cached)"),
            source.index("current_generation: candidate.generationId"),
        )

    def test_service_worker_includes_status_controller(self) -> None:
        worker = SERVICE_WORKER.read_text(encoding="utf-8")
        self.assertIn('"./fact-lite-parquet-status.mjs?v=1"', worker)
        self.assertIn('jrdb-pwa-shell-v48', worker)


if __name__ == "__main__":
    unittest.main()
