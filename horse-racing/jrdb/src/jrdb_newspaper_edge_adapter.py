#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adapt JRDB Edge matcher output for Newspaper ``特注メモ`` consumption.

The adapter is intentionally a display boundary.  It never re-evaluates Edge
conditions, aggregates strength, or converts ROI into a score.  Exact matcher
output is validated and normalized so the Newspaper layer can join it by
``race_key + race_horse_key + horse_no`` and render only the currently allowed
serving subset.

Current matcher compatibility:
- ``status`` is accepted as the legacy spelling of ``registry_status``.
- ``evidence.performance_signal`` is accepted when the future top-level
  evidence-level fields are not present.
- Missing future fields remain ``None``; they are not silently fabricated.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

VERSION = "0.1.0"

ACTIVE_STATUS = "ACTIVE"
DISPLAY_PERFORMANCE_SIGNALS = {"POSITIVE", "NEGATIVE"}
KNOWN_PERFORMANCE_SIGNALS = {"POSITIVE", "NEGATIVE", "NEUTRAL"}
KNOWN_EVIDENCE_LEVELS = {"CONFIRMED", "SUGGESTIVE", "NONE"}
KNOWN_PRESENTATION_ROLES = {"PRIMARY", "SECONDARY", "CONFLICT"}
SIGNED_PREFIXES = ("＋", "+", "－", "-", "−", "±")


class NewspaperEdgeAdapterError(ValueError):
    """Raised when Edge matcher input is unsafe or structurally ambiguous."""


def _text(value: Any) -> str | None:
    """Return normalized non-empty text without inventing missing values."""
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return normalized


def _required_text(value: Any, field: str, context: str) -> str:
    """Read a required text value with a useful validation error."""
    normalized = _text(value)
    if normalized is None:
        raise NewspaperEdgeAdapterError(f"{context}: {field} is required")
    return normalized


def _positive_int(value: Any, field: str, context: str) -> int:
    """Read a positive integer identity value."""
    if isinstance(value, bool):
        raise NewspaperEdgeAdapterError(f"{context}: {field} must be a positive integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise NewspaperEdgeAdapterError(
            f"{context}: {field} must be a positive integer"
        ) from exc
    if normalized < 1:
        raise NewspaperEdgeAdapterError(f"{context}: {field} must be a positive integer")
    return normalized


def _upper_optional(value: Any) -> str | None:
    """Normalize optional enum-like text."""
    normalized = _text(value)
    if normalized is None:
        return None
    return normalized.upper()


def _performance_signal(match: Mapping[str, Any]) -> str | None:
    """Resolve performance direction without using outer mixed polarity."""
    direct = _upper_optional(match.get("performance_signal"))
    if direct is not None:
        return direct

    evidence = match.get("evidence")
    if isinstance(evidence, Mapping):
        nested = _upper_optional(evidence.get("performance_signal"))
        if nested is not None:
            return nested
    return None


def _registry_status(match: Mapping[str, Any]) -> str | None:
    """Resolve future ``registry_status`` with legacy ``status`` fallback."""
    status = _upper_optional(match.get("registry_status"))
    if status is not None:
        return status
    return _upper_optional(match.get("status"))


def _validate_optional_enum(
    value: str | None,
    allowed: set[str],
    field: str,
    context: str,
) -> None:
    """Fail closed when a supplied future enum has unknown semantics."""
    if value is None:
        return
    if value not in allowed:
        raise NewspaperEdgeAdapterError(
            f"{context}: unsupported {field}={value!r}"
        )


def _memo_text(display_text: str, performance_signal: str | None) -> str:
    """Add a display sign only when EdgeDB text does not already contain one."""
    stripped = display_text.lstrip()
    if stripped.startswith(SIGNED_PREFIXES):
        return display_text

    if performance_signal == "POSITIVE":
        return f"＋ {display_text}"
    if performance_signal == "NEGATIVE":
        return f"－ {display_text}"
    return display_text


def _serving_decision(
    *,
    registry_status: str | None,
    performance_signal: str | None,
    performance_evidence_level: str | None,
    presentation_role: str | None,
) -> tuple[bool, str]:
    """Apply only the Newspaper serving gate, never Edge condition logic."""
    if registry_status != ACTIVE_STATUS:
        return False, "REGISTRY_NOT_ACTIVE"
    if performance_signal not in DISPLAY_PERFORMANCE_SIGNALS:
        return False, "PERFORMANCE_NEUTRAL_OR_MISSING"

    # Future contract: once an explicit evidence level exists, initial
    # Newspaper serving is CONFIRMED-only.
    if performance_evidence_level is not None:
        if performance_evidence_level != "CONFIRMED":
            return False, "PERFORMANCE_NOT_CONFIRMED"

    # SECONDARY remains available in normalized data but is hidden by default.
    if presentation_role == "SECONDARY":
        return False, "SECONDARY_HIDDEN"

    if performance_evidence_level is None:
        return True, "LEGACY_ACTIVE_PERFORMANCE_SIGNAL"
    return True, "ACTIVE_CONFIRMED"


def normalize_match(match: Mapping[str, Any], *, context: str) -> dict[str, Any]:
    """Normalize one Edge match while retaining future-facing metadata."""
    if not isinstance(match, Mapping):
        raise NewspaperEdgeAdapterError(f"{context}: edge match must be an object")

    edge_id = _required_text(match.get("edge_id"), "edge_id", context)
    display_text = _required_text(match.get("display_text"), "display_text", context)
    registry_status = _registry_status(match)
    performance_signal = _performance_signal(match)
    performance_evidence_level = _upper_optional(
        match.get("performance_evidence_level")
    )
    value_evidence_level = _upper_optional(match.get("value_evidence_level"))
    presentation_role = _upper_optional(match.get("presentation_role"))

    _validate_optional_enum(
        performance_signal,
        KNOWN_PERFORMANCE_SIGNALS,
        "performance_signal",
        context,
    )
    _validate_optional_enum(
        performance_evidence_level,
        KNOWN_EVIDENCE_LEVELS,
        "performance_evidence_level",
        context,
    )
    _validate_optional_enum(
        value_evidence_level,
        KNOWN_EVIDENCE_LEVELS,
        "value_evidence_level",
        context,
    )
    _validate_optional_enum(
        presentation_role,
        KNOWN_PRESENTATION_ROLES,
        "presentation_role",
        context,
    )

    serving_eligible, serving_reason = _serving_decision(
        registry_status=registry_status,
        performance_signal=performance_signal,
        performance_evidence_level=performance_evidence_level,
        presentation_role=presentation_role,
    )

    return {
        "edge_id": edge_id,
        "display_text": display_text,
        "memo_text": _memo_text(display_text, performance_signal),
        "polarity": _upper_optional(match.get("polarity")),
        "performance_signal": performance_signal,
        "registry_status": registry_status,
        "performance_evidence_level": performance_evidence_level,
        "value_evidence_level": value_evidence_level,
        "presentation_role": presentation_role,
        "serving_eligible": serving_eligible,
        "serving_reason": serving_reason,
        "strength_score": match.get("strength_score"),
        "confidence_band": match.get("confidence_band"),
        "registry_version": match.get("registry_version"),
        "evidence": match.get("evidence"),
    }


def normalize_row(row: Mapping[str, Any], *, line_no: int) -> dict[str, Any]:
    """Normalize one runner row from ``edge_matches.jsonl``."""
    context = f"edge_matches line {line_no}"
    if not isinstance(row, Mapping):
        raise NewspaperEdgeAdapterError(f"{context}: row must be an object")

    key = row.get("key")
    if not isinstance(key, Mapping):
        raise NewspaperEdgeAdapterError(f"{context}: key must be an object")

    normalized_key = {
        "race_key": _required_text(key.get("race_key"), "key.race_key", context),
        "race_horse_key": _required_text(
            key.get("race_horse_key"), "key.race_horse_key", context
        ),
        "horse_no": _positive_int(key.get("horse_no"), "key.horse_no", context),
        "horse_id": _text(key.get("horse_id")),
        "race_date": _text(key.get("race_date")),
    }

    raw_matches = row.get("edge_matches")
    if not isinstance(raw_matches, list):
        raise NewspaperEdgeAdapterError(f"{context}: edge_matches must be an array")

    normalized_matches: list[dict[str, Any]] = []
    for match_index, raw_match in enumerate(raw_matches, start=1):
        match_context = f"{context} match {match_index}"
        normalized_match = normalize_match(raw_match, context=match_context)
        normalized_matches.append(normalized_match)

    special_memos = [
        match for match in normalized_matches if match["serving_eligible"]
    ]

    return {
        "key": normalized_key,
        "edge_matches": normalized_matches,
        "special_memos": special_memos,
    }


def _sha256(path: Path) -> str:
    """Calculate the exact source-file SHA-256 for audit metadata."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def load_special_memo_index(
    path: str | Path,
) -> tuple[dict[tuple[str, str, int], dict[str, Any]], dict[str, Any]]:
    """Load EdgeDB JSONL into the Newspaper exact-join index.

    Duplicate ``race_key + race_horse_key + horse_no`` identities are rejected.
    The returned audit separates raw Edge occurrences from display-eligible
    ``特注メモ`` occurrences.
    """
    source_path = Path(path)
    index: dict[tuple[str, str, int], dict[str, Any]] = {}
    row_count = 0
    raw_match_count = 0
    special_memo_count = 0
    matched_runner_count = 0
    special_memo_runner_count = 0

    with source_path.open(encoding="utf-8") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                raw_row = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise NewspaperEdgeAdapterError(
                    f"edge_matches line {line_no}: invalid JSON"
                ) from exc

            row = normalize_row(raw_row, line_no=line_no)
            key_data = row["key"]
            key = (
                str(key_data["race_key"]),
                str(key_data["race_horse_key"]),
                int(key_data["horse_no"]),
            )
            if key in index:
                raise NewspaperEdgeAdapterError(
                    f"edge_matches line {line_no}: duplicate join key {key}"
                )

            index[key] = row
            row_count += 1
            raw_match_count += len(row["edge_matches"])
            special_memo_count += len(row["special_memos"])
            if row["edge_matches"]:
                matched_runner_count += 1
            if row["special_memos"]:
                special_memo_runner_count += 1

    audit = {
        "status": "PASS",
        "adapter_version": VERSION,
        "source_sha256": _sha256(source_path),
        "row_count": row_count,
        "raw_match_count": raw_match_count,
        "matched_runner_count": matched_runner_count,
        "special_memo_count": special_memo_count,
        "special_memo_runner_count": special_memo_runner_count,
    }
    return index, audit
