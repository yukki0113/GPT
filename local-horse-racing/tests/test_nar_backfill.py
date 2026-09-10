from __future__ import annotations

import unittest

from nar.download.backfill import month_range, parse_ym


class NarBackfillTests(unittest.TestCase):
    def test_parse_ym(self) -> None:
        self.assertEqual(parse_ym("2016-01"), (2016, 1))
        with self.assertRaises(ValueError):
            parse_ym("2016-13")

    def test_month_range_crosses_year(self) -> None:
        self.assertEqual(
            month_range("2025-11", "2026-02"),
            [(2025, 11), (2025, 12), (2026, 1), (2026, 2)],
        )

    def test_month_range_rejects_reverse(self) -> None:
        with self.assertRaises(ValueError):
            month_range("2026-02", "2025-11")


if __name__ == "__main__":
    unittest.main()
