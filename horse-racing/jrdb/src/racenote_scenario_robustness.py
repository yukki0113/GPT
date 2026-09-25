#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate RaceNote Scenario Robustness v0.1.

The validator checks whether a pairwise order survives three plausible pace
scenarios: SLOW, MEDIUM, and FAST.  It does not calculate a prediction score
and does not open market/current-JRDB/Training-Edge information.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

SCENARIO_SCHEMA_VERSION = "RaceNote-Scenario-Robustness-0.1"
SCENARIO_CONTRACT_VERSION = "Pace3-Scenario-v0.1"
EXPECTED_PAIRWISE_AUDIT = "RaceNote-Pairwise-Audit-0.1"
REQUIRED_SCENARIOS = ("SLOW", "MEDIUM", "FAST")
AXIS_STATUS = {"ROBUST", "CONDITIONAL", "FRAGILE"}


class ScenarioRobustnessError(RuntimeError):
    """Raised when scenario robustness input violates the contract."""


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise ScenarioRobustnessError(
            f"{field} must be a positive integer"
        )
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ScenarioRobustnessError(
            f"{field} must be a positive integer"
        ) from exc
    if number < 1:
        raise ScenarioRobustnessError(
            f"{field} must be a positive integer"
        )
    return number


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ScenarioRobustnessError(f"{field} must be an object")
    return value


def _list(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ScenarioRobustnessError(f"{field} must be an array")
    return value


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
        raise ScenarioRobustnessError(
            "target date and venue are required"
        )
    return date_text, venue, race_no


def _validate_pairwise_audit(
    pairwise_audit: Mapping[str, object],
) -> list[int]:
    if _text(pairwise_audit.get("audit_schema_version")) != EXPECTED_PAIRWISE_AUDIT:
        raise ScenarioRobustnessError(
            "unsupported pairwise audit schema"
        )
    if _text(pairwise_audit.get("status")) != "PASS":
        raise ScenarioRobustnessError(
            "pairwise audit must be PASS"
        )

    policy = _mapping(
        pairwise_audit.get("policy"),
        "pairwise.policy",
    )
    if policy.get("numeric_score_used") is not False:
        raise ScenarioRobustnessError(
            "numeric pairwise score is forbidden"
        )
    if policy.get("market_visible") is not False:
        raise ScenarioRobustnessError(
            "market must remain hidden"
        )
    if policy.get("jrdb_current_consensus_visible") is not False:
        raise ScenarioRobustnessError(
            "current JRDB consensus must remain hidden"
        )
    if policy.get("training_edge_visible") is not False:
        raise ScenarioRobustnessError(
            "Training Edge must remain hidden"
        )

    raw_order = _list(
        pairwise_audit.get("final_order"),
        "pairwise.final_order",
    )
    order: list[int] = []
    for index, raw_value in enumerate(raw_order, start=1):
        order.append(
            _positive_int(
                raw_value,
                f"pairwise.final_order[{index}]",
            )
        )
    if not order or len(order) != len(set(order)):
        raise ScenarioRobustnessError(
            "pairwise final order must contain unique runners"
        )
    return order


def _normalize_complete_order(
    raw_order: object,
    field: str,
    runners: set[int],
) -> list[int]:
    values = _list(raw_order, field)
    order: list[int] = []
    for index, raw_value in enumerate(values, start=1):
        order.append(
            _positive_int(
                raw_value,
                f"{field}[{index}]",
            )
        )
    if len(order) != len(set(order)):
        raise ScenarioRobustnessError(
            f"{field} contains duplicate runners"
        )
    if set(order) != runners:
        raise ScenarioRobustnessError(
            f"{field} must contain every runner exactly once"
        )
    return order


def _unique_strings(
    raw: object,
    field: str,
    allow_empty: bool,
) -> list[str]:
    values = _list(raw, field)
    output: list[str] = []
    for raw_value in values:
        value = _text(raw_value)
        if value and value not in output:
            output.append(value)
    if not allow_empty and not output:
        raise ScenarioRobustnessError(
            f"{field} requires at least one item"
        )
    return output


def _validate_scenario(
    raw: object,
    field: str,
    runners: set[int],
    base_order: list[int],
) -> dict[str, object]:
    scenario = _mapping(raw, field)
    scenario_id = _text(scenario.get("scenario_id")).upper()
    if scenario_id not in REQUIRED_SCENARIOS:
        raise ScenarioRobustnessError(
            f"{field}.scenario_id is unsupported"
        )

    pace = _text(scenario.get("pace")).upper()
    if pace != scenario_id:
        raise ScenarioRobustnessError(
            f"{field}.pace must equal scenario_id"
        )

    order = _normalize_complete_order(
        scenario.get("order"),
        f"{field}.order",
        runners,
    )

    declared_changed = scenario.get("changed_from_pairwise")
    if not isinstance(declared_changed, bool):
        raise ScenarioRobustnessError(
            f"{field}.changed_from_pairwise must be boolean"
        )
    actual_changed = order != base_order
    if declared_changed != actual_changed:
        raise ScenarioRobustnessError(
            f"{field}.changed_from_pairwise is inconsistent"
        )

    summary = _text(scenario.get("scenario_summary"))
    if not summary:
        raise ScenarioRobustnessError(
            f"{field}.scenario_summary is required"
        )

    reason_codes = _unique_strings(
        scenario.get("key_reason_codes"),
        f"{field}.key_reason_codes",
        False,
    )
    reversal_conditions = _unique_strings(
        scenario.get("triggered_reversal_conditions"),
        f"{field}.triggered_reversal_conditions",
        True,
    )
    if actual_changed and not reversal_conditions:
        raise ScenarioRobustnessError(
            f"{field} changed order but has no triggered reversal condition"
        )

    return {
        "scenario_id": scenario_id,
        "pace": pace,
        "assumption_summary": _text(
            scenario.get("assumption_summary")
        ),
        "order": order,
        "changed_from_pairwise": actual_changed,
        "scenario_summary": summary,
        "key_reason_codes": reason_codes,
        "triggered_reversal_conditions": reversal_conditions,
    }


def _rank_map(order: list[int]) -> dict[int, int]:
    output: dict[int, int] = {}
    for rank, horse_no in enumerate(order, start=1):
        output[horse_no] = rank
    return output


def _axis_status(axis_wins: int) -> str:
    if axis_wins == 3:
        return "ROBUST"
    if axis_wins == 2:
        return "CONDITIONAL"
    return "FRAGILE"


def _horse_sensitivity(
    base_order: list[int],
    scenarios: list[dict[str, object]],
) -> list[dict[str, object]]:
    base_ranks = _rank_map(base_order)
    scenario_maps: dict[str, dict[int, int]] = {}
    for scenario in scenarios:
        scenario_maps[str(scenario["scenario_id"])] = _rank_map(
            list(scenario["order"])
        )

    output: list[dict[str, object]] = []
    for horse_no in base_order:
        ranks: dict[str, int] = {}
        values: list[int] = []
        for scenario_id in REQUIRED_SCENARIOS:
            rank = scenario_maps[scenario_id][horse_no]
            ranks[scenario_id] = rank
            values.append(rank)

        output.append(
            {
                "horse_no": horse_no,
                "pairwise_rank": base_ranks[horse_no],
                "scenario_ranks": ranks,
                "best_rank": min(values),
                "worst_rank": max(values),
                "rank_span": max(values) - min(values),
            }
        )
    return output


def validate_scenario_robustness(
    pairwise_audit: Mapping[str, object],
    payload: Mapping[str, object],
) -> dict[str, object]:
    """Validate authored SLOW/MEDIUM/FAST scenario analysis."""
    base_order = _validate_pairwise_audit(pairwise_audit)
    runners = set(base_order)

    if _text(payload.get("scenario_schema_version")) != SCENARIO_SCHEMA_VERSION:
        raise ScenarioRobustnessError(
            "unsupported scenario schema version"
        )
    if _text(payload.get("scenario_contract_version")) != SCENARIO_CONTRACT_VERSION:
        raise ScenarioRobustnessError(
            "unsupported scenario contract version"
        )

    expected_hash = semantic_sha256(pairwise_audit)
    actual_hash = _text(payload.get("pairwise_audit_sha256"))
    if actual_hash.lower() != expected_hash:
        raise ScenarioRobustnessError(
            "pairwise audit semantic hash mismatch"
        )

    pairwise_target = _mapping(
        pairwise_audit.get("target"),
        "pairwise.target",
    )
    payload_target = _mapping(
        payload.get("target"),
        "payload.target",
    )
    if _target_key(pairwise_target) != _target_key(payload_target):
        raise ScenarioRobustnessError(
            "scenario target does not match pairwise audit"
        )

    raw_scenarios = _list(
        payload.get("scenarios"),
        "payload.scenarios",
    )
    scenarios: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for index, raw_scenario in enumerate(raw_scenarios, start=1):
        scenario = _validate_scenario(
            raw_scenario,
            f"payload.scenarios[{index}]",
            runners,
            base_order,
        )
        scenario_id = str(scenario["scenario_id"])
        if scenario_id in seen_ids:
            raise ScenarioRobustnessError(
                f"duplicate scenario: {scenario_id}"
            )
        seen_ids.add(scenario_id)
        scenarios.append(scenario)

    if seen_ids != set(REQUIRED_SCENARIOS):
        raise ScenarioRobustnessError(
            "SLOW, MEDIUM, and FAST scenarios are all required"
        )
    scenario_index = {
        str(item["scenario_id"]): item
        for item in scenarios
    }
    scenarios = [
        scenario_index[scenario_id]
        for scenario_id in REQUIRED_SCENARIOS
    ]

    axis_horse_no = base_order[0]
    axis_wins = 0
    risk_scenarios: list[str] = []
    for scenario in scenarios:
        order = list(scenario["order"])
        if order[0] == axis_horse_no:
            axis_wins += 1
        else:
            risk_scenarios.append(str(scenario["scenario_id"]))

    derived_status = _axis_status(axis_wins)
    conclusion = _mapping(
        payload.get("conclusion"),
        "payload.conclusion",
    )
    declared_status = _text(
        conclusion.get("pairwise_axis_status")
    ).upper()
    if declared_status not in AXIS_STATUS:
        raise ScenarioRobustnessError(
            "conclusion.pairwise_axis_status is invalid"
        )
    if declared_status != derived_status:
        raise ScenarioRobustnessError(
            "declared axis robustness does not match scenario outcomes"
        )

    declared_risks = _unique_strings(
        conclusion.get("main_risk_scenario_ids"),
        "payload.conclusion.main_risk_scenario_ids",
        True,
    )
    if set(declared_risks) != set(risk_scenarios):
        raise ScenarioRobustnessError(
            "main_risk_scenario_ids must match scenarios where axis loses"
        )

    summary = _text(conclusion.get("summary"))
    if not summary:
        raise ScenarioRobustnessError(
            "conclusion.summary is required"
        )

    pairwise_recheck_recommended = axis_wins <= 1

    return {
        "audit_schema_version": "RaceNote-Scenario-Robustness-Audit-0.1",
        "status": "PASS",
        "scenario_schema_version": SCENARIO_SCHEMA_VERSION,
        "scenario_contract_version": SCENARIO_CONTRACT_VERSION,
        "pairwise_audit_sha256": expected_hash,
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
            "required_scenarios": list(REQUIRED_SCENARIOS),
            "numeric_score_used": False,
            "market_visible": False,
            "jrdb_current_consensus_visible": False,
            "training_edge_visible": False,
            "scenario_order_does_not_auto_replace_pairwise_order": True,
        },
        "pairwise_order": base_order,
        "axis_horse_no": axis_horse_no,
        "axis_rank1_scenario_count": axis_wins,
        "axis_robustness": derived_status,
        "risk_scenario_ids": risk_scenarios,
        "horse_sensitivity": _horse_sensitivity(
            base_order,
            scenarios,
        ),
        "scenarios": scenarios,
        "conclusion": {
            "pairwise_axis_status": derived_status,
            "main_risk_scenario_ids": risk_scenarios,
            "summary": summary,
        },
        "pairwise_recheck_recommended": pairwise_recheck_recommended,
        "next_stage": {
            "name": "FORECAST_NEXT_GENERATION_CONTRACT",
            "status": "READY",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pairwise-audit",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--scenario",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output-audit",
        type=Path,
        required=True,
    )
    args = parser.parse_args()

    pairwise = json.loads(
        args.pairwise_audit.read_text(encoding="utf-8")
    )
    payload = json.loads(
        args.scenario.read_text(encoding="utf-8")
    )
    audit = validate_scenario_robustness(
        pairwise,
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
                "axis_horse_no": audit["axis_horse_no"],
                "axis_robustness": audit["axis_robustness"],
                "pairwise_recheck_recommended": audit[
                    "pairwise_recheck_recommended"
                ],
                "output": str(args.output_audit),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
