from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import racenote_decision_core_v051 as v051


def reader() -> dict:
    return {
        "race": {"venue": "東京", "race_no": 1},
        "horses": [{"basic": {"horse_no": n}} for n in range(1, 8)],
    }


def core() -> dict:
    return {
        "venue": "東京",
        "race_no": 1,
        "race_model": "先行勢の配置と末脚の再現性を中心に、通常本線と外部の非対称候補を分けて比較するレース。",
        "marks": [1, 2, 3, 4, 5],
        "mainline_cases": [
            {"horse_no": 1, "case": "能力と展開の両面で最も明瞭な勝ち筋がある。"},
            {"horse_no": 2, "case": "通常本線の二番手として崩れにくい根拠がある。"},
            {"horse_no": 4, "case": "相手候補として展開適合と再現性を評価できる。"},
            {"horse_no": 5, "case": "五頭境界でも残すだけの通常支持根拠がある。"},
        ],
        "single_shot_case": {
            "horse_no": 3,
            "case": "通常順位とは別に、展開が振れた時の単発上振れ経路が明確にある。",
        },
        "boundary_review": {
            "alternative_horse_no": 6,
            "reason": "通常五頭の末尾6と外部挑戦3を比較し、非対称性を優先して3を採用した。",
        },
        "candidate_compression": {
            "ordinary_five": [1, 2, 4, 5, 6],
            "external_challenger_horse_no": 3,
            "external_challenger_case": "通常五頭とは異なる展開依存の勝ち筋を持ち、外部候補として比較する価値がある。",
            "excluded_horse_no": 6,
            "decision": "ADMIT_CHALLENGER",
            "reason": "◎と○は固定したまま、通常支持の末尾6より3の非対称な勝ち切り余地を評価して入れ替える。",
        },
        "rrdb_refs": [],
        "reader_facing_reason": "通常本線では1と2を軸に評価し、支持候補4と5を残す。一方で3には本線とは異なる上振れ経路があり、六頭比較の結果として6を押し出して▲に採用する。",
    }


class V051DecisionCoreTest(unittest.TestCase):
    def test_admitted_external_challenger_is_valid(self) -> None:
        v051.validate_core(core(), reader())

    def test_challenger_cannot_displace_honmei_or_second(self) -> None:
        changed = copy.deepcopy(core())
        changed["candidate_compression"]["excluded_horse_no"] = 1
        changed["marks"] = [4, 2, 3, 5, 6]
        changed["boundary_review"]["alternative_horse_no"] = 7
        changed["mainline_cases"] = [
            {"horse_no": 4, "case": "十分な通常本線根拠を持つ候補として評価する。"},
            {"horse_no": 2, "case": "十分な通常本線根拠を持つ候補として評価する。"},
            {"horse_no": 5, "case": "十分な通常支持根拠を持つ候補として評価する。"},
            {"horse_no": 6, "case": "十分な通常支持根拠を持つ候補として評価する。"},
        ]
        with self.assertRaisesRegex(ValueError, "◎/○|cannot displace"):
            v051.validate_core(changed, reader())

    def test_keep_ordinary_five_excludes_challenger(self) -> None:
        changed = copy.deepcopy(core())
        changed["marks"] = [1, 2, 4, 5, 6]
        changed["mainline_cases"] = [
            {"horse_no": 1, "case": "能力と展開の両面で最も明瞭な勝ち筋がある。"},
            {"horse_no": 2, "case": "通常本線の二番手として崩れにくい根拠がある。"},
            {"horse_no": 5, "case": "相手候補として展開適合と再現性を評価できる。"},
            {"horse_no": 6, "case": "五頭境界でも残すだけの通常支持根拠がある。"},
        ]
        changed["single_shot_case"] = {
            "horse_no": 4,
            "case": "通常五頭の中では4が最も非対称な上振れ経路を持つため▲とする。",
        }
        changed["boundary_review"] = {
            "alternative_horse_no": 3,
            "reason": "外部候補3も比較したが、通常五頭を崩すほどの優位はない。",
        }
        changed["candidate_compression"]["excluded_horse_no"] = 3
        changed["candidate_compression"]["decision"] = "KEEP_ORDINARY_FIVE"
        changed["candidate_compression"]["reason"] = "外部挑戦3は魅力を認めるが、通常五頭の末尾を押し出すほどではないため五頭を維持する。"
        v051.validate_core(changed, reader())


    def test_exactly_five_runners_use_no_external_challenger(self) -> None:
        five_reader = {
            "race": {"venue": "東京", "race_no": 1},
            "horses": [{"basic": {"horse_no": n}} for n in range(1, 6)],
        }
        changed = copy.deepcopy(core())
        changed["marks"] = [1, 2, 4, 3, 5]
        changed["mainline_cases"] = [
            {"horse_no": 1, "case": "能力と展開の両面で最も明瞭な勝ち筋がある。"},
            {"horse_no": 2, "case": "通常本線の二番手として崩れにくい根拠がある。"},
            {"horse_no": 3, "case": "通常支持として展開適合と再現性を評価できる。"},
            {"horse_no": 5, "case": "通常支持として五頭内に残す根拠がある。"},
        ]
        changed["single_shot_case"] = {
            "horse_no": 4,
            "case": "五頭立ての通常支持内では4が最も非対称な上振れ経路を持つ。",
        }
        changed["boundary_review"] = {
            "alternative_horse_no": None,
            "reason": "五頭立てのため除外候補は存在せず、全頭を五印に残す。",
        }
        changed["candidate_compression"] = {
            "ordinary_five": [1, 2, 3, 4, 5],
            "external_challenger_horse_no": None,
            "external_challenger_case": "五頭立てのため外部の六頭目候補は存在しない。",
            "excluded_horse_no": None,
            "decision": "NO_EXTERNAL_CHALLENGER",
            "reason": "五頭立てなので通常五頭をそのまま保持し、支持三頭の中から▲を割り当てる。",
        }
        v051.validate_core(changed, five_reader)

    def test_reader_projection_is_not_changed_by_v051(self) -> None:
        import racenote_reader_v050 as v050_reader
        import racenote_reader_v051 as v051_reader
        self.assertNotEqual(v050_reader.VERSION, v051_reader.VERSION)


if __name__ == "__main__":
    unittest.main()
