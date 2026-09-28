#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build and validate RaceNote ◎-only Best Bet research packets.

This layer is intentionally separate from Mark Policy.  It asks for exactly one
◎: the horse the user would most want to buy in this race.

Key research changes from the current TrendFirst semantic stack:
- every runner remains eligible; there is no top-6 candidate cutoff;
- no fixed DATA_TREND > RACEREVIEW >= ABILITY priority;
- race context is interpreted before choosing which evidence is most
  discriminating;
- local/named-race trend may break a close ability comparison;
- clearly superior ability may override an adverse trend;
- concerns are explicit but are not automatic vetoes;
- market, results, RL, EdgeDB and Training Edge remain hidden.

The module does not itself invent a winner.  It creates a structured authoring
request and validates a model-authored blind response.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

REQUEST_VERSION = "RaceNote-Best-Bet-Request-v0.1"
OUTPUT_VERSION = "RaceNote-Best-Bet-Research-v0.1"

DECISION_TYPES = {
    "TREND_ALIGNED",
    "ABILITY_OVERRIDE",
    "BALANCED_EVIDENCE",
    "CONTEXTUAL_EDGE",
    "MIXED_RACE_BEST_AVAILABLE",
}

THESIS_CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}


class BestBetError(RuntimeError):
    pass


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _mapping(value: object, field: str = "value") -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise BestBetError(f"{field} must be an object")
    return value


def _list(value: object, field: str = "value") -> list[object]:
    if not isinstance(value, list):
        raise BestBetError(f"{field} must be an array")
    return value


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise BestBetError(f"{field} must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise BestBetError(f"{field} must be a positive integer") from exc
    if number < 1:
        raise BestBetError(f"{field} must be a positive integer")
    return number


def semantic_sha256(value: object) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _validate_firewall(general: Mapping[str, object]) -> None:
    firewall = _mapping(general.get("firewall"), "general.firewall")
    required_false = (
        "current_jrdb_consensus_visible",
        "current_market_visible",
        "training_edge_visible",
        "rl_index_visible",
        "edgedb_match_visible",
    )
    for field in required_false:
        if firewall.get(field) is not False:
            raise BestBetError(f"{field} must remain hidden")
    if firewall.get("jrdb_condition_signal_visible") is not True:
        raise BestBetError("jrdb_condition_signal must remain visible")


def _target(general: Mapping[str, object]) -> dict[str, object]:
    target = _mapping(general.get("target"), "general.target")
    return {
        "date": _text(target.get("date")),
        "venue": _text(target.get("venue")),
        "race_no": _positive_int(target.get("race_no"), "target.race_no"),
        "race_name": _text(target.get("race_name")),
    }


def _horse_payload(raw: object, index: int) -> dict[str, object]:
    horse = _mapping(raw, f"general.horses[{index}]")
    horse_no = _positive_int(horse.get("horse_no"), f"general.horses[{index}].horse_no")
    return {
        "horse_no": horse_no,
        "horse_name": _text(horse.get("horse_name")),
        "current_facts": copy.deepcopy(horse.get("current_facts", {})),
        "evidence_lanes": copy.deepcopy(horse.get("evidence_lanes", {})),
        "prediction_interpretation": copy.deepcopy(
            horse.get("prediction_interpretation", {})
        ),
    }


def build_request(general: Mapping[str, object]) -> dict[str, object]:
    _validate_firewall(general)
    raw_horses = _list(general.get("horses"), "general.horses")
    if not raw_horses:
        raise BestBetError("general evidence contains no runners")

    horses = [_horse_payload(raw, i) for i, raw in enumerate(raw_horses, start=1)]
    horse_nos = [int(h["horse_no"]) for h in horses]
    if len(horse_nos) != len(set(horse_nos)):
        raise BestBetError("duplicate horse_no")

    return {
        "request_version": REQUEST_VERSION,
        "output_version": OUTPUT_VERSION,
        "general_evidence_sha256": semantic_sha256(general),
        "target": _target(general),
        "result_visibility_status": "HIDDEN",
        "market_visibility_status": "HIDDEN",
        "race_context": {
            "race_data_context": copy.deepcopy(general.get("race_data_context", {})),
            "race_structure": copy.deepcopy(general.get("race_structure", {})),
            "field_evidence_summary": copy.deepcopy(
                general.get("field_evidence_summary", {})
            ),
        },
        "horses": horses,
        "author_fields": {
            "race_thesis": {
                "summary": None,
                "confidence": None,
                "most_discriminating_evidence": [],
                "trend_scope_used": None,
                "trend_scope_status": None,
                "limitations": [],
            },
            "best_bet": {
                "horse_no": None,
                "horse_name": None,
                "decision_type": None,
                "fundamental_ability_case": None,
                "trend_case": None,
                "recent_form_case": None,
                "current_suitability_case": None,
                "condition_case": None,
                "concerns": [],
                "why_concerns_do_not_overturn": None,
                "why_best_buy": None,
                "comment": None,
            },
            "nearest_alternatives": [],
        },
        "instructions": {
            "definition_of_best_bet": (
                "◎ is the one horse the user most wants to buy in this race, "
                "not a generic highest score and not necessarily the market favorite."
            ),
            "read_every_runner_before_selection": True,
            "top_n_candidate_cutoff": None,
            "fixed_evidence_priority": None,
            "no_numeric_score": True,
            "race_context_before_horse_selection": True,
            "trend_role": (
                "Trend may decide a close ability comparison, but it is not an "
                "automatic veto or universal first priority."
            ),
            "ability_override_rule": (
                "If one horse has a materially stronger ability/class case, an "
                "adverse trend may be overridden when the trend is not strong "
                "enough to negate that edge."
            ),
            "trend_alignment_rule": (
                "If leading horses are close on ability, a race-specific or "
                "local-context trend may be the deciding reason for ◎."
            ),
            "concern_rule": (
                "A concern must be stated explicitly but does not automatically "
                "disqualify ◎; explain whether it is strong enough to overturn "
                "the positive case."
            ),
            "recent_form_rule": (
                "Read recent form contextually: class/grade, opponent strength, "
                "course relevance and race content matter; do not reduce it only "
                "to latest/median/peak numbers."
            ),
            "trend_scope_rule": (
                "Use named-race/local-context trend only when supplied by the "
                "input. If unavailable, mark it unavailable and never invent it."
            ),
            "jrdb_condition_role": "CORROBORATION_OR_CONTRADICTION_ONLY",
            "do_not_use_market": True,
            "do_not_use_result": True,
            "do_not_use_current_jrdb_consensus": True,
            "do_not_use_training_edge": True,
            "do_not_use_rl_index": True,
            "do_not_use_edgedb_match": True,
            "output_exactly_one_best_bet": True,
            "comment_style": (
                "2-5 Japanese sentences explaining why this is the horse to buy "
                "now, including the main concern when material."
            ),
        },
    }


def validate_output(
    request: Mapping[str, object],
    payload: Mapping[str, object],
) -> dict[str, object]:
    if _text(payload.get("output_version")) != OUTPUT_VERSION:
        raise BestBetError("unsupported output_version")
    if _text(payload.get("general_evidence_sha256")).lower() != _text(
        request.get("general_evidence_sha256")
    ).lower():
        raise BestBetError("general evidence hash mismatch")

    req_target = _mapping(request.get("target"), "request.target")
    out_target = _mapping(payload.get("target"), "payload.target")
    req_key = (
        _text(req_target.get("date")),
        _text(req_target.get("venue")),
        _positive_int(req_target.get("race_no"), "request.target.race_no"),
    )
    out_key = (
        _text(out_target.get("date")),
        _text(out_target.get("venue")),
        _positive_int(out_target.get("race_no"), "payload.target.race_no"),
    )
    if req_key != out_key:
        raise BestBetError("target mismatch")

    runners = {
        int(_mapping(raw, "request.horse").get("horse_no"))
        for raw in _list(request.get("horses"), "request.horses")
    }
    thesis = _mapping(payload.get("race_thesis"), "payload.race_thesis")
    if not _text(thesis.get("summary")):
        raise BestBetError("race_thesis.summary is required")
    confidence = _text(thesis.get("confidence")).upper()
    if confidence not in THESIS_CONFIDENCE:
        raise BestBetError("invalid race_thesis.confidence")

    best = _mapping(payload.get("best_bet"), "payload.best_bet")
    horse_no = _positive_int(best.get("horse_no"), "best_bet.horse_no")
    if horse_no not in runners:
        raise BestBetError("best_bet horse is not a runner")
    decision_type = _text(best.get("decision_type")).upper()
    if decision_type not in DECISION_TYPES:
        raise BestBetError("invalid best_bet.decision_type")
    if not _text(best.get("why_best_buy")):
        raise BestBetError("best_bet.why_best_buy is required")
    if not _text(best.get("comment")):
        raise BestBetError("best_bet.comment is required")

    return {
        "status": "PASS",
        "output_version": OUTPUT_VERSION,
        "target": dict(out_target),
        "best_bet": dict(best),
        "race_thesis": dict(thesis),
        "nearest_alternatives": copy.deepcopy(
            payload.get("nearest_alternatives", [])
        ),
        "policy": {
            "all_runners_eligible": True,
            "numeric_score_used": False,
            "fixed_trend_first_priority_used": False,
            "market_visible": False,
            "result_visible": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--general-evidence", type=Path, required=True)
    parser.add_argument("--output-request", type=Path, required=True)
    parser.add_argument("--author-output", type=Path)
    parser.add_argument("--output-audit", type=Path)
    args = parser.parse_args()

    general = json.loads(args.general_evidence.read_text(encoding="utf-8"))
    request = build_request(general)
    args.output_request.parent.mkdir(parents=True, exist_ok=True)
    args.output_request.write_text(
        json.dumps(request, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if args.author_output is not None:
        if args.output_audit is None:
            raise BestBetError("--output-audit is required with --author-output")
        payload = json.loads(args.author_output.read_text(encoding="utf-8"))
        audit = validate_output(request, payload)
        args.output_audit.parent.mkdir(parents=True, exist_ok=True)
        args.output_audit.write_text(
            json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(json.dumps({
        "status": "PASS",
        "request_version": REQUEST_VERSION,
        "runner_count": len(request["horses"]),
        "output": str(args.output_request),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
