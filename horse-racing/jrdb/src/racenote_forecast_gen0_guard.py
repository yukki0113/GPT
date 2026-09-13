#!/usr/bin/env python3
"""Input-completeness guard for RaceNote Forecast Gen0.

This module does not choose marks, ranks, or factor weights. It checks only
research integrity that cannot safely be inferred from a frozen forecast alone:
all source runners were evaluated, runner identities match the source race,
horse-scoped factor records refer to source runners, and factor-usage identities
are unique.
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


def _require_text(value: Any, field: str) -> str:
    """Normalize required identity text while rejecting blanks."""
    if value is None:
        raise ForecastGuardError(f"{field} is required")
    text = str(value).strip()
    if not text:
        raise ForecastGuardError(f"{field} is required")
    return text


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


def _source_horse_identity(
    source_horses: Sequence[Mapping[str, Any]],
) -> dict[int, str]:
    """Build authoritative horse-number/name identities from RaceNote source."""
    rows = _require_sequence(source_horses, "source_horses")
    if not rows:
        raise ForecastGuardError("source_horses must not be empty")

    identities: dict[int, str] = {}
    for index, raw_row in enumerate(rows, 1):
        if not isinstance(raw_row, Mapping):
            raise ForecastGuardError(f"source_horses[{index}] must be an object")
        horse_no = _positive_int(
            raw_row.get("horse_no"),
            f"source_horses[{index}].horse_no",
        )
        horse_name = _require_text(
            raw_row.get("horse_name"),
            f"source_horses[{index}].horse_name",
        )
        if horse_no in identities:
            raise ForecastGuardError(f"duplicate source horse_no: {horse_no}")
        identities[horse_no] = horse_name
    return identities


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

    source_identity = _source_horse_identity(source_horses)
    source_numbers = set(source_identity)
    forecast_identity: dict[int, str] = {}
    for index, row in enumerate(frozen_forecast.get("horses", []), 1):
        if not isinstance(row, Mapping):
            raise ForecastGuardError(f"horses[{index}] must be an object")
        horse_no = _positive_int(row.get("horse_no"), f"horses[{index}].horse_no")
        horse_name = _require_text(
            row.get("horse_name"),
            f"horses[{index}].horse_name",
        )
        if horse_no in forecast_identity:
            raise ForecastGuardError(f"duplicate forecast horse_no: {horse_no}")
        forecast_identity[horse_no] = horse_name

    forecast_numbers = set(forecast_identity)
    missing = sorted(source_numbers - forecast_numbers)
    extra = sorted(forecast_numbers - source_numbers)
    if missing or extra:
        raise ForecastGuardError(
            f"forecast runner coverage mismatch: missing={missing}, extra={extra}"
        )

    for horse_no in sorted(source_numbers):
        source_name = source_identity[horse_no]
        forecast_name = forecast_identity[horse_no]
        if source_name != forecast_name:
            raise ForecastGuardError(
                "forecast runner identity mismatch: "
                f"horse_no={horse_no}, source={source_name}, forecast={forecast_name}"
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

        if scope == "RACE" and horse_no is not None:
            raise ForecastGuardError(
                f"factor_usage[{index}] RACE scope must not include horse_no"
            )
        if scope == "HORSE" and horse_no is None:
            raise ForecastGuardError(
                f"factor_usage[{index}] HORSE scope requires horse_no"
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
        "runner_identity_match": True,
        "factor_usage_identity_unique": True,
        "audit_status": "PASS",
    }


def to_guarded_ledger_rows(
    frozen_forecast: Mapping[str, Any],
    source_horses: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Project frozen rows only after all-runner input completeness passes.

    The returned structure is the normal Gen0 pre-result ledger projection with
    the completeness-audit fields merged into its single ``Freeze監査`` row.
    """
    completeness = audit_forecast_input_completeness(
        frozen_forecast,
        source_horses,
    )
    ledger_rows = gen0.to_ledger_rows(frozen_forecast)
    freeze_rows = ledger_rows.get("Freeze監査", [])
    if len(freeze_rows) != 1:
        raise ForecastGuardError("Freeze監査 projection must contain exactly one row")

    freeze_row = freeze_rows[0]
    freeze_row["source_runner_count"] = completeness["source_runner_count"]
    freeze_row["forecast_runner_count"] = completeness["forecast_runner_count"]
    freeze_row["factor_usage_count"] = completeness["factor_usage_count"]
    freeze_row["runner_coverage_match"] = completeness["runner_coverage_match"]
    freeze_row["runner_identity_match"] = completeness["runner_identity_match"]
    freeze_row["factor_usage_identity_unique"] = completeness[
        "factor_usage_identity_unique"
    ]
    return ledger_rows
