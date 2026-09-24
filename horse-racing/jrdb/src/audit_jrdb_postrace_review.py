#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail-closed audit gates for JRDB Post-Race Review v0.1 bundles."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

from jrdb_postrace_review import REVIEW_LOGIC_VERSION, REVIEW_SCHEMA_VERSION

MAIN_RELATIONS = (
    "fact_race_context",
    "fact_race_review",
    "fact_horse_performance",
)
OPTIONAL_RELATIONS = ("fact_track_bias",)


def _text(value: object) -> str:
    """Return stripped text for key validation."""
    if value is None:
        return ""
    return str(value).strip()


def _iso_date(value: object) -> str | None:
    """Normalize one date to YYYY-MM-DD without guessing malformed values."""
    digits = "".join(character for character in _text(value) if character.isdigit())
    if len(digits) != 8:
        return None
    try:
        parsed = dt.date(
            int(digits[:4]),
            int(digits[4:6]),
            int(digits[6:8]),
        )
    except ValueError:
        return None
    return parsed.isoformat()


def _nonfinite_paths(value: object, prefix: str = "") -> list[str]:
    """Return paths containing NaN/Infinity in a JSON-like persisted row."""
    result: list[str] = []

    if isinstance(value, float):
        if not math.isfinite(value):
            result.append(prefix or "$")
        return result

    if isinstance(value, Mapping):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            result.extend(_nonfinite_paths(child, child_prefix))
        return result

    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            child_prefix = f"{prefix}[{index}]"
            result.extend(_nonfinite_paths(child, child_prefix))
        return result

    return result


def _canonical_value(value: object) -> object:
    """Normalize values for deterministic bundle hashing."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite value cannot be canonicalized")
        return {"__float__": format(value, ".17g")}
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _canonical_value(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    return str(value)


def canonical_rows_hash(
    rows: Sequence[Mapping[str, object]],
    sort_fields: Sequence[str],
) -> str:
    """Return a deterministic SHA-256 over canonically sorted logical rows."""
    def sort_key(row: Mapping[str, object]) -> tuple[str, ...]:
        return tuple(_text(row.get(field)) for field in sort_fields)

    digest = hashlib.sha256()
    for row in sorted(rows, key=sort_key):
        canonical = _canonical_value(row)
        encoded = json.dumps(
            canonical,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        digest.update(encoded)
        digest.update(b"\n")
    return digest.hexdigest()


def canonical_bundle_hash(bundle: Mapping[str, object]) -> str:
    """Return one deterministic digest for the persisted Review relations."""
    relation_keys = {
        "fact_race_context": ("race_key",),
        "fact_race_review": ("race_key",),
        "fact_horse_performance": ("race_key", "horse_no"),
        "fact_track_bias": (
            "race_date",
            "venue_code",
            "surface_code",
            "bias_dimension",
            "bias_bucket",
        ),
    }

    digest = hashlib.sha256()
    for relation in (*MAIN_RELATIONS, *OPTIONAL_RELATIONS):
        raw_rows = bundle.get(relation)
        if raw_rows is None:
            continue
        if not isinstance(raw_rows, list):
            raise TypeError(f"{relation} must be a list")
        rows = [
            row
            for row in raw_rows
            if isinstance(row, Mapping)
        ]
        if len(rows) != len(raw_rows):
            raise TypeError(f"{relation} contains a non-mapping row")

        digest.update(relation.encode("utf-8"))
        digest.update(b"\n")
        digest.update(
            canonical_rows_hash(rows, relation_keys[relation]).encode("ascii")
        )
        digest.update(b"\n")
    return digest.hexdigest()


def _duplicate_count(
    rows: Sequence[Mapping[str, object]],
    fields: Sequence[str],
) -> tuple[int, int]:
    """Return duplicate-key row count and missing-key row count."""
    counts: dict[tuple[str, ...], int] = {}
    missing = 0

    for row in rows:
        key = tuple(_text(row.get(field)) for field in fields)
        if any(not value for value in key):
            missing += 1
            continue
        counts[key] = counts.get(key, 0) + 1

    duplicates = sum(count - 1 for count in counts.values() if count > 1)
    return duplicates, missing


def _version_errors(
    rows: Sequence[Mapping[str, object]],
) -> int:
    """Count rows outside the current Review schema/logic contract."""
    errors = 0
    for row in rows:
        if _text(row.get("review_schema_version")) != REVIEW_SCHEMA_VERSION:
            errors += 1
            continue
        if _text(row.get("review_logic_version")) != REVIEW_LOGIC_VERSION:
            errors += 1
    return errors


def audit_review_bundle(
    bundle: Mapping[str, object],
    *,
    expected_target_date: str | None = None,
    require_single_target_date: bool = True,
) -> dict[str, object]:
    """Audit a Review bundle and return PASS/FAIL plus hard/soft evidence."""
    hard_errors: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    relation_rows: dict[str, list[Mapping[str, object]]] = {}

    for relation in MAIN_RELATIONS:
        raw_rows = bundle.get(relation)
        if not isinstance(raw_rows, list):
            hard_errors.append(
                {
                    "code": "MISSING_RELATION",
                    "relation": relation,
                    "detail": "required relation must be a list",
                }
            )
            relation_rows[relation] = []
            continue

        rows: list[Mapping[str, object]] = []
        invalid_rows = 0
        for row in raw_rows:
            if isinstance(row, Mapping):
                rows.append(row)
            else:
                invalid_rows += 1
        if invalid_rows:
            hard_errors.append(
                {
                    "code": "INVALID_ROW_TYPE",
                    "relation": relation,
                    "count": invalid_rows,
                }
            )
        relation_rows[relation] = rows

    key_contracts = {
        "fact_race_context": ("race_key",),
        "fact_race_review": ("race_key",),
        "fact_horse_performance": ("race_horse_key",),
    }
    for relation, fields in key_contracts.items():
        rows = relation_rows[relation]
        duplicates, missing = _duplicate_count(rows, fields)
        if duplicates:
            hard_errors.append(
                {
                    "code": "DUPLICATE_KEY",
                    "relation": relation,
                    "count": duplicates,
                    "fields": list(fields),
                }
            )
        if missing:
            hard_errors.append(
                {
                    "code": "MISSING_KEY",
                    "relation": relation,
                    "count": missing,
                    "fields": list(fields),
                }
            )

    context_keys = {
        _text(row.get("race_key"))
        for row in relation_rows["fact_race_context"]
        if _text(row.get("race_key"))
    }
    review_keys = {
        _text(row.get("race_key"))
        for row in relation_rows["fact_race_review"]
        if _text(row.get("race_key"))
    }
    if context_keys != review_keys:
        hard_errors.append(
            {
                "code": "RACE_RELATION_KEY_MISMATCH",
                "context_only_count": len(context_keys - review_keys),
                "review_only_count": len(review_keys - context_keys),
            }
        )

    orphan_horses = 0
    for row in relation_rows["fact_horse_performance"]:
        race_key = _text(row.get("race_key"))
        if race_key and race_key not in review_keys:
            orphan_horses += 1
    if orphan_horses:
        hard_errors.append(
            {
                "code": "ORPHAN_HORSE_RACE",
                "count": orphan_horses,
            }
        )

    for relation, rows in relation_rows.items():
        version_errors = _version_errors(rows)
        if version_errors:
            hard_errors.append(
                {
                    "code": "VERSION_CONTRACT_MISMATCH",
                    "relation": relation,
                    "count": version_errors,
                }
            )

        nonfinite_count = 0
        samples: list[str] = []
        for index, row in enumerate(rows):
            paths = _nonfinite_paths(row)
            nonfinite_count += len(paths)
            if paths and len(samples) < 5:
                samples.append(f"row={index}:{','.join(paths[:5])}")
        if nonfinite_count:
            hard_errors.append(
                {
                    "code": "NONFINITE_NUMERIC",
                    "relation": relation,
                    "count": nonfinite_count,
                    "samples": samples,
                }
            )

    expected_date = None
    if expected_target_date is not None:
        expected_date = _iso_date(expected_target_date)
        if expected_date is None:
            raise ValueError("expected_target_date must be a valid date")

    date_errors = 0
    observed_dates: set[str] = set()
    for relation in MAIN_RELATIONS:
        for row in relation_rows[relation]:
            row_date = _iso_date(row.get("race_date"))
            if row_date is None:
                date_errors += 1
                continue
            observed_dates.add(row_date)
            if expected_date is not None and row_date != expected_date:
                date_errors += 1
    if date_errors:
        hard_errors.append(
            {
                "code": "RACE_DATE_CONTRACT",
                "count": date_errors,
                "expected_target_date": expected_date,
            }
        )
    if require_single_target_date and len(observed_dates) > 1:
        hard_errors.append(
            {
                "code": "MULTIPLE_TARGET_DATES",
                "dates": sorted(observed_dates),
            }
        )

    leakage_count = 0
    for row in relation_rows["fact_race_review"]:
        race_date = _iso_date(row.get("race_date"))
        sample_end = _iso_date(row.get("standard_sample_end_date"))
        if race_date is not None and sample_end is not None and sample_end >= race_date:
            leakage_count += 1
    if leakage_count:
        hard_errors.append(
            {
                "code": "STANDARD_FUTURE_LEAKAGE",
                "count": leakage_count,
            }
        )

    race_review = relation_rows["fact_race_review"]
    missing_standard = sum(
        1
        for row in race_review
        if row.get("historical_standard_time_sec") is None
    )
    if missing_standard:
        warnings.append(
            {
                "code": "MISSING_TIME_STANDARD",
                "count": missing_standard,
            }
        )

    no_day_adjustment = sum(
        1
        for row in race_review
        if not bool(row.get("day_adjustment_applied"))
    )
    if no_day_adjustment:
        warnings.append(
            {
                "code": "DAY_ADJUSTMENT_NOT_APPLIED",
                "count": no_day_adjustment,
            }
        )

    low_pace = sum(
        1
        for row in relation_rows["fact_race_context"]
        if row.get("pace_shape") is None
    )
    if low_pace:
        warnings.append(
            {
                "code": "PACE_CLASSIFICATION_UNAVAILABLE",
                "count": low_pace,
            }
        )

    nonmonotonic_curve = sum(
        1
        for row in race_review
        if row.get("class_curve_monotonic") is False
    )
    if nonmonotonic_curve:
        warnings.append(
            {
                "code": "NONMONOTONIC_CLASS_CURVE",
                "count": nonmonotonic_curve,
            }
        )

    optional_bias = bundle.get("fact_track_bias")
    bias_row_count = 0
    if optional_bias is not None:
        if not isinstance(optional_bias, list):
            hard_errors.append(
                {
                    "code": "INVALID_OPTIONAL_RELATION",
                    "relation": "fact_track_bias",
                }
            )
        else:
            bias_rows = [
                row
                for row in optional_bias
                if isinstance(row, Mapping)
            ]
            if len(bias_rows) != len(optional_bias):
                hard_errors.append(
                    {
                        "code": "INVALID_ROW_TYPE",
                        "relation": "fact_track_bias",
                        "count": len(optional_bias) - len(bias_rows),
                    }
                )
            bias_row_count = len(bias_rows)
            duplicates, missing = _duplicate_count(
                bias_rows,
                (
                    "race_date",
                    "venue_code",
                    "surface_code",
                    "bias_dimension",
                    "bias_bucket",
                ),
            )
            if duplicates:
                hard_errors.append(
                    {
                        "code": "DUPLICATE_KEY",
                        "relation": "fact_track_bias",
                        "count": duplicates,
                    }
                )
            if missing:
                hard_errors.append(
                    {
                        "code": "MISSING_KEY",
                        "relation": "fact_track_bias",
                        "count": missing,
                    }
                )

            nonfinite_count = sum(
                len(_nonfinite_paths(row))
                for row in bias_rows
            )
            if nonfinite_count:
                hard_errors.append(
                    {
                        "code": "NONFINITE_NUMERIC",
                        "relation": "fact_track_bias",
                        "count": nonfinite_count,
                    }
                )

    bundle_hash = None
    if not hard_errors:
        bundle_hash = canonical_bundle_hash(bundle)

    return {
        "status": "PASS" if not hard_errors else "FAIL",
        "review_schema_version": REVIEW_SCHEMA_VERSION,
        "review_logic_version": REVIEW_LOGIC_VERSION,
        "target_date": expected_date or (
            next(iter(observed_dates)) if len(observed_dates) == 1 else None
        ),
        "row_counts": {
            "fact_race_context": len(
                relation_rows["fact_race_context"]
            ),
            "fact_race_review": len(
                relation_rows["fact_race_review"]
            ),
            "fact_horse_performance": len(
                relation_rows["fact_horse_performance"]
            ),
            "fact_track_bias": bias_row_count,
        },
        "hard_error_count": len(hard_errors),
        "warning_count": len(warnings),
        "hard_errors": hard_errors,
        "warnings": warnings,
        "canonical_bundle_hash": bundle_hash,
    }
