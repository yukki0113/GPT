#!/usr/bin/env python3
"""RaceNote 0.5.2 candidate Reader.

v0.5.2 intentionally keeps the same model-facing normal_view projection as
v0.5.0/v0.5.1. The experiment changes candidate compression and role
assignment, not the evidence presented to the model.
"""
from __future__ import annotations

from typing import Any

import racenote_reader_v050 as v050

VERSION = "RaceNote-Human-Context-Reader-0.5.2-candidate"
DEFAULT_BINDING = v050.DEFAULT_BINDING
DEFAULT_POLICY_COMPATIBLE_VERSION = v050.VERSION


def load_binding(path=DEFAULT_BINDING):
    return v050.load_binding(path)


def validate_policy_binding(binding: dict[str, Any], policy: dict[str, Any]) -> None:
    v050.validate_policy_binding(binding, policy)


def transform(clean_view: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    candidate = v050.transform(clean_view, binding)
    candidate["candidate_version"] = VERSION
    return candidate


def compact_bytes(value: Any) -> bytes:
    return v050.compact_bytes(value)


def metrics(clean_view: dict[str, Any], candidate: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    result = v050.metrics(clean_view, candidate, binding)
    result["candidate_version"] = VERSION
    result["reader_projection"] = "identical_to_v0.5.0_normal_view"
    return result
