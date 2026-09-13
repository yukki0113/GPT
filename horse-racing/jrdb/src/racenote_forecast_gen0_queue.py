#!/usr/bin/env python3
"""Deterministic queue helpers for RaceNote Forecast Gen0.

This module does not access Google Sheets directly and does not predict races.
It validates queue state transitions so ChatGPT can safely edit the native
Google Sheet through the Drive/Sheets connector.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

DEFAULT_CHUNK_SIZE = 5
DEFAULT_MAX_PER_DATE = 3
ALLOWED_STATUSES = {
    "READY",
    "SOURCE_READY",
    "IN_PROGRESS",
    "FROZEN",
    "RESULT_JOINED",
    "EVALUATED",
    "SKIPPED_TECH",
    "RESERVE",
}
ALLOWED_TRANSITIONS = {
    "READY": {"SOURCE_READY", "SKIPPED_TECH"},
    "SOURCE_READY": {"IN_PROGRESS", "SKIPPED_TECH"},
    "IN_PROGRESS": {"FROZEN"},
    "FROZEN": {"RESULT_JOINED"},
    "RESULT_JOINED": {"EVALUATED"},
    "EVALUATED": set(),
    "SKIPPED_TECH": set(),
    "RESERVE": {"READY"},
}


class QueueStateError(ValueError):
    """Raised when a queue operation would violate the Gen0 contract."""


def _text(value: Any, field: str) -> str:
    """Normalize required queue text."""
    if value is None:
        raise QueueStateError(f"{field} is required")
    text = str(value).strip()
    if not text:
        raise QueueStateError(f"{field} is required")
    return text


def _order(value: Any) -> int:
    """Normalize positive sample order."""
    if isinstance(value, bool):
        raise QueueStateError("sample_order must be positive integer")
    try:
        number = int(value)
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise QueueStateError("sample_order must be positive integer") from exc
    if number <= 0 or numeric != number:
        raise QueueStateError("sample_order must be positive integer")
    return number


def validate_queue_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one queue row and return a normalized shallow copy."""
    if not isinstance(row, Mapping):
        raise QueueStateError("queue row must be an object")
    normalized = dict(row)
    normalized["manifest_id"] = _text(row.get("manifest_id"), "manifest_id")
    normalized["generation_id"] = _text(row.get("generation_id"), "generation_id")
    normalized["race_key"] = _text(row.get("race_key"), "race_key")
    normalized["race_date"] = _text(row.get("race_date"), "race_date")
    normalized["surface_code"] = _text(row.get("surface_code"), "surface_code")
    if normalized["surface_code"] not in {"1", "2"}:
        raise QueueStateError(f"unsupported surface_code: {normalized['surface_code']}")
    normalized["sample_order"] = _order(row.get("sample_order"))
    normalized["sample_role"] = _text(row.get("sample_role"), "sample_role").upper()
    if normalized["sample_role"] not in {"PRIMARY", "RESERVE"}:
        raise QueueStateError(f"unsupported sample_role: {normalized['sample_role']}")
    normalized["queue_status"] = _text(row.get("queue_status"), "queue_status").upper()
    if normalized["queue_status"] not in ALLOWED_STATUSES:
        raise QueueStateError(f"unsupported queue_status: {normalized['queue_status']}")
    return normalized


def next_ready_rows(
    rows: Sequence[Mapping[str, Any]],
    generation_id: str,
    limit: int = DEFAULT_CHUNK_SIZE,
) -> list[dict[str, Any]]:
    """Return the next READY races in immutable sample order."""
    if limit <= 0:
        raise QueueStateError("limit must be positive")
    generation = _text(generation_id, "generation_id")
    selected: list[dict[str, Any]] = []
    for raw_row in rows:
        row = validate_queue_row(raw_row)
        if row["generation_id"] != generation:
            continue
        if row["queue_status"] == "READY":
            selected.append(row)
    selected.sort(key=lambda row: row["sample_order"])
    return selected[:limit]


def validate_transition(old_status: str, new_status: str) -> None:
    """Reject queue rewinds and unsupported state jumps."""
    old_value = _text(old_status, "old_status").upper()
    new_value = _text(new_status, "new_status").upper()
    if old_value not in ALLOWED_TRANSITIONS:
        raise QueueStateError(f"unsupported old status: {old_value}")
    if new_value not in ALLOWED_STATUSES:
        raise QueueStateError(f"unsupported new status: {new_value}")
    if new_value not in ALLOWED_TRANSITIONS[old_value]:
        raise QueueStateError(f"invalid queue transition: {old_value} -> {new_value}")


def transition_row(
    row: Mapping[str, Any],
    new_status: str,
    **updates: Any,
) -> dict[str, Any]:
    """Create one validated queue-row update without mutating the input."""
    normalized = validate_queue_row(row)
    target = _text(new_status, "new_status").upper()
    validate_transition(normalized["queue_status"], target)
    normalized.update(updates)
    normalized["queue_status"] = target
    return normalized


def _effective_date_counts(
    rows: Sequence[Mapping[str, Any]],
    excluded_race_key: str,
) -> Counter[str]:
    """Count dates in the effective 50R set after removing one failed primary."""
    counts: Counter[str] = Counter()
    for row in rows:
        if row["race_key"] == excluded_race_key:
            continue
        if row["sample_role"] == "PRIMARY":
            if row["queue_status"] != "SKIPPED_TECH":
                counts[row["race_date"]] += 1
            continue
        if row["sample_role"] == "RESERVE" and row["queue_status"] != "RESERVE":
            counts[row["race_date"]] += 1
    return counts


def technical_replacement(
    rows: Sequence[Mapping[str, Any]],
    failed_race_key: str,
    skip_reason: str,
    max_per_date: int = DEFAULT_MAX_PER_DATE,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Skip a technical failure and promote a structure-preserving reserve.

    Replacement is allowed only before forecast starts. The promoted reserve must
    have the same turf/dirt code as the failed PRIMARY and must not make the
    effective sample exceed the same-date cap.
    """
    if max_per_date <= 0:
        raise QueueStateError("max_per_date must be positive")
    failed_key = _text(failed_race_key, "failed_race_key")
    reason = _text(skip_reason, "skip_reason")
    normalized_rows = [validate_queue_row(row) for row in rows]

    failed_matches = [row for row in normalized_rows if row["race_key"] == failed_key]
    if len(failed_matches) != 1:
        raise QueueStateError("failed race must exist exactly once in queue")
    failed = failed_matches[0]
    if failed["sample_role"] != "PRIMARY":
        raise QueueStateError("only PRIMARY race may be replaced")
    if failed["queue_status"] not in {"READY", "SOURCE_READY"}:
        raise QueueStateError("technical replacement must occur before forecast starts")

    date_counts = _effective_date_counts(normalized_rows, failed_key)
    reserves = [
        row
        for row in normalized_rows
        if row["sample_role"] == "RESERVE"
        and row["queue_status"] == "RESERVE"
        and row["surface_code"] == failed["surface_code"]
        and date_counts[row["race_date"]] < max_per_date
    ]
    reserves.sort(key=lambda row: row["sample_order"])
    if not reserves:
        raise QueueStateError(
            "no unused RESERVE race preserves surface and date-cap constraints"
        )

    skipped = transition_row(
        failed,
        "SKIPPED_TECH",
        skip_reason=reason,
    )
    promoted = transition_row(
        reserves[0],
        "READY",
        replacement_for=failed_key,
        skip_reason="",
    )
    return skipped, promoted
