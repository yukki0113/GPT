import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PWA = ROOT / "horse-racing/jrdb/pwa"
WORKFLOW = ROOT / ".github/workflows/jrdb_pwa_pages.yml"


class FactLiteSqliteDeliveryTest(unittest.TestCase):
    def test_fact_lite_uses_sqljs_and_opfs_sqlite(self) -> None:
        source = (PWA / "fact-lite.js").read_text(encoding="utf-8")
        self.assertIn('FACT_RUNTIME_CONFIG.sqlJsUrl || "./vendor/sql-wasm.js"', source)
        self.assertIn('FACT_RUNTIME_CONFIG.factManifestUrl || "./data/fact-lite/manifest.json"', source)
        self.assertIn('const FACT_CURRENT = "current.sqlite"', source)
        self.assertIn('const FACT_LEGACY_PREVIOUS = "previous.sqlite"', source)
        self.assertIn('const FACT_INCOMING = "incoming.sqlite"', source)
        self.assertIn("await loadFactSqlJs()", source)
        self.assertIn("new FACT_SQL.Database(bytes)", source)
        self.assertIn("PRAGMA integrity_check", source)
        self.assertNotIn("runtime.restoreCache", source)
        self.assertNotIn("createDuckDb(database)", source)

    def test_pages_distributes_current_fact_lite_sqlite(self) -> None:
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("FACT_RELEASE_TAG: jrdb-pwa-fact-lite-current", source)
        self.assertIn('--pattern "jrdb_pwa_fact_lite.sqlite"', source)
        self.assertIn("download_release_assets \"$FACT_RELEASE_TAG\" .pages/data/fact-lite", source)
        self.assertIn("Current Fact Lite release added to Pages artifact.", source)
        self.assertIn("Fact Lite SQLite SHA-256 mismatch", source)
        self.assertNotIn("FACT_PARQUET_RELEASE_TAG", source)
        self.assertNotIn("fact-lite-parquet", source)
        self.assertNotIn("duckdb-wasm", source)

    def test_shell_loads_only_sqlite_fact_lite_runtime(self) -> None:
        html = (PWA / "fact-lite.html").read_text(encoding="utf-8")
        worker = (PWA / "service-worker.js").read_text(encoding="utf-8")
        self.assertIn("./fact-lite.js?v=24", html)
        self.assertIn("./fact-lite-v3.js?v=4", html)
        self.assertIn("./fact-lite-sort.js?v=20", html)
        self.assertNotIn("fact-lite-duckdb.js", html)
        self.assertNotIn("fact-lite-query-adapter.js", html)
        self.assertNotIn("apache-arrow", html)
        self.assertIn('CACHE_NAME = "jrdb-pwa-shell-v72"', worker)
        self.assertIn("./vendor/sql-wasm.js", worker)
        self.assertIn("./vendor/sql-wasm.wasm", worker)
        self.assertNotIn("./vendor/duckdb/", worker)
        self.assertNotIn("fact-lite-duckdb.js", worker)


if __name__ == "__main__":
    unittest.main()
