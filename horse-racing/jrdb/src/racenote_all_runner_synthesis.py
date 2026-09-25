#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate RaceNote All-Runner Synthesis v0.1.

This layer sits between Prediction Interpretation and Pairwise Comparison.
It does not calculate a score or choose an order automatically. GPT authors a
full-field draft order after reading every runner. The validator makes that
draft auditable and prevents unsupported / Ability-only ordering.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

SYNTHESIS_SCHEMA_VERSION = "RaceNote-All-Runner-Synthesis-0.1"
SYNTHESIS_CONTRACT_VERSION = "FullField-Draft-v0.1"
EXPECTED_GENERAL_SCHEMA = "RaceNote-General-Evidence-0.1"
EXPECTED_INTERPRETATION_VERSION = "PredictionInterpretation-v0.1"

PRIMARY_LANES = {
    "DATA_TREND",
    "RACEREVIEW",
    "MIXED",
    "UNCERTAINTY",
}
CONFIDENCE_VALUES = {"LOW", "MEDIUM", "HIGH"}
BOUNDARY_PRIORITIES = {"STANDARD", "HIGH"}


class AllRunnerSynthesisError(RuntimeError):
    """Raised when All-Runner Synthesis violates the contract."""


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AllRunnerSynthesisError(f"{field} must be an object")
    return value


def _list(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise AllRunnerSynthesisError(f"{field} must be an array")
    return value


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise AllRunnerSynthesisError(
            f"{field} must be a positive integer"
        )
    try:
        number = int(value)
        raw = float(value)
    except (TypeError, ValueError) as exc:
        raise AllRunnerSynthesisError(
            f"{field} must be a positive integer"
        ) from exc
    if number < 1 or raw != number:
        raise AllRunnerSynthesisError(
            f"{field} must be a positive integer"
        )
    return number


def semantic_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _target_key(target: Mapping[str, object]) -> tuple[str, str, int]:
    date_text = _text(target.get("date"))
    venue = _text(target.get("venue"))
    race_no = _positive_int(target.get("race_no"), "target.race_no")
    if not date_text or not venue:
        raise AllRunnerSynthesisError(
            "target date and venue are required"
        )
    return date_text, venue, race_no


def _validate_general(
    general: Mapping[str, object],
) -> dict[int, Mapping[str, object]]:
    if (
        _text(general.get("general_schema_version"))
        != EXPECTED_GENERAL_SCHEMA
    ):
        raise AllRunnerSynthesisError(
            "unsupported General Evidence schema"
        )

    firewall = _mapping(
        general.get("firewall"),
        "general.firewall",
    )
    if firewall.get("current_market_visible") is not False:
        raise AllRunnerSynthesisError(
            "market must remain hidden"
        )
    if (
        firewall.get("current_jrdb_consensus_visible")
        is not False
    ):
        raise AllRunnerSynthesisError(
            "current JRDB consensus must remain hidden"
        )
    if firewall.get("training_edge_visible") is not False:
        raise AllRunnerSynthesisError(
            "Training Edge must remain hidden"
        )

    result: dict[int, Mapping[str, object]] = {}
    raw_horses = _list(general.get("horses"), "general.horses")
    if not raw_horses:
        raise AllRunnerSynthesisError(
            "General Evidence contains no horses"
        )

    for index, raw_horse in enumerate(raw_horses, start=1):
        horse = _mapping(
            raw_horse,
            f"general.horses[{index}]",
        )
        horse_no = _positive_int(
            horse.get("horse_no"),
            f"general.horses[{index}].horse_no",
        )
        if horse_no in result:
            raise AllRunnerSynthesisError(
                f"duplicate General Evidence horse_no={horse_no}"
            )
        interpretation = _mapping(
            horse.get("prediction_interpretation"),
            f"general.horses[{index}].prediction_interpretation",
        )
        if (
            _text(interpretation.get("interpretation_version"))
            != EXPECTED_INTERPRETATION_VERSION
        ):
            raise AllRunnerSynthesisError(
                f"horse_no={horse_no} has unsupported interpretation"
            )
        policy = _mapping(
            interpretation.get("policy"),
            f"general.horses[{index}].prediction_interpretation.policy",
        )
        if policy.get("no_numeric_score") is not True:
            raise AllRunnerSynthesisError(
                "Prediction Interpretation must remain non-scoring"
            )
        if (
            policy.get("final_upgrade_or_downgrade_requires_pairwise")
            is not True
        ):
            raise AllRunnerSynthesisError(
                "Pairwise boundary policy changed unexpectedly"
            )
        result[horse_no] = horse

    return result


def _unique_strings(
    raw: object,
    field: str,
) -> list[str]:
    output: list[str] = []
    for raw_value in _list(raw, field):
        value = _text(raw_value)
        if value and value not in output:
            output.append(value)
    return output


def _interpretation_components(
    general_horse: Mapping[str, object],
) -> tuple[set[str], set[str]]:
    interpretation = _mapping(
        general_horse.get("prediction_interpretation"),
        "general_horse.prediction_interpretation",
    )
    positives = {
        _text(value)
        for value in _list(
            interpretation.get("positive_case_components"),
            "prediction_interpretation.positive_case_components",
        )
        if _text(value)
    }
    concerns = {
        _text(value)
        for value in _list(
            interpretation.get("concern_case_components"),
            "prediction_interpretation.concern_case_components",
        )
        if _text(value)
    }
    return positives, concerns


def _validate_runner(
    raw: object,
    field: str,
    general_horses: Mapping[int, Mapping[str, object]],
) -> dict[str, object]:
    item = _mapping(raw, field)
    horse_no = _positive_int(
        item.get("horse_no"),
        f"{field}.horse_no",
    )
    general_horse = general_horses.get(horse_no)
    if general_horse is None:
        raise AllRunnerSynthesisError(
            f"{field} references unknown horse_no={horse_no}"
        )

    draft_rank = _positive_int(
        item.get("draft_rank"),
        f"{field}.draft_rank",
    )
    confidence = _text(item.get("confidence")).upper()
    if confidence not in CONFIDENCE_VALUES:
        raise AllRunnerSynthesisError(
            f"{field}.confidence is invalid"
        )

    primary_lane = _text(item.get("primary_lane")).upper()
    if primary_lane not in PRIMARY_LANES:
        raise AllRunnerSynthesisError(
            f"{field}.primary_lane is invalid"
        )

    positive_components = _unique_strings(
        item.get("positive_components"),
        f"{field}.positive_components",
    )
    concern_components = _unique_strings(
        item.get("concern_components"),
        f"{field}.concern_components",
    )
    allowed_positive, allowed_concern = _interpretation_components(
        general_horse
    )

    unknown_positive = [
        code
        for code in positive_components
        if code not in allowed_positive
    ]
    if unknown_positive:
        raise AllRunnerSynthesisError(
            f"{field} references unavailable positive components: "
            f"{unknown_positive}"
        )

    unknown_concern = [
        code
        for code in concern_components
        if code not in allowed_concern
    ]
    if unknown_concern:
        raise AllRunnerSynthesisError(
            f"{field} references unavailable concern components: "
            f"{unknown_concern}"
        )

    if primary_lane == "DATA_TREND":
        if not any(
            code.startswith("DATA_TREND_")
            for code in positive_components + concern_components
        ):
            raise AllRunnerSynthesisError(
                f"{field} DATA_TREND primary lane lacks trend component"
            )
    elif primary_lane == "RACEREVIEW":
        if not any(
            code.startswith("RACEREVIEW_")
            for code in positive_components + concern_components
        ):
            raise AllRunnerSynthesisError(
                f"{field} RACEREVIEW primary lane lacks review component"
            )
    elif primary_lane == "MIXED":
        families = set()
        for code in positive_components + concern_components:
            if code.startswith("DATA_TREND_"):
                families.add("DATA_TREND")
            if code.startswith("RACEREVIEW_"):
                families.add("RACEREVIEW")
        if len(families) < 2:
            raise AllRunnerSynthesisError(
                f"{field} MIXED primary lane requires both Trend and Review"
            )

    ability_context_used = item.get("ability_context_used")
    if not isinstance(ability_context_used, bool):
        raise AllRunnerSynthesisError(
            f"{field}.ability_context_used must be boolean"
        )

    draft_reason = _text(item.get("draft_reason"))
    main_uncertainty = _text(item.get("main_uncertainty"))
    if not draft_reason:
        raise AllRunnerSynthesisError(
            f"{field}.draft_reason is required"
        )
    if not main_uncertainty:
        raise AllRunnerSynthesisError(
            f"{field}.main_uncertainty is required"
        )

    if not positive_components and not concern_components:
        if primary_lane != "UNCERTAINTY":
            raise AllRunnerSynthesisError(
                f"{field} without directional components must use UNCERTAINTY"
            )

    interpretation = _mapping(
        general_horse.get("prediction_interpretation"),
        "general_horse.prediction_interpretation",
    )
    return {
        "horse_no": horse_no,
        "horse_name": _text(general_horse.get("horse_name")),
        "draft_rank": draft_rank,
        "confidence": confidence,
        "primary_lane": primary_lane,
        "positive_components": positive_components,
        "concern_components": concern_components,
        "ability_context_used": ability_context_used,
        "draft_reason": draft_reason,
        "main_uncertainty": main_uncertainty,
        "prediction_interpretation": copy.deepcopy(
            dict(interpretation)
        ),
    }


def _derived_boundary_priority(
    upper: Mapping[str, object],
    lower: Mapping[str, object],
) -> tuple[str, list[str]]:
    reasons: list[str] = []

    if _text(upper.get("confidence")).upper() == "LOW":
        reasons.append("UPPER_LOW_CONFIDENCE")
    if _text(lower.get("confidence")).upper() == "LOW":
        reasons.append("LOWER_LOW_CONFIDENCE")

    for side, item in (("UPPER", upper), ("LOWER", lower)):
        interpretation = item.get("prediction_interpretation")
        if not isinstance(interpretation, Mapping):
            continue
        trend = interpretation.get("data_trend")
        review = interpretation.get("racereview")
        if isinstance(trend, Mapping):
            state = _text(trend.get("state")).upper()
            if state == "MIXED":
                reasons.append(f"{side}_TREND_MIXED")
            if trend.get("small_sample_only") is True:
                reasons.append(f"{side}_SMALL_SAMPLE_ONLY")
        if isinstance(review, Mapping):
            state = _text(review.get("state")).upper()
            if state in {"MIXED", "MIXED_CONTEXT_ONLY"}:
                reasons.append(f"{side}_REVIEW_MIXED")
            if (
                _text(review.get("contradiction_status")).upper()
                == "MIXED"
            ):
                reasons.append(f"{side}_REVIEW_CONTRADICTION")

    priority = "HIGH" if reasons else "STANDARD"
    return priority, reasons


def _validate_boundaries(
    raw: object,
    ordered_horses: list[dict[str, object]],
) -> list[dict[str, object]]:
    raw_boundaries = _list(raw, "boundaries")
    if len(raw_boundaries) != max(0, len(ordered_horses) - 1):
        raise AllRunnerSynthesisError(
            "boundaries must cover every adjacent draft-order pair"
        )

    expected_pairs = [
        (
            int(ordered_horses[index]["horse_no"]),
            int(ordered_horses[index + 1]["horse_no"]),
        )
        for index in range(len(ordered_horses) - 1)
    ]

    output: list[dict[str, object]] = []
    for index, raw_boundary in enumerate(raw_boundaries, start=1):
        boundary = _mapping(
            raw_boundary,
            f"boundaries[{index}]",
        )
        upper = _positive_int(
            boundary.get("upper_horse_no"),
            f"boundaries[{index}].upper_horse_no",
        )
        lower = _positive_int(
            boundary.get("lower_horse_no"),
            f"boundaries[{index}].lower_horse_no",
        )
        if (upper, lower) != expected_pairs[index - 1]:
            raise AllRunnerSynthesisError(
                "boundary pair must follow adjacent draft order"
            )

        declared = _text(
            boundary.get("comparison_priority")
        ).upper()
        if declared not in BOUNDARY_PRIORITIES:
            raise AllRunnerSynthesisError(
                f"boundaries[{index}].comparison_priority is invalid"
            )

        derived, reasons = _derived_boundary_priority(
            ordered_horses[index - 1],
            ordered_horses[index],
        )
        if declared != derived:
            raise AllRunnerSynthesisError(
                f"boundaries[{index}] priority must be {derived}"
            )

        summary = _text(boundary.get("boundary_summary"))
        if not summary:
            raise AllRunnerSynthesisError(
                f"boundaries[{index}].boundary_summary is required"
            )

        output.append(
            {
                "upper_horse_no": upper,
                "lower_horse_no": lower,
                "comparison_priority": derived,
                "priority_reason_codes": reasons,
                "boundary_summary": summary,
            }
        )
    return output


def build_synthesis_request(
    general: Mapping[str, object],
) -> dict[str, object]:
    """Build a no-winner-chosen authoring request from General Evidence."""
    general_horses = _validate_general(general)
    target = _mapping(general.get("target"), "general.target")

    horses: list[dict[str, object]] = []
    for horse_no in sorted(general_horses):
        horse = general_horses[horse_no]
        interpretation = _mapping(
            horse.get("prediction_interpretation"),
            f"general.horse[{horse_no}].prediction_interpretation",
        )
        horses.append(
            {
                "horse_no": horse_no,
                "horse_name": _text(horse.get("horse_name")),
                "prediction_interpretation": copy.deepcopy(
                    dict(interpretation)
                ),
                "author_fields": {
                    "draft_rank": None,
                    "confidence": None,
                    "primary_lane": None,
                    "positive_components": [],
                    "concern_components": [],
                    "ability_context_used": None,
                    "draft_reason": None,
                    "main_uncertainty": None,
                },
            }
        )

    return {
        "request_schema_version": (
            "RaceNote-All-Runner-Synthesis-Request-0.1"
        ),
        "synthesis_schema_version": SYNTHESIS_SCHEMA_VERSION,
        "synthesis_contract_version": SYNTHESIS_CONTRACT_VERSION,
        "general_evidence_sha256": semantic_sha256(general),
        "target": {
            "date": _text(target.get("date")),
            "venue": _text(target.get("venue")),
            "race_no": _positive_int(
                target.get("race_no"),
                "target.race_no",
            ),
            "race_name": _text(target.get("race_name")),
        },
        "race_data_context": copy.deepcopy(
            general.get("race_data_context", {})
        ),
        "race_structure": copy.deepcopy(
            general.get("race_structure", {})
        ),
        "horses": horses,
        "author_fields": {
            "boundaries": [],
            "draft_order_summary": None,
        },
        "instructions": {
            "read_every_runner_before_ranking": True,
            "reading_order": [
                "DATA_TREND",
                "RACEREVIEW",
                "ABILITY_ANCHOR",
            ],
            "do_not_score": True,
            "do_not_count_positive_components_as_votes": True,
            "ability_cannot_be_primary_lane": True,
            "preserve_mixed_and_uncertainty": True,
            "complete_rank_1_to_n_required": True,
            "build_every_adjacent_boundary_after_ranking": True,
            "draft_order_is_not_final_forecast": True,
            "pairwise_required_next": True,
            "do_not_use_market": True,
            "do_not_use_current_jrdb_consensus": True,
            "do_not_use_training_edge": True,
        },
    }


def validate_all_runner_synthesis(
    general: Mapping[str, object],
    payload: Mapping[str, object],
) -> dict[str, object]:
    """Validate one GPT-authored full-field draft ordering."""
    general_horses = _validate_general(general)
    runners = set(general_horses)

    if (
        _text(payload.get("synthesis_schema_version"))
        != SYNTHESIS_SCHEMA_VERSION
    ):
        raise AllRunnerSynthesisError(
            "unsupported synthesis schema version"
        )
    if (
        _text(payload.get("synthesis_contract_version"))
        != SYNTHESIS_CONTRACT_VERSION
    ):
        raise AllRunnerSynthesisError(
            "unsupported synthesis contract version"
        )

    expected_hash = semantic_sha256(general)
    if (
        _text(payload.get("general_evidence_sha256")).lower()
        != expected_hash
    ):
        raise AllRunnerSynthesisError(
            "General Evidence semantic hash mismatch"
        )

    general_target = _mapping(
        general.get("target"),
        "general.target",
    )
    payload_target = _mapping(
        payload.get("target"),
        "payload.target",
    )
    if _target_key(general_target) != _target_key(payload_target):
        raise AllRunnerSynthesisError(
            "synthesis target does not match General Evidence"
        )

    raw_horses = _list(payload.get("horses"), "payload.horses")
    horses = [
        _validate_runner(
            raw_horse,
            f"payload.horses[{index}]",
            general_horses,
        )
        for index, raw_horse in enumerate(raw_horses, start=1)
    ]
    if len(horses) != len(runners):
        raise AllRunnerSynthesisError(
            "synthesis must contain every runner"
        )
    if {int(horse["horse_no"]) for horse in horses} != runners:
        raise AllRunnerSynthesisError(
            "synthesis runner coverage mismatch"
        )

    ranks = [int(horse["draft_rank"]) for horse in horses]
    if len(ranks) != len(set(ranks)):
        raise AllRunnerSynthesisError(
            "draft ranks must be unique"
        )
    expected_ranks = set(range(1, len(horses) + 1))
    if set(ranks) != expected_ranks:
        raise AllRunnerSynthesisError(
            "draft ranks must be contiguous from 1 to runner count"
        )

    ordered = sorted(
        horses,
        key=lambda horse: int(horse["draft_rank"]),
    )
    draft_order = [
        int(horse["horse_no"])
        for horse in ordered
    ]

    boundaries = _validate_boundaries(
        payload.get("boundaries"),
        ordered,
    )

    summary = _text(payload.get("draft_order_summary"))
    if not summary:
        raise AllRunnerSynthesisError(
            "draft_order_summary is required"
        )

    high_priority_boundaries = [
        {
            "upper_horse_no": item["upper_horse_no"],
            "lower_horse_no": item["lower_horse_no"],
            "priority_reason_codes": item["priority_reason_codes"],
        }
        for item in boundaries
        if item["comparison_priority"] == "HIGH"
    ]

    return {
        "audit_schema_version": "RaceNote-All-Runner-Synthesis-Audit-0.1",
        "status": "PASS",
        "synthesis_schema_version": SYNTHESIS_SCHEMA_VERSION,
        "synthesis_contract_version": SYNTHESIS_CONTRACT_VERSION,
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
            "numeric_score_used": False,
            "current_market_visible": False,
            "current_jrdb_consensus_visible": False,
            "training_edge_visible": False,
            "ability_may_be_primary_basis": False,
            "draft_order_is_final_forecast": False,
            "pairwise_required_after_synthesis": True,
        },
        "draft_order": draft_order,
        "horses": ordered,
        "boundaries": boundaries,
        "high_priority_boundaries": high_priority_boundaries,
        "draft_order_summary": summary,
        "next_stage": {
            "name": "PAIRWISE_COMPARISON",
            "status": "READY",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--general-evidence",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--synthesis",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output-audit",
        type=Path,
        required=True,
    )
    args = parser.parse_args()

    general = json.loads(
        args.general_evidence.read_text(encoding="utf-8")
    )
    payload = json.loads(
        args.synthesis.read_text(encoding="utf-8")
    )
    audit = validate_all_runner_synthesis(
        general,
        payload,
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
                "runner_count": len(audit["draft_order"]),
                "high_priority_boundary_count": len(
                    audit["high_priority_boundaries"]
                ),
                "output": str(args.output_audit),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
