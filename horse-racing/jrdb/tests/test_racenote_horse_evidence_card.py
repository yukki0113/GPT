#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from racenote_horse_evidence_card import (  # noqa: E402
    HorseEvidenceCardError,
    build_horse_evidence_cards,
)


def _run(
    race_key: str,
    race_date: str,
    *,
    finish: int,
    field_size: int,
    declared_class: str,
    time_class: str,
    pace_shape: str,
    corner4_frontness: float,
    last3f_rank: int,
    tags: list[str],
) -> dict[str, object]:
    return {
        "race_key": race_key,
        "race_date": race_date,
        "venue_code": "06",
        "surface_code": "1",
        "distance_m": 1600,
        "field_size": field_size,
        "finish": finish,
        "families": {
            "ability": {
                "declared_class_group": declared_class,
                "time_class_equivalent": time_class,
                "time_class_equivalent_numeric": 3.0,
                "horse_adjusted_delta_sec": -0.3,
                "horse_adjusted_delta_per_1000m": -0.1875,
            },
            "pace": {
                "pace_shape": pace_shape,
            },
            "position": {
                "corner1_frontness": 0.50,
                "corner2_frontness": 0.60,
                "corner3_frontness": 0.70,
                "corner4_frontness": corner4_frontness,
                "early_position_gain": 0.10,
                "middle_position_gain": 0.10,
                "late_position_gain": -0.10,
                "overall_position_gain": 0.10,
            },
            "finish": {
                "last3f_rank": last3f_rank,
                "last3f_speed_percentile": 100.0
                if last3f_rank == 1
                else 50.0,
                "closing_gain_sec": 0.20,
                "winner_gap_sec": 0.60,
            },
            "trouble": {
                "calibration_status": "RAW_ONLY_UNCALIBRATED",
                "jrdb_track_diff": 0.0,
                "jrdb_pace_score": 0.0,
                "jrdb_late_break_score": 0.0,
                "jrdb_position_score": 0.0,
                "jrdb_trouble_score": 0.0,
                "jrdb_prev_trouble_score": 0.0,
                "jrdb_mid_trouble_score": 0.0,
                "jrdb_late_trouble_score": 0.0,
            },
        },
        "review_tags": tags,
    }


def _profile(
    runs: list[dict[str, object]],
    requested_runs: int = 5,
) -> dict[str, object]:
    counts: dict[str, int] = {}
    for run in runs:
        tags = run.get("review_tags")
        if not isinstance(tags, list):
            continue
        for tag in tags:
            text = str(tag)
            counts[text] = counts.get(text, 0) + 1

    repeated = []
    for tag, count in sorted(counts.items()):
        if count >= 2:
            repeated.append({"tag": tag, "count": count})

    coverage = "PARTIAL"
    if len(runs) == 0:
        coverage = "NONE"
    if len(runs) >= requested_runs:
        coverage = "FULL"

    return {
        "observed_runs": len(runs),
        "requested_runs": requested_runs,
        "coverage_status": coverage,
        "pattern_counts": counts,
        "repeated_patterns": repeated,
        "hidden_strength_signals": [],
        "fragile_form_signals": [],
        "composite_signal_status": "NOT_DERIVED_V0_1",
    }


def _sidecar(
    horses: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "evidence_schema_version": "RaceReview-Evidence-0.1",
        "adapter_version": "0.1",
        "source": {
            "kind": "RaceReviewDB",
            "generation_id": "review-test",
            "period_from": "2010-01-01",
            "period_to": "2026-09-24",
            "review_schema_version": "v0.1",
            "review_logic_version": "review-test-v1",
            "baseline_version": "baseline-test-v1",
            "row_counts": {},
        },
        "target": {
            "date": "2026-09-25",
            "venue": "中山",
            "race_no": 11,
            "race_name": "テストステークス",
        },
        "policy": {
            "as_of_exclusive": True,
            "horse_identity": "JRDB_BLOOD_REGISTRATION_NO",
            "name_fallback": False,
            "stable_fields_only": True,
            "performance_label_status": "NOT_USED_UNSTABLE",
            "reason_codes_status": "NOT_USED_UNSTABLE",
            "track_bias_status": "NOT_USED_UNCALIBRATED_V0_1",
            "market_visibility_status": "NOT_APPLICABLE",
        },
        "horses": horses,
    }


def _horse(
    horse_no: int,
    name: str,
    horse_id: str,
    runs: list[dict[str, object]],
    *,
    history_status: str = "AVAILABLE",
) -> dict[str, object]:
    return {
        "horse_no": horse_no,
        "horse_name": name,
        "horse_id": horse_id,
        "history_status": history_status,
        "runs": runs,
        "profile": _profile(runs),
    }


class RaceNoteHorseEvidenceCardTest(unittest.TestCase):
    def test_hidden_strength_repeats_without_additive_score(self) -> None:
        run1 = _run(
            "0626a101",
            "2026-09-20",
            finish=5,
            field_size=12,
            declared_class="CLASS_1",
            time_class="CLASS_2",
            pace_shape="FRONT_LOADED",
            corner4_frontness=0.82,
            last3f_rank=1,
            tags=[
                "TIME_ABOVE_DECLARED_CLASS",
                "FASTEST_LAST3F",
                "PACE_FRONT_LOADED",
            ],
        )
        run2 = _run(
            "0626a090",
            "2026-09-13",
            finish=4,
            field_size=10,
            declared_class="CLASS_1",
            time_class="CLASS_2",
            pace_shape="FRONT_LOADED",
            corner4_frontness=0.75,
            last3f_rank=2,
            tags=[
                "TIME_ABOVE_DECLARED_CLASS",
                "PACE_FRONT_LOADED",
            ],
        )

        payload = build_horse_evidence_cards(
            _sidecar([
                _horse(
                    1,
                    "レビューエース",
                    "12345678",
                    [run1, run2],
                )
            ])
        )

        self.assertEqual(
            payload["policy"]["score_status"],
            "NO_ADDITIVE_SCORE",
        )
        card = payload["horses"][0]
        self.assertEqual(
            card["source_run_contexts"][0]["run_ref"],
            "0626a101@2026-09-20",
        )
        self.assertEqual(
            card["source_run_contexts"][0]["surface_code"],
            "1",
        )
        self.assertEqual(
            card["source_run_contexts"][0]["distance_m"],
            1600,
        )
        self.assertEqual(
            card["source_run_contexts"][0]["pace_shape"],
            "FRONT_LOADED",
        )
        hidden = card["profile"]["hidden_strength"]
        self.assertEqual(hidden["status"], "CANDIDATE")
        self.assertEqual(hidden["confidence"], "HIGH")
        self.assertIn(
            "REPEATED_RESULT_UNDERRATES_TIME",
            hidden["reason_codes"],
        )
        self.assertIn(
            "REPEATED_ABOVE_CLASS_PERFORMANCE",
            hidden["reason_codes"],
        )
        self.assertIn(
            "REPEATED_PACE_POSITION_AGAINST",
            hidden["reason_codes"],
        )

        primary_codes = {
            item["code"]
            for item in card["primary_positive"]
        }
        self.assertIn(
            "REPEATED_ABOVE_CLASS_PERFORMANCE",
            primary_codes,
        )
        self.assertIn(
            "REPEATED_PACE_POSITION_AGAINST",
            primary_codes,
        )
        self.assertEqual(len(card["primary_positive"]), 2)
        self.assertEqual(
            card["comment_evidence"]["prose_generation_status"],
            "NOT_GENERATED_V0_1",
        )

    def test_fragile_form_from_top_three_but_weak_time_and_pace_aid(self) -> None:
        run = _run(
            "0626a101",
            "2026-09-20",
            finish=2,
            field_size=12,
            declared_class="CLASS_2",
            time_class="CLASS_1",
            pace_shape="FRONT_LOADED",
            corner4_frontness=0.18,
            last3f_rank=2,
            tags=[
                "TIME_BELOW_DECLARED_CLASS",
                "PACE_FRONT_LOADED",
            ],
        )

        payload = build_horse_evidence_cards(
            _sidecar([
                _horse(
                    2,
                    "レビューリスク",
                    "87654321",
                    [run],
                )
            ])
        )
        card = payload["horses"][0]
        fragile = card["profile"]["fragile_form"]

        self.assertEqual(fragile["status"], "CANDIDATE")
        self.assertEqual(fragile["confidence"], "LOW")
        self.assertIn(
            "RESULT_OVERRATES_TIME",
            fragile["reason_codes"],
        )
        self.assertIn(
            "PACE_POSITION_AIDED_RESULT",
            fragile["reason_codes"],
        )

        concern_codes = {
            item["code"]
            for item in card["concerns"]
        }
        self.assertEqual(
            concern_codes,
            {
                "RESULT_OVERRATES_TIME",
                "PACE_POSITION_AIDED_RESULT",
            },
        )

    def test_mixed_history_is_preserved_as_contradiction(self) -> None:
        positive = _run(
            "0626a101",
            "2026-09-20",
            finish=5,
            field_size=12,
            declared_class="CLASS_1",
            time_class="CLASS_2",
            pace_shape="BALANCED",
            corner4_frontness=0.50,
            last3f_rank=3,
            tags=["TIME_ABOVE_DECLARED_CLASS"],
        )
        negative = _run(
            "0626a090",
            "2026-09-13",
            finish=2,
            field_size=12,
            declared_class="CLASS_2",
            time_class="CLASS_1",
            pace_shape="BALANCED",
            corner4_frontness=0.50,
            last3f_rank=3,
            tags=["TIME_BELOW_DECLARED_CLASS"],
        )

        payload = build_horse_evidence_cards(
            _sidecar([
                _horse(
                    3,
                    "レビュー混在",
                    "11112222",
                    [positive, negative],
                )
            ])
        )
        contradiction = payload["horses"][0]["profile"][
            "contradiction"
        ]

        self.assertEqual(contradiction["status"], "MIXED")
        self.assertIn(
            "HIDDEN_AND_FRAGILE_EVIDENCE_COEXIST",
            contradiction["conflict_codes"],
        )

    def test_missing_identity_is_explicit_uncertainty(self) -> None:
        horse = _horse(
            4,
            "IDナシ",
            "",
            [],
            history_status="NO_HORSE_ID",
        )
        payload = build_horse_evidence_cards(
            _sidecar([horse])
        )
        card = payload["horses"][0]

        self.assertEqual(
            card["comment_evidence"]["status"],
            "INSUFFICIENT",
        )
        self.assertEqual(
            card["uncertainties"],
            [
                {
                    "code": "NO_HORSE_ID",
                    "severity": "HIGH",
                }
            ],
        )

    def test_nonexclusive_history_fails_closed(self) -> None:
        run = _run(
            "0626a111",
            "2026-09-25",
            finish=5,
            field_size=12,
            declared_class="CLASS_1",
            time_class="CLASS_2",
            pace_shape="BALANCED",
            corner4_frontness=0.50,
            last3f_rank=3,
            tags=["TIME_ABOVE_DECLARED_CLASS"],
        )

        with self.assertRaises(HorseEvidenceCardError):
            build_horse_evidence_cards(
                _sidecar([
                    _horse(
                        5,
                        "未来混入",
                        "33334444",
                        [run],
                    )
                ])
            )

    def test_name_fallback_policy_is_rejected(self) -> None:
        sidecar = _sidecar([
            _horse(
                6,
                "方針違反",
                "55556666",
                [],
                history_status="NO_HISTORY",
            )
        ])
        sidecar["policy"]["name_fallback"] = True

        with self.assertRaises(HorseEvidenceCardError):
            build_horse_evidence_cards(sidecar)


if __name__ == "__main__":
    unittest.main()
