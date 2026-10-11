from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import racenote_decision_core_v053 as v053


def reader(count: int = 7) -> dict:
    return {
        "race": {"venue": "東京", "race_no": 1},
        "horses": [{"basic": {"horse_no": n}} for n in range(1, count + 1)],
    }


def core() -> dict:
    return {
        "venue": "東京",
        "race_no": 1,
        "race_model": "通常候補を先に形成し、勝ち切り経路と境界交換を一貫した根拠で比較するレース。",
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
            "reason": "外部3を入れる価値と通常境界6を失う損失を直接比較し、3の独立経路を上に取る。",
        },
        "candidate_compression": {
            "ordinary_five": [1, 4, 2, 5, 6],
            "external_challenger_horse_no": 3,
            "external_challenger_case": "通常順位の六番手ではなく、展開が振れた時に勝ち切る独立ルートを持つ。",
            "excluded_horse_no": 6,
            "decision": "ADMIT_CHALLENGER",
            "reason": "候補集合の◎4・○1を守り、通常境界6との交換価値で3を採用する。",
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
        "reader_facing_reason": "通常候補五頭を守りつつ4を勝ち切り重視で◎へ。外部3は境界6との直接比較で交換価値が上回るため▲に採用する。",
    }


class V053DecisionCoreTest(unittest.TestCase):
    def test_admit_boundary_is_displaced_ordinary_horse(self) -> None:
        v053.validate_core(core(), reader())

    def test_admit_rejects_unrelated_boundary_alternative(self) -> None:
        changed = copy.deepcopy(core())
        changed["boundary_review"]["alternative_horse_no"] = 7
        with self.assertRaisesRegex(ValueError, "ADMIT boundary"):
            v053.validate_core(changed, reader())

    def test_keep_boundary_is_external_challenger(self) -> None:
        changed = copy.deepcopy(core())
        changed["marks"] = [4, 1, 2, 5, 6]
        changed["single_shot_case"] = {
            "horse_no": 2,
            "case": "通常五頭の非アンカーでは2が最も非対称な勝ち筋を持つため▲へ置く。",
        }
        changed["mainline_cases"] = [
            {"horse_no": 4, "case": "勝ち切り経路が最も明確で◎として評価する。"},
            {"horse_no": 1, "case": "能力と再現性から○として主線に残す。"},
            {"horse_no": 5, "case": "通常支持として相手本線に残す根拠がある。"},
            {"horse_no": 6, "case": "境界比較後も通常候補として残す根拠が十分にある。"},
        ]
        changed["boundary_review"] = {
            "alternative_horse_no": 3,
            "reason": "外部3の経路と通常境界を直接比較したが、通常五頭を崩す交換価値には届かない。",
        }
        changed["candidate_compression"]["excluded_horse_no"] = 3
        changed["candidate_compression"]["decision"] = "KEEP_ORDINARY_FIVE"
        changed["candidate_compression"]["reason"] = "外部3の独立経路は認めるが通常五頭を失う損失が大きいため維持する。"
        v053.validate_core(changed, reader())

    def test_keep_rejects_wrong_boundary_alternative(self) -> None:
        changed = copy.deepcopy(core())
        changed["marks"] = [4, 1, 2, 5, 6]
        changed["single_shot_case"] = {
            "horse_no": 2,
            "case": "通常五頭の非アンカーでは2が最も非対称な勝ち筋を持つため▲へ置く。",
        }
        changed["mainline_cases"] = [
            {"horse_no": 4, "case": "勝ち切り経路が最も明確で◎として評価する。"},
            {"horse_no": 1, "case": "能力と再現性から○として主線に残す。"},
            {"horse_no": 5, "case": "通常支持として相手本線に残す根拠がある。"},
            {"horse_no": 6, "case": "境界比較後も通常候補として残す根拠が十分にある。"},
        ]
        changed["boundary_review"]["alternative_horse_no"] = 6
        changed["candidate_compression"]["excluded_horse_no"] = 3
        changed["candidate_compression"]["decision"] = "KEEP_ORDINARY_FIVE"
        changed["candidate_compression"]["reason"] = "外部3の独立経路は認めるが通常五頭を失う損失が大きいため維持する。"
        with self.assertRaisesRegex(ValueError, "KEEP boundary"):
            v053.validate_core(changed, reader())

    def test_five_runner_boundary_is_null(self) -> None:
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
            "reason": "五頭立てのため外部の境界候補は存在せず、全馬を候補集合として保持する。",
        }
        changed["candidate_compression"] = {
            "ordinary_five": [1, 4, 2, 3, 5],
            "external_challenger_horse_no": None,
            "external_challenger_case": "五頭立てのため外部の六頭目候補は存在しない。",
            "excluded_horse_no": None,
            "decision": "NO_EXTERNAL_CHALLENGER",
            "reason": "五頭立てなので候補集合をそのまま保持し、内部で◎○▲を役割付けする。",
        }
        v053.validate_core(changed, reader(5))


if __name__ == "__main__":
    unittest.main()
