from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from jrdb_next_watch_rules import grade_matched_rules, human_summary, reason_groups


class NextWatchSharedRulesTest(unittest.TestCase):
    def test_tightened_s_contract(self) -> None:
        self.assertEqual(grade_matched_rules(["HV06"]), "S")
        self.assertEqual(grade_matched_rules(["HV13"]), "S")
        self.assertEqual(grade_matched_rules(["HV05", "HV07"]), "S")
        self.assertEqual(grade_matched_rules(["HV05", "HV11"]), "S")
        self.assertEqual(grade_matched_rules(["HV05", "HV12"]), "S")

    def test_hierarchical_duplicates_do_not_promote_s(self) -> None:
        self.assertEqual(grade_matched_rules(["HV01", "HV02"]), "A")
        self.assertEqual(grade_matched_rules(["HV03", "HV07"]), "A")

    def test_no_hidden_value_match_is_none(self) -> None:
        self.assertIsNone(grade_matched_rules([]))
        self.assertIsNone(grade_matched_rules(["P01", "P03"]))

    def test_reason_group_compression(self) -> None:
        groups = reason_groups(["HV01", "HV02", "HV03", "HV11"])
        self.assertEqual(groups, ["PERFORMANCE", "LAST3F", "OWN_HISTORY_IMPROVEMENT"])
        summary = human_summary(["HV06", "HV11"])
        self.assertIn("走破内容", summary)
        self.assertIn("近走比較", summary)


if __name__ == "__main__":
    unittest.main()
