#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analysis Lite projection adapter built on the common JRDB Raw Reader.

This module intentionally owns no fixed-width offsets.  ``jrdb_raw.Parser`` is
the byte-position source of truth; this adapter only preserves the established
Analysis Lite field names, blank/null conventions and lightweight derivations.
"""
from __future__ import annotations

from typing import Any

from jrdb_raw import Parser

_COMMON = Parser()


def _text(value: object) -> str:
    """Preserve the legacy Analysis convention: blank text is ``""``."""
    if value is None:
        return ""
    return str(value)


def _int(value: object) -> int | None:
    """Return an integer when the common parser produced a numeric value."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_bac(raw: bytes, race_date: str, year: int) -> dict[str, object]:
    """Project one BAC row into the existing Analysis race representation."""
    parsed = _COMMON.bac(raw)
    return {
        "race_date": race_date,
        "year": year,
        "venue_code": _text(str(parsed["race_key_raw"])[:2]),
        "race_no": _int(str(parsed["race_key_raw"])[6:8]),
        "distance": _int(parsed.get("distance_raw")),
        "track_type": _text(parsed.get("surface_code")),
        "race_condition_code": _text(parsed.get("race_class_code")),
        "track_condition_code": None,
        "grade_code": _text(parsed.get("grade_code")),
    }


def parse_kyi(raw: bytes) -> tuple[tuple[str, int | None], dict[str, object]]:
    """Project one KYI row into the existing Analysis entry representation."""
    parsed = _COMMON.kyi(raw)
    race_key = _text(parsed.get("race_key_raw"))
    horse_no = _int(parsed.get("horse_no"))
    previous = parsed.get("previous")
    first: dict[str, Any] = {}
    if isinstance(previous, list) and previous and isinstance(previous[0], dict):
        first = previous[0]
    entry = {
        "frame_no": _int(parsed.get("frame_no")),
        "horse_id": _text(parsed.get("blood_registration_no")),
        "horse_name": _text(parsed.get("horse_name")),
        "jockey_name": _text(parsed.get("jockey")),
        "running_style": _text(parsed.get("running_style_code")),
        "distance_aptitude": _text(parsed.get("distance_fit_code")),
        "uptrend": _text(parsed.get("improvement_code")),
        "prev_result_key_1": _text(first.get("result_key")) or None,
        "prev_race_key_1": _text(first.get("race_key_raw")) or None,
    }
    return (race_key, horse_no), entry


def parse_sed(raw: bytes, race_date: str, year: int) -> tuple[
    tuple[str, int | None], dict[str, object], dict[str, object]
]:
    """Project one SED row into Analysis result plus BAC-fallback race fields."""
    parsed = _COMMON.sed(raw)
    race_key = _text(parsed.get("race_key_raw"))
    horse_no = _int(parsed.get("horse_no"))
    result = {
        "finish": _int(parsed.get("finish")),
        "abnormal_code": _text(parsed.get("abnormal_code")),
        "final_win_odds": _int(parsed.get("final_win_odds")),
        "final_win_popularity": _int(parsed.get("final_popularity")),
        "win_payout": _int(parsed.get("win_payout")),
        "place_payout": _int(parsed.get("place_payout")),
    }
    fallback_race = {
        "race_date": race_date,
        "year": year,
        "venue_code": race_key[:2],
        "race_no": _int(race_key[6:8]),
        "distance": _int(parsed.get("distance_m")),
        "track_type": _text(parsed.get("surface_code")),
        "race_condition_code": None,
        "track_condition_code": _text(parsed.get("track_condition_code")),
        "grade_code": None,
    }
    return (race_key, horse_no), result, fallback_race


def parse_cyb(raw: bytes) -> tuple[tuple[str, int | None], int | None]:
    """Project one CYB row into the existing Analysis training value."""
    parsed = _COMMON.cyb(raw)
    race_horse_key = _text(parsed.get("race_horse_key"))
    race_key = race_horse_key[:8]
    horse_no = _int(race_horse_key[8:10])
    return (race_key, horse_no), _int(parsed.get("training_index"))


def parse_ukc(raw: bytes) -> tuple[str, dict[str, object]]:
    """Project one UKC row into the existing Analysis horse-profile contract."""
    parsed = _COMMON.ukc(raw)
    birth_date = _text(parsed.get("birth_date"))
    birth_year = None
    if len(birth_date) >= 4 and birth_date[:4].isdigit():
        birth_year = int(birth_date[:4])
    horse_id = _text(parsed.get("horse_id"))
    profile = {
        "sex_code": _text(parsed.get("sex_code")),
        "birth_year": birth_year,
        "sire_name": _text(parsed.get("sire_name")),
        "broodmare_sire_name": _text(parsed.get("broodmare_sire_name")),
        "sire_line_code": _text(parsed.get("sire_line_code")),
        "broodmare_sire_line_code": _text(parsed.get("broodmare_sire_line_code")),
        "data_date": _text(parsed.get("data_date")),
    }
    return horse_id, profile
