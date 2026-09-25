#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate RaceNote Pairwise Comparison v0.1.

This module does not choose horses and does not calculate a score.

GPT or another comparison consumer authors a concise pairwise judgment from the
validated RaceNote General Evidence view. This validator enforces:
- complete runner coverage in draft/final order;
- direct comparison of final-order adjacent runners;
- direct comparison of the top runner with major challengers;
- trend-first lane reading;
- explicit reasons for lower-priority overrides;
- concise reason summaries and reversal conditions;
- no market/current-JRDB/Training-Edge use.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

PAIRWISE_SCHEMA_VERSION = "RaceNote-Pairwise-Comparison-0.1"
PAIRWISE_CONTRACT_VERSION = "TrendFirst-Pairwise-v0.1"
EXPECTED_GENERAL_SCHEMA = "RaceNote-General-Evidence-0.1"

LANE_ORDER = (
    "DATA_TREND",
    "RACEREVIEW",
    "ABILITY_ANCHOR",
)
LANE_PRIORITY = {
    "DATA_TREND": 1,
    "RACEREVIEW": 2,
    "ABILITY_ANCHOR": 3,
}
RELATIONS = {"A", "B", "EVEN", "UNKNOWN"}
PREFERENCES = {"A", "B"}
CONFIDENCE_VALUES = {"LOW", "MEDIUM", "HIGH"}
DECISIVE_LANES = {
    "DATA_TREND",
    "RACEREVIEW",
    "ABILITY_ANCHOR",
    "MIXED",
    "UNCERTAINTY",
}


class PairwiseComparisonError(RuntimeError):
    """Raised when a pairwise comparison contract is invalid."""


def _text(value: object) -> str:
    """Return stripped text or an empty string."""
    if value is None:
        return ""
    return str(value).strip()


def _positive_int(value: object, field: str) -> int:
    """Return a positive integer and fail closed otherwise."""
    if isinstance(value, bool):
        raise PairwiseComparisonError(
            f"{field} must be a positive integer"
        )
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise PairwiseComparisonError(
            f"{field} must be a positive integer"
        ) from exc
    if number < 1:
        raise PairwiseComparisonError(
            f"{field} must be a positive integer"
        )
    return number


def _mapping(value: object, field: str) -> Mapping[str, object]:
    """Require a mapping."""
    if not isinstance(value, Mapping):
        raise PairwiseComparisonError(f"{field} must be an object")
    return value


def _list(value: object, field: str) -> list[object]:
    """Require a list."""
    if not isinstance(value, list):
        raise PairwiseComparisonError(f"{field} must be an array")
    return value


def semantic_sha256(value: object) -> str:
    """Return a deterministic semantic SHA-256."""
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _target_key(value: Mapping[str, object]) -> tuple[str, str, int]:
    """Return normalized target identity."""
    date_text = _text(value.get("date"))
    venue = _text(value.get("venue"))
    race_no = _positive_int(value.get("race_no"), "target.race_no")
    if not date_text:
        raise PairwiseComparisonError("target.date is required")
    if not venue:
        raise PairwiseComparisonError("target.venue is required")
    return date_text, venue, race_no


def _validate_prediction_interpretation(
    horse: Mapping[str, object],
    field: str,
) -> None:
    """Validate the deterministic pre-read required by current Pairwise."""
    interpretation = _mapping(
        horse.get("prediction_interpretation"),
        f"{field}.prediction_interpretation",
    )
    if (
        _text(interpretation.get("interpretation_version"))
        != "PredictionInterpretation-v0.1"
    ):
        raise PairwiseComparisonError(
            f"{field} has unsupported Prediction Interpretation"
        )

    raw_order = _list(
        interpretation.get("pairwise_reading_order"),
        f"{field}.prediction_interpretation.pairwise_reading_order",
    )
    order = tuple(_text(item) for item in raw_order)
    if order != LANE_ORDER:
        raise PairwiseComparisonError(
            f"{field} Interpretation reading order changed unexpectedly"
        )

    ability = _mapping(
        interpretation.get("ability_anchor"),
        f"{field}.prediction_interpretation.ability_anchor",
    )
    if ability.get("may_create_upgrade_by_itself") is not False:
        raise PairwiseComparisonError(
            f"{field} allows Ability-only upgrade"
        )
    if ability.get("may_create_downgrade_by_itself") is not False:
        raise PairwiseComparisonError(
            f"{field} allows Ability-only downgrade"
        )

    policy = _mapping(
        interpretation.get("policy"),
        f"{field}.prediction_interpretation.policy",
    )
    if policy.get("no_numeric_score") is not True:
        raise PairwiseComparisonError(
            f"{field} Interpretation must remain non-scoring"
        )


def _runner_index(
    general_evidence: Mapping[str, object],
) -> dict[int, Mapping[str, object]]:
    """Index general-evidence runners by horse number."""
    raw_horses = _list(
        general_evidence.get("horses"),
        "general_evidence.horses",
    )
    if not raw_horses:
        raise PairwiseComparisonError(
            "general evidence contains no runners"
        )

    output: dict[int, Mapping[str, object]] = {}
    for index, raw_horse in enumerate(raw_horses, start=1):
        horse = _mapping(
            raw_horse,
            f"general_evidence.horses[{index}]",
        )
        horse_no = _positive_int(
            horse.get("horse_no"),
            f"general_evidence.horses[{index}].horse_no",
        )
        _validate_prediction_interpretation(
            horse,
            f"general_evidence.horses[{index}]",
        )
        if horse_no in output:
            raise PairwiseComparisonError(
                f"duplicate horse_no in general evidence: {horse_no}"
            )
        output[horse_no] = horse
    return output


def _validate_general_evidence(
    general_evidence: Mapping[str, object],
) -> None:
    """Validate the upstream trend-first contract."""
    schema_version = _text(
        general_evidence.get("general_schema_version")
    )
    if schema_version != EXPECTED_GENERAL_SCHEMA:
        raise PairwiseComparisonError(
            "unsupported general evidence schema"
        )

    policy = _mapping(
        general_evidence.get("priority_policy"),
        "general_evidence.priority_policy",
    )
    relation = _text(policy.get("relation"))
    if relation != "DATA_TREND > RACEREVIEW >= ABILITY_ANCHOR":
        raise PairwiseComparisonError(
            "general evidence priority relation changed unexpectedly"
        )

    decision_order = _list(
        policy.get("decision_order"),
        "general_evidence.priority_policy.decision_order",
    )
    normalized_order = [_text(item) for item in decision_order]
    if tuple(normalized_order) != LANE_ORDER:
        raise PairwiseComparisonError(
            "general evidence decision order changed unexpectedly"
        )

    if policy.get("numeric_weights") is not None:
        raise PairwiseComparisonError(
            "numeric evidence weights are forbidden"
        )

    firewall = _mapping(
        general_evidence.get("firewall"),
        "general_evidence.firewall",
    )
    if firewall.get("current_jrdb_consensus_visible") is not False:
        raise PairwiseComparisonError(
            "current JRDB consensus must remain hidden"
        )
    if firewall.get("current_market_visible") is not False:
        raise PairwiseComparisonError(
            "current market must remain hidden"
        )
    if firewall.get("training_edge_visible") is not False:
        raise PairwiseComparisonError(
            "Training Edge must remain hidden"
        )


def _normalize_order(
    raw_order: object,
    field: str,
    runner_nos: set[int],
) -> list[int]:
    """Validate one complete runner order."""
    values = _list(raw_order, field)
    output: list[int] = []

    for index, raw_value in enumerate(values, start=1):
        horse_no = _positive_int(
            raw_value,
            f"{field}[{index}]",
        )
        output.append(horse_no)

    if len(output) != len(set(output)):
        raise PairwiseComparisonError(
            f"{field} contains duplicate horse numbers"
        )
    if set(output) != runner_nos:
        raise PairwiseComparisonError(
            f"{field} must contain every runner exactly once"
        )
    return output


def _pair_key(horse_a: int, horse_b: int) -> tuple[int, int]:
    """Return orientation-independent pair identity."""
    if horse_a == horse_b:
        raise PairwiseComparisonError(
            "pair cannot compare a horse with itself"
        )
    if horse_a < horse_b:
        return horse_a, horse_b
    return horse_b, horse_a


def required_pair_keys(
    final_order: list[int],
) -> set[tuple[int, int]]:
    """Return the minimum direct comparisons required for one final order."""
    required: set[tuple[int, int]] = set()

    for index in range(len(final_order) - 1):
        required.add(
            _pair_key(
                final_order[index],
                final_order[index + 1],
            )
        )

    if len(final_order) >= 3:
        required.add(
            _pair_key(
                final_order[0],
                final_order[2],
            )
        )
    if len(final_order) >= 4:
        required.add(
            _pair_key(
                final_order[0],
                final_order[3],
            )
        )

    return required


def _relation_for_horse(
    relation: str,
    horse_no: int,
    horse_a: int,
    horse_b: int,
) -> str:
    """Return FAVOR / OPPOSE / EVEN / UNKNOWN for one horse."""
    if relation == "EVEN":
        return "EVEN"
    if relation == "UNKNOWN":
        return "UNKNOWN"
    if relation == "A":
        if horse_no == horse_a:
            return "FAVOR"
        return "OPPOSE"
    if relation == "B":
        if horse_no == horse_b:
            return "FAVOR"
        return "OPPOSE"
    raise PairwiseComparisonError(
        f"unsupported lane relation: {relation}"
    )


def _preferred_horse(
    comparison: Mapping[str, object],
    horse_a: int,
    horse_b: int,
) -> int:
    """Resolve preferred horse number from A/B orientation."""
    preference = _text(comparison.get("preference")).upper()
    if preference not in PREFERENCES:
        raise PairwiseComparisonError(
            "comparison.preference must be A or B"
        )
    if preference == "A":
        return horse_a
    return horse_b


def _validate_lane_judgment(
    value: object,
    field: str,
) -> dict[str, object]:
    """Validate one concise lane judgment."""
    lane = _mapping(value, field)
    relation = _text(lane.get("relation")).upper()
    if relation not in RELATIONS:
        raise PairwiseComparisonError(
            f"{field}.relation is invalid"
        )

    summary = _text(lane.get("summary"))
    if not summary:
        raise PairwiseComparisonError(
            f"{field}.summary is required"
        )

    codes: list[str] = []
    raw_codes = lane.get("evidence_codes")
    if raw_codes is not None:
        for raw_code in _list(
            raw_codes,
            f"{field}.evidence_codes",
        ):
            code = _text(raw_code)
            if code and code not in codes:
                codes.append(code)

    refs: list[str] = []
    raw_refs = lane.get("source_refs")
    if raw_refs is not None:
        for raw_ref in _list(
            raw_refs,
            f"{field}.source_refs",
        ):
            ref = _text(raw_ref)
            if ref and ref not in refs:
                refs.append(ref)

    return {
        "relation": relation,
        "summary": summary,
        "evidence_codes": codes,
        "source_refs": refs,
    }


def _needs_lower_priority_override(
    preferred_horse: int,
    horse_a: int,
    horse_b: int,
    lane_judgments: Mapping[str, Mapping[str, object]],
    decisive_lane: str,
) -> tuple[bool, list[str]]:
    """Detect protected higher-priority evidence that favors the loser.

    DATA_TREND is always protected unless it is itself decisive.
    RACEREVIEW is also protected when the declared decision is based on the
    lower ABILITY_ANCHOR lane.  MIXED / UNCERTAINTY decisions must still
    explain choosing against either DATA_TREND or RACEREVIEW so those labels
    cannot be used to bypass the trend-first policy.
    """
    protected_lanes: list[str] = []

    if decisive_lane == "DATA_TREND":
        protected_lanes = []
    elif decisive_lane == "RACEREVIEW":
        protected_lanes = ["DATA_TREND"]
    elif decisive_lane == "ABILITY_ANCHOR":
        protected_lanes = ["DATA_TREND", "RACEREVIEW"]
    else:
        protected_lanes = ["DATA_TREND", "RACEREVIEW"]

    contrary_lanes: list[str] = []
    for lane_name in protected_lanes:
        lane = lane_judgments[lane_name]
        relation = _text(lane.get("relation")).upper()
        stance = _relation_for_horse(
            relation,
            preferred_horse,
            horse_a,
            horse_b,
        )
        if stance == "OPPOSE":
            contrary_lanes.append(lane_name)

    return bool(contrary_lanes), contrary_lanes


def _validate_comparison(
    raw: object,
    field: str,
    runner_nos: set[int],
) -> dict[str, object]:
    """Validate one authored pairwise comparison."""
    comparison = _mapping(raw, field)
    horse_a = _positive_int(
        comparison.get("horse_a"),
        f"{field}.horse_a",
    )
    horse_b = _positive_int(
        comparison.get("horse_b"),
        f"{field}.horse_b",
    )

    if horse_a not in runner_nos or horse_b not in runner_nos:
        raise PairwiseComparisonError(
            f"{field} references an unknown runner"
        )
    pair_key = _pair_key(horse_a, horse_b)

    lane_judgments_raw = _mapping(
        comparison.get("lane_judgments"),
        f"{field}.lane_judgments",
    )
    lane_judgments: dict[str, dict[str, object]] = {}

    for lane_name in LANE_ORDER:
        if lane_name not in lane_judgments_raw:
            raise PairwiseComparisonError(
                f"{field}.lane_judgments missing {lane_name}"
            )
        lane_judgments[lane_name] = _validate_lane_judgment(
            lane_judgments_raw[lane_name],
            f"{field}.lane_judgments.{lane_name}",
        )

    extra_lanes = {
        _text(key)
        for key in lane_judgments_raw.keys()
    } - set(LANE_ORDER)
    if extra_lanes:
        raise PairwiseComparisonError(
            f"{field}.lane_judgments has unsupported lanes: "
            f"{sorted(extra_lanes)}"
        )

    preferred_horse = _preferred_horse(
        comparison,
        horse_a,
        horse_b,
    )

    confidence = _text(comparison.get("confidence")).upper()
    if confidence not in CONFIDENCE_VALUES:
        raise PairwiseComparisonError(
            f"{field}.confidence is invalid"
        )

    decisive_lane = _text(
        comparison.get("decisive_lane")
    ).upper()
    if decisive_lane not in DECISIVE_LANES:
        raise PairwiseComparisonError(
            f"{field}.decisive_lane is invalid"
        )

    summary = _text(comparison.get("comparison_summary"))
    if not summary:
        raise PairwiseComparisonError(
            f"{field}.comparison_summary is required"
        )

    reversal_conditions_raw = _list(
        comparison.get("reversal_conditions"),
        f"{field}.reversal_conditions",
    )
    reversal_conditions: list[str] = []
    for raw_condition in reversal_conditions_raw:
        condition = _text(raw_condition)
        if condition and condition not in reversal_conditions:
            reversal_conditions.append(condition)
    if not reversal_conditions:
        raise PairwiseComparisonError(
            f"{field}.reversal_conditions requires at least one item"
        )

    detected_override, contrary_lanes = _needs_lower_priority_override(
        preferred_horse,
        horse_a,
        horse_b,
        lane_judgments,
        decisive_lane,
    )

    declared_override = comparison.get("lower_priority_override")
    if not isinstance(declared_override, bool):
        raise PairwiseComparisonError(
            f"{field}.lower_priority_override must be boolean"
        )
    if declared_override != detected_override:
        raise PairwiseComparisonError(
            f"{field}.lower_priority_override must equal "
            f"detected override status {detected_override}"
        )

    override_reason = _text(comparison.get("override_reason"))
    if detected_override and not override_reason:
        raise PairwiseComparisonError(
            f"{field}.override_reason is required because "
            f"{decisive_lane} overrides {contrary_lanes}"
        )
    if not detected_override and override_reason:
        raise PairwiseComparisonError(
            f"{field}.override_reason must be blank when no "
            "lower-priority override is detected"
        )

    return {
        "pair_key": pair_key,
        "horse_a": horse_a,
        "horse_b": horse_b,
        "preference": _text(
            comparison.get("preference")
        ).upper(),
        "preferred_horse_no": preferred_horse,
        "confidence": confidence,
        "decisive_lane": decisive_lane,
        "lane_judgments": lane_judgments,
        "lower_priority_override": detected_override,
        "contrary_higher_priority_lanes": contrary_lanes,
        "override_reason": override_reason,
        "comparison_summary": summary,
        "reversal_conditions": reversal_conditions,
    }


def _order_position(order: list[int]) -> dict[int, int]:
    """Return 1-based rank positions."""
    output: dict[int, int] = {}
    for index, horse_no in enumerate(order, start=1):
        output[horse_no] = index
    return output


def _change_audit(
    draft_order: list[int],
    final_order: list[int],
) -> list[dict[str, object]]:
    """Record order movement without explaining it post hoc."""
    draft_positions = _order_position(draft_order)
    final_positions = _order_position(final_order)

    output: list[dict[str, object]] = []
    for horse_no in final_order:
        draft_rank = draft_positions[horse_no]
        final_rank = final_positions[horse_no]
        if draft_rank == final_rank:
            continue
        output.append(
            {
                "horse_no": horse_no,
                "draft_rank": draft_rank,
                "final_rank": final_rank,
                "movement": draft_rank - final_rank,
            }
        )
    return output


def validate_pairwise_comparison(
    general_evidence: Mapping[str, object],
    payload: Mapping[str, object],
) -> dict[str, object]:
    """Validate an authored pairwise comparison and return an audit record."""
    _validate_general_evidence(general_evidence)
    runner_index = _runner_index(general_evidence)
    runner_nos = set(runner_index)

    schema_version = _text(payload.get("pairwise_schema_version"))
    if schema_version != PAIRWISE_SCHEMA_VERSION:
        raise PairwiseComparisonError(
            "unsupported pairwise schema version"
        )
    contract_version = _text(
        payload.get("pairwise_contract_version")
    )
    if contract_version != PAIRWISE_CONTRACT_VERSION:
        raise PairwiseComparisonError(
            "unsupported pairwise contract version"
        )

    expected_hash = semantic_sha256(general_evidence)
    actual_hash = _text(payload.get("general_evidence_sha256"))
    if actual_hash.lower() != expected_hash:
        raise PairwiseComparisonError(
            "general evidence semantic hash mismatch"
        )

    general_target = _mapping(
        general_evidence.get("target"),
        "general_evidence.target",
    )
    payload_target = _mapping(
        payload.get("target"),
        "payload.target",
    )
    if _target_key(general_target) != _target_key(payload_target):
        raise PairwiseComparisonError(
            "pairwise target does not match general evidence"
        )

    draft_order = _normalize_order(
        payload.get("draft_order"),
        "payload.draft_order",
        runner_nos,
    )
    final_order = _normalize_order(
        payload.get("final_order"),
        "payload.final_order",
        runner_nos,
    )

    raw_comparisons = _list(
        payload.get("comparisons"),
        "payload.comparisons",
    )
    if not raw_comparisons:
        raise PairwiseComparisonError(
            "pairwise comparisons are required"
        )

    comparisons: list[dict[str, object]] = []
    by_pair: dict[tuple[int, int], dict[str, object]] = {}
    for index, raw_comparison in enumerate(
        raw_comparisons,
        start=1,
    ):
        comparison = _validate_comparison(
            raw_comparison,
            f"payload.comparisons[{index}]",
            runner_nos,
        )
        pair_key = comparison["pair_key"]
        if pair_key in by_pair:
            raise PairwiseComparisonError(
                f"duplicate pairwise comparison: {pair_key}"
            )
        by_pair[pair_key] = comparison
        comparisons.append(comparison)

    required = required_pair_keys(final_order)
    missing = sorted(required - set(by_pair))
    if missing:
        raise PairwiseComparisonError(
            f"missing required pairwise comparisons: {missing}"
        )

    final_position = _order_position(final_order)
    wrong_winners: list[dict[str, object]] = []

    for pair_key in sorted(required):
        comparison = by_pair[pair_key]
        horse_a = int(comparison["horse_a"])
        horse_b = int(comparison["horse_b"])
        preferred = int(comparison["preferred_horse_no"])

        higher = horse_a
        if final_position[horse_b] < final_position[horse_a]:
            higher = horse_b
        if preferred != higher:
            wrong_winners.append(
                {
                    "pair_key": list(pair_key),
                    "preferred_horse_no": preferred,
                    "higher_final_horse_no": higher,
                }
            )

    if wrong_winners:
        raise PairwiseComparisonError(
            "required comparison preference conflicts with final order: "
            f"{wrong_winners}"
        )

    final_summary = _text(payload.get("final_order_summary"))
    if not final_summary:
        raise PairwiseComparisonError(
            "payload.final_order_summary is required"
        )

    comparison_records: list[dict[str, object]] = []
    override_count = 0
    for comparison in comparisons:
        record = dict(comparison)
        record["pair_key"] = list(record["pair_key"])
        if bool(record["lower_priority_override"]):
            override_count += 1
        comparison_records.append(record)

    return {
        "audit_schema_version": "RaceNote-Pairwise-Audit-0.1",
        "status": "PASS",
        "pairwise_schema_version": PAIRWISE_SCHEMA_VERSION,
        "pairwise_contract_version": PAIRWISE_CONTRACT_VERSION,
        "general_evidence_sha256": expected_hash,
        "target": {
            "date": _text(payload_target.get("date")),
            "venue": _text(payload_target.get("venue")),
            "race_no": _positive_int(
                payload_target.get("race_no"),
                "payload.target.race_no",
            ),
            "race_name": _text(payload_target.get("race_name")),
        },
        "policy": {
            "priority_relation": (
                "DATA_TREND > RACEREVIEW >= ABILITY_ANCHOR"
            ),
            "numeric_score_used": False,
            "market_visible": False,
            "jrdb_current_consensus_visible": False,
            "training_edge_visible": False,
            "adjacent_pair_coverage_required": True,
            "top_challenger_direct_comparison_required": True,
            "reversal_condition_required": True,
            "lower_priority_override_reason_required": True,
        },
        "draft_order": draft_order,
        "final_order": final_order,
        "order_changes": _change_audit(
            draft_order,
            final_order,
        ),
        "required_pair_keys": [
            list(pair_key)
            for pair_key in sorted(required)
        ],
        "comparison_count": len(comparisons),
        "lower_priority_override_count": override_count,
        "comparisons": comparison_records,
        "final_order_summary": final_summary,
        "next_stage": {
            "name": "SCENARIO_ROBUSTNESS",
            "status": "READY",
        },
    }


def _validated_synthesis_draft(
    general_evidence: Mapping[str, object],
    synthesis_audit: Mapping[str, object],
) -> tuple[list[int], list[dict[str, object]]]:
    """Validate All-Runner Synthesis audit as the canonical draft source."""
    if (
        _text(synthesis_audit.get("audit_schema_version"))
        != "RaceNote-All-Runner-Synthesis-Audit-0.1"
    ):
        raise PairwiseComparisonError(
            "unsupported All-Runner Synthesis audit"
        )
    if _text(synthesis_audit.get("status")) != "PASS":
        raise PairwiseComparisonError(
            "All-Runner Synthesis audit must PASS"
        )

    expected_hash = semantic_sha256(general_evidence)
    if (
        _text(synthesis_audit.get("general_evidence_sha256")).lower()
        != expected_hash
    ):
        raise PairwiseComparisonError(
            "All-Runner Synthesis is not bound to General Evidence"
        )

    general_target = _mapping(
        general_evidence.get("target"),
        "general_evidence.target",
    )
    synthesis_target = _mapping(
        synthesis_audit.get("target"),
        "synthesis.target",
    )
    if _target_key(general_target) != _target_key(synthesis_target):
        raise PairwiseComparisonError(
            "All-Runner Synthesis target mismatch"
        )

    policy = _mapping(
        synthesis_audit.get("policy"),
        "synthesis.policy",
    )
    if policy.get("numeric_score_used") is not False:
        raise PairwiseComparisonError(
            "All-Runner Synthesis numeric score is forbidden"
        )
    if policy.get("current_market_visible") is not False:
        raise PairwiseComparisonError(
            "All-Runner Synthesis must keep market hidden"
        )
    if (
        policy.get("current_jrdb_consensus_visible")
        is not False
    ):
        raise PairwiseComparisonError(
            "All-Runner Synthesis must keep JRDB consensus hidden"
        )
    if policy.get("training_edge_visible") is not False:
        raise PairwiseComparisonError(
            "All-Runner Synthesis must keep Training Edge hidden"
        )
    if policy.get("ability_may_be_primary_basis") is not False:
        raise PairwiseComparisonError(
            "All-Runner Synthesis cannot be Ability-first"
        )
    if policy.get("pairwise_required_after_synthesis") is not True:
        raise PairwiseComparisonError(
            "All-Runner Synthesis must require Pairwise"
        )

    runner_nos = set(_runner_index(general_evidence))
    draft_order = _normalize_order(
        synthesis_audit.get("draft_order"),
        "synthesis.draft_order",
        runner_nos,
    )

    raw_boundaries = _list(
        synthesis_audit.get("high_priority_boundaries", []),
        "synthesis.high_priority_boundaries",
    )
    boundaries: list[dict[str, object]] = []
    adjacent = {
        _pair_key(draft_order[index], draft_order[index + 1])
        for index in range(len(draft_order) - 1)
    }
    for index, raw_boundary in enumerate(raw_boundaries, start=1):
        boundary = _mapping(
            raw_boundary,
            f"synthesis.high_priority_boundaries[{index}]",
        )
        upper = _positive_int(
            boundary.get("upper_horse_no"),
            f"synthesis.high_priority_boundaries[{index}].upper_horse_no",
        )
        lower = _positive_int(
            boundary.get("lower_horse_no"),
            f"synthesis.high_priority_boundaries[{index}].lower_horse_no",
        )
        if _pair_key(upper, lower) not in adjacent:
            raise PairwiseComparisonError(
                "high-priority synthesis boundary must be adjacent"
            )
        raw_codes = boundary.get("priority_reason_codes", [])
        reason_codes = [
            _text(value)
            for value in _list(
                raw_codes,
                f"synthesis.high_priority_boundaries[{index}].priority_reason_codes",
            )
            if _text(value)
        ]
        boundaries.append(
            {
                "upper_horse_no": upper,
                "lower_horse_no": lower,
                "priority_reason_codes": reason_codes,
            }
        )

    return draft_order, boundaries


def build_comparison_request_from_synthesis(
    general_evidence: Mapping[str, object],
    synthesis_audit: Mapping[str, object],
) -> dict[str, object]:
    """Build the canonical Pairwise request from audited full-field synthesis."""
    draft_order, high_priority_boundaries = _validated_synthesis_draft(
        general_evidence,
        synthesis_audit,
    )
    request = build_comparison_request(
        general_evidence,
        draft_order,
    )

    high_priority_pairs = {
        _pair_key(
            int(item["upper_horse_no"]),
            int(item["lower_horse_no"]),
        )
        for item in high_priority_boundaries
    }
    for pair in request["required_pairs_for_draft"]:
        key = _pair_key(
            int(pair["horse_a"]),
            int(pair["horse_b"]),
        )
        pair["comparison_priority"] = (
            "HIGH"
            if key in high_priority_pairs
            else "STANDARD"
        )

    request["all_runner_synthesis_sha256"] = semantic_sha256(
        synthesis_audit
    )
    request["draft_source"] = {
        "kind": "ALL_RUNNER_SYNTHESIS",
        "audit_schema_version": _text(
            synthesis_audit.get("audit_schema_version")
        ),
        "high_priority_boundaries": copy.deepcopy(
            high_priority_boundaries
        ),
    }
    request["instructions"][
        "draft_order_must_not_be_reauthored"
    ] = True
    request["instructions"][
        "high_priority_boundaries_require_explicit_attention"
    ] = True
    return request


def build_comparison_request(
    general_evidence: Mapping[str, object],
    draft_order: list[int],
) -> dict[str, object]:
    """Build a compact authored-comparison request skeleton."""
    _validate_general_evidence(general_evidence)
    runner_index = _runner_index(general_evidence)
    runner_nos = set(runner_index)
    normalized_order = _normalize_order(
        draft_order,
        "draft_order",
        runner_nos,
    )

    pairs = required_pair_keys(normalized_order)
    pair_requests: list[dict[str, object]] = []

    for horse_a, horse_b in sorted(pairs):
        pair_requests.append(
            {
                "horse_a": horse_a,
                "horse_b": horse_b,
                "horse_a_name": _text(
                    runner_index[horse_a].get("horse_name")
                ),
                "horse_b_name": _text(
                    runner_index[horse_b].get("horse_name")
                ),
                "horse_a_interpretation": copy.deepcopy(
                    runner_index[horse_a].get(
                        "prediction_interpretation",
                        {},
                    )
                ),
                "horse_b_interpretation": copy.deepcopy(
                    runner_index[horse_b].get(
                        "prediction_interpretation",
                        {},
                    )
                ),
                "required_lane_order": list(LANE_ORDER),
                "author_fields": {
                    "lane_judgments": {
                        "DATA_TREND": {
                            "relation": None,
                            "summary": None,
                            "evidence_codes": [],
                            "source_refs": [],
                        },
                        "RACEREVIEW": {
                            "relation": None,
                            "summary": None,
                            "evidence_codes": [],
                            "source_refs": [],
                        },
                        "ABILITY_ANCHOR": {
                            "relation": None,
                            "summary": None,
                            "evidence_codes": [],
                            "source_refs": [],
                        },
                    },
                    "preference": None,
                    "confidence": None,
                    "decisive_lane": None,
                    "lower_priority_override": None,
                    "override_reason": None,
                    "comparison_summary": None,
                    "reversal_conditions": [],
                },
            }
        )

    target = _mapping(
        general_evidence.get("target"),
        "general_evidence.target",
    )

    return {
        "request_schema_version": "RaceNote-Pairwise-Request-0.1",
        "pairwise_schema_version": PAIRWISE_SCHEMA_VERSION,
        "pairwise_contract_version": PAIRWISE_CONTRACT_VERSION,
        "general_evidence_sha256": semantic_sha256(
            general_evidence
        ),
        "target": {
            "date": _text(target.get("date")),
            "venue": _text(target.get("venue")),
            "race_no": _positive_int(
                target.get("race_no"),
                "target.race_no",
            ),
            "race_name": _text(target.get("race_name")),
        },
        "draft_order": normalized_order,
        "required_pairs_for_draft": pair_requests,
        "instructions": {
            "read_order": list(LANE_ORDER),
            "use_prediction_interpretation_first": True,
            "verify_interpretation_against_evidence_lanes": True,
            "do_not_score": True,
            "do_not_use_market": True,
            "do_not_use_current_jrdb_consensus": True,
            "record_reversal_condition": True,
            "if_final_order_changes_revalidate_required_pairs": True,
        },
    }


def main() -> int:
    """Validate one authored Pairwise Comparison payload."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--general-evidence",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--comparison",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output-audit",
        type=Path,
        required=True,
    )
    args = parser.parse_args()

    general_evidence = json.loads(
        args.general_evidence.read_text(encoding="utf-8")
    )
    comparison = json.loads(
        args.comparison.read_text(encoding="utf-8")
    )
    audit = validate_pairwise_comparison(
        general_evidence,
        comparison,
    )

    args.output_audit.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    args.output_audit.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": audit["status"],
                "comparison_count": audit["comparison_count"],
                "lower_priority_override_count": audit[
                    "lower_priority_override_count"
                ],
                "output": str(args.output_audit),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
