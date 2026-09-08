#!/usr/bin/env python3
"""Regression tests for deterministic RaceNote/HJC settlement."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import settle_racenote_backtest as subject


def put(record: bytearray, start: int, width: int, value: str | int) -> None:
    text = str(value).rjust(width)
    if len(text) != width:
        raise AssertionError((start, width, value))
    record[start - 1 : start - 1 + width] = text.encode("ascii")


def make_record(key: str) -> bytes:
    body = bytearray(b" " * 442)
    put(body, 1, 8, key)
    put(body, 9, 2, 10); put(body, 11, 7, 190)
    put(body, 108, 2, 6); put(body, 110, 2, 10); put(body, 112, 8, 630)
    put(body, 300, 2, 6); put(body, 302, 2, 8); put(body, 304, 2, 10); put(body, 306, 8, 1500)
    return bytes(body)


def prediction_payload() -> dict:
    return {
        "logic_profile": "provisional_handoff_v0.1_unweighted",
        "status": "FROZEN_BEFORE_RESULT_LOOKUP",
        "races": [{
            "date": "2025-08-24", "venue": "中京", "race_no": 9,
            "prediction": {"marks": [
                {"mark": "◎", "horse_no": 10}, {"mark": "○", "horse_no": 6},
                {"mark": "▲", "horse_no": 8}, {"mark": "△", "horse_no": 7},
                {"mark": "△", "horse_no": 1}, {"mark": "△", "horse_no": 12},
            ]},
        }],
    }


class SettlementTests(unittest.TestCase):
    def test_six_ticket_construction_uses_first_two_deltas(self) -> None:
        trio = [ticket.horses for ticket in subject.build_tickets(prediction_payload()["races"][0]) if ticket.group == "3"]
        self.assertEqual(len(trio), 6)
        self.assertIn((6, 8, 10), trio)
        self.assertIn((1, 7, 10), trio)
        self.assertFalse(any(12 in ticket for ticket in trio))

    def test_one_race_settlement_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prediction = root / "prediction.json"
            prediction.write_text(json.dumps(prediction_payload(), ensure_ascii=False), encoding="utf-8")
            hjc = root / "HJC_2025.zip"
            with zipfile.ZipFile(hjc, "w") as zf:
                zf.writestr("HJC250824.txt", make_record("07254209") + b"\r\n")
            result = subject.settle_prediction_file(prediction, hjc)
            race = result["races"][0]
            self.assertEqual(race["group_payout_jpy"], {"1": 190, "2": 630, "3": 1500})
            self.assertEqual(result["summary"]["1+2+3"]["payout_jpy"], 2320)
            self.assertEqual(result["summary"]["1+2+3"]["investment_jpy"], 900)

    def test_duplicate_winning_slots_are_preserved_and_summed(self) -> None:
        parsed = {"win": [{"numbers": [10], "payout": 100}, {"numbers": [10], "payout": 200}], "quinella": [], "trio": []}
        self.assertEqual(subject.payout_for_ticket(subject.Ticket("1", "win", (10,)), parsed), 300)

    def test_missing_second_delta_fails_closed(self) -> None:
        race = prediction_payload()["races"][0]
        race["prediction"]["marks"] = race["prediction"]["marks"][:4]
        with self.assertRaisesRegex(ValueError, "at least two"):
            subject.build_tickets(race)


if __name__ == "__main__":
    unittest.main()
