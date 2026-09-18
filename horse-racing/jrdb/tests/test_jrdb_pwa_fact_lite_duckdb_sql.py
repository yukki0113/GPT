import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FACT_LITE = ROOT / "horse-racing/jrdb/pwa/fact-lite.js"


class FactLiteDuckDbSqlTest(unittest.TestCase):
    def test_dimension_axes_keep_id_grouping_with_duckdb_safe_label(self) -> None:
        source = FACT_LITE.read_text(encoding="utf-8")
        self.assertIn('select: "ANY_VALUE(s.name)", group: "f.sire_id"', source)
        self.assertIn('select: "ANY_VALUE(j.name)", group: "f.jockey_id"', source)


if __name__ == "__main__":
    unittest.main()
