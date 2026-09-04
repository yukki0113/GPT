from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eval_ocr import numeric_ocr  # noqa: E402
from eval_ocr.color_detector import COLOR_RANK_ORDER  # noqa: E402
from eval_ocr.validator import _validate_colors  # noqa: E402


class NumericOcrRegressionTests(unittest.TestCase):
    def _resolve(self, initial: int, reread: int):
        binary = np.full((80, 160), 255, dtype=np.uint8)
        with (
            patch.object(numeric_ocr, "_digit_components", return_value=[(1, 1, 10, 40), (20, 1, 10, 40)]),
            patch.object(numeric_ocr, "_ocr_by_digit_components", return_value=reread),
            patch.object(numeric_ocr, "_ocr_single_cell_candidates", return_value=[reread, reread]),
        ):
            return numeric_ocr._choose_value_with_audit(initial, binary, colored_fill=False)

    def test_0905_2_to_9_family_is_rechecked_and_repaired(self):
        for initial, expected in ((94, 24), (91, 21), (93, 23), (99, 29)):
            with self.subTest(initial=initial, expected=expected):
                value, audit = self._resolve(initial, expected)
                self.assertEqual(expected, value)
                self.assertTrue(audit["recheck_triggered"])
                self.assertIn("leading_2_or_9_ambiguity", audit["recheck_reason"])
                self.assertEqual("multi_ocr_vote", audit["resolution_method"])
                self.assertFalse(audit["requires_review"])

    def test_correct_90s_survives_when_rereads_confirm_it(self):
        value, audit = self._resolve(95, 95)
        self.assertEqual(95, value)
        self.assertEqual("recheck_confirmed", audit["resolution_method"])
        self.assertFalse(audit["requires_review"])


class ColorValidationRegressionTests(unittest.TestCase):
    def test_color_order_is_fixed_from_image_legend(self):
        self.assertEqual(("red", "blue", "orange", "green", "yellow"), COLOR_RANK_ORDER)
        observations = [
            {"venue": "阪神", "race_no": 1, "horse_no": 1, "color": "red", "eval": 60},
            {"venue": "阪神", "race_no": 1, "horse_no": 2, "color": "blue", "eval": 50},
            {"venue": "阪神", "race_no": 1, "horse_no": 3, "color": "orange", "eval": 40},
            {"venue": "阪神", "race_no": 1, "horse_no": 4, "color": "green", "eval": 30},
            {"venue": "阪神", "race_no": 1, "horse_no": 5, "color": "yellow", "eval": 20},
        ]
        result = _validate_colors(observations)
        self.assertEqual("master_eval_image_legend_fixed", result["color_order_source"])
        self.assertEqual([], result["order_violations"])

    def test_lower_rank_color_cannot_hide_a_94_misread(self):
        observations = [
            {"venue": "札幌", "race_no": 5, "horse_no": 3, "color": "red", "eval": 27},
            {"venue": "札幌", "race_no": 5, "horse_no": 7, "color": "red", "eval": 27},
            {"venue": "札幌", "race_no": 5, "horse_no": 1, "color": "orange", "eval": 24},
            {"venue": "札幌", "race_no": 5, "horse_no": 12, "color": "orange", "eval": 24},
            {"venue": "札幌", "race_no": 5, "horse_no": 14, "color": "orange", "eval": 94},
        ]
        result = _validate_colors(observations)
        self.assertTrue(result["order_violations"])
        self.assertTrue(result["inconsistent_same_color_groups"])

    def test_uncolored_high_value_is_detected(self):
        observations = [
            {"venue": "阪神", "race_no": 6, "horse_no": 1, "color": "red", "eval": 50},
            {"venue": "阪神", "race_no": 6, "horse_no": 2, "color": "blue", "eval": 40},
            {"venue": "阪神", "race_no": 6, "horse_no": 13, "color": None, "eval": 91},
        ]
        result = _validate_colors(observations)
        self.assertEqual(1, len(result["top_set_violations"]))

    def test_boundary_tie_may_be_partly_uncolored(self):
        observations = [
            {"venue": "中山", "race_no": 1, "horse_no": 1, "color": "red", "eval": 60},
            {"venue": "中山", "race_no": 1, "horse_no": 2, "color": "blue", "eval": 50},
            {"venue": "中山", "race_no": 1, "horse_no": 3, "color": "yellow", "eval": 40},
            {"venue": "中山", "race_no": 1, "horse_no": 4, "color": None, "eval": 40},
        ]
        result = _validate_colors(observations)
        self.assertEqual([], result["top_set_violations"])
        self.assertEqual([], result["order_violations"])

    def test_same_color_same_eval_is_normal_tie(self):
        observations = [
            {"venue": "中山", "race_no": 2, "horse_no": 1, "color": "red", "eval": 55},
            {"venue": "中山", "race_no": 2, "horse_no": 2, "color": "red", "eval": 55},
        ]
        result = _validate_colors(observations)
        self.assertEqual(1, len(result["tie_color_groups"]))
        self.assertEqual([], result["inconsistent_same_color_groups"])


if __name__ == "__main__":
    unittest.main()
