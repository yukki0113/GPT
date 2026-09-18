import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "horse-racing/jrdb/pwa/fact-lite-duckdb.js"
WORKFLOW = ROOT / ".github/workflows/jrdb_pwa_fact_lite_publish.yml"


class FactLiteDuckDbRuntimeContractTest(unittest.TestCase):
    def test_runtime_uses_single_thread_mvp_bundle_and_manifest_contract(self) -> None:
        source = RUNTIME.read_text(encoding="utf-8")
        self.assertIn('const FACT_DUCKDB_VERSION = "1.32.0"', source)
        self.assertIn('duckdb-mvp.wasm', source)
        self.assertIn('duckdb-browser-mvp.worker.js', source)
        self.assertIn('artifact_type: "jrdb_fact_lite"', source)
        self.assertIn('storage_format: "parquet"', source)
        self.assertIn('storage_version: "1"', source)
        self.assertIn('"fact_stats_entry"', source)
        self.assertIn('await database.registerFileURL', source)
        self.assertIn('CREATE OR REPLACE VIEW', source)

    def test_runtime_has_fail_closed_generation_cache_contract(self) -> None:
        source = RUNTIME.read_text(encoding="utf-8")
        self.assertIn('const FACT_PARQUET_METADATA = "parquet-metadata.json"', source)
        self.assertIn('generations/" + generationId', source)
        self.assertIn('download SHA-256不一致', source)
        self.assertIn('cache SHA-256不一致', source)
        self.assertIn('await database.registerFileBuffer', source)
        self.assertIn('await validateDuckDbCachedGeneration(cached)', source)
        self.assertIn('current_generation: candidate.generationId', source)

    def test_publish_workflow_vendors_exact_runtime_assets(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        base = "https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@1.32.0/dist/"
        for asset in (
            "duckdb-browser.mjs",
            "duckdb-browser-mvp.worker.js",
            "duckdb-mvp.wasm",
        ):
            self.assertIn(base + asset, workflow)
            self.assertIn(".pages/vendor/duckdb/" + asset, workflow)


if __name__ == "__main__":
    unittest.main()
