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
