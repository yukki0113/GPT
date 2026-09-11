import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import racenote_prediction_presentation as presentation  # noqa: E402


def _horse(
    horse_no,
    name,
    *,
    idm,
    total,
    style,
    pace,
    finish_order,
    training_index,
    condition_index,
    arrow,
):
    return {
        "basic": {"horse_no": horse_no, "horse_name": name},
        "ability": {
            "idm": idm,
            "total_index": total,
            "running_style": style,
            "distance_fit": "マイル",
        },
        "pace": {
            "forecast_pace": pace,
            "forecast_positions": {
                "mid": {"order": finish_order},
                "finish": {"order": finish_order},
            },
        },
        "training": {
            "analysis": {
                "training_index": training_index,
                "condition_index": condition_index,
            },
            "summary": {
                "training_arrow": arrow,
                "volume_grade": "A",
            },
        },
    }


def _score(
    horse_no,
    *,
    good,
    ability,
    suitability,
    pace_fit,
    condition,
    distance,
    forecast,
):
    return {
        "horse_no": horse_no,
        "good": good,
        "ability_good": ability,
        "suitability_good": suitability,
        "pace_style_fit": pace_fit,
        "condition_good": condition,
        "distance_fit": distance,
        "forecast_good": forecast,
        "distance_contradiction": False,
    }


def _fixture():
    bundle = {
        "race": {
            "date": "2026-09-05",
            "venue": "阪神",
            "race_no": 6,
            "surface": "ダート",
            "distance_m": 1800,
        },
        "horses": [
            _horse(
                11,
                "サンライズモロヘイ",
                idm=38.6,
                total=45.6,
                style="先行",
                pace="平均",
                finish_order=1,
                training_index=50,
                condition_index=43,
                arrow="平行線",
            ),
            _horse(
                13,
                "ナリタライズ",
                idm=34.2,
                total=38.9,
                style="逃げ",
                pace="平均",
                finish_order=2,
                training_index=58,
                condition_index=56,
                arrow="上昇",
            ),
            _horse(
                8,
                "オメガダフネ",
                idm=33.1,
                total=37.0,
                style="差し",
                pace="平均",
                finish_order=3,
                training_index=47,
                condition_index=49,
                arrow="平行線",
            ),
            _horse(
                3,
                "ムスペルヘイム",
                idm=28.0,
                total=30.0,
                style="先行",
                pace="平均",
                finish_order=4,
                training_index=40,
                condition_index=42,
                arrow="平行線",
            ),
        ],
    }
    prediction = {
        "v0_2_control": {
            "confidence": "C",
            "p1_p2_good_gap": 0.012,
            "all_runners": [
                _score(
                    11,
                    good=0.71,
                    ability=0.80,
                    suitability=0.66,
                    pace_fit=0.70,
                    condition=0.46,
                    distance=0.70,
                    forecast=1.00,
                ),
                _score(
                    13,
                    good=0.70,
                    ability=0.64,
                    suitability=0.72,
                    pace_fit=0.74,
                    condition=0.62,
                    distance=0.72,
                    forecast=0.80,
                ),
                _score(
                    8,
                    good=0.67,
                    ability=0.61,
                    suitability=0.69,
                    pace_fit=0.76,
                    condition=0.52,
                    distance=0.69,
                    forecast=0.60,
                ),
                _score(
                    3,
                    good=0.55,
                    ability=0.42,
                    suitability=0.50,
                    pace_fit=0.54,
                    condition=0.44,
                    distance=0.51,
                    forecast=0.30,
                ),
            ],
        },
        "v1_1_P_candidate": {
            "confidence": "C",
            "marks": [
                {"mark": "◎", "horse_no": 11},
                {"mark": "○", "horse_no": 13},
                {"mark": "▲", "horse_no": 8},
                {"mark": "△1", "horse_no": 3},
            ],
        },
    }
    return bundle, prediction


def test_horse_briefs_explain_relative_differences_instead_of_mark_suffix_only():
    bundle, prediction = _fixture()

    result = presentation.build_presentation_brief(bundle, prediction)
    by_no = {row["horse_no"]: row for row in result["horse_comment_briefs"]}

    axis = by_no[11]
    second = by_no[13]

    assert axis["relative"]["idm"]["rank_among_top3"] == 1
    assert axis["relative"]["total_index"]["rank_among_top3"] == 1
    assert "ability" in axis["strength_axes"]

    assert second["relative"]["training_index"]["rank_among_top3"] == 1
    assert second["relative"]["condition_index"]["rank_among_top3"] == 1
    assert "training_condition" in second["strength_axes"]
    assert second["rendering_role"] == "explain_difference_from_axis_and_upside"

    assert axis["observations"] != second["observations"]
    assert axis["strength_axes"] != second["strength_axes"]


def test_race_brief_contains_pace_selection_method_and_material_risk():
    bundle, prediction = _fixture()

    result = presentation.build_presentation_brief(bundle, prediction)
    race = result["race_comment_brief"]

    assert race["pace"]["forecast_mode"] == "平均"
    assert race["pace"]["style_counts"]["逃げ"] == 1
    assert race["selection_priorities"]
    assert race["selection_priorities"][0]["top3_minus_field"] > 0
    assert "low_prediction_confidence" in race["risk_flags"]
    assert "axis_good_gap_small" in race["risk_flags"]
    assert race["rendering_contract"]["required_content"] == ["pace_read", "selection_method"]


def test_presentation_layer_is_non_predictive_and_result_free():
    bundle, prediction = _fixture()

    result = presentation.build_presentation_brief(bundle, prediction)

    assert result["result_data_used"] is False
    assert result["version"] == "racenote-presentation-evidence-0.1"
    assert [row["mark"] for row in result["horse_comment_briefs"]] == ["◎", "○", "▲"]
    assert [row["horse_no"] for row in result["horse_comment_briefs"]] == [11, 13, 8]
