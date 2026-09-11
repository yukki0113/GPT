#!/usr/bin/env python3
"""Edge-aware deterministic evidence extraction for RaceNote presentation.

This module extends ``racenote_prediction_presentation`` v0.1. It does not
change ranks, marks, confidence, or Edge policy decisions. It only makes an
already-frozen v1.1-P axis decision visible to the natural-language renderer.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

import racenote_prediction_presentation as base

VERSION = "racenote-presentation-evidence-0.2"


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

    return {
        "axis_changed": axis_changed,
        "base_axis_horse_no": base_axis_no,
        "selected_axis_horse_no": selected_axis_no,
        "axis_good_guard": candidate.get("axis_good_guard"),
        "base_axis_polarity": candidate.get("base_axis_polarity"),
        "selected_axis_polarity": candidate.get("selected_axis_polarity"),
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

    return {
        "mark_decision_role": role,
        **edge,
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
    race_brief["rendering_contract"] = rendering_contract

    payload["version"] = VERSION
    payload["race_comment_brief"] = race_brief
    payload["result_data_used"] = False
    return payload
