#!/usr/bin/env python3
"""Typed, machine-readable fail-closed errors for RaceNote forward T1.

These codes describe *known* contract failures. Unclassified runner/network
failures must never be mislabeled as accepted data or as a data mismatch.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Callable

SCHEMA = "racenote-forward-failure-v1"
DATA_INVALID = "DATA_INVALID"
ORCHESTRATION_MISSING = "ORCHESTRATION_MISSING"


class ForwardFailure(ValueError):
    error_code: str


class DataInvalid(ForwardFailure):
    """Verified input or a committed contract violates a deterministic rule."""

    error_code = DATA_INVALID


class OrchestrationMissing(ForwardFailure):
    """Required acceptance, input delivery or stage has not been completed."""

    error_code = ORCHESTRATION_MISSING


def failure_receipt(error: ForwardFailure, stage: str) -> dict:
    return {
        "schema_version": SCHEMA,
        "status": "FAILED",
        "error_code": error.error_code,
        "failed_stage": stage,
        "detail": str(error),
        "retryable": False,
    }


def run_cli(entrypoint: Callable[[], int], stage: str) -> int:
    """Emit a structured report for typed failures without turning them into PASS."""
    try:
        return entrypoint()
    except ForwardFailure as error:
        payload = failure_receipt(error, stage)
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        print("RACENOTE_FORWARD_FAILURE " + serialized, file=sys.stderr)
        output = os.environ.get("RACENOTE_FORWARD_FAILURE_JSON")
        if output:
            path = Path(output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(serialized + "\n", encoding="utf-8")
        return 2
