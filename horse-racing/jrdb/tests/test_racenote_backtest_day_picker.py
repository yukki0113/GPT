import unittest
from racenote_backtest_day_picker import new_state, pick_days, release_selection, summary, sync_state

class TestRaceNoteBacktestDayPicker(unittest.TestCase):
    def rows(self, *dates):
        return [{"date": d, "file_name": f"PACI{d[2:].replace('-', '')}.zip", "drive_file_id": f"id-{d}"} for d in dates]

    def test_pick_marks_used_and_is_reproducible(self):
        rows = self.rows("2026-01-04", "2026-01-05", "2026-01-10", "2026-01-11")
        a = new_state(rows)
        b = new_state(rows)
        self.assertEqual(pick_days(a, 2, "fixed-seed")["dates"], pick_days(b, 2, "fixed-seed")["dates"])
        self.assertEqual(summary(a)["used_days"], 2)

    def test_sync_preserves_used_and_adds_new_date(self):
        state = new_state(self.rows("2026-01-04", "2026-01-05"))
        used_date = pick_days(state, 1, "seed")["dates"][0]
        sync_state(state, self.rows("2026-01-04", "2026-01-05", "2026-01-10"))
        by_date = {row["date"]: row for row in state["days"]}
        self.assertTrue(by_date[used_date]["used"])
        self.assertFalse(by_date["2026-01-10"]["used"])

    def test_release_returns_dates_to_pool(self):
        state = new_state(self.rows("2026-01-04", "2026-01-05"))
        record = pick_days(state, 2, "seed")
        self.assertEqual(release_selection(state, record["selection_id"]), 2)
        self.assertEqual(summary(state)["unused_days"], 2)

    def test_cannot_over_pick(self):
        state = new_state(self.rows("2026-01-04"))
        with self.assertRaises(ValueError):
            pick_days(state, 2, "seed")

if __name__ == "__main__":
    unittest.main()
