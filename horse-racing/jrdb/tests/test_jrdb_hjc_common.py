#!/usr/bin/env python3
"""Regression tests for JRDB HJC payout support in the Common Reader."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jrdb_raw import BODY_LENGTHS, RECORD_LENGTHS, Parser, split_fixed_records


# JRDB official HJC sample: 2024-09-29 中山1R.
# The published web sample trims trailing spaces; restore the fixed 442-byte body.
_SAMPLE_VISIBLE = (
    "0624490104    75000      000      004    23012    15015    44000      000      026   115000      000      00412    14200000       00000       00412     5300415    21301215    10000000       00000       00000       00000       00412    29200000       00000       00000       00000       00000       0041215    8550000000       0000000       0041215   39040 000000       0 000000       0 000000       0 000000       0 000000       0"
)


def sample_body() -> bytes:
    raw = _SAMPLE_VISIBLE.encode("ascii")
    if len(raw) > BODY_LENGTHS["HJC"]:
        raise AssertionError("official HJC sample exceeds configured body length")
    return raw + b" " * (BODY_LENGTHS["HJC"] - len(raw))


class HjcCommonReaderTests(unittest.TestCase):
    def test_record_length_contract(self) -> None:
        self.assertEqual(RECORD_LENGTHS["HJC"], 444)
        self.assertEqual(BODY_LENGTHS["HJC"], 442)
        body = sample_body()
        self.assertEqual(len(body), 442)
        records = split_fixed_records(body + b"\r\n", "HJC")
        self.assertEqual(len(records), 1)
        self.assertEqual(len(records[0]), 444)

    def test_official_sample_core_payouts(self) -> None:
        parsed = Parser().hjc(sample_body())
        self.assertEqual(parsed["race_key_raw"], "06244901")

        self.assertEqual(parsed["win"][0]["numbers"], [4])
        self.assertEqual(parsed["win"][0]["payout"], 750)

        self.assertEqual(parsed["quinella"][0]["numbers"], [4, 12])
        self.assertEqual(parsed["quinella"][0]["combination_raw"], "0412")
        self.assertEqual(parsed["quinella"][0]["payout"], 1420)

        self.assertEqual(parsed["trio"][0]["numbers"], [4, 12, 15])
        self.assertEqual(parsed["trio"][0]["combination_raw"], "041215")
        self.assertEqual(parsed["trio"][0]["payout"], 8550)

        self.assertEqual(parsed["trifecta"][0]["numbers"], [4, 12, 15])
        self.assertEqual(parsed["trifecta"][0]["combination_raw"], "041215")
        self.assertEqual(parsed["trifecta"][0]["payout"], 39040)

    def test_fixed_slot_counts_preserve_dead_heat_capacity(self) -> None:
        parsed = Parser().hjc(sample_body())
        self.assertEqual(len(parsed["win"]), 3)
        self.assertEqual(len(parsed["place"]), 5)
        self.assertEqual(len(parsed["frame_quinella"]), 3)
        self.assertEqual(len(parsed["quinella"]), 3)
        self.assertEqual(len(parsed["wide"]), 7)
        self.assertEqual(len(parsed["exacta"]), 6)
        self.assertEqual(len(parsed["trio"]), 3)
        self.assertEqual(len(parsed["trifecta"]), 6)


if __name__ == "__main__":
    unittest.main()
