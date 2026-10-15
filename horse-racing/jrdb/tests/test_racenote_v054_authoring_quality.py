"""Negative regression cases for the v0.5.4 authoring quality gate."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from racenote_v054_authoring_quality import inspect
from racenote_decision_core_v054 import (
    CONTRACT_REVISION,
    R2_CONTRACT_REVISION,
    validate_prose,
)


def core(race_no, generic=False):
    if generic:
        case = "4番は主線二頭に次ぐ能力・条件適性を持ち、連下圏で評価する。"
        rank = "11番を勝ち切り評価で最上位、12番を対抗とした。"
    else:
        case = f"4番は前走東京芝1600mで3着。差し脚の持続力から同距離を評価する。{race_no}"
        rank = "11番は直近IDM58と先行力が12番のIDM52を上回るため、11番を勝ち切りで優先する。"
    return {
        "venue": "東京", "race_no": race_no, "marks": [11, 12, 3, 4, 5],
        "mainline_cases": [{"horse_no": n, "case": case} for n in (11, 12, 4, 5)],
        "single_shot_case": {"horse_no": 3, "case": "3番は前走芝1800mで先行して4着、今回の距離短縮で粘り込みがある。"},
        "candidate_compression": {
            "ordinary_five": [11, 12, 4, 5, 3],
            "external_challenger_horse_no": 6, "decision": "KEEP_ORDINARY_FIVE",
            "reason": "6番は前走芝1800mで8着に対して3番は同距離で4着のため、通常五頭を維持する。",
            "external_challenger_case": "6番は前走芝1800mで8着、前残りの再現性には疑問が残る。"
        },
        "boundary_review": {"alternative_horse_no": 6,
            "reason": "6番は前走芝1800mで8着、一方3番は同距離で4着。後者の先行持続力を優先してKEEP。"},
        "role_assignment": {"honmei_horse_no": 11, "second_horse_no": 12,
            "honmei_win_case": "11番は直近東京芝1600mのIDM58と先行力で勝ち切りがある。",
            "second_case": "12番は東京芝1600mで2着、追い込みの安定性がある。",
            "ranking_reason": rank},
        "reader_facing_reason_authorship": {
            "mode": "MODEL_AUTHORED_PER_RACE",
            "programmatic_template": False,
            "basis": ["ranking_reason"],
        },
        "reader_facing_reason": ("11番は前走東京芝1600mでIDM58を記録し、先行から長く脚を使える。"
            "12番も同距離で2着した実績がある一方、直近IDMと位置取りの優位で11番を上に取る。"
            "3番は逃げる展開なら別の勝ち筋を持つ。")
    }


class GateTests(unittest.TestCase):
    def test_generic_incident_rejected(self):
        report = inspect([core(1, generic=True)])
        self.assertEqual(report["status"], "FAIL")
        self.assertGreater(report["generic_case_count"], 0)

    def test_day_wide_repetition_rejected(self):
        report = inspect([core(1), core(2)])
        self.assertEqual(report["status"], "FAIL")
        self.assertGreater(report["template_similarity_violations"], 0)

    def test_weak_boundary_rejected(self):
        obj = core(1)
        obj["boundary_review"]["reason"] = "6番は3番を明確に上回らないためKEEPとする。"
        self.assertEqual(inspect([obj])["boundary_specificity_pass"], 0)

    def test_weak_ranking_rejected(self):
        obj = core(1)
        obj["role_assignment"]["ranking_reason"] = "11番を最上位、12番を対抗とした。"
        self.assertEqual(inspect([obj])["ranking_comparison_specificity_pass"], 0)


    def test_r3_free_form_prose_does_not_require_mark_checklist(self):
        obj = core(1)
        obj["reader_facing_reason"] = (
            "前走の持続力が今回の条件に最もつながる。位置を取りに行ける強みを素直に評価したい。"
        )
        obj["reader_facing_reason_authorship"]["basis"] = ["honmei_win_case"]
        validate_prose(obj, contract_revision=CONTRACT_REVISION)
        report = inspect([obj])
        self.assertEqual(report["reader_facing_reason_safety_pass"], 1)
        self.assertEqual(report["status"], "PASS")

    def test_r2_legacy_still_requires_honmei_and_second_mentions(self):
        obj = core(1)
        obj["reader_facing_reason"] = (
            "前走の持続力が今回の条件に最もつながる。位置を取りに行ける強みを素直に評価したい。"
        )
        obj["reader_facing_reason_authorship"]["basis"] = [
            "honmei_win_case", "ranking_reason"
        ]
        with self.assertRaises(ValueError):
            validate_prose(obj, contract_revision=R2_CONTRACT_REVISION)

    def test_r3_known_fallback_phrase_rejected(self):
        obj = core(1)
        obj["reader_facing_reason"] = (
            "勝ち切る形を最も描きやすい。現条件へのつながりで評価する。"
        )
        with self.assertRaises(ValueError):
            validate_prose(obj, contract_revision=CONTRACT_REVISION)


if __name__ == "__main__":
    unittest.main()
