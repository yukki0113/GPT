#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from racenote_general_evidence import (  # noqa: E402
    GeneralEvidenceError,
    build_general_evidence,
)


def _summary(
    starts: int,
    wins: int,
    top3: int,
    win_rate: float,
    top3_rate: float,
    band: str,
) -> dict[str, object]:
    return {
        "starts": starts,
        "wins": wins,
        "top3": top3,
        "win_rate": win_rate,
        "top3_rate": top3_rate,
        "sample_size_band": band,
    }


def _stat(
    starts: int,
    win_rate: float,
    top3_rate: float,
    band: str,
) -> dict[str, object]:
    wins = int(round(starts * win_rate / 100.0))
    top3 = int(round(starts * top3_rate / 100.0))
    return {
        **_summary(
            starts,
            wins,
            top3,
            win_rate,
            top3_rate,
            band,
        ),
        "distance_ranges": [],
    }


def _recent_run(
    date: str,
    idm: float,
    finish: int,
    corners: list[int] | None = None,
    field_size: int = 12,
) -> dict[str, object]:
    if corners is None:
        corners = [finish, finish, finish, finish]
    return {
        "race": {
            "date": date,
            "venue": "中山",
            "race_no": 8,
            "surface": "芝",
            "distance_m": 1600,
            "class": "2勝クラス",
            "grade": "",
            "field_size": field_size,
        },
        "result": {
            "finish": finish,
        },
        "performance": {
            "idm": idm,
            "corners": corners,
        },
    }


def _independent() -> dict[str, object]:
    return {
        "view_kind": "INDEPENDENT",
        "policy": {
            "current_jrdb_consensus_visible": False,
            "current_market_visible": False,
            "training_edge_visible": False,
        },
        "race": {
            "date": "2026-09-25",
            "venue": "中山",
            "race_no": 11,
            "race_name": "テストステークス",
            "surface": "芝",
            "distance_m": 1600,
            "turn": "右",
            "course_layout": "外",
            "race_type": "3歳以上",
            "class": "3勝クラス",
            "field_size": 2,
            "race_trends": {
                "frame": {
                    "2": _stat(
                        80,
                        12.5,
                        31.2,
                        "sufficient",
                    ),
                    "6": _stat(
                        75,
                        9.3,
                        25.3,
                        "sufficient",
                    ),
                },
                "running_style": {
                    "1": {
                        "label": "逃げ",
                        **_stat(
                            50,
                            14.0,
                            34.0,
                            "sufficient",
                        ),
                    },
                    "3": {
                        "label": "差し",
                        **_stat(
                            120,
                            8.0,
                            25.0,
                            "sufficient",
                        ),
                    },
                },
            },
        },
        "horses": [
            {
                "basic": {
                    "frame_no": 2,
                    "horse_no": 1,
                    "horse_id": "12345678",
                    "horse_name": "トレンドエース",
                    "jockey": "騎手A",
                    "trainer": "厩舎A",
                    "carried_weight_kg": 57.0,
                },
                "condition_facts": {
                    "rotation_interval": 3,
                },
                "recent_runs": [
                    _recent_run("2026-09-20", 60.0, 4),
                    _recent_run("2026-08-30", 56.0, 2),
                    _recent_run("2026-08-02", 58.0, 5),
                ],
                "older_runs": [],
                "historical_profile": {
                    "source": "JRDB Analysis Lite",
                    "source_window_start": "2010-01-01",
                    "as_of_exclusive": "2026-09-25",
                    "career": _summary(
                        10,
                        2,
                        3,
                        20.0,
                        30.0,
                        "small",
                    ),
                    "same_surface": _summary(
                        8,
                        2,
                        3,
                        25.0,
                        37.5,
                        "small",
                    ),
                    "same_distance": _summary(
                        4,
                        2,
                        3,
                        50.0,
                        75.0,
                        "small",
                    ),
                    "distance_ranges": [
                        {
                            "min_m": 1400,
                            "max_m": 1800,
                            **_summary(
                                6,
                                2,
                                3,
                                33.3,
                                50.0,
                                "small",
                            ),
                        }
                    ],
                    "same_venue": _summary(
                        5,
                        1,
                        1,
                        20.0,
                        20.0,
                        "small",
                    ),
                },
                "history_coverage": {
                    "observed_history": "present",
                },
                "stats": {
                    "sire": _stat(
                        100,
                        11.0,
                        29.0,
                        "sufficient",
                    ),
                    "jockey": _stat(
                        60,
                        15.0,
                        35.0,
                        "sufficient",
                    ),
                },
            },
            {
                "basic": {
                    "frame_no": 6,
                    "horse_no": 2,
                    "horse_id": "87654321",
                    "horse_name": "アビリティ型",
                    "jockey": "騎手B",
                    "trainer": "厩舎B",
                    "carried_weight_kg": 57.0,
                },
                "condition_facts": {
                    "rotation_interval": 4,
                },
                "recent_runs": [
                    _recent_run("2026-09-14", 64.0, 1),
                    _recent_run("2026-08-16", 63.0, 1),
                ],
                "older_runs": [],
                "historical_profile": {
                    "source": "JRDB Analysis Lite",
                    "source_window_start": "2010-01-01",
                    "as_of_exclusive": "2026-09-25",
                    "career": _summary(
                        8,
                        3,
                        5,
                        37.5,
                        62.5,
                        "small",
                    ),
                    "same_surface": _summary(
                        7,
                        3,
                        5,
                        42.9,
                        71.4,
                        "small",
                    ),
                    "same_distance": _summary(
                        2,
                        0,
                        0,
                        0.0,
                        0.0,
                        "small",
                    ),
                    "distance_ranges": [],
                    "same_venue": _summary(
                        2,
                        0,
                        1,
                        0.0,
                        50.0,
                        "small",
                    ),
                },
                "history_coverage": {
                    "observed_history": "present",
                },
                "stats": {
                    "sire": _stat(
                        90,
                        8.0,
                        23.0,
                        "sufficient",
                    ),
                    "jockey": _stat(
                        55,
                        10.0,
                        28.0,
                        "sufficient",
                    ),
                },
            },
        ],
    }


def _rr_card(
    horse_no: int,
    horse_name: str,
    horse_id: str,
    *,
    hidden: bool,
) -> dict[str, object]:
    hidden_status = "NONE"
    hidden_confidence = "NONE"
    hidden_codes: list[str] = []
    hidden_ids: list[str] = []
    hidden_refs: list[str] = []

    if hidden:
        hidden_status = "CANDIDATE"
        hidden_confidence = "MEDIUM"
        hidden_codes = ["RESULT_UNDERRATES_TIME"]
        hidden_ids = ["HEC:1:RESULT_UNDERRATES_TIME"]
        hidden_refs = ["0626a101@2026-09-20"]

    return {
        "horse_no": horse_no,
        "horse_name": horse_name,
        "horse_id": horse_id,
        "history_status": "AVAILABLE",
        "card_scope": "RACEREVIEW_HISTORY_V0_1",
        "source_run_contexts": [
            {
                "run_ref": "0626a101@2026-09-20",
                "race_date": "2026-09-20",
                "venue_code": "06",
                "surface_code": "1",
                "distance_m": 1600,
                "field_size": 12,
                "finish": 5,
                "pace_shape": "FRONT_LOADED",
            }
        ] if hidden else [],
        "primary_positive": [],
        "supporting_positive": [],
        "concerns": [],
        "mixed_context": [],
        "profile": {
            "hidden_strength": {
                "status": hidden_status,
                "confidence": hidden_confidence,
                "reason_codes": hidden_codes,
                "evidence_ids": hidden_ids,
                "source_run_refs": hidden_refs,
            },
            "fragile_form": {
                "status": "NONE",
                "confidence": "NONE",
                "reason_codes": [],
                "evidence_ids": [],
                "source_run_refs": [],
            },
            "contradiction": {
                "status": "NONE",
                "conflict_codes": [],
            },
            "repeatability_source": "RACEREVIEW_HISTORY",
        },
        "uncertainties": [],
        "comment_evidence": {
            "status": "READY",
            "positive_codes": [],
            "concern_codes": [],
            "mixed_codes": [],
            "source_evidence_ids": [],
            "prose_generation_status": "NOT_GENERATED_V0_1",
        },
    }


def _rr_cards() -> dict[str, object]:
    return {
        "card_schema_version": "RaceNote-Horse-Evidence-Card-0.1",
        "card_logic_version": "RaceReview-Card-v0.1",
        "target": {
            "date": "2026-09-25",
            "venue": "中山",
            "race_no": 11,
            "race_name": "テストステークス",
        },
        "source": {
            "kind": "RaceReviewDB",
            "generation_id": "review-test",
            "review_schema_version": "v0.1",
            "review_logic_version": "review-test-v1",
            "baseline_version": "baseline-test-v1",
            "adapter_version": "0.1",
            "evidence_schema_version": "RaceReview-Evidence-0.1",
        },
        "policy": {
            "market_visibility_status": "HIDDEN_NOT_CONSUMED",
            "jrdb_current_consensus_status": "HIDDEN_NOT_CONSUMED",
            "training_edge_status": "NOT_CONSUMED",
            "score_status": "NO_ADDITIVE_SCORE",
            "comment_prose_status": "NOT_GENERATED",
            "hidden_strength_semantics": (
                "HISTORICAL_RESULT_VS_CONTENT_ONLY"
            ),
            "fragile_form_semantics": (
                "HISTORICAL_RESULT_VS_CONTENT_ONLY"
            ),
        },
        "horses": [
            _rr_card(
                1,
                "トレンドエース",
                "12345678",
                hidden=True,
            ),
            _rr_card(
                2,
                "アビリティ型",
                "87654321",
                hidden=False,
            ),
        ],
    }


class RaceNoteGeneralEvidenceTest(unittest.TestCase):
    def test_priority_policy_is_trend_first(self) -> None:
        result = build_general_evidence(
            _independent(),
            _rr_cards(),
        )

        self.assertEqual(
            result["priority_policy"]["relation"],
            "DATA_TREND > RACEREVIEW >= ABILITY_ANCHOR",
        )
        self.assertEqual(
            result["priority_policy"]["decision_order"],
            [
                "DATA_TREND",
                "RACEREVIEW",
                "ABILITY_ANCHOR",
            ],
        )
        self.assertIsNone(
            result["priority_policy"]["numeric_weights"]
        )
        self.assertFalse(
            result["priority_policy"]["rules"][
                "ability_may_auto_rank"
            ]
        )

    def test_data_trend_lane_precedes_higher_raw_ability(self) -> None:
        result = build_general_evidence(
            _independent(),
            _rr_cards(),
        )

        first = result["horses"][0]
        second = result["horses"][1]

        first_lanes = first["evidence_lanes"]
        second_lanes = second["evidence_lanes"]

        self.assertEqual(
            first_lanes["data_trend"]["priority_rank"],
            1,
        )
        self.assertEqual(
            first_lanes["racereview"]["priority_rank"],
            2,
        )
        self.assertEqual(
            first_lanes["ability_anchor"]["priority_rank"],
            3,
        )

        self.assertEqual(
            first_lanes["ability_anchor"]["profile"]["peak"],
            60.0,
        )
        self.assertEqual(
            second_lanes["ability_anchor"]["profile"]["peak"],
            64.0,
        )
        self.assertFalse(
            second_lanes["ability_anchor"]["policy"][
                "may_auto_rank"
            ]
        )

        observations = first_lanes["data_trend"][
            "horse_history"
        ]["observations"]
        same_distance = next(
            item
            for item in observations
            if item["code"] == "SAME_DISTANCE"
        )
        self.assertEqual(
            same_distance["direction"],
            "POSITIVE",
        )
        self.assertEqual(
            same_distance["delta_pp"]["top3_rate"],
            45.0,
        )
        self.assertEqual(
            same_distance["sample_size_band"],
            "small",
        )
        self.assertEqual(
            same_distance["redundancy_group_id"],
            "DISTANCE",
        )
        distance_range = next(
            item
            for item in observations
            if item["code"] == "DISTANCE_RANGE_1"
        )
        self.assertEqual(
            distance_range["redundancy_group_id"],
            "DISTANCE",
        )

        second_observations = second_lanes["data_trend"][
            "horse_history"
        ]["observations"]
        second_same_distance = next(
            item
            for item in second_observations
            if item["code"] == "SAME_DISTANCE"
        )
        self.assertEqual(
            second_same_distance["direction"],
            "NEGATIVE",
        )

    def test_prediction_interpretation_keeps_small_sample_direction(self) -> None:
        result = build_general_evidence(
            _independent(),
            _rr_cards(),
        )
        interpretation = result["horses"][0][
            "prediction_interpretation"
        ]
        trend = interpretation["data_trend"]

        self.assertEqual(trend["state"], "MIXED")
        self.assertEqual(
            trend["best_directional_sample_band"],
            "small",
        )
        self.assertTrue(trend["small_sample_only"])
        self.assertIn(
            "DATA_TREND_MIXED_SUPPORT",
            interpretation["positive_case_components"],
        )
        self.assertIn(
            "DATA_TREND_MIXED_CONCERN",
            interpretation["concern_case_components"],
        )
        self.assertTrue(
            interpretation["policy"][
                "sample_size_changes_confidence_not_direction"
            ]
        )

    def test_racereview_hidden_strength_and_target_overlap_are_visible(self) -> None:
        result = build_general_evidence(
            _independent(),
            _rr_cards(),
        )
        interpretation = result["horses"][0][
            "prediction_interpretation"
        ]
        review = interpretation["racereview"]

        self.assertEqual(review["state"], "HIDDEN_STRENGTH")
        self.assertEqual(
            review["transferability"]["state"],
            "EXACT_SURFACE_DISTANCE_PRESENT",
        )
        self.assertEqual(
            review["transferability"][
                "exact_surface_distance_count"
            ],
            1,
        )
        self.assertIn(
            "RACEREVIEW_SUPPORT",
            interpretation["positive_case_components"],
        )

    def test_ability_anchor_cannot_create_upgrade_or_downgrade_by_itself(self) -> None:
        result = build_general_evidence(
            _independent(),
            _rr_cards(),
        )
        ability = result["horses"][1][
            "prediction_interpretation"
        ]["ability_anchor"]

        self.assertEqual(ability["role"], "AVAILABLE_ANCHOR")
        self.assertFalse(
            ability["may_create_upgrade_by_itself"]
        )
        self.assertFalse(
            ability["may_create_downgrade_by_itself"]
        )

    def test_rr_transferability_does_not_invent_distance_tolerance(self) -> None:
        cards = _rr_cards()
        cards["horses"][0]["source_run_contexts"][0][
            "distance_m"
        ] = 1800

        result = build_general_evidence(
            _independent(),
            cards,
        )
        transfer = result["horses"][0][
            "prediction_interpretation"
        ]["racereview"]["transferability"]

        self.assertEqual(
            transfer["state"],
            "PARTIAL_EXACT_MATCH_PRESENT",
        )
        self.assertEqual(
            transfer["exact_surface_distance_count"],
            0,
        )
        self.assertTrue(
            transfer["policy"][
                "distance_tolerance_not_invented"
            ]
        )

    def test_race_day_facts_require_explicit_pre_result_source(self) -> None:
        independent = _independent()
        independent["race"]["race_day_facts"] = {
            "source_kind": "PRE_RACE_INDEPENDENT",
            "as_of": "2026-09-25T10:00:00+09:00",
            "weather": "雨",
            "track_condition": "重",
            "result_independent": True,
        }

        result = build_general_evidence(
            independent,
            _rr_cards(),
        )
        facts = result["race_data_context"]["race_day_facts"]

        self.assertEqual(facts["status"], "AVAILABLE")
        self.assertEqual(facts["weather"], "雨")
        self.assertEqual(facts["track_condition"], "重")
        self.assertFalse(facts["policy"]["may_auto_rank"])

    def test_race_day_facts_reject_result_dependent_source(self) -> None:
        independent = _independent()
        independent["race"]["race_day_facts"] = {
            "source_kind": "RESULT_DERIVED",
            "weather": "雨",
            "track_condition": "重",
            "result_independent": False,
        }

        result = build_general_evidence(
            independent,
            _rr_cards(),
        )
        facts = result["race_data_context"]["race_day_facts"]

        self.assertEqual(facts["status"], "UNAVAILABLE")
        self.assertIsNone(facts["weather"])
        self.assertIsNone(facts["track_condition"])

    def test_race_trend_sources_separate_pre_and_post_freeze(self) -> None:
        result = build_general_evidence(
            _independent(),
            _rr_cards(),
        )
        context = result["race_data_context"]

        self.assertEqual(
            context["race_day_facts"]["status"],
            "UNAVAILABLE",
        )
        self.assertEqual(
            context["trend_sources_v0_1"],
            ["FRAME", "RUNNING_STYLE"],
        )
        self.assertNotIn(
            "POPULARITY",
            context["independent_future_trend_sources"],
        )
        self.assertEqual(
            context["post_freeze_trend_sources"],
            ["POPULARITY"],
        )

    def test_independent_race_structure_uses_only_historical_corners(self) -> None:
        independent = _independent()
        independent["horses"][0]["recent_runs"] = [
            _recent_run(
                "2026-09-20",
                60.0,
                4,
                corners=[1, 1, 2, 2],
            ),
            _recent_run(
                "2026-08-30",
                56.0,
                2,
                corners=[2, 2, 2, 2],
            ),
            _recent_run(
                "2026-08-02",
                58.0,
                5,
                corners=[3, 3, 4, 4],
            ),
        ]
        independent["horses"][1]["recent_runs"] = [
            _recent_run(
                "2026-09-14",
                64.0,
                1,
                corners=[8, 7, 6, 4],
            ),
            _recent_run(
                "2026-08-16",
                63.0,
                1,
                corners=[9, 8, 5, 2],
            ),
        ]

        result = build_general_evidence(
            independent,
            _rr_cards(),
        )
        structure = result["race_structure"]

        self.assertEqual(
            structure["structure_version"],
            "IndependentRaceStructure-v0.1",
        )
        self.assertEqual(structure["pace_pressure"], "LOW")
        self.assertEqual(
            structure["position_tendency_counts"],
            {
                "FRONT": 1,
                "FORWARD": 0,
                "MID": 1,
                "BACK": 0,
                "UNKNOWN": 0,
            },
        )
        self.assertEqual(
            structure["position_variability_counts"],
            {
                "SINGLE_BAND": 2,
                "MULTI_BAND": 0,
                "UNAVAILABLE": 0,
            },
        )
        self.assertTrue(
            structure["policy"][
                "front_or_forward_count_is_not_lead_contest_count"
            ]
        )
        first = structure["horses"][0]["historical_position"]
        second = structure["horses"][1]["historical_position"]
        self.assertEqual(first["tendency"], "FRONT")
        self.assertEqual(second["tendency"], "MID")
        self.assertEqual(first["dominant_band_count"], 3)
        self.assertEqual(first["dominant_share"], 1.0)
        self.assertEqual(first["distinct_band_count"], 1)
        self.assertEqual(first["variability_status"], "SINGLE_BAND")
        self.assertEqual(second["dominant_band_count"], 2)
        self.assertEqual(second["dominant_share"], 1.0)
        self.assertEqual(second["distinct_band_count"], 1)
        self.assertEqual(second["variability_status"], "SINGLE_BAND")
        self.assertFalse(
            first["policy"]["current_jrdb_running_style_used"]
        )
        self.assertTrue(
            first["policy"][
                "historical_tendency_is_not_position_commitment"
            ]
        )
        self.assertFalse(
            structure["policy"]["current_jrdb_forecast_pace_used"]
        )

    def test_historical_position_profile_exposes_variability(self) -> None:
        independent = _independent()
        independent["horses"][0]["recent_runs"] = [
            _recent_run(
                "2026-09-20",
                60.0,
                4,
                corners=[1, 1, 2, 2],
            ),
            _recent_run(
                "2026-08-30",
                56.0,
                2,
                corners=[2, 2, 2, 2],
            ),
            _recent_run(
                "2026-08-02",
                58.0,
                5,
                corners=[8, 8, 8, 8],
            ),
        ]

        result = build_general_evidence(
            independent,
            _rr_cards(),
        )
        profile = result["race_structure"]["horses"][0][
            "historical_position"
        ]

        self.assertEqual(profile["tendency"], "FRONT")
        self.assertEqual(profile["dominant_band_count"], 2)
        self.assertEqual(profile["dominant_share"], 0.667)
        self.assertEqual(profile["distinct_band_count"], 2)
        self.assertEqual(profile["variability_status"], "MULTI_BAND")

    def test_prediction_interpretation_exposes_race_structure_without_auto_direction(self) -> None:
        independent = _independent()
        independent["horses"][0]["recent_runs"] = [
            _recent_run(
                "2026-09-20",
                60.0,
                4,
                corners=[1, 1, 2, 2],
            ),
            _recent_run(
                "2026-08-30",
                56.0,
                2,
                corners=[2, 2, 2, 2],
            ),
        ]
        result = build_general_evidence(
            independent,
            _rr_cards(),
        )
        structure = result["horses"][0][
            "prediction_interpretation"
        ]["race_structure"]

        self.assertIn(
            structure["pace_pressure"],
            {"LOW", "MEDIUM", "HIGH", "UNKNOWN"},
        )
        self.assertEqual(
            structure["horse_historical_position"]["tendency"],
            "FRONT",
        )
        self.assertTrue(
            structure["running_style_trend_available"]
        )
        self.assertTrue(
            structure["policy"]["no_automatic_style_mapping_v0_1"]
        )

    def test_population_trends_keep_sample_size_visible(self) -> None:
        result = build_general_evidence(
            _independent(),
            _rr_cards(),
        )

        lane = result["horses"][0]["evidence_lanes"][
            "data_trend"
        ]
        frame = lane["population_context"]["frame"]
        sire = lane["population_context"]["sire"]
        jockey = lane["population_context"]["jockey"]

        self.assertEqual(frame["sample_size_band"], "sufficient")
        self.assertEqual(sire["sample_size_band"], "sufficient")
        self.assertEqual(
            jockey["sample_size_band"],
            "sufficient",
        )

    def test_ability_anchor_is_historical_and_descriptive(self) -> None:
        result = build_general_evidence(
            _independent(),
            _rr_cards(),
        )
        anchor = result["horses"][0]["evidence_lanes"][
            "ability_anchor"
        ]

        self.assertEqual(anchor["observed_count"], 3)
        self.assertEqual(anchor["profile"]["latest"], 60.0)
        self.assertEqual(anchor["profile"]["peak"], 60.0)
        self.assertEqual(
            anchor["profile"]["typical_median"],
            58.0,
        )
        self.assertEqual(anchor["profile"]["minimum"], 56.0)
        self.assertEqual(anchor["profile"]["mad"], 2.0)
        self.assertFalse(
            anchor["policy"]["current_entry_idm_used"]
        )
        self.assertFalse(
            anchor["policy"]["current_total_index_used"]
        )

    def test_no_selected_rr_evidence_keeps_transferability_unknown(self) -> None:
        result = build_general_evidence(
            _independent(),
            _rr_cards(),
        )
        transfer = result["horses"][1][
            "prediction_interpretation"
        ]["racereview"]["transferability"]

        self.assertEqual(transfer["state"], "UNKNOWN")
        self.assertEqual(transfer["selected_source_run_count"], 0)

    def test_racereview_signal_is_preserved_as_second_lane(self) -> None:
        result = build_general_evidence(
            _independent(),
            _rr_cards(),
        )
        rr = result["horses"][0]["evidence_lanes"][
            "racereview"
        ]

        self.assertEqual(rr["priority_rank"], 2)
        self.assertEqual(
            rr["profile"]["hidden_strength"]["status"],
            "CANDIDATE",
        )

    def test_target_mismatch_fails_closed(self) -> None:
        cards = _rr_cards()
        cards["target"]["race_no"] = 10

        with self.assertRaises(GeneralEvidenceError):
            build_general_evidence(
                _independent(),
                cards,
            )

    def test_horse_identity_mismatch_fails_closed(self) -> None:
        cards = _rr_cards()
        cards["horses"][0]["horse_id"] = "99999999"

        with self.assertRaises(GeneralEvidenceError):
            build_general_evidence(
                _independent(),
                cards,
            )

    def test_market_visibility_fails_closed(self) -> None:
        independent = _independent()
        independent["policy"]["current_market_visible"] = True

        with self.assertRaises(GeneralEvidenceError):
            build_general_evidence(
                independent,
                _rr_cards(),
            )


if __name__ == "__main__":
    unittest.main()
