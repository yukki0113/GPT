#!/usr/bin/env python3
"""Fail-closed hand-off from a GPT Gen0 decision to the existing freeze contract.

This is intentionally *not* a scorer.  It builds a request from the isolated
RaceNote independent view and accepts only a structured decision produced by
the approved GPT prediction step.  The existing Gen0 module remains the sole
validator/freezer.  Keeping this boundary explicit prevents a local heuristic,
current JRDB consensus, market data, or a post-race field from silently becoming
a prediction producer.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Mapping

import racenote_forecast_gen0 as gen0
import racenote_gen0_2_input_firewall as firewall

PRODUCER_VERSION = "RaceNote-Gen0-GPT-Producer-0.1"


class ProducerError(ValueError):
    """Raised when a GPT decision cannot be tied to its independent input."""


def _text(value: Any, field: str) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        raise ProducerError(f"{field} is required")
    return text


def _identity(view: Mapping[str, Any]) -> tuple[str, str, int, dict[int, str]]:
    race = view.get("race")
    horses = view.get("horses")
    if not isinstance(race, Mapping) or not isinstance(horses, list):
        raise ProducerError("independent view is missing race/horses")
    target_date = _text(race.get("date"), "race.date")
    venue = _text(race.get("venue"), "race.venue")
    try:
        race_no = int(race.get("race_no"))
    except (TypeError, ValueError) as exc:
        raise ProducerError("race.race_no is required") from exc
    runners: dict[int, str] = {}
    for index, horse in enumerate(horses, 1):
        if not isinstance(horse, Mapping) or not isinstance(horse.get("basic"), Mapping):
            raise ProducerError(f"independent horses[{index}] is invalid")
        basic = horse["basic"]
        try:
            no = int(basic.get("horse_no"))
        except (TypeError, ValueError) as exc:
            raise ProducerError(f"independent horses[{index}].horse_no is required") from exc
        if no in runners:
            raise ProducerError(f"duplicate independent horse_no: {no}")
        runners[no] = _text(basic.get("horse_name"), f"independent horses[{index}].horse_name")
    return target_date, venue, race_no, runners


def build_prediction_request(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Create the exact independently-visible, hash-addressed GPT input."""
    parts = firewall.build_partitioned_views(bundle)
    independent = parts["independent"]
    audit = firewall.audit_independent_view(independent)
    if audit.get("status") != "PASS":
        raise ProducerError("independent firewall audit did not pass")
    target_date, venue, race_no, runners = _identity(independent)
    return {
        "producer_version": PRODUCER_VERSION,
        "prediction_contract": "FORECAST_GEN0_PREDICTION_CONTRACT_v0_1",
        "evaluation_mode": "BLINDED_HISTORICAL",
        "result_visibility_status": "HIDDEN",
        "target_date": target_date,
        "venue": venue,
        "race_no": race_no,
        "source_semantic_sha256": parts["source_semantic_sha256"],
        "independent_semantic_sha256": parts["independent_semantic_sha256"],
        "independent_view": independent,
        "expected_runners": [
            {"horse_no": no, "horse_name": name} for no, name in sorted(runners.items())
        ],
        "prohibited_inputs": [
            "current_jrdb_consensus", "current_total_index", "jrdb_current_marks",
            "final_odds", "final_popularity", "payout", "target_result",
            "training_edge", "post_freeze_edge_evidence",
        ],
    }


def materialize_gpt_decision(
    request: Mapping[str, Any], decision: Mapping[str, Any], *, created_at: str
) -> dict[str, Any]:
    """Bind a GPT's structured decision to exactly one independent RaceNote view."""
    if not isinstance(request, Mapping) or not isinstance(decision, Mapping):
        raise ProducerError("request and decision must be objects")
    independent = request.get("independent_view")
    if not isinstance(independent, Mapping):
        raise ProducerError("request is missing independent_view")
    target_date, venue, race_no, expected = _identity(independent)
    if request.get("independent_semantic_sha256") != firewall.semantic_sha256(independent):
        raise ProducerError("request independent semantic hash mismatch")
    payload = copy.deepcopy(dict(decision))
    for field, expected_value in (("target_date", target_date), ("venue", venue), ("race_no", race_no)):
        supplied = payload.get(field)
        if supplied not in (None, "") and str(supplied) != str(expected_value):
            raise ProducerError(f"GPT decision identity mismatch: {field}")
        payload[field] = expected_value
    payload["race_key"] = _text(payload.get("race_key"), "decision.race_key")
    payload["generation_id"] = payload.get("generation_id", gen0.DEFAULT_GENERATION_ID)
    payload["evaluation_mode"] = request.get("evaluation_mode")
    payload["forecast_created_at"] = created_at
    payload["pre_race_guard_status"] = "PASS"
    payload["result_visibility_status"] = "HIDDEN"
    payload["source"] = {
        "schema": "1.0",
        "reader_view_version": "independent-0.1",
        "semantic_sha256": request["source_semantic_sha256"],
        "artifact_ref": _text(payload.get("artifact_ref"), "decision.artifact_ref"),
    }
    payload["producer"] = {
        "version": PRODUCER_VERSION,
        "input_firewall_version": independent.get("firewall_version"),
        "independent_semantic_sha256": request["independent_semantic_sha256"],
        "forbidden_evidence_status": "PASS",
    }
    actual: dict[int, str] = {}
    for row in payload.get("horses", []):
        if not isinstance(row, Mapping):
            raise ProducerError("decision.horses must contain objects")
        try:
            no = int(row.get("horse_no"))
        except (TypeError, ValueError) as exc:
            raise ProducerError("decision horse_no is required") from exc
        actual[no] = str(row.get("horse_name", "")).strip()
    if actual != expected:
        raise ProducerError("GPT decision must cover exactly the independent source runners")
    # The validator is deliberately called before a file can be emitted.
    return gen0.validate_forecast(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize an approved GPT Gen0 decision")
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--decision", type=Path, required=True,
                        help="Structured GPT decision; no scorer fallback is provided")
    parser.add_argument("--created-at", required=True)
    parser.add_argument("--request-output", type=Path, required=True)
    parser.add_argument("--candidate-output", type=Path, required=True)
    args = parser.parse_args()
    request = build_prediction_request(json.loads(args.bundle.read_text(encoding="utf-8")))
    candidate = materialize_gpt_decision(
        request, json.loads(args.decision.read_text(encoding="utf-8")), created_at=args.created_at
    )
    for path, value in ((args.request_output, request), (args.candidate_output, candidate)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
