"""Shared JRA Course Profile identity resolver.

This module owns the deterministic translation from JRDB-observed course fields
to the stable Course Profile course_key. It does not resolve physical version
history or obstacle-route ambiguity.
"""
from __future__ import annotations

SURFACE_NAMES = {"1": "turf", "2": "dirt", "3": "obstacle"}
TOKENS = {"1": "T", "2": "D", "3": "O"}


def layout_from_observation(
    venue_code: str,
    surface_code: str,
    distance_m: int,
    turn_code: str,
    layout_code: str,
) -> str:
    venue = str(venue_code)
    surface = str(surface_code)
    distance = int(distance_m)
    turn = str(turn_code)
    layout = str(layout_code)

    if surface == "1":
        if turn == "3":
            return "straight"
        if venue == "04":
            return "outer" if layout == "2" else "inner"
        if venue == "06":
            return "outer-inner" if distance == 3200 else ("outer" if layout == "2" else "inner")
        if venue == "08":
            return "outer" if layout == "2" else "inner"
        if venue == "09":
            return "outer-inner" if distance == 3200 else ("outer" if layout == "2" else "inner")
        return "main"
    if surface == "2":
        return "main"
    return "obstacle"


def course_key_from_observation(
    venue_code: str,
    surface_code: str,
    distance_m: int,
    turn_code: str,
    layout_code: str,
) -> str | None:
    surface = str(surface_code)
    if surface not in TOKENS:
        return None
    layout_variant = layout_from_observation(
        str(venue_code), surface, int(distance_m), str(turn_code), str(layout_code)
    )
    return f"JRA:{str(venue_code)}:{TOKENS[surface]}:{int(distance_m)}:{layout_variant}"
