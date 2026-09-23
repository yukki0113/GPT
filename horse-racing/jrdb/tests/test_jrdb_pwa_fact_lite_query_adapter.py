import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FACT_LITE = ROOT / "horse-racing/jrdb/pwa/fact-lite.js"
V3 = ROOT / "horse-racing/jrdb/pwa/fact-lite-v3.js"
HTML = ROOT / "horse-racing/jrdb/pwa/fact-lite.html"


class FactLiteSqliteQueryContractTest(unittest.TestCase):
    def test_ui_queries_sqlite_database_directly(self) -> None:
        source = FACT_LITE.read_text(encoding="utf-8")
        self.assertIn("const statement = factDb.prepare(query.sql)", source)
        self.assertIn("statement.bind(query.params)", source)
        self.assertIn("statement.getAsObject()", source)
        self.assertNotIn("factQueryAdapter.query", source)

    def test_win5_capability_uses_sqlite_schema(self) -> None:
        source = V3.read_text(encoding="utf-8")
        self.assertIn("PRAGMA table_info", source)
        self.assertIn("f.win5_leg_no IS NOT NULL", source)
        self.assertIn('new Set(["0.2", "0.3"])', source)

    def test_query_adapter_is_not_loaded_by_fact_lite_page(self) -> None:
        html = HTML.read_text(encoding="utf-8")
        self.assertNotIn("fact-lite-query-adapter.js", html)
        self.assertNotIn("fact-lite-duckdb.js", html)


if __name__ == "__main__":
    unittest.main()
