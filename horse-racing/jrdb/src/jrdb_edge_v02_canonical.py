#!/usr/bin/env python3
"""Canonical v0.2 Edge derivations shared by historical and current matching."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

UPTREND_CODES = {"1", "2", "3", "4", "5"}
TRAINING_ARROW_CODES = {"1", "2", "3", "4", "5"}
STABLE_EVALUATION_CODES = {"1", "2", "3", "4"}


def _date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def _canonical_code(value: Any, allowed: set[str]) -> str | None:
    """Return one documented JRDB code or None for blank/undefined values."""
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text in allowed:
        return text
    return None


def canonical_uptrend_code(value: Any) -> str | None:
    """Normalize JRDB 上昇度 to documented codes 1..5; code 0 is undefined."""
    return _canonical_code(value, UPTREND_CODES)


def canonical_training_arrow_code(value: Any) -> str | None:
    """Normalize JRDB 調教矢印 to documented codes 1..5."""
    return _canonical_code(value, TRAINING_ARROW_CODES)


def canonical_stable_evaluation_code(value: Any) -> str | None:
    """Normalize JRDB 厩舎評価 to documented codes 1..4; code 0 is undefined."""
    return _canonical_code(value, STABLE_EVALUATION_CODES)


def horse_age_at_race(race_date: Any, birth_date: Any) -> int | None:
    """Return JRA calendar age (race year - birth year), leakage-safe."""
    race = _date(race_date)
    birth = _date(birth_date)
    if race is None or birth is None or birth > race:
        return None
    age = race.year - birth.year
    if 0 <= age <= 30:
        return age
    return None


def track_condition_bucket(value: Any) -> str | None:
    """Normalize JRDB SED track condition to the four JRA broad states.

    Historical SED may encode 10/11/12=良, 20/21/22=稍重,
    30/31/32=重, 40/41/42=不良. Older/derived sources may already
    contain 1/2/3/4. Edge discovery intentionally uses only the broad
    state so JRDB's speed subcodes do not fragment the sample.
    """
    if value in (None, ""):
        return None
    text = str(value).strip()
    if text in {"1", "2", "3", "4"}:
        return text
    if len(text) >= 2 and text[0] in {"1", "2", "3", "4"} and text[1:].isdigit():
        return text[0]
    return None