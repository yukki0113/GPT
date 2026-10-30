#!/usr/bin/env python3
"""v0.5.6 contract-level structural gates. Never authors or changes LLM judgments.

This module is additive and NOT a v0.5.6 production Freeze implementation.
"""
from __future__ import annotations

import re

CONFIDENCE_FIELDS = (
    "winning_case", "primary_rival", "relative_advantage",
    "main_defeat_scenario", "risk_assessment", "final_grade_reason",
)
_GRADES = frozenset(("A", "B", "C", "Z"))
_INTERNAL = re.compile(r"(?:Decision Core|source_semantic|sha256|sealed Reader)", re.I)


def check_prediction_audit_comment(record: dict) -> None:
    value = record.get("prediction_audit_comment")
    if not isinstance(value, str) or not (12 <= len(value.strip()) <= 1000):
        raise ValueError("prediction_audit_comment must be substantial nonempty text")
    if record.get("confidence") is not None:
        raise ValueError("Prediction record must not carry unfrozen Confidence")


def check_confidence_review(record: dict, frozen_honmei: int, *, z_required: bool) -> None:
    if type(record.get("honmei")) is not int or record["honmei"] != frozen_honmei:
        raise ValueError("Confidence honmei differs from frozen Prediction")
    grade = record.get("confidence")
    if grade not in _GRADES:
        raise ValueError("Unsupported Confidence grade")
    if (grade == "Z") != z_required:
        raise ValueError("Z applicability does not match existing special-race policy")
    review = record.get("confidence_review")
    if not isinstance(review, dict):
        raise ValueError("Missing structured confidence_review")
    if grade == "Z":
        if set(review) != {"not_applicable_reason"}:
            raise ValueError("Z requires exactly not_applicable_reason")
        if not isinstance(review["not_applicable_reason"], str) or len(review["not_applicable_reason"].strip()) < 8:
            raise ValueError("Insufficient Z reason")
        return
    if set(review) != set(CONFIDENCE_FIELDS):
        raise ValueError("Incorrect Confidence review fields")
    for key in CONFIDENCE_FIELDS:
        value = review[key]
        if not isinstance(value, str) or len(value.strip()) < 8:
            raise ValueError(f"Missing or insufficient {key}")


def check_newspaper_comment(record: dict, *, execution_mode: str, prediction_frozen: bool,
                            confidence_frozen: bool) -> None:
    if execution_mode != "FORWARD":
        raise ValueError("Newspaper phase is forbidden for BTDAY")
    if not (prediction_frozen and confidence_frozen):
        raise ValueError("Both Prediction and Confidence Freeze must precede newspaper phase")
    value = record.get("forward_newspaper_comment")
    if not isinstance(value, str) or not (12 <= len(value.strip()) <= 1000):
        raise ValueError("Missing newspaper comment")
    if _INTERNAL.search(value):
        raise ValueError("Internal tooling terminology in newspaper comment")
    if not isinstance(record.get("prediction_frozen_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", record["prediction_frozen_sha256"]):
        raise ValueError("Invalid prediction freeze reference")
    if not isinstance(record.get("confidence_frozen_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", record["confidence_frozen_sha256"]):
        raise ValueError("Invalid confidence freeze reference")
