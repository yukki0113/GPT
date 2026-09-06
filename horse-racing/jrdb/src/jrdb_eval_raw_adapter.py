#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Eval-facing JRDB Raw projections built on the common fixed-width reader.

No fixed-width byte offsets live here. ``jrdb_raw.Parser`` owns byte positions;
this adapter preserves the existing Eval exporter field contracts and blank/null
semantics above that neutral parse layer.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from jrdb_raw import Parser, race_key_parts, ymd

_COMMON = Parser()


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _iso_date(raw_date: object) -> str:
    value = ymd(_text(raw_date))
    if value is None:
        raise ValueError(f"invalid JRDB date: {raw_date!r}")
    return value


def _venue_and_race(race_key_raw: object) -> tuple[str, int | None]:
    key = _text(race_key_raw)
    parts = race_key_parts(key)
    return _text(parts.get("venue_code")), _int(parts.get("race_no"))


def parse_bac_eval(raw: bytes) -> dict[str, object]:
    """Return the existing Eval BAC race-condition projection."""
    parsed = _COMMON.bac(raw)
    venue_code, race_no = _venue_and_race(parsed.get("race_key_raw"))
    return {
        "race_date": _iso_date(parsed.get("date_raw")),
        "venue_code": venue_code,
        "race_no": race_no,
        "race_name": _text(parsed.get("race_name")),
        "race_type_code": _text(parsed.get("race_type_code")),
        "race_condition_code": _text(parsed.get("race_class_code")),
        "race_symbol_code": _text(parsed.get("symbol_code")),
        "weight_condition_code": _text(parsed.get("weight_rule_code")),
        "grade_code": _text(parsed.get("grade_code")),
        "track_type": _text(parsed.get("surface_code")),
        "distance": _int(parsed.get("distance_raw")),
        "declared_field_size": _int(parsed.get("field_size")),
        "turn_direction_code": _text(parsed.get("turn_code")),
        "inner_outer_code": _text(parsed.get("layout_code")),
        "course_code": _text(parsed.get("course_code")),
        "event_region_code": _text(parsed.get("meeting_area_code")),
    }


def parse_sed_race_eval(raw: bytes) -> dict[str, object]:
    """Return race-common result fields from one SED record."""
    parsed = _COMMON.sed(raw)
    venue_code, race_no = _venue_and_race(parsed.get("race_key_raw"))
    return {
        "race_date": _iso_date(parsed.get("date_raw")),
        "venue_code": venue_code,
        "race_no": race_no,
        "race_name": _text(parsed.get("race_name")),
        "race_type_code": _text(parsed.get("race_type_code")),
        "race_condition_code": _text(parsed.get("race_class_code")),
        "race_symbol_code": _text(parsed.get("race_symbol_code")),
        "weight_condition_code": _text(parsed.get("weight_condition_code")),
        "grade_code": _text(parsed.get("grade_code")),
        "track_type": _text(parsed.get("surface_code")),
        "distance": _int(parsed.get("distance_m")),
        "track_condition_code": _text(parsed.get("track_condition_code")),
        "declared_field_size": _int(parsed.get("field_size")),
        "turn_direction_code": _text(parsed.get("turn_code")),
        "inner_outer_code": _text(parsed.get("layout_code")),
    }


def decimal_text(value: object) -> str:
    """Preserve the legacy Eval CSV decimal text convention."""
    if value is None or value == "":
        return ""
    return format(Decimal(str(value)), "f")


def int_or_blank(value: object) -> int | str:
    """Preserve the legacy Eval CSV integer-or-empty-string convention."""
    parsed = _int(value)
    return "" if parsed is None else parsed


def parse_sed_horse_eval(raw: bytes) -> dict[str, object]:
    """Return the raw horse-level fields needed by Eval result import."""
    parsed = _COMMON.sed(raw)
    venue_code, race_no = _venue_and_race(parsed.get("race_key_raw"))
    return {
        "race_date": _iso_date(parsed.get("date_raw")),
        "venue_code": venue_code,
        "race_no": race_no,
        "horse_no": _int(parsed.get("horse_no")),
        "horse_name": _text(parsed.get("horse_name")),
        "blood_registration_no": _text(parsed.get("blood_registration_no")),
        "finish_position": _int(parsed.get("finish")),
        "abnormality_code": _text(parsed.get("abnormal_code")),
        "final_place_odds_lower": decimal_text(parsed.get("final_place_odds_lower")),
        "place_payout": int_or_blank(parsed.get("place_payout")),
    }
