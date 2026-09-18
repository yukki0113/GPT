import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PWA = ROOT / "horse-racing/jrdb/pwa"
WORKFLOW = ROOT / ".github/workflows/jrdb_pwa_pages.yml"


class FactLiteParquetCutoverTest(unittest.TestCase):
    def test_fact_lite_uses_only_verified_parquet_duckdb_path(self) -> None:
        source = (PWA / "fact-lite.js").read_text(encoding="utf-8")
        self.assertIn("runtime.restoreCache(factProgress)", source)
        self.assertIn("runtime.synchronizeCache(fetch, factProgress)", source)
        self.assertIn("createDuckDb(database)", source)
        self.assertNotIn("initSqlJs", source)
        self.assertNotIn("new SQL.Database", source)
        self.assertNotIn("current.sqlite", source)
        self.assertNotIn("data/fact-lite/", source)

    def test_pages_requires_parquet_and_never_downloads_fact_lite_sqlite(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('if ! gh release view "$FACT_PARQUET_RELEASE_TAG"', source)
        self.assertNotIn("FACT_RELEASE_TAG", source)
        self.assertNotIn('--pattern "jrdb_pwa_fact_lite.sqlite"', source)
        self.assertIn(".pages/data/fact-lite-parquet/current.json", source)
        self.assertIn("test ! -e .pages/data/fact-lite/jrdb_pwa_fact_lite.sqlite", source)
        self.assertIn("Stats Mart still uses sql.js", source)
        self.assertIn("@duckdb/duckdb-wasm@1.32.0 apache-arrow@17.0.0", source)
        self.assertIn(".pages/vendor/duckdb/duckdb-mvp.wasm", source)
        self.assertIn(".pages/vendor/duckdb/apache-arrow.umd.js", source)

    def test_shell_has_only_current_fact_lite_runtime_assets(self) -> None:
        html = (PWA / "fact-lite.html").read_text(encoding="utf-8")
        worker = (PWA / "service-worker.js").read_text(encoding="utf-8")
        self.assertIn("./fact-lite.js?v=19", html)
        self.assertIn("./fact-lite-v3.js?v=3", html)
        self.assertIn("./fact-lite-sort.js?v=19", html)
        self.assertIn('"apache-arrow":"./fact-lite-arrow-bridge.mjs"', html)
        self.assertIn("./vendor/duckdb/apache-arrow.umd.js", html)
        self.assertNotIn("fact-lite-parquet-status", html)
        self.assertIn('CACHE_NAME = "jrdb-pwa-shell-v54"', worker)
        self.assertIn("./vendor/duckdb/apache-arrow.umd.js", worker)
        self.assertNotIn("fact-lite-parquet-status", worker)


if __name__ == "__main__":
    unittest.main()
