#!/usr/bin/env python3
"""RaceNote Forecast Gen0 validation, freeze, and ledger row projection.

This module deliberately does not predict races. GPT remains the predictor.
The module owns the deterministic boundary around a GPT forecast: validation,
result-leakage guard, immutable hashing, freeze metadata, and projection to the
Google Sheets ledger contract.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime
from typing import Any, Mapping, Sequence

FORECAST_VERSION = "RaceNote-Forecast-Gen0.1"
FACTOR_SET_VERSION = "FSET-Gen0.1"
DEFAULT_GENERATION_ID = "Gen0-G000"
LEDGER_SPREADSHEET_ID = "1z9TJQJ61WEcrVSDxhAWP9D48plP1ixU0hCH-QGZrhnU"

FACTOR_NAMES = {
    "F01": "基礎能力",
    "F02": "条件適性",
    "F03": "展開・位置取り",
    "F04": "調教・状態",
    "F05": "近走内容",
    "F06": "長期履歴・条件実績",
    "F07": "騎手・厩舎",
    "F08": "血統",
    "F09": "枠・条件統計",
    "F10": "事前市場情報",
}

ALLOWED_MARKS = {"◎", "○", "▲", "△", ""}
ALLOWED_CONFIDENCE = {"A", "B", "C"}
ALLOWED_EVALUATION_MODES = {"BLINDED_HISTORICAL", "TRUE_FORWARD"}
ALLOWED_IMPORTANCE = {"HIGH", "MEDIUM", "LOW", "NOT_USED"}
ALLOWED_DIRECTION = {"POSITIVE", "NEGATIVE", "MIXED", "NEUTRAL"}
ALLOWED_ROLE = {"PRIMARY", "SUPPORT", "RISK", "DEEMPHASIZED"}
ALLOWED_SCOPE = {"RACE", "HORSE"}

# Exact key names that must never exist in a pre-result prediction payload.
# result_visibility_status is intentionally allowed because it proves the result
# was hidden at prediction time.
FORBIDDEN_RESULT_KEYS = {
    "finish",
    "finish_position",
    "final_odds",
    "final_popularity",
    "payout",
    "win_payout",
    "place_payout",
    "result",
    "results",
    "target_result",
    "outcome",
}


class ForecastValidationError(ValueError):
    """Raised when a Gen0 forecast violates the pre-result contract."""


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    """Return a mapping or fail with a field-specific message."""
    if not isinstance(value, Mapping):
        raise ForecastValidationError(f"{field} must be an object")
    return value


def _require_sequence(value: Any, field: str) -> Sequence[Any]:
    """Return a non-string sequence or fail."""
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ForecastValidationError(f"{field} must be a list")
    return value


def _require_text(value: Any, field: str) -> str:
    """Normalize required text while rejecting blank values."""
    if value is None:
        raise ForecastValidationError(f"{field} is required")
    text = str(value).strip()
    if not text:
        raise ForecastValidationError(f"{field} is required")
    return text


def _positive_int(value: Any, field: str) -> int:
    """Normalize a positive integer field."""
    if isinstance(value, bool):
        raise ForecastValidationError(f"{field} must be a positive integer")
    try:
        number = int(value)
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ForecastValidationError(f"{field} must be a positive integer") from exc
    if number <= 0 or numeric != number:
        raise ForecastValidationError(f"{field} must be a positive integer")
    return number


def _parse_iso_datetime(value: Any, field: str) -> datetime:
    """Parse an offset-aware ISO 8601 datetime."""
    text = _require_text(value, field)
    normalized = text
    if text.endswith("Z"):
        normalized = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ForecastValidationError(f"{field} must be ISO 8601 datetime") from exc
    if parsed.tzinfo is None:
        raise ForecastValidationError(f"{field} must include timezone offset")
    return parsed


def _validate_sha256(value: Any, field: str) -> str:
    """Validate and normalize a SHA-256 hex digest."""
    text = _require_text(value, field).lower()
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        raise ForecastValidationError(f"{field} must be 64 hex chars")
    return text


def _walk_forbidden_result_keys(value: Any, path: str = "$") -> None:
    """Reject result-only fields anywhere in the pre-result payload."""
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            if key.lower() in FORBIDDEN_RESULT_KEYS:
                raise ForecastValidationError(
                    f"post-race field is forbidden before freeze: {path}.{key}"
                )
            _walk_forbidden_result_keys(child, f"{path}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, child in enumerate(value):
            _walk_forbidden_result_keys(child, f"{path}[{index}]")


def _normalize_factor_codes(value: Any, field: str) -> list[str]:
    """Validate a factor-code list and preserve the supplied order."""
    rows = _require_sequence(value, field)
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_code in rows:
        code = _require_text(raw_code, field).upper()
        if code not in FACTOR_NAMES:
            raise ForecastValidationError(
                f"{field} contains unsupported factor: {code}"
            )
        if code in seen:
            raise ForecastValidationError(
                f"{field} contains duplicate factor: {code}"
            )
        seen.add(code)
        normalized.append(code)
    return normalized


def _normalize_horses(rows: Any) -> list[dict[str, Any]]:
    """Validate all horse comparisons and normalize ranks and marks."""
    source = _require_sequence(rows, "horses")
    if not source:
        raise ForecastValidationError("horses must not be empty")

    normalized: list[dict[str, Any]] = []
    seen_horses: set[int] = set()
    seen_ranks: set[int] = set()
    mark_counts = {"◎": 0, "○": 0, "▲": 0}

    for index, raw_row in enumerate(source, 1):
        row = dict(_require_mapping(raw_row, f"horses[{index}]"))
        horse_no = _positive_int(
            row.get("horse_no"),
            f"horses[{index}].horse_no",
        )
        if horse_no in seen_horses:
            raise ForecastValidationError(f"duplicate horse_no: {horse_no}")
        seen_horses.add(horse_no)

        rank = _positive_int(
            row.get("gpt_rank"),
            f"horses[{index}].gpt_rank",
        )
        if rank in seen_ranks:
            raise ForecastValidationError(f"duplicate gpt_rank: {rank}")
        seen_ranks.add(rank)

        mark = str(row.get("mark", "")).strip()
        if mark not in ALLOWED_MARKS:
            raise ForecastValidationError(
                f"unsupported mark for horse {horse_no}: {mark}"
            )
        if mark in mark_counts:
            mark_counts[mark] += 1

        row["horse_no"] = horse_no
        row["horse_name"] = _require_text(
            row.get("horse_name"),
            f"horses[{index}].horse_name",
        )
        row["gpt_rank"] = rank
        row["mark"] = mark
        row["primary_factor_codes"] = _normalize_factor_codes(
            row.get("primary_factor_codes", []),
            f"horses[{index}].primary_factor_codes",
        )
        row["supporting_factor_codes"] = _normalize_factor_codes(
            row.get("supporting_factor_codes", []),
            f"horses[{index}].supporting_factor_codes",
        )
        row["risk_factor_codes"] = _normalize_factor_codes(
            row.get("risk_factor_codes", []),
            f"horses[{index}].risk_factor_codes",
        )
        normalized.append(row)

    expected_ranks = set(range(1, len(normalized) + 1))
    if seen_ranks != expected_ranks:
        raise ForecastValidationError(
            "gpt_rank must be contiguous from 1 to horse count"
        )
    if mark_counts["◎"] != 1:
        raise ForecastValidationError("exactly one ◎ is required")
    if mark_counts["○"] > 1:
        raise ForecastValidationError("at most one ○ is allowed")
    if mark_counts["▲"] > 1:
        raise ForecastValidationError("at most one ▲ is allowed")

    normalized.sort(key=lambda item: item["gpt_rank"])
    return normalized


def _normalize_factor_usage(rows: Any) -> list[dict[str, Any]]:
    """Validate structured observations of how GPT used each factor."""
    source = _require_sequence(rows, "factor_usage")
    normalized: list[dict[str, Any]] = []

    for index, raw_row in enumerate(source, 1):
        row = dict(_require_mapping(raw_row, f"factor_usage[{index}]"))
        code = _require_text(
            row.get("factor_code"),
            f"factor_usage[{index}].factor_code",
        ).upper()
        if code not in FACTOR_NAMES:
            raise ForecastValidationError(f"unsupported factor code: {code}")

        scope = _require_text(
            row.get("scope"),
            f"factor_usage[{index}].scope",
        ).upper()
        if scope not in ALLOWED_SCOPE:
            raise ForecastValidationError(f"unsupported factor scope: {scope}")

        importance = _require_text(
            row.get("importance"),
            f"factor_usage[{index}].importance",
        ).upper()
        if importance not in ALLOWED_IMPORTANCE:
            raise ForecastValidationError(
                f"unsupported factor importance: {importance}"
            )

        direction = _require_text(
            row.get("direction"),
            f"factor_usage[{index}].direction",
        ).upper()
        if direction not in ALLOWED_DIRECTION:
            raise ForecastValidationError(
                f"unsupported factor direction: {direction}"
            )

        role = _require_text(
            row.get("role"),
            f"factor_usage[{index}].role",
        ).upper()
        if role not in ALLOWED_ROLE:
            raise ForecastValidationError(f"unsupported factor role: {role}")

        horse_no = row.get("horse_no")
        if horse_no not in (None, ""):
            horse_no = _positive_int(
                horse_no,
                f"factor_usage[{index}].horse_no",
            )
        if scope == "HORSE" and horse_no in (None, ""):
            raise ForecastValidationError(
                f"factor_usage[{index}] HORSE scope requires horse_no"
            )

        row["factor_code"] = code
        row["factor_name"] = FACTOR_NAMES[code]
        row["scope"] = scope
        row["importance"] = importance
        row["direction"] = direction
        row["role"] = role
        row["horse_no"] = horse_no
        normalized.append(row)

    return normalized


def _make_forecast_id(
    target_date: str,
    venue: str,
    race_no: int,
    generation_id: str,
) -> str:
    """Build a stable human-readable forecast identity."""
    compact_date = target_date.replace("-", "")
    compact_venue = venue.replace(" ", "")
    return f"{compact_date}_{compact_venue}_{race_no:02d}_{generation_id}"


def validate_forecast(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize a pre-result RaceNote Forecast Gen0 payload."""
    source_payload = dict(_require_mapping(payload, "forecast"))

    # Fail closed before any normalization can hide a leaked result field.
    _walk_forbidden_result_keys(source_payload)

    target_date = _require_text(source_payload.get("target_date"), "target_date")
    venue = _require_text(source_payload.get("venue"), "venue")
    race_no = _positive_int(source_payload.get("race_no"), "race_no")
    race_key = _require_text(source_payload.get("race_key"), "race_key")
    generation_id = _require_text(
        source_payload.get("generation_id", DEFAULT_GENERATION_ID),
        "generation_id",
    )

    evaluation_mode = _require_text(
        source_payload.get("evaluation_mode"),
        "evaluation_mode",
    ).upper()
    if evaluation_mode not in ALLOWED_EVALUATION_MODES:
        raise ForecastValidationError(
            f"unsupported evaluation_mode: {evaluation_mode}"
        )

    source = dict(_require_mapping(source_payload.get("source"), "source"))
    source["schema"] = _require_text(source.get("schema"), "source.schema")
    source["reader_view_version"] = _require_text(
        source.get("reader_view_version"),
        "source.reader_view_version",
    )
    source["semantic_sha256"] = _validate_sha256(
        source.get("semantic_sha256"),
        "source.semantic_sha256",
    )
    source["artifact_ref"] = _require_text(
        source.get("artifact_ref"),
        "source.artifact_ref",
    )

    forecast_created_at = _require_text(
        source_payload.get("forecast_created_at"),
        "forecast_created_at",
    )
    _parse_iso_datetime(forecast_created_at, "forecast_created_at")

    pre_race_guard_status = _require_text(
        source_payload.get("pre_race_guard_status"),
        "pre_race_guard_status",
    ).upper()
    if pre_race_guard_status != "PASS":
        raise ForecastValidationError("pre_race_guard_status must be PASS")

    result_visibility_status = _require_text(
        source_payload.get("result_visibility_status"),
        "result_visibility_status",
    ).upper()
    if result_visibility_status != "HIDDEN":
        raise ForecastValidationError("result_visibility_status must be HIDDEN")

    race_reading = dict(
        _require_mapping(source_payload.get("race_reading"), "race_reading")
    )
    race_reading["shape_summary"] = _require_text(
        race_reading.get("shape_summary"),
        "race_reading.shape_summary",
    )
    race_reading["expected_pace"] = _require_text(
        race_reading.get("expected_pace"),
        "race_reading.expected_pace",
    )
    race_reading["important_condition_factors"] = _require_text(
        race_reading.get("important_condition_factors"),
        "race_reading.important_condition_factors",
    )
    race_reading["primary_factor_codes"] = _normalize_factor_codes(
        race_reading.get("primary_factor_codes", []),
        "race_reading.primary_factor_codes",
    )
    race_reading["de_emphasized_factor_codes"] = _normalize_factor_codes(
        race_reading.get("de_emphasized_factor_codes", []),
        "race_reading.de_emphasized_factor_codes",
    )

    overlap = set(race_reading["primary_factor_codes"])
    overlap &= set(race_reading["de_emphasized_factor_codes"])
    if overlap:
        joined = ",".join(sorted(overlap))
        raise ForecastValidationError(
            f"factor cannot be both primary and de-emphasized: {joined}"
        )

    horses = _normalize_horses(source_payload.get("horses"))
    factor_usage = _normalize_factor_usage(
        source_payload.get("factor_usage", [])
    )

    final_prediction = dict(
        _require_mapping(
            source_payload.get("final_prediction"),
            "final_prediction",
        )
    )
    axis_horse_no = _positive_int(
        final_prediction.get("axis_horse_no"),
        "final_prediction.axis_horse_no",
    )
    confidence = _require_text(
        final_prediction.get("confidence"),
        "final_prediction.confidence",
    ).upper()
    if confidence not in ALLOWED_CONFIDENCE:
        raise ForecastValidationError(f"unsupported confidence: {confidence}")

    final_prediction["axis_horse_no"] = axis_horse_no
    final_prediction["confidence"] = confidence
    final_prediction["axis_reason"] = _require_text(
        final_prediction.get("axis_reason"),
        "final_prediction.axis_reason",
    )
    final_prediction["uncertainty_summary"] = _require_text(
        final_prediction.get("uncertainty_summary"),
        "final_prediction.uncertainty_summary",
    )
    alternatives = final_prediction.get("alternatives", "")
    final_prediction["alternatives"] = str(alternatives).strip()

    axis_rows = [
        row
        for row in horses
        if row["horse_no"] == axis_horse_no
    ]
    if len(axis_rows) != 1:
        raise ForecastValidationError("axis_horse_no must exist in horses")
    if axis_rows[0]["mark"] != "◎":
        raise ForecastValidationError("axis_horse_no must be the ◎ horse")

    # Build the normalized immutable prediction body.
    normalized = copy.deepcopy(source_payload)
    forecast_id = source_payload.get("forecast_id")
    if forecast_id in (None, ""):
        forecast_id = _make_forecast_id(
            target_date,
            venue,
            race_no,
            generation_id,
        )

    normalized["forecast_id"] = _require_text(forecast_id, "forecast_id")
    normalized["generation_id"] = generation_id
    normalized["target_date"] = target_date
    normalized["venue"] = venue
    normalized["race_no"] = race_no
    normalized["race_key"] = race_key
    normalized["evaluation_mode"] = evaluation_mode
    normalized["source"] = source
    normalized["forecast_version"] = FORECAST_VERSION
    normalized["factor_set_version"] = FACTOR_SET_VERSION
    normalized["forecast_created_at"] = forecast_created_at
    normalized["pre_race_guard_status"] = pre_race_guard_status
    normalized["result_visibility_status"] = result_visibility_status
    normalized["race_reading"] = race_reading
    normalized["horses"] = horses
    normalized["factor_usage"] = factor_usage
    normalized["final_prediction"] = final_prediction
    return normalized


def canonical_prediction_bytes(forecast: Mapping[str, Any]) -> bytes:
    """Serialize prediction content deterministically for hashing."""
    normalized = copy.deepcopy(dict(forecast))
    for key in ("prediction_hash", "freeze_status", "frozen_at"):
        normalized.pop(key, None)
    text = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return text.encode("utf-8")


def compute_prediction_hash(forecast: Mapping[str, Any]) -> str:
    """Compute deterministic SHA-256 for the prediction body."""
    return hashlib.sha256(canonical_prediction_bytes(forecast)).hexdigest()


def freeze_forecast(
    payload: Mapping[str, Any],
    frozen_at: str,
) -> dict[str, Any]:
    """Validate a forecast and attach immutable freeze metadata."""
    normalized = validate_forecast(payload)
    frozen_time = _parse_iso_datetime(frozen_at, "frozen_at")
    created_time = _parse_iso_datetime(
        normalized["forecast_created_at"],
        "forecast_created_at",
    )
    if frozen_time < created_time:
        raise ForecastValidationError(
            "frozen_at must not precede forecast_created_at"
        )

    frozen = copy.deepcopy(normalized)
    frozen["prediction_hash"] = compute_prediction_hash(normalized)
    frozen["freeze_status"] = "FROZEN"
    frozen["frozen_at"] = frozen_at
    return frozen


def audit_frozen_forecast(
    frozen_forecast: Mapping[str, Any],
    result_acquired_at: str | None = None,
) -> dict[str, Any]:
    """Audit hash integrity and freeze-before-result ordering."""
    row = dict(_require_mapping(frozen_forecast, "frozen_forecast"))
    if row.get("freeze_status") != "FROZEN":
        raise ForecastValidationError("freeze_status must be FROZEN")

    expected_hash = _validate_sha256(
        row.get("prediction_hash"),
        "prediction_hash",
    )
    recomputed_hash = compute_prediction_hash(row)
    hash_match = expected_hash == recomputed_hash

    frozen_time = _parse_iso_datetime(row.get("frozen_at"), "frozen_at")
    freeze_before_result = True
    result_time_text = ""
    if result_acquired_at not in (None, ""):
        result_time = _parse_iso_datetime(
            result_acquired_at,
            "result_acquired_at",
        )
        result_time_text = str(result_acquired_at)
        freeze_before_result = frozen_time < result_time

    audit_status = "PASS"
    if not hash_match or not freeze_before_result:
        audit_status = "FAIL"

    forward_status = "FROZEN_PRE_RESULT"
    if result_time_text:
        forward_status = "RESULT_JOINED"

    return {
        "forecast_id": row["forecast_id"],
        "generation_id": row["generation_id"],
        "race_key": row["race_key"],
        "forecast_created_at": row["forecast_created_at"],
        "frozen_at": row["frozen_at"],
        "result_acquired_at": result_time_text,
        "pre_race_guard_status": row["pre_race_guard_status"],
        "result_visibility_status": row["result_visibility_status"],
        "source_hash": row["source"]["semantic_sha256"],
        "prediction_hash": expected_hash,
        "recomputed_hash": recomputed_hash,
        "hash_match": hash_match,
        "freeze_before_result": freeze_before_result,
        "forward_status": forward_status,
        "audit_status": audit_status,
        "audit_note": "",
        "evaluation_mode": row["evaluation_mode"],
    }


def _joined_factor_codes(value: Sequence[str]) -> str:
    """Join factor codes for spreadsheet storage."""
    return ",".join(value)


def _marks_by_symbol(
    horses: Sequence[Mapping[str, Any]],
    mark: str,
) -> str:
    """Return comma-separated horse numbers for one mark."""
    horse_numbers = [
        str(row["horse_no"])
        for row in horses
        if row.get("mark") == mark
    ]
    return ",".join(horse_numbers)


def to_ledger_rows(
    frozen_forecast: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Project one frozen forecast into the Google Sheets ledger row model."""
    row = dict(_require_mapping(frozen_forecast, "frozen_forecast"))
    audit = audit_frozen_forecast(row)
    horses = list(row["horses"])
    axis_no = int(row["final_prediction"]["axis_horse_no"])

    axis_name = ""
    for horse in horses:
        if horse["horse_no"] == axis_no:
            axis_name = horse["horse_name"]
            break

    freeze_row = {
        "forecast_id": row["forecast_id"],
        "generation_id": row["generation_id"],
        "target_date": row["target_date"],
        "venue": row["venue"],
        "race_no": row["race_no"],
        "race_key": row["race_key"],
        "source_schema": row["source"]["schema"],
        "reader_view_version": row["source"]["reader_view_version"],
        "source_semantic_sha256": row["source"]["semantic_sha256"],
        "source_artifact_ref": row["source"]["artifact_ref"],
        "forecast_version": row["forecast_version"],
        "factor_set_version": row["factor_set_version"],
        "forecast_created_at": row["forecast_created_at"],
        "pre_race_guard_status": row["pre_race_guard_status"],
        "result_visibility_status": row["result_visibility_status"],
        "race_shape_summary": row["race_reading"]["shape_summary"],
        "expected_pace": row["race_reading"]["expected_pace"],
        "important_condition_factors": row["race_reading"][
            "important_condition_factors"
        ],
        "primary_factor_codes": _joined_factor_codes(
            row["race_reading"]["primary_factor_codes"]
        ),
        "de_emphasized_factor_codes": _joined_factor_codes(
            row["race_reading"]["de_emphasized_factor_codes"]
        ),
        "axis_horse_no": axis_no,
        "axis_horse_name": axis_name,
        "mark_◎": _marks_by_symbol(horses, "◎"),
        "mark_○": _marks_by_symbol(horses, "○"),
        "mark_▲": _marks_by_symbol(horses, "▲"),
        "mark_△": _marks_by_symbol(horses, "△"),
        "confidence": row["final_prediction"]["confidence"],
        "axis_reason": row["final_prediction"]["axis_reason"],
        "uncertainty_summary": row["final_prediction"][
            "uncertainty_summary"
        ],
        "alternatives": row["final_prediction"]["alternatives"],
        "prediction_hash": row["prediction_hash"],
        "freeze_status": row["freeze_status"],
        "frozen_at": row["frozen_at"],
        "notes": "",
        "evaluation_mode": row["evaluation_mode"],
    }

    horse_rows: list[dict[str, Any]] = []
    for horse in horses:
        race_horse_key = f'{row["race_key"]}{horse["horse_no"]:02d}'
        horse_rows.append(
            {
                "forecast_id": row["forecast_id"],
                "generation_id": row["generation_id"],
                "race_key": row["race_key"],
                "race_horse_key": race_horse_key,
                "horse_no": horse["horse_no"],
                "horse_name": horse["horse_name"],
                "gpt_rank": horse["gpt_rank"],
                "mark": horse["mark"],
                "strengths": str(horse.get("strengths", "")),
                "risks": str(horse.get("risks", "")),
                "evidence_summary": str(horse.get("evidence_summary", "")),
                "evidence_conflicts": str(
                    horse.get("evidence_conflicts", "")
                ),
                "relative_comparison": str(
                    horse.get("relative_comparison", "")
                ),
                "primary_factor_codes": _joined_factor_codes(
                    horse["primary_factor_codes"]
                ),
                "supporting_factor_codes": _joined_factor_codes(
                    horse["supporting_factor_codes"]
                ),
                "risk_factor_codes": _joined_factor_codes(
                    horse["risk_factor_codes"]
                ),
                "ability_reading": str(horse.get("ability_reading", "")),
                "suitability_reading": str(
                    horse.get("suitability_reading", "")
                ),
                "pace_position_reading": str(
                    horse.get("pace_position_reading", "")
                ),
                "condition_training_reading": str(
                    horse.get("condition_training_reading", "")
                ),
                "recent_form_reading": str(
                    horse.get("recent_form_reading", "")
                ),
                "history_reading": str(horse.get("history_reading", "")),
                "context_reading": str(horse.get("context_reading", "")),
                "uncertainty": str(horse.get("uncertainty", "")),
            }
        )

    factor_rows: list[dict[str, Any]] = []
    for factor in row["factor_usage"]:
        horse_no = factor.get("horse_no", "")
        if horse_no is None:
            horse_no = ""
        factor_rows.append(
            {
                "forecast_id": row["forecast_id"],
                "generation_id": row["generation_id"],
                "race_key": row["race_key"],
                "horse_no": horse_no,
                "factor_code": factor["factor_code"],
                "factor_name": factor["factor_name"],
                "scope": factor["scope"],
                "importance": factor["importance"],
                "direction": factor["direction"],
                "role": factor["role"],
                "judgment_summary": str(
                    factor.get("judgment_summary", "")
                ),
                "evidence_summary": str(
                    factor.get("evidence_summary", "")
                ),
                "evidence_ref": str(factor.get("evidence_ref", "")),
                "pre_result_note": str(
                    factor.get("pre_result_note", "")
                ),
                "created_at": row["forecast_created_at"],
                "freeze_hash": row["prediction_hash"],
                "factor_set_version": row["factor_set_version"],
                "record_status": "FROZEN",
            }
        )

    return {
        "予想Freeze": [freeze_row],
        "馬別評価": horse_rows,
        "ファクター使用": factor_rows,
        "Freeze監査": [audit],
    }
