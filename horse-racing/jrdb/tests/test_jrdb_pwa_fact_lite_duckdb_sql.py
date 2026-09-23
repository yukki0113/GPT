import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FACT_LITE = ROOT / "horse-racing/jrdb/pwa/fact-lite.js"


class FactLiteSqliteSqlTest(unittest.TestCase):
    def test_dimension_axes_use_sqlite_labels_with_id_grouping(self) -> None:
        source = FACT_LITE.read_text(encoding="utf-8")
        self.assertIn('select: "s.name",', source)
        self.assertIn('group: "f.sire_id"', source)
        self.assertIn('select: "j.name",', source)
        self.assertIn('group: "f.jockey_id"', source)
        self.assertNotIn("ANY_VALUE(s.name)", source)
        self.assertNotIn("ANY_VALUE(j.name)", source)


if __name__ == "__main__":
    unittest.main()
