from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from racenote_v053_reasoning_lint import lint_core


def good_core() -> dict:
    return {
        "venue": "中京",
        "race_no": 11,
        "candidate_compression": {
            "decision": "KEEP_ORDINARY_FIVE",
            "external_challenger_horse_no": 7,
            "excluded_horse_no": 7,
            "reason": (
                "challenger7は同距離オープン2着と高いIDMを持つ。一方10は"
                "同2000mオープン連続2着、forecast finish上位、状態面も良く、"
                "今回条件の再現性を失う損失が大きいためordinary fiveを維持する。"
            ),
        },
        "boundary_review": {
            "alternative_horse_no": 7,
            "reason": (
                "7の能力上限より、10の同条件での直近再現性と現在状態を優先し、"
                "交換しない。"
            ),
        },
        "role_assignment": {
            "ranking_reason": (
                "◎5は同2000mで自ら先行して押し切れる経路があり、○2より"
                "展開依存が小さいためWIN_FIRSTで上位に置く。"
            )
        },
    }


def test_concrete_capture_passes() -> None:
    assert lint_core(good_core()) == []


def test_identical_boundary_and_compression_reason_fails() -> None:
    core = good_core()
    core["boundary_review"]["reason"] = core["candidate_compression"]["reason"]
    assert any("must not be identical" in x for x in lint_core(core))


def test_keep_boilerplate_fails() -> None:
    core = good_core()
    core["candidate_compression"]["reason"] = (
        "ディープモンスターにも異なる勝ち筋はあるが、ordinary fiveの境界経路と"
        "比べて今回条件での追加価値が上回るまではなく、5頭を維持する。"
    )
    assert any("KEEP reason is generic boilerplate" in x for x in lint_core(core))


def test_admit_boilerplate_fails() -> None:
    core = good_core()
    core["candidate_compression"].update({
        "decision": "ADMIT_CHALLENGER",
        "external_challenger_horse_no": 8,
        "excluded_horse_no": 13,
        "reason": (
            "ジェミートの別経路は、境界のメイショウタイピンが担う通常経路より"
            "今回条件での交換価値が高い。◎○は固定したまま、最終比較で"
            "ジェミートを採用する。"
        ),
    })
    assert any("ADMIT reason is generic boilerplate" in x for x in lint_core(core))


def test_generic_ranking_reason_fails() -> None:
    core = good_core()
    core["role_assignment"]["ranking_reason"] = (
        "○の安定感より、◎が自分の形を作った時の勝ち切り可能性を優先して"
        "WIN_FIRSTで上位に置いた。"
    )
    assert any("ranking_reason is generic" in x for x in lint_core(core))
