"""Neutral leader-based SRB shape metrics; shared with legacy RaceNote evidence."""
from __future__ import annotations

import statistics
from typing import Any

LOGIC_VERSION = "SRB-Neutral-RaceShape-v0.1"

def _round(value: float | None, digits: int = 3) -> float | None:
    return None if value is None else round(float(value), digits)


def shape_from_segments(
    segments: list[dict[str, Any]],
    pace_up_remaining_furlongs: int | float | None,
    optional_context_available: bool,
) -> dict[str, Any]:
    full = [row for row in segments if row["segment_distance_m"] == 200]
    values = [float(row["lap_sec"]) for row in full]
    segment_nos = [int(row["segment_no"]) for row in full]

    early3f: float | None = None
    late3f: float | None = None
    early_late: float | None = None

    if len(segments) >= 3 and all(row["segment_distance_m"] == 200 for row in segments[:3]):
        early3f = sum(float(row["lap_sec"]) for row in segments[:3])
    if len(full) >= 3:
        late3f = sum(values[-3:])
    if early3f is not None and late3f is not None:
        early_late = late3f - early3f

    if values:
        fastest = min(values)
        fastest_index = values.index(fastest)
        fastest_segment_no = segment_nos[fastest_index]
        lap_std = statistics.pstdev(values) if len(values) >= 2 else 0.0
        lap_range = max(values) - min(values)
        last_vs_best = values[-1] - fastest
    else:
        fastest = None
        fastest_segment_no = None
        lap_std = None
        lap_range = None
        last_vs_best = None

    accel: list[float] = []
    decel: list[float] = []
    for previous, current in zip(values, values[1:]):
        delta = current - previous
        if delta < 0:
            accel.append(-delta)
        elif delta > 0:
            decel.append(delta)

    last3_slope: float | None = None
    if len(values) >= 3:
        y0, _, y2 = values[-3:]
        last3_slope = (y2 - y0) / 2.0

    pace_up = None
    if pace_up_remaining_furlongs is not None:
        try:
            pace_up = int(pace_up_remaining_furlongs)
        except (TypeError, ValueError):
            pace_up = None

    return {
        "coverage": {
            "status": "AVAILABLE" if segments else "NO_LAPS",
            "comparable_200m_lap_count": len(full),
            "early_late_delta_available": early_late is not None,
            "optional_srb_context_available": bool(optional_context_available),
        },
        "lap_shape": {
            "early3f_sec": _round(early3f, 1),
            "late3f_sec": _round(late3f, 1),
            "early_late_delta_sec": _round(early_late, 1),
            "lap_std_sec": _round(lap_std),
            "lap_range_sec": _round(lap_range, 1),
            "fastest_lap_sec": _round(fastest, 1),
            "fastest_segment_no": fastest_segment_no,
            "max_accel_sec": _round(max(accel) if accel else 0.0, 1) if values else None,
            "max_decel_sec": _round(max(decel) if decel else 0.0, 1) if values else None,
            "last_vs_best_sec": _round(last_vs_best, 1),
            "last3_slope_sec_per_segment": _round(last3_slope, 2),
            "pace_up_remaining_furlongs": pace_up,
        },
    }
