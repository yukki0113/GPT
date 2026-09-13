#!/usr/bin/env python3
"""Input-completeness guard for RaceNote Forecast Gen0.

This module does not choose marks, ranks, or factor weights. It checks only
research integrity that cannot safely be inferred from a frozen forecast alone:
all source runners were evaluated, horse-scoped factor records refer to source
runners, and factor-usage identities are unique.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import racenote_forecast_gen0 as gen0


class ForecastGuardError(ValueError):
    """Raised when a frozen forecast is incomplete relative to its source race."""


def _require_sequence(value: Any, field: str) -> Sequence[Any]:
    """Return a non-string sequence or fail with a clear message."""
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ForecastGuardError(f"{field} must be a list")
    return value


def _positive_int(value: Any, field: str) -> int:
    """Normalize a positive integer without accepting booleans/fractions."""
    if isinstance(value, bool):
        raise ForecastGuardError(f"{field} must be a positive integer")
    try:
        number = int(value)
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ForecastGuardError(f"{field} must be a positive integer") from exc
    if number <= 0 or numeric != number:
        raise ForecastGuardError(f"{field} must be a positive integer")
    return number


def _source_horse_numbers(source_horses: Sequence[Mapping[str, Any]]) -> set[int]:
    """Build the authoritative runner-number set from RaceNote source rows."""
    rows = _require_sequence(source_horses, "source_horses")
    if not rows:
        raise ForecastGuardError("source_horses must not be empty")

    horse_numbers: set[int] = set()
    for index, raw_row in enumerate(rows, 1):
        if not isinstance(raw_row, Mapping):
            raise ForecastGuardError(f"source_horses[{index}] must be an object")
        horse_no = _positive_int(
            raw_row.get("horse_no"),
            f"source_horses[{index}].horse_no",
        )
        if horse_no in horse_numbers:
            raise ForecastGuardError(f"duplicate source horse_no: {horse_no}")
        horse_numbers.add(horse_no)
    return horse_numbers


def audit_forecast_input_completeness(
    frozen_forecast: Mapping[str, Any],
    source_horses: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Audit source-runner coverage and factor-usage identity integrity.

    ``source_horses`` must come from the same validated RaceNote source used for
    the forecast. This function intentionally accepts only runner identity data;
    it does not re-read or reinterpret racing evidence.
    """
    if not isinstance(frozen_forecast, Mapping):
        raise ForecastGuardError("frozen_forecast must be an object")

    try:
        freeze_audit = gen0.audit_frozen_forecast(frozen_forecast)
    except gen0.ForecastValidationError as exc:
        raise ForecastGuardError(str(exc)) from exc
    if freeze_audit["audit_status"] != "PASS":
        raise ForecastGuardError("frozen forecast hash audit must pass")

    source_numbers = _source_horse_numbers(source_horses)
    forecast_numbers: set[int] = set()
    for index, row in enumerate(frozen_forecast.get("horses", []), 1):
        if not isinstance(row, Mapping):
            raise ForecastGuardError(f"horses[{index}] must be an object")
        horse_no = _positive_int(row.get("horse_no"), f"horses[{index}].horse_no")
        if horse_no in forecast_numbers:
            raise ForecastGuardError(f"duplicate forecast horse_no: {horse_no}")
        forecast_numbers.add(horse_no)

    missing = sorted(source_numbers - forecast_numbers)
    extra = sorted(forecast_numbers - source_numbers)
    if missing or extra:
        raise ForecastGuardError(
            f"forecast runner coverage mismatch: missing={missing}, extra={extra}"
        )

    factor_identities: set[tuple[str, str, int | None]] = set()
    for index, raw_usage in enumerate(frozen_forecast.get("factor_usage", []), 1):
        if not isinstance(raw_usage, Mapping):
            raise ForecastGuardError(f"factor_usage[{index}] must be an object")

        factor_code = str(raw_usage.get("factor_code", "")).strip().upper()
        scope = str(raw_usage.get("scope", "")).strip().upper()
        horse_no: int | None = None
        raw_horse_no = raw_usage.get("horse_no")
        if raw_horse_no not in (None, ""):
            horse_no = _positive_int(
                raw_horse_no,
                f"factor_usage[{index}].horse_no",
            )
            if horse_no not in source_numbers:
                raise ForecastGuardError(
                    f"factor_usage[{index}] references non-source horse_no: {horse_no}"
                )

        identity = (factor_code, scope, horse_no)
        if identity in factor_identities:
            raise ForecastGuardError(
                f"duplicate factor usage identity: {identity}"
            )
        factor_identities.add(identity)

    return {
        "forecast_id": frozen_forecast.get("forecast_id"),
        "race_key": frozen_forecast.get("race_key"),
        "source_runner_count": len(source_numbers),
        "forecast_runner_count": len(forecast_numbers),
        "factor_usage_count": len(factor_identities),
        "runner_coverage_match": True,
        "factor_usage_identity_unique": True,
        "audit_status": "PASS",
    }
