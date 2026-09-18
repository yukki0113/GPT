import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FACT_LITE = ROOT / "horse-racing/jrdb/pwa/fact-lite.js"
V3 = ROOT / "horse-racing/jrdb/pwa/fact-lite-v3.js"
ADAPTER = ROOT / "horse-racing/jrdb/pwa/fact-lite-query-adapter.js"


class FactLiteQueryAdapterContractTest(unittest.TestCase):
    def test_ui_uses_adapter_for_aggregation_and_capabilities(self) -> None:
        source = FACT_LITE.read_text(encoding="utf-8")
        self.assertIn("let factQueryAdapter = null", source)
        self.assertIn("await factQueryAdapter.query(query.sql, query.params)", source)
        self.assertIn("await queryAdapter.tableColumns(\"fact_stats_entry\")", source)
        self.assertNotIn("factDb.prepare(query.sql)", source)

    def test_win5_capability_uses_adapter_not_pragma(self) -> None:
        source = V3.read_text(encoding="utf-8")
        self.assertIn("return factQueryAdapterFor(adapter).tableColumns(tableName)", source)
        self.assertNotIn("PRAGMA table_info", source)
        self.assertNotIn("createSqlJs", source)
        self.assertIn("f.win5_leg_no IS NOT NULL", source)

    def test_adapter_provides_sqlite_and_duckdb_implementations(self) -> None:
        source = ADAPTER.read_text(encoding="utf-8")
        self.assertIn("createSqlJsFactQueryAdapter", source)
        self.assertIn("createDuckDbFactQueryAdapter", source)
        self.assertIn("information_schema.columns", source)
        self.assertIn("statement.query.apply(statement, params || [])", source)


if __name__ == "__main__":
    unittest.main()
