"""Regression tests for a full-pool cycle rollover without losing audit history."""

import copy
import unittest

from racenote_backtest_day_picker import (
    new_state,
    pick_days,
    release_selection,
    sync_state,
)


class PoolCycleRolloverTest(unittest.TestCase):
    """A new active cycle must preserve the prior draws as audit evidence."""

    @staticmethod
    def historical_row(cycle):
        """Build a Historical Warehouse inventory entry for a selected date."""
        return {
            "date": "2025-12-28",
            "file_name": "",
            "drive_file_id": "",
            "source_mode": "historical_warehouse",
            "source_reference": "jrdb_normalized_warehouse_v1_2010_2025_g20260921",
            "selection_cycle": cycle,
            "eligible": True,
            "exclusion_reason": None,
        }

    @staticmethod
    def paci_row(cycle):
        """Build an explicitly cycle-tagged daily PACI inventory entry."""
        return {
            "date": "2026-09-27",
            "file_name": "PACI260927.zip",
            "drive_file_id": "test-paci-file",
            "source_mode": "paci",
            "selection_cycle": cycle,
            "eligible": True,
            "exclusion_reason": None,
        }

    def test_rolled_over_historical_day_uses_archived_first_cycle(self):
        """An archived first-cycle draw unlocks a single second-cycle draw."""
        state = new_state([self.historical_row(1)])
        first = pick_days(
            state,
            n=1,
            seed="first-cycle",
            source_mode="historical_warehouse",
        )
        first_audit = copy.deepcopy(state["selections"])

        # The active inventory resets; the immutable audit list remains.
        state["days"] = [{
            **self.historical_row(2),
            "used": False,
            "used_at": None,
            "selection_id": None,
        }]

        second = pick_days(
            state,
            n=1,
            seed="second-cycle",
            source_mode="historical_warehouse",
            selection_cycle=2,
        )

        self.assertEqual(first_audit, state["selections"][:1])
        self.assertNotEqual(first["selection_id"], second["selection_id"])
        self.assertEqual(second["sources"][0]["selection_cycle"], 2)
        self.assertTrue(state["days"][0]["used"])

    def test_historical_cycle_two_without_first_draw_is_rejected(self):
        """Cycle two cannot be drawn with no prior first-cycle evidence."""
        state = new_state([self.historical_row(2)])

        with self.assertRaisesRegex(ValueError, "not enough unused eligible dates"):
            pick_days(
                state,
                n=1,
                seed="second-cycle",
                source_mode="historical_warehouse",
                selection_cycle=2,
            )

    def test_released_first_draw_does_not_unlock_second_cycle(self):
        """A released or invalidated first draw does not count as completed."""
        state = new_state([self.historical_row(1)])
        first = pick_days(
            state,
            n=1,
            seed="first-cycle",
            source_mode="historical_warehouse",
        )
        release_selection(state, first["selection_id"])

        state["days"] = [{
            **self.historical_row(2),
            "used": False,
            "used_at": None,
            "selection_id": None,
        }]

        with self.assertRaisesRegex(ValueError, "not enough unused eligible dates"):
            pick_days(
                state,
                n=1,
                seed="second-cycle",
                source_mode="historical_warehouse",
                selection_cycle=2,
            )

    def test_paci_explicit_second_cycle_survives_sync(self):
        """PACI rows retain their cycle and log it on the next reservation."""
        state = new_state([self.paci_row(2)])
        selected = pick_days(
            state,
            n=1,
            seed="paci-second-cycle",
            source_mode="paci",
            selection_cycle=2,
        )
        self.assertEqual(selected["sources"][0]["source_mode"], "paci")
        self.assertEqual(selected["sources"][0]["selection_cycle"], 2)

        sync_state(state, [self.paci_row(2)])
        self.assertEqual(state["days"][0]["selection_cycle"], 2)
        self.assertTrue(state["days"][0]["used"])

    def test_ineligible_paci_day_stays_out_of_regular_pool(self):
        """Known-exposed dates are not revived by an inventory rollover."""
        old = self.paci_row(1)
        old["eligible"] = False
        old["exclusion_reason"] = "known result exposure"
        state = new_state([old])

        with self.assertRaisesRegex(ValueError, "not enough unused eligible dates"):
            pick_days(state, n=1, seed="regular-picker")


if __name__ == "__main__":
    unittest.main()
