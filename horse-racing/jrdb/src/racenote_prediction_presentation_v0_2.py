#!/usr/bin/env python3
"""Edge-aware deterministic evidence extraction for RaceNote presentation.

This module extends ``racenote_prediction_presentation`` v0.1. It does not
change ranks, marks, confidence, or Edge policy decisions. It only makes an
already-frozen v1.1-P axis decision visible to the natural-language renderer.

The presentation contract deliberately separates implementation vocabulary
from reader-facing Japanese. Internal fields remain available for audit, while
horse comments and race summaries must translate those fields into terms a
reader can understand without knowing the scoring implementation.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

import racenote_prediction_presentation as base

VERSION = "racenote-presentation-evidence-0.2.1"


def _reader_edge_direction(value: Any) -> str:
    """Translate frozen performance Edge polarity to reader-facing Japanese."""
    if isinstance(value, bool):
        return "不明"
    if isinstance(value, (int, float)):
        if value > 0:
            return "プラス"
        if value < 0:
            return "マイナス"
        return "中立"

    text = str(value or "").strip().upper()
    if text in {"POSITIVE", "PLUS", "+1", "1"}:
        return "プラス"
    if text in {"NEGATIVE", "MINUS", "-1"}:
        return "マイナス"
    if text in {"NEUTRAL", "0", ""}:
        return "中立"
    return "不明"


def _edge_rows(prediction: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    """Return frozen Edge diagnostics keyed by horse number."""
    mapped: dict[int, dict[str, Any]] = {}
    for row in prediction.get("edge_diagnostics") or []:
        if not isinstance(row, Mapping):
            raise ValueError("edge_diagnostics entry must be an object")
        horse_no = int(row["horse_no"])
        if horse_no in mapped:
            raise ValueError(f"duplicate edge diagnostic horse_no: {horse_no}")
        mapped[horse_no] = dict(row)
    return mapped


def _axis_context(prediction: Mapping[str, Any]) -> dict[str, Any]:
    """Build race-level context for the already-frozen v1.1-P axis choice."""
    control = prediction.get("v0_2_control") or {}
    candidate = prediction.get("v1_1_P_candidate") or {}
    base_axis_no = int(control["axis_horse_no"])
    selected_axis_no = int(candidate["axis_horse_no"])
    axis_changed = bool(candidate.get("axis_changed"))
    if axis_changed != (base_axis_no != selected_axis_no):
        raise ValueError("v1.1-P axis_changed is inconsistent with axis horse numbers")

    decision_label = "◎据え置き"
    if axis_changed:
        decision_label = "◎へ変更"

    return {
        "axis_changed": axis_changed,
        "base_axis_horse_no": base_axis_no,
        "selected_axis_horse_no": selected_axis_no,
        "axis_good_guard": candidate.get("axis_good_guard"),
        "base_axis_polarity": candidate.get("base_axis_polarity"),
        "selected_axis_polarity": candidate.get("selected_axis_polarity"),
        "reader": {
            "base_evaluation_term": "基礎総合評価",
            "decision": decision_label,
            "base_axis_edge_direction": _reader_edge_direction(candidate.get("base_axis_polarity")),
            "selected_axis_edge_direction": _reader_edge_direction(candidate.get("selected_axis_polarity")),
        },
    }


def _horse_edge_context(
    horse_no: int,
    mark: str,
    axis: Mapping[str, Any],
    edge_rows: Mapping[int, Mapping[str, Any]],
) -> dict[str, Any]:
    """Describe how Edge evidence relates to one displayed top-three mark."""
    row = edge_rows.get(horse_no)
    if row is None:
        edge = {
            "performance_edge_polarity": "NEUTRAL",
            "family_vote_sum": 0,
            "performance_family_votes": {},
            "axis_eligible": False,
            "good_gap_from_base_axis": None,
            "active_unexpired_match_count": 0,
            "supporting_edge_id": None,
            "opposing_edge_id": None,
        }
    else:
        edge = {
            "performance_edge_polarity": row.get("performance_edge_polarity"),
            "family_vote_sum": row.get("family_vote_sum"),
            "performance_family_votes": dict(row.get("performance_family_votes") or {}),
            "axis_eligible": bool(row.get("axis_eligible")),
            "good_gap_from_base_axis": row.get("good_gap_from_base_axis"),
            "active_unexpired_match_count": int(row.get("active_unexpired_match_count") or 0),
            "supporting_edge_id": row.get("displayed_supporting_edge_id"),
            "opposing_edge_id": row.get("displayed_opposing_edge_id"),
        }

    role = "base_order_preserved"
    if axis["axis_changed"]:
        if horse_no == axis["selected_axis_horse_no"] and mark == "◎":
            role = "edge_promoted_to_axis"
        elif horse_no == axis["base_axis_horse_no"]:
            role = "base_axis_displaced_by_edge_comparison"
        else:
            role = "relative_order_preserved_after_axis_change"

    reader_relation = "基礎総合評価の通常順位"
    if horse_no == axis["base_axis_horse_no"]:
        reader_relation = "基礎総合評価1位"
    elif edge["axis_eligible"]:
        reader_relation = "逆転許容圏内"
    else:
        reader_relation = "逆転許容圏外"

    reader_mark_decision = "順位関係を維持"
    if axis["axis_changed"]:
        if role == "edge_promoted_to_axis":
            reader_mark_decision = "Edge比較で◎へ変更"
        elif role == "base_axis_displaced_by_edge_comparison":
            reader_mark_decision = "Edge比較で◎から変更"
    elif horse_no == axis["selected_axis_horse_no"] and mark == "◎":
        reader_mark_decision = "◎据え置き"

    return {
        "mark_decision_role": role,
        **edge,
        "reader": {
            "edge_direction": _reader_edge_direction(edge["performance_edge_polarity"]),
            "base_evaluation_relation": reader_relation,
            "mark_decision": reader_mark_decision,
        },
    }


def _reader_language_contract() -> dict[str, Any]:
    """Return the shared reader-facing language contract for both comment types."""
    return {
        "applies_to": ["horse_short_comment", "race_short_comment"],
        "preferred_terms": {
            "good": "基礎総合評価",
            "axis_eligible": "逆転許容圏内",
            "axis_not_eligible": "逆転許容圏外",
            "axis_changed": "◎へ変更",
            "axis_unchanged": "◎据え置き",
            "positive_polarity": "プラス",
            "neutral_polarity": "中立",
            "negative_polarity": "マイナス",
        },
        "horse_comment_rule": [
            "explain_the_horses_base_strengths_or_risks_in_reader_facing_terms",
            "use_edge_direction_only_when_it_materially_explains_the_displayed_mark",
            "keep_race_wide_axis_reversal_mechanics_in_the_race_summary_instead_of_repeating_them_for_every_horse",
            "treat_jrdb_finish_forecast_as_one_component_of_base_evaluation_not_as_an_independent_post_edge_vote",
        ],
        "race_summary_rule": [
            "state_the_base_evaluation_leader_when_axis_choice_needs_explanation",
            "when_changed_identify_the_selected_horse_as_within_the_reversal_window_without_exposing_the_raw_guard_by_default",
            "when_changed_compare_edge_directions_as_plus_neutral_or_minus_and_state_that_the_axis_was_changed",
            "when_unchanged_edge_context_may_be_omitted_if_it_did_not_materially_affect_the_mark",
            "keep_pace_and_other_base_components_as_explanations_of_base_evaluation_not_as_duplicate_independent_votes",
        ],
        "reasoning_guards": [
            "do_not_double_count_a_base_score_component_as_a_second_independent_reason_after_base_evaluation",
            "do_not_imply_that_performance_edge_direction_is_betting_value",
            "do_not_recompute_or_override_frozen_marks_in_the_presentation_layer",
            "keep_exact_thresholds_scores_vote_sums_and_edge_ids_in_audit_or_detail_views_unless_explicitly_requested",
        ],
        "forbidden_reader_terms": [
            "Good",
            "good",
            "base_good",
            "ability_good",
            "suitability_good",
            "forecast_good",
            "performance_edge_tier",
            "performance_edge_polarity",
            "family_vote_sum",
            "axis_good_guard",
            "axis_eligible",
            "mark_decision_role",
            "POSITIVE",
            "NEUTRAL",
            "NEGATIVE",
        ],
    }


def build_presentation_brief(
    bundle: Mapping[str, Any],
    prediction: Mapping[str, Any],
) -> dict[str, Any]:
    """Return v0.1 evidence plus frozen v1.1-P Edge axis-decision context."""
    payload = deepcopy(base.build_presentation_brief(bundle, prediction))
    axis = _axis_context(prediction)
    edge_rows = _edge_rows(prediction)

    horse_briefs = payload.get("horse_comment_briefs") or []
    for horse in horse_briefs:
        horse_no = int(horse["horse_no"])
        mark = str(horse["mark"])
        horse["edge_context"] = _horse_edge_context(horse_no, mark, axis, edge_rows)

    race_brief = payload.get("race_comment_brief") or {}
    race_brief["axis_decision"] = axis
    rendering_contract = race_brief.get("rendering_contract") or {}
    rendering_contract["axis_change_rule"] = {
        "when_axis_changed": [
            "explain_that_the_selected_axis_was_promoted_by_frozen_edge_polarity_comparison",
            "do_not_claim_the_selected_axis_was_the_highest_base_good_if_it_was_not",
            "contrast_the_displaced_base_axis_when_useful",
        ],
        "when_axis_unchanged": [
            "edge_context_may_be_omitted_when_it_does_not_materially_explain_the_mark",
        ],
        "forbidden": [
            "recompute_or_override_marks",
            "invent_edge_evidence",
            "expose_raw_edge_ids_as_reader_facing_reason_without_need",
        ],
    }
    rendering_contract["reader_language"] = _reader_language_contract()
    race_brief["rendering_contract"] = rendering_contract

    payload["version"] = VERSION
    payload["race_comment_brief"] = race_brief
    payload["result_data_used"] = False
    return payload
