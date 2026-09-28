#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analysis Lite v1.4 projection adapter.

Preserves the production v1.3 adapter contract untouched and adds only the
extra BAC fields required for RaceNote local/named trend sampling.
"""
from __future__ import annotations

from jrdb_analysis_raw_adapter import (
    parse_bac as parse_bac_v13,
    parse_cyb,
    parse_kyi,
    parse_sed,
    parse_ukc,
)
from jrdb_raw import Parser

_COMMON = Parser()


def _text(value: object) -> str:
    return "" if value is None else str(value)


def _int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _hex_digit(value: object) -> int | None:
    text = _text(value).strip().lower()
    if len(text) != 1:
        return None
    try:
        return int(text, 16)
    except ValueError:
        return None


def parse_bac(raw: bytes, race_date: str, year: int) -> dict[str, object]:
    base = dict(parse_bac_v13(raw, race_date, year))
    parsed = _COMMON.bac(raw)
    race_key = _text(parsed.get("race_key_raw"))
    base.update(
        {
            "meeting_no": _int(race_key[4:5]),
            "meeting_day": _hex_digit(race_key[5:6]),
            "race_name": _text(parsed.get("race_name")) or None,
            "course_code": _text(parsed.get("course_code")) or None,
        }
    )
    return base
