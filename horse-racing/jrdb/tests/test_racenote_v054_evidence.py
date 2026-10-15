from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jrdb_raw import Parser
from racenote_v054_evidence import (
    decode_reference_runs, historical_lap_contexts, kyi_hidden_value_context,
)
from racenote_decision_core_v054 import validate_prose


class FakeLapReader:
    def get_race_contexts(self, keys):
        rows = {
            "PAST": {
                "race": {"race_date": "2025-01-01"},
                "shape": {"early_late_delta_sec": -1.2},
                "coverage": {"status": "FULL"},
                "provenance": {"archive": "test"},
                "policy": {"leader_based": True},
            },
            "TODAY": {
                "race": {"race_date": "2025-07-12"},
                "coverage": {"status": "FULL"},
            },
            "FUTURE": {
                "race": {"race_date": "2025-07-13"},
                "coverage": {"status": "FULL"},
            },
            "EMPTY": {
                "race": {"race_date": "2025-03-01"},
                "coverage": {"status": "NO_LAPS"},
            },
        }
        return {key: rows.get(key) for key in keys}


class V054EvidenceTest(unittest.TestCase):
    def test_kyi_hidden_fields_offsets_are_neutral(self):
        raw = bytearray(b" " * 1022)
        def put(pos, value):
            raw[pos - 1:pos - 1 + len(value)] = value.encode("ascii")
        put(528, "31")
        put(530, "12345")
        put(535, "061")
        put(538, "1")
        put(540, "A1")
        kyi = Parser().kyi(bytes(raw))
        self.assertEqual(kyi["reference_previous_raw"], "31")
        self.assertEqual(kyi["reference_jockey_code"], "12345")
        self.assertEqual(kyi["ticket_index"], 61)
        self.assertEqual(kyi["ticket_mark"], "1")
        self.assertEqual(kyi["longshot_type"], "A1")

    def test_reference_digit_31_resolves_third_and_first(self):
        kyi = {
            "reference_previous_raw": "31",
            "previous": [
                {"race_key_raw": f"R{i}", "result_key": f"K{i}"}
                for i in range(1, 6)
            ],
        }
        result = decode_reference_runs(kyi)
        self.assertEqual(result["primary"]["run_back"], 3)
        self.assertEqual(result["primary"]["race_key"], "R3")
        self.assertEqual(result["secondary"]["run_back"], 1)
        self.assertEqual(result["secondary"]["race_key"], "R1")
        self.assertFalse(kyi_hidden_value_context(kyi)["policy"]["additive_score"])

    def test_invalid_or_unresolved_reference_does_not_guess(self):
        self.assertEqual(decode_reference_runs({"reference_previous_raw": "90"})["status"], "PARTIAL_OR_INVALID")
        self.assertEqual(decode_reference_runs({"reference_previous_raw": "3", "previous": []})["primary"]["status"], "UNRESOLVED")

    def test_lap_reader_excludes_same_day_and_future(self):
        result = historical_lap_contexts(
            ["PAST", "TODAY", "FUTURE", "EMPTY", "MISSING"],
            target_date="2025-07-12", race_lap_reader=FakeLapReader(),
        )
        self.assertEqual(result["PAST"]["status"], "AVAILABLE")
        self.assertEqual(result["TODAY"]["status"], "AS_OF_EXCLUDED")
        self.assertEqual(result["FUTURE"]["status"], "AS_OF_EXCLUDED")
        self.assertEqual(result["EMPTY"]["status"], "NO_LAPS")
        self.assertEqual(result["MISSING"]["status"], "MISSING")

    def test_newspaper_quality_guard(self):
        marks = [3, 13, 4, 2, 7]
        good = "◎3はクラス上位級の走りを繰り返し、調教も上向き。○13も能力上位だが、現条件での勝ち切り再現性では3を上に取る。▲4は先行残りの別筋。"
        validate_prose({"marks": marks, "reader_facing_reason": good})
        with self.assertRaisesRegex(ValueError, "internal/template"):
            validate_prose({"marks": marks, "reader_facing_reason": "sealed Readerを全馬比較し、通常五頭を先に固定。◎3・○13を選択。▲4は異なる勝ち筋を評価し、境界処理はr2既定どおり維持した。"})


if __name__ == "__main__":
    unittest.main()
