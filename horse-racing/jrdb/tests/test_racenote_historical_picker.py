"""Historical picker cycles preserve first-blind history and source identity."""
import unittest

from racenote_backtest_day_picker import new_state, pick_days, sync_state


def row(cycle):
    return {"date": "2025-12-28", "source_mode": "historical_warehouse",
            "source_reference": "jrdb_normalized_warehouse_v1_2010_2025_g20260921",
            "selection_cycle": cycle, "eligible": True}


class HistoricalPickerTest(unittest.TestCase):
    def test_second_cycle_keeps_first_cycle_used(self):
        state = new_state([row(1)])
        first = pick_days(state, 1, seed="first", source_mode="historical_warehouse",
                          selection_cycle=1)
        self.assertEqual(first["sources"][0]["selection_cycle"], 1)
        sync_state(state, [row(2)])
        self.assertEqual(len(state["days"]), 2)
        self.assertTrue(next(x for x in state["days"] if x["selection_cycle"] == 1)["used"])
        second = pick_days(state, 1, seed="second", source_mode="historical_warehouse",
                           selection_cycle=2)
        self.assertEqual(second["sources"][0]["selection_cycle"], 2)
        self.assertNotEqual(first["selection_id"], second["selection_id"])

    def test_historical_inventory_requires_reference(self):
        with self.assertRaisesRegex(ValueError, "source_reference"):
            new_state([{**row(1), "source_reference": ""}])

    def test_second_cycle_requires_used_first_cycle(self):
        state = new_state([row(1), row(2)])
        with self.assertRaisesRegex(ValueError, "not enough unused eligible dates"):
            pick_days(state, 1, source_mode="historical_warehouse",
                      selection_cycle=2)


if __name__ == "__main__":
    unittest.main()
