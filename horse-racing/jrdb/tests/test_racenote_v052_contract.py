from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import racenote_decision_core_v052 as v052


def reader(count: int = 7) -> dict:
    return {
        "race": {"venue": "東京", "race_no": 1},
        "horses": [{"basic": {"horse_no": n}} for n in range(1, count + 1)],
    }


def core() -> dict:
    return {
        "venue": "東京",
        "race_no": 1,
        "race_model": "通常評価で五頭を先に守り、その集合内では勝ち切り経路を優先して印順を再評価するレース。",
        "marks": [4, 1, 3, 2, 5],
        "mainline_cases": [
            {"horse_no": 4, "case": "主導権を取った時の勝ち切り経路が最も明確で◎に値する。"},
            {"horse_no": 1, "case": "通常能力と再現性が高く○として主線に残す。"},
            {"horse_no": 2, "case": "通常支持として五頭内に残す根拠が十分にある。"},
            {"horse_no": 5, "case": "境界比較でも支持できる通常候補として残す。"},
        ],
        "single_shot_case": {
            "horse_no": 3,
            "case": "通常順位とは別の展開依存の勝ち筋があり、外部▲として採用する。",
        },
        "boundary_review": {
            "alternative_horse_no": 6,
            "reason": "通常五頭の末尾5と外部挑戦3を比較し、非対称な勝ち筋を優先して3を採用する。",
        },
        "candidate_compression": {
            "ordinary_five": [1, 4, 2, 5, 6],
            "external_challenger_horse_no": 3,
            "external_challenger_case": "通常順位の六番手ではなく、展開が振れた時に勝ち切る独立ルートを持つ。",
            "excluded_horse_no": 6,
            "decision": "ADMIT_CHALLENGER",
            "reason": "候補集合の◎4・○1を守りながら、通常末尾6より3の非対称な勝ち筋を優先する。",
        },
        "role_assignment": {
            "honmei_horse_no": 4,
            "second_horse_no": 1,
            "honmei_win_case": "通常順位では1が上でも、4が主導権を取る形の方が実際の勝ち切り経路として明瞭である。",
            "second_case": "1は能力と再現性が高く、勝ち筋の次位として○に残す。",
            "honmei_selection_mode": "WIN_FIRST_NOT_PLACE_FIRST",
            "shot_selection_mode": "ASYMMETRIC_PAYOUT_ROUTE_NOT_ORDINARY_RANK",
            "ranking_reason": "複勝圏の安全性ではなく勝率側を優先し、ordinary rank 2の4を◎へ再順位付けした。",
        },
        "rrdb_refs": [],
        "reader_facing_reason": "通常候補五頭を先に確保し、その中では4の勝ち切り経路を最重視して◎へ再順位付けする。外部3は別展開の勝ち筋として▲に採用し、6を押し出す。",
    }


class V052DecisionCoreTest(unittest.TestCase):
    def test_aggressive_honmei_can_differ_from_ordinary_rank_one(self) -> None:
        v052.validate_core(core(), reader())

    def test_honmei_must_stay_inside_ordinary_five(self) -> None:
        changed = copy.deepcopy(core())
        changed["role_assignment"]["honmei_horse_no"] = 3
        changed["marks"][0] = 3
        changed["marks"][2] = 4
        changed["single_shot_case"]["horse_no"] = 4
        with self.assertRaisesRegex(ValueError, "ordinary-five"):
            v052.validate_core(changed, reader())

    def test_challenger_cannot_displace_audited_honmei(self) -> None:
        changed = copy.deepcopy(core())
        changed["candidate_compression"]["excluded_horse_no"] = 4
        changed["marks"] = [4, 1, 3, 2, 5]
        with self.assertRaisesRegex(ValueError, "cannot displace"):
            v052.validate_core(changed, reader())

    def test_keep_ordinary_five_allows_internal_shot(self) -> None:
        changed = copy.deepcopy(core())
        changed["marks"] = [4, 1, 2, 5, 6]
        changed["single_shot_case"] = {
            "horse_no": 2,
            "case": "通常五頭の中では2が最も非対称な勝ち筋を持つため▲へ回す。",
        }
        changed["mainline_cases"] = [
            {"horse_no": 4, "case": "勝ち切り経路が最も明確で◎として評価する。"},
            {"horse_no": 1, "case": "能力と再現性から○として主線に残す。"},
            {"horse_no": 5, "case": "通常支持として相手本線に残す根拠がある。"},
            {"horse_no": 6, "case": "五頭境界でも残す通常根拠が十分にある。"},
        ]
        changed["boundary_review"] = {
            "alternative_horse_no": 3,
            "reason": "外部3も比較したが、通常五頭を崩すほどの優位はない。",
        }
        changed["candidate_compression"]["excluded_horse_no"] = 3
        changed["candidate_compression"]["decision"] = "KEEP_ORDINARY_FIVE"
        changed["candidate_compression"]["reason"] = "外部3の別経路は認めるが、通常五頭の候補集合を崩すほどではないため維持する。"
        v052.validate_core(changed, reader())

    def test_exactly_five_runners(self) -> None:
        changed = copy.deepcopy(core())
        changed["marks"] = [4, 1, 2, 3, 5]
        changed["mainline_cases"] = [
            {"horse_no": 4, "case": "勝ち切り経路が最も明確で◎として評価する。"},
            {"horse_no": 1, "case": "能力と再現性から○として主線に残す。"},
            {"horse_no": 3, "case": "通常支持として相手本線に残す根拠がある。"},
            {"horse_no": 5, "case": "五頭立てでも支持できる通常根拠がある。"},
        ]
        changed["single_shot_case"] = {
            "horse_no": 2,
            "case": "五頭立ての非アンカー候補では2が最も非対称な勝ち筋を持つ。",
        }
        changed["boundary_review"] = {
            "alternative_horse_no": None,
            "reason": "五頭立てのため外部の境界候補は存在しない。",
        }
        changed["candidate_compression"] = {
            "ordinary_five": [1, 4, 2, 3, 5],
            "external_challenger_horse_no": None,
            "external_challenger_case": "五頭立てのため外部の六頭目候補は存在しない。",
            "excluded_horse_no": None,
            "decision": "NO_EXTERNAL_CHALLENGER",
            "reason": "五頭立てなので候補集合をそのまま保持し、内部で◎○▲を役割付けする。",
        }
        v052.validate_core(changed, reader(5))


if __name__ == "__main__":
    unittest.main()
