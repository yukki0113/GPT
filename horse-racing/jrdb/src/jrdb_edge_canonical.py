#!/usr/bin/env python3
"""Canonical pre-race feature derivations shared by JRDB Edge producers/consumers."""
from __future__ import annotations

from typing import Any

VERSION = "0.1.0"


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def frame_zone(frame_no: Any) -> str | None:
    """Map JRDB frame number to the frozen Phase1 INNER/MIDDLE/OUTER bucket."""
    value = _int_or_none(frame_no)
    if value is None:
        return None
    if value <= 3:
        return "INNER"
    if value <= 6:
        return "MIDDLE"
    return "OUTER"


def distance_delta(current_distance: Any, previous_distance: Any) -> int | None:
    """Return current minus previous distance in metres when both are available."""
    current = _int_or_none(current_distance)
    previous = _int_or_none(previous_distance)
    if current is None or previous is None:
        return None
    return current - previous


def distance_bucket(delta: Any) -> str | None:
    """Bucket a current-minus-previous distance delta under Edge Contract v0.1."""
    value = _int_or_none(delta)
    if value is None:
        return None
    if value <= -400:
        return "LARGE_SHORTEN"
    if value <= -200:
        return "SHORTEN"
    if value < 200:
        return "SAME_BAND"
    if value < 400:
        return "EXTEND"
    return "LARGE_EXTEND"


def distance_change_bucket(current_distance: Any, previous_distance: Any) -> str | None:
    """Derive the frozen distance-change bucket directly from two distances."""
    return distance_bucket(distance_delta(current_distance, previous_distance))


def transition(before: Any, after: Any) -> str | None:
    """Return a canonical ``before->after`` transition without code coercion."""
    if before is None or after is None:
        return None
    before_text = str(before).strip()
    after_text = str(after).strip()
    if not before_text or not after_text:
        return None
    return f"{before_text}->{after_text}"


def derive_transition_features(
    *,
    current_distance: Any,
    current_surface_code: Any,
    current_frame_no: Any,
    previous_distance: Any = None,
    previous_surface_code: Any = None,
    previous_frame_no: Any = None,
) -> dict[str, Any]:
    """Build the shared transition fields consumed by Feature Mart and Matcher."""
    current_zone = frame_zone(current_frame_no)
    previous_zone = frame_zone(previous_frame_no)
    delta = distance_delta(current_distance, previous_distance)
    return {
        "frame_zone": current_zone,
        "distance_change_m": delta,
        "distance_change_bucket": distance_bucket(delta),
        "surface_transition": transition(previous_surface_code, current_surface_code),
        "frame_transition": transition(previous_zone, current_zone),
    }
