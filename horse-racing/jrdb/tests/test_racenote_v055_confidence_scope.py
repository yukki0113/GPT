from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from racenote_decision_core_v055 import CONTRACT_REVISION, R4_CONTRACT_REVISION
from racenote_v055_single_day import _validate_confidence_grade, confidence_scope


def _normal(*, race_class: str = "1勝クラス", surface: str = "芝", race_type: str = "3歳以上") -> dict:
    return {"race": {"class": race_class, "surface": surface, "race_type": race_type}}


def test_r6_standard_flat_race_uses_abc_only() -> None:
    normal = _normal()
    assert confidence_scope(normal) == ("STANDARD", None)
    for grade in ("A", "B", "C"):
        _validate_confidence_grade(normal, grade, CONTRACT_REVISION)
    with pytest.raises(ValueError, match="standard race confidence must be A/B/C"):
        _validate_confidence_grade(normal, "Z", CONTRACT_REVISION)


def test_r6_debut_race_must_use_z() -> None:
    normal = _normal(race_class="新馬", race_type="2歳")
    assert confidence_scope(normal) == ("OUT_OF_SCOPE", "DEBUT")
    _validate_confidence_grade(normal, "Z", CONTRACT_REVISION)
    with pytest.raises(ValueError, match="special race DEBUT must use confidence Z"):
        _validate_confidence_grade(normal, "B", CONTRACT_REVISION)


def test_r6_jump_race_must_use_z() -> None:
    normal = _normal(race_class="オープン", surface="障害", race_type="障害")
    assert confidence_scope(normal) == ("OUT_OF_SCOPE", "JUMP")
    _validate_confidence_grade(normal, "Z", CONTRACT_REVISION)
    with pytest.raises(ValueError, match="special race JUMP must use confidence Z"):
        _validate_confidence_grade(normal, "A", CONTRACT_REVISION)


def test_r4_remains_abc_only_for_reproducibility() -> None:
    debut = _normal(race_class="新馬", race_type="2歳")
    _validate_confidence_grade(debut, "A", R4_CONTRACT_REVISION)
    with pytest.raises(ValueError, match="legacy pre-r5 confidence must be A/B/C"):
        _validate_confidence_grade(debut, "Z", R4_CONTRACT_REVISION)
