import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fetch_keibailuka_blog import classify_race  # noqa: E402
from fetch_keibailuka_historical import (  # noqa: E402
    iter_months,
    parse_month,
    parse_target_title,
)


class HistoricalHelpersTest(unittest.TestCase):
    def test_parse_target_title(self):
        parsed = parse_target_title(
            "2026/9/20 阪神 全レース中の強き不利馬達"
        )
        self.assertEqual(parsed, (date(2026, 9, 20), "阪神"))

    def test_non_target_title_is_ignored(self):
        self.assertIsNone(parse_target_title("2026/9/20 阪神 重賞予想"))

    def test_masked_cta_without_clown_marker_is_preserved(self):
        race = classify_race(
            "中山",
            12,
            "",
            ["前走は前に入られた時に引っ張る感じで。", "（noteにスキボタンを押すと馬名を表示）"],
        )
        self.assertEqual(race.status, "included")
        self.assertEqual(race.horse, "🤡")
        self.assertNotIn("noteにスキボタン", race.comment)

    def test_month_range_is_inclusive(self):
        months = iter_months(parse_month("2024-11"), parse_month("2025-02"))
        self.assertEqual(
            months,
            [
                date(2024, 11, 1),
                date(2024, 12, 1),
                date(2025, 1, 1),
                date(2025, 2, 1),
            ],
        )

    def test_month_range_rejects_more_than_12(self):
        with self.assertRaises(ValueError):
            iter_months(parse_month("2024-01"), parse_month("2025-01"))


if __name__ == "__main__":
    unittest.main()
