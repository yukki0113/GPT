#!/usr/bin/env python3
"""Post-race evaluation helpers for RaceNote Forecast Gen0.

The prediction is already frozen before this module is used. This module joins
official result rows to the frozen forecast, computes objective outcome fields,
and projects GPT's post-race reading review into separate ledger rows without
modifying the frozen prediction.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

import racenote_forecast_gen0 as gen0

READING_GRADES = {"GOOD", "MIXED", "POOR", "UNRESOLVED"}
POST_RELEVANCE = {"HELPFUL", "NEUTRAL", "MISLEADING", "UNRESOLVED"}
OVER_UNDER = {"OVER", "UNDER", "APPROPRIATE", "NA"}
EVIDENCE_QUALITY = {"GOOD", "MIXED", "POOR", "UNRESOLVED"}


class EvaluationValidationError(ValueError):
    """Raised when post-race evaluation input violates the Gen0 contract."""


def _require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    """Return a mapping or raise a field-specific validation error."""
    if not isinstance(value, Mapping):
        raise EvaluationValidationError(f"{field} must be an object")
    return value


def _require_sequence(value: Any, field: str) -> Sequence[Any]:
    """Return a non-string sequence or raise."""
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise EvaluationValidationError(f"{field} must be a list")
    return value


def _require_text(value: Any, field: str) -> str:
    """Normalize required text while rejecting blanks."""
    if value is None:
        raise EvaluationValidationError(f"{field} is required")
    text = str(value).strip()
    if not text:
        raise EvaluationValidationError(f"{field} is required")
    return text


def _positive_int(value: Any, field: str) -> int:
    """Normalize a positive integer."""
    if isinstance(value, bool):
        raise EvaluationValidationError(f"{field} must be a positive integer")
    try:
        number = int(value)
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise EvaluationValidationError(f"{field} must be a positive integer") from exc
    if number <= 0 or numeric != number:
        raise EvaluationValidationError(f"{field} must be a positive integer")
    return number


def _optional_number(value: Any, field: str) -> float | None:
    """Normalize an optional non-negative numeric field."""
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise EvaluationValidationError(f"{field} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EvaluationValidationError(f"{field} must be numeric") from exc
    if number < 0:
        raise EvaluationValidationError(f"{field} must be non-negative")
    return number


def _result_set_hash(rows: Sequence[Mapping[str, Any]]) -> str:
    """Compute deterministic SHA-256 for normalized official result rows."""
    text = json.dumps(
        list(rows),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_result_rows(
    frozen_forecast: Mapping[str, Any],
    result_rows: Sequence[Mapping[str, Any]],
    result_source: Mapping[str, Any],
    result_acquired_at: str,
) -> list[dict[str, Any]]:
    """Validate a complete result set after confirming freeze-before-result."""
    audit = gen0.audit_frozen_forecast(
        frozen_forecast,
        result_acquired_at=result_acquired_at,
    )
    if audit["audit_status"] != "PASS":
        raise EvaluationValidationError(
            "frozen forecast failed freeze-before-result integrity"
        )

    source = _require_mapping(result_source, "result_source")
    source_ref = _require_text(source.get("ref"), "result_source.ref")
    try:
        source_sha = gen0._validate_sha256(
            source.get("sha256"),
            "result_source.sha256",
        )
    except gen0.ForecastValidationError as exc:
        raise EvaluationValidationError(str(exc)) from exc

    expected_horses = {
        int(row["horse_no"]): str(row["horse_name"])
        for row in frozen_forecast["horses"]
    }
    rows = _require_sequence(result_rows, "result_rows")
    normalized: list[dict[str, Any]] = []
    seen: set[int] = set()

    for index, raw_row in enumerate(rows, 1):
        row = dict(_require_mapping(raw_row, f"result_rows[{index}]"))
        horse_no = _positive_int(
            row.get("horse_no"),
            f"result_rows[{index}].horse_no",
        )
        if horse_no in seen:
            raise EvaluationValidationError(f"duplicate result horse_no: {horse_no}")
        if horse_no not in expected_horses:
            raise EvaluationValidationError(
                f"result contains horse outside frozen forecast: {horse_no}"
            )
        seen.add(horse_no)

        abnormal_status = str(row.get("abnormal_status", "")).strip()
        finish_position = row.get("finish_position")
        normalized_finish: int | None = None
        if finish_position not in (None, ""):
            normalized_finish = _positive_int(
                finish_position,
                f"result_rows[{index}].finish_position",
            )
        if normalized_finish is None and not abnormal_status:
            raise EvaluationValidationError(
                f"result_rows[{index}] requires finish_position or abnormal_status"
            )

        final_popularity = row.get("final_popularity")
        normalized_popularity: int | None = None
        if final_popularity not in (None, ""):
            normalized_popularity = _positive_int(
                final_popularity,
                f"result_rows[{index}].final_popularity",
            )

        normalized.append(
            {
                "horse_no": horse_no,
                "horse_name": expected_horses[horse_no],
                "finish_position": normalized_finish,
                "abnormal_status": abnormal_status,
                "final_odds": _optional_number(
                    row.get("final_odds"),
                    f"result_rows[{index}].final_odds",
                ),
                "final_popularity": normalized_popularity,
            }
        )

    if seen != set(expected_horses):
        missing = sorted(set(expected_horses) - seen)
        raise EvaluationValidationError(
            f"result set is incomplete; missing horse_no: {missing}"
        )

    winners = [
        row
        for row in normalized
        if row["finish_position"] == 1
    ]
    if not winners:
        raise EvaluationValidationError("result set must contain at least one winner")

    normalized.sort(key=lambda item: item["horse_no"])
    result_hash = _result_set_hash(normalized)

    ledger_rows: list[dict[str, Any]] = []
    for row in normalized:
        race_horse_key = (
            f'{frozen_forecast["race_key"]}{row["horse_no"]:02d}'
        )
        ledger_rows.append(
            {
                "result_id": f'{frozen_forecast["target_date"]}_{race_horse_key}',
                "target_date": frozen_forecast["target_date"],
                "venue": frozen_forecast["venue"],
                "race_no": frozen_forecast["race_no"],
                "race_key": frozen_forecast["race_key"],
                "race_horse_key": race_horse_key,
                "horse_no": row["horse_no"],
                "horse_name": row["horse_name"],
                "finish_position": row["finish_position"],
                "abnormal_status": row["abnormal_status"],
                "final_odds": row["final_odds"],
                "final_popularity": row["final_popularity"],
                "result_source_ref": source_ref,
                "result_source_sha256": source_sha,
                "result_acquired_at": result_acquired_at,
                "result_hash": result_hash,
                "join_status": "MATCHED",
                "notes": "",
            }
        )
    return ledger_rows


def _normalize_grade(value: Any, field: str) -> str:
    """Validate one reading-review grade."""
    grade = _require_text(value, field).upper()
    if grade not in READING_GRADES:
        raise EvaluationValidationError(f"unsupported {field}: {grade}")
    return grade


def _marks_by_horse(frozen_forecast: Mapping[str, Any]) -> dict[int, str]:
    """Build a horse-number to frozen-mark lookup."""
    return {
        int(row["horse_no"]): str(row.get("mark", ""))
        for row in frozen_forecast["horses"]
    }


def _normalize_factor_reviews(
    frozen_forecast: Mapping[str, Any],
    factor_reviews: Sequence[Mapping[str, Any]],
    evaluation_id: str,
    evaluated_at: str,
) -> list[dict[str, Any]]:
    """Validate post-race reviews for every recorded pre-result factor use."""
    source_reviews = _require_sequence(factor_reviews, "factor_reviews")
    review_map: dict[tuple[str, str], Mapping[str, Any]] = {}

    for index, raw_review in enumerate(source_reviews, 1):
        review = _require_mapping(raw_review, f"factor_reviews[{index}]")
        factor_code = _require_text(
            review.get("factor_code"),
            f"factor_reviews[{index}].factor_code",
        ).upper()
        horse_key = ""
        horse_no = review.get("horse_no")
        if horse_no not in (None, ""):
            horse_key = str(
                _positive_int(
                    horse_no,
                    f"factor_reviews[{index}].horse_no",
                )
            )
        identity = (factor_code, horse_key)
        if identity in review_map:
            raise EvaluationValidationError(
                f"duplicate factor review: {identity}"
            )
        review_map[identity] = review

    output: list[dict[str, Any]] = []
    expected_identities: set[tuple[str, str]] = set()
    for usage in frozen_forecast["factor_usage"]:
        horse_key = ""
        if usage.get("horse_no") not in (None, ""):
            horse_key = str(usage["horse_no"])
        identity = (usage["factor_code"], horse_key)
        expected_identities.add(identity)
        if identity not in review_map:
            raise EvaluationValidationError(
                f"missing post-race factor review: {identity}"
            )
        review = review_map[identity]

        post_relevance = _require_text(
            review.get("post_relevance"),
            f"factor_review{identity}.post_relevance",
        ).upper()
        if post_relevance not in POST_RELEVANCE:
            raise EvaluationValidationError(
                f"unsupported post_relevance: {post_relevance}"
            )

        over_under_eval = _require_text(
            review.get("over_under_eval"),
            f"factor_review{identity}.over_under_eval",
        ).upper()
        if over_under_eval not in OVER_UNDER:
            raise EvaluationValidationError(
                f"unsupported over_under_eval: {over_under_eval}"
            )

        evidence_quality = _require_text(
            review.get("evidence_quality"),
            f"factor_review{identity}.evidence_quality",
        ).upper()
        if evidence_quality not in EVIDENCE_QUALITY:
            raise EvaluationValidationError(
                f"unsupported evidence_quality: {evidence_quality}"
            )

        output.append(
            {
                "evaluation_id": evaluation_id,
                "forecast_id": frozen_forecast["forecast_id"],
                "generation_id": frozen_forecast["generation_id"],
                "race_key": frozen_forecast["race_key"],
                "factor_code": usage["factor_code"],
                "factor_name": usage["factor_name"],
                "pre_importance": usage["importance"],
                "pre_direction": usage["direction"],
                "applied_to_horse_no": usage.get("horse_no", ""),
                "post_relevance": post_relevance,
                "outcome_summary": _require_text(
                    review.get("outcome_summary"),
                    f"factor_review{identity}.outcome_summary",
                ),
                "over_under_eval": over_under_eval,
                "evidence_quality": evidence_quality,
                "recurring_pattern_tag": str(
                    review.get("recurring_pattern_tag", "")
                ).strip(),
                "evaluated_at": evaluated_at,
                "notes": str(review.get("notes", "")).strip(),
            }
        )

    extra = set(review_map) - expected_identities
    if extra:
        raise EvaluationValidationError(
            f"factor review has no matching frozen usage: {sorted(extra)}"
        )
    return output


def build_post_race_rows(
    frozen_forecast: Mapping[str, Any],
    result_rows: Sequence[Mapping[str, Any]],
    result_source: Mapping[str, Any],
    result_acquired_at: str,
    review: Mapping[str, Any],
    factor_reviews: Sequence[Mapping[str, Any]],
    evaluated_at: str,
) -> dict[str, list[dict[str, Any]]]:
    """Build post-race ledger rows without altering frozen prediction rows."""
    normalized_results = validate_result_rows(
        frozen_forecast,
        result_rows,
        result_source,
        result_acquired_at,
    )
    review_row = _require_mapping(review, "review")
    marks = _marks_by_horse(frozen_forecast)

    winners = [
        row
        for row in normalized_results
        if row["finish_position"] == 1
    ]
    winner_horse_numbers = [str(row["horse_no"]) for row in winners]
    winner_marks = [marks.get(int(row["horse_no"]), "") for row in winners]
    winner_marks = [mark for mark in winner_marks if mark]

    axis_no = int(frozen_forecast["final_prediction"]["axis_horse_no"])
    axis_rows = [
        row
        for row in normalized_results
        if int(row["horse_no"]) == axis_no
    ]
    if len(axis_rows) != 1:
        raise EvaluationValidationError("axis result row is not unique")
    axis_finish = axis_rows[0]["finish_position"]
    axis_win_flag = axis_finish == 1

    top3_marks_count = 0
    for row in normalized_results:
        finish_position = row["finish_position"]
        if finish_position is None:
            continue
        if finish_position <= 3 and marks.get(int(row["horse_no"]), ""):
            top3_marks_count += 1

    evaluation_id = f'EVAL_{frozen_forecast["forecast_id"]}'
    evaluation_row = {
        "evaluation_id": evaluation_id,
        "forecast_id": frozen_forecast["forecast_id"],
        "generation_id": frozen_forecast["generation_id"],
        "target_date": frozen_forecast["target_date"],
        "venue": frozen_forecast["venue"],
        "race_no": frozen_forecast["race_no"],
        "race_key": frozen_forecast["race_key"],
        "axis_horse_no": axis_no,
        "axis_finish": axis_finish,
        "axis_win_flag": axis_win_flag,
        "winner_horse_no": ",".join(winner_horse_numbers),
        "winner_mark": ",".join(winner_marks),
        "winner_in_marks": bool(winner_marks),
        "top3_marks_count": top3_marks_count,
        "race_reading_grade": _normalize_grade(
            review_row.get("race_reading_grade"),
            "race_reading_grade",
        ),
        "ability_reading_eval": _normalize_grade(
            review_row.get("ability_reading_eval"),
            "ability_reading_eval",
        ),
        "suitability_eval": _normalize_grade(
            review_row.get("suitability_eval"),
            "suitability_eval",
        ),
        "pace_position_eval": _normalize_grade(
            review_row.get("pace_position_eval"),
            "pace_position_eval",
        ),
        "condition_training_eval": _normalize_grade(
            review_row.get("condition_training_eval"),
            "condition_training_eval",
        ),
        "recent_form_eval": _normalize_grade(
            review_row.get("recent_form_eval"),
            "recent_form_eval",
        ),
        "history_eval": _normalize_grade(
            review_row.get("history_eval"),
            "history_eval",
        ),
        "uncertainty_eval": _normalize_grade(
            review_row.get("uncertainty_eval"),
            "uncertainty_eval",
        ),
        "primary_failure_category": str(
            review_row.get("primary_failure_category", "")
        ).strip(),
        "post_race_summary": _require_text(
            review_row.get("post_race_summary"),
            "post_race_summary",
        ),
        "evaluated_at": evaluated_at,
    }

    factor_rows = _normalize_factor_reviews(
        frozen_forecast,
        factor_reviews,
        evaluation_id,
        evaluated_at,
    )
    freeze_audit = gen0.audit_frozen_forecast(
        frozen_forecast,
        result_acquired_at=result_acquired_at,
    )

    return {
        "結果_馬別": normalized_results,
        "振返り": [evaluation_row],
        "ファクター検証": factor_rows,
        "Freeze監査": [freeze_audit],
    }
