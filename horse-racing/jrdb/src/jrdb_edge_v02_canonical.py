#!/usr/bin/env python3
"""Canonical v0.2 Edge derivations shared by historical and current matching."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any


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


def horse_age_at_race(race_date: Any, birth_date: Any) -> int | None:
    """Return JRA calendar age (race year - birth year), leakage-safe."""
    race = _date(race_date)
    birth = _date(birth_date)
    if race is None or birth is None or birth > race:
        return None
    age = race.year - birth.year
    return age if 0 <= age <= 30 else None


def track_condition_bucket(value: Any) -> str | None:
    """Normalize JRDB SED track condition to the four JRA broad states.

    Historical SED may encode 10/11/12=良, 20/21/22=稍重,
    30/31/32=重, 40/41/42=不良.  Older/derived sources may already
    contain 1/2/3/4.  Edge discovery intentionally uses only the broad
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
