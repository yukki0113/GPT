"""Internal physical contract for the JRDB race-lap dataset v0.1."""
from __future__ import annotations

import datetime as dt
import json
import math
from typing import Any

from jrdb_race_lap import segment_distances
from jrdb_race_lap_shape import LOGIC_VERSION

DATASET_SCHEMA_VERSION = "JRDB-Race-Lap-Parquet-0.1"
EVIDENCE_SCHEMA_VERSION = "JRDB-Race-Lap-Evidence-0.1"
SHAPE_COLUMNS = (
    "early3f_sec", "late3f_sec", "early_late_delta_sec", "lap_std_sec",
    "lap_range_sec", "fastest_lap_sec", "fastest_segment_no", "max_accel_sec",
    "max_decel_sec", "last_vs_best_sec", "last3_slope_sec_per_segment",
    "pace_up_remaining_furlongs",
)
INTEGER_SHAPE_COLUMNS = {"fastest_segment_no", "pace_up_remaining_furlongs"}
COLUMN_TYPES = {
    "race_key": "VARCHAR", "race_date": "DATE", "surface_code": "VARCHAR",
    "distance_m": "INTEGER", "lap_count": "INTEGER",
    "comparable_200m_lap_count": "INTEGER", "coverage_status": "VARCHAR",
    "early_late_delta_available": "BOOLEAN", "optional_srb_context_available": "BOOLEAN",
    "partial_first_segment": "BOOLEAN", "segment_distances_m": "INTEGER[]",
    "lap_times_sec": "DOUBLE[]",
    **{key: "INTEGER" if key in INTEGER_SHAPE_COLUMNS else "DOUBLE" for key in SHAPE_COLUMNS},
    "track_bias_raw_json": "VARCHAR", "race_comment": "VARCHAR",
    "source_archive": "VARCHAR", "source_sed_member": "VARCHAR", "source_srb_member": "VARCHAR",
    "dataset_schema_version": "VARCHAR", "shape_logic_version": "VARCHAR",
}
POLICY = {
    "leader_based": True, "individual_sectionals": False,
    "score_status": "NO_ADDITIVE_SCORE",
    "target_race_usage": "HISTORICAL_ONLY_AS_OF_EXCLUSIVE",
    "partial_first_segment_policy": "EXCLUDE_FROM_200M_COMPARABLE_METRICS",
}


def normalize_race_key(value: object) -> str:
    key = str(value).strip()
    if len(key) != 8:
        raise ValueError("race_key must contain exactly 8 characters")
    return key


def reconstruct_segments(distances: list[int], times: list[float]) -> list[dict[str, Any]]:
    result = []
    start = 0
    for number, (distance, lap) in enumerate(zip(distances, times, strict=True), 1):
        result.append({"segment_no": number, "start_m": start, "end_m": start + distance,
                       "segment_distance_m": distance, "lap_sec": lap})
        start += distance
    return result


def optional_context_available(pace: object, bias: dict[str, Any], comment: str | None) -> bool:
    return pace is not None or bool(comment) or any(value not in (None, "") for value in bias.values())


def decode_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate physical types/sequence/coverage and return JSON-compatible values.

    This checks stored invariants without interpreting or recalculating shape metrics.
    """
    row = dict(raw)
    for name, kind in COLUMN_TYPES.items():
        value = row[name]
        nullable = name in SHAPE_COLUMNS or name in {"race_comment", "track_bias_raw_json"}
        if value is None and nullable:
            continue
        if kind == "VARCHAR" and not isinstance(value, str):
            raise ValueError(f"invalid string: {name}")
        if kind == "INTEGER" and type(value) is not int:
            raise ValueError(f"invalid integer: {name}")
        if kind == "BOOLEAN" and type(value) is not bool:
            raise ValueError(f"invalid boolean: {name}")
        if kind == "DOUBLE" and (type(value) not in (float, int) or not math.isfinite(value)):
            raise ValueError(f"invalid finite number: {name}")
    if normalize_race_key(row["race_key"]) != row["race_key"]:
        raise ValueError("stored race_key is not canonical")
    date = row["race_date"]
    if type(date) is dt.date:
        date = date.isoformat()
    if not isinstance(date, str) or dt.date.fromisoformat(date).isoformat() != date:
        raise ValueError("invalid race_date")
    row["race_date"] = date
    if row["distance_m"] <= 0 or not row["surface_code"].strip():
        raise ValueError("invalid distance/surface")
    for key in ("source_archive", "source_sed_member", "source_srb_member"):
        if not row[key].strip():
            raise ValueError(f"empty provenance: {key}")
    if row["dataset_schema_version"] != DATASET_SCHEMA_VERSION or row["shape_logic_version"] != LOGIC_VERSION:
        raise ValueError("unexpected dataset/shape version")
    distances, times = row["segment_distances_m"], row["lap_times_sec"]
    if not isinstance(distances, list) or not isinstance(times, list):
        raise ValueError("native lap LIST required")
    if any(type(d) is not int or d <= 0 for d in distances):
        raise ValueError("invalid segment distance")
    if any(type(t) not in (float, int) or not math.isfinite(t) or t <= 0 for t in times):
        raise ValueError("invalid lap time")
    count = row["lap_count"]
    if not 0 <= count <= 18 or len(distances) != count or len(times) != count:
        raise ValueError("lap_count/list length mismatch")
    if row["coverage_status"] != ("AVAILABLE" if count else "NO_LAPS"):
        raise ValueError("invalid coverage_status")
    if count and distances != segment_distances(row["distance_m"], count):
        raise ValueError("invalid segment layout/distance sum")
    if row["comparable_200m_lap_count"] != distances.count(200):
        raise ValueError("invalid comparable count")
    if row["partial_first_segment"] != bool(count and distances[0] != 200):
        raise ValueError("invalid partial_first_segment")
    early_available = count >= 3 and not row["partial_first_segment"]
    late_available = distances.count(200) >= 3
    for name, available in (("early3f_sec", early_available), ("late3f_sec", late_available),
                            ("early_late_delta_sec", early_available and late_available),
                            ("last3_slope_sec_per_segment", late_available)):
        if (row[name] is not None) != available:
            raise ValueError(f"invalid metric availability: {name}")
    if row["early_late_delta_available"] != (row["early_late_delta_sec"] is not None):
        raise ValueError("invalid early_late_delta_available")
    if not count and any(row[name] is not None for name in SHAPE_COLUMNS if name != "pace_up_remaining_furlongs"):
        raise ValueError("NO_LAPS has shape metrics")
    full_numbers = [i for i, d in enumerate(distances, 1) if d == 200]
    for name in ("lap_std_sec", "lap_range_sec", "fastest_lap_sec", "fastest_segment_no",
                 "max_accel_sec", "max_decel_sec", "last_vs_best_sec"):
        if (row[name] is not None) != bool(full_numbers):
            raise ValueError(f"invalid metric availability: {name}")
    if full_numbers and row["fastest_segment_no"] not in full_numbers:
        raise ValueError("fastest_segment_no is not a full segment")
    bias_raw = row.pop("track_bias_raw_json")
    bias = {} if bias_raw is None else json.loads(bias_raw)
    if not isinstance(bias, dict) or any(not isinstance(k, str) or not isinstance(v, (str, type(None))) for k, v in bias.items()):
        raise ValueError("track bias must be an object of raw strings/null")
    row["track_bias_raw"] = bias
    comment = row["race_comment"]
    row["race_comment"] = comment.strip() or None if comment is not None else None
    if row["optional_srb_context_available"] != optional_context_available(row["pace_up_remaining_furlongs"], bias, row["race_comment"]):
        raise ValueError("invalid optional_srb_context_available")
    json.dumps(row, allow_nan=False)
    return row
