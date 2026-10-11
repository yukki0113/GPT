#!/usr/bin/env python3
"""RaceNote 0.5.3 candidate Reader.

v0.5.3 intentionally preserves the v0.5.2 model-facing projection. The
revision changes candidate-boundary judgment, not the evidence surface.
"""
from __future__ import annotations

from typing import Any

import racenote_reader_v052 as v052

VERSION = "RaceNote-Human-Context-Reader-0.5.3-candidate"
DEFAULT_BINDING = v052.DEFAULT_BINDING
DEFAULT_POLICY_COMPATIBLE_VERSION = v052.DEFAULT_POLICY_COMPATIBLE_VERSION


def load_binding(path=DEFAULT_BINDING):
    return v052.load_binding(path)


def validate_policy_binding(binding: dict[str, Any], policy: dict[str, Any]) -> None:
    v052.validate_policy_binding(binding, policy)


def transform(clean_view: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    candidate = v052.transform(clean_view, binding)
    candidate["candidate_version"] = VERSION
    return candidate


def compact_bytes(value: Any) -> bytes:
    return v052.compact_bytes(value)


def metrics(clean_view: dict[str, Any], candidate: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    result = v052.metrics(clean_view, candidate, binding)
    result["candidate_version"] = VERSION
    result["reader_projection"] = "identical_to_v0.5.2_normal_view"
    return result
