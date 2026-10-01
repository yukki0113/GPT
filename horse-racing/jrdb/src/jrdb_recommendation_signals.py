#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Canonical RaceReviewDB recommendation signals v0.2.

This module is the current operational recommendation contract after the
2024-2025 Historical OOS and strength/monotonicity studies.

Recommendations are evidence signals, not a betting system and not grades.
Multiple matched signals do not automatically increase recommendation rank.
Expose measured strength values to downstream consumers instead.
"""
from __future__ import annotations

from collections.abc import Mapping
import math

VERSION = "rrdb-recommendation-signals-v0.2"
OPERATIONAL_LOOKBACK_DAYS = 730

# Frozen from the accepted pre-OOS / OOS research contracts.
PERFORMANCE_Q80 = -0.09305555555555287
PERFORMANCE_Q90 = 0.16777149321267684
PERFORMANCE_Q95_PRE_OOS = 0.3612475482

PACE_FRONT_MIN = 70.0
FRONTNESS_MIN = 0.60
FRONT_WINNER_GAP_MAX = 0.50

PACE_REAR_MAX = 30.0
REAR_FRONTNESS_MAX = 0.40
REAR_LAST3F_MIN = 90.0

CLASS_NUMERIC = {
    "NEWCOMER": 0.0,
    "MAIDEN": 1.0,
    "CLASS_1": 2.0,
    "CLASS_2": 3.0,
    "CLASS_3": 4.0,
    "OPEN": 5.0,
    "G3": 6.0,
    "G2": 7.0,
    "G1": 8.0,
}

SIGNAL_ORDER = (
    "TIME_CLASS_PLUS1",
    "FRONT_SURVIVE_GAP05",
    "REAR_HIGH_LAST3F90",
    "HV01",
    "HV02",
)

SIGNAL_LABELS = {
    "TIME_CLASS_PLUS1": "上位クラス時計",
    "FRONT_SURVIVE_GAP05": "前傾前受け耐性",
    "REAR_HIGH_LAST3F90": "後傾差し逆行",
    "HV01": "着順以上のタイム内容",
    "HV02": "大敗着順以上のタイム内容",
}


def _finite(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def class_gap_numeric(row: Mapping[str, object]) -> float | None:
    equivalent = _finite(row.get("time_class_equivalent_numeric"))
    declared = CLASS_NUMERIC.get(_text(row.get("declared_class_group")).upper())
    if equivalent is None or declared is None:
        return None
    return equivalent - declared


def performance_signal(row: Mapping[str, object]) -> float | None:
    direct = _finite(row.get("performance_signal"))
    if direct is not None:
        return direct
    delta = _finite(row.get("horse_adjusted_delta_per_1000m"))
    return -delta if delta is not None else None


def performance_band(value: float | None) -> str | None:
    if value is None:
        return None
    if value >= PERFORMANCE_Q95_PRE_OOS:
        return "Q95_PLUS"
    if value >= PERFORMANCE_Q90:
        return "Q90_Q95"
    if value >= PERFORMANCE_Q80:
        return "Q80_Q90"
    return "BELOW_Q80"


def matched_signals(row: Mapping[str, object]) -> list[str]:
    finish = _int(row.get("finish"))
    perf = performance_signal(row)
    gap = class_gap_numeric(row)
    pace = _finite(row.get("pace_balance_percentile"))
    frontness = _finite(row.get("corner4_frontness"))
    winner_gap = _finite(row.get("winner_gap_sec"))
    last3f = _finite(row.get("last3f_speed_percentile"))

    matched: list[str] = []

    if gap is not None and gap >= 1.0:
        matched.append("TIME_CLASS_PLUS1")

    if (
        pace is not None
        and pace >= PACE_FRONT_MIN
        and frontness is not None
        and frontness >= FRONTNESS_MIN
        and winner_gap is not None
        and winner_gap <= FRONT_WINNER_GAP_MAX
    ):
        matched.append("FRONT_SURVIVE_GAP05")

    if (
        pace is not None
        and pace <= PACE_REAR_MAX
        and frontness is not None
        and frontness <= REAR_FRONTNESS_MAX
        and last3f is not None
        and last3f >= REAR_LAST3F_MIN
    ):
        matched.append("REAR_HIGH_LAST3F90")

    if finish is not None and perf is not None:
        if finish >= 4 and perf >= PERFORMANCE_Q80:
            matched.append("HV01")
        if finish >= 6 and perf >= PERFORMANCE_Q80:
            matched.append("HV02")

    return [signal for signal in SIGNAL_ORDER if signal in matched]


def signal_strength(signal_id: str, row: Mapping[str, object]) -> dict[str, object]:
    perf = performance_signal(row)
    if signal_id == "TIME_CLASS_PLUS1":
        return {
            "class_gap_numeric": class_gap_numeric(row),
            "time_class_equivalent": row.get("time_class_equivalent"),
            "time_class_equivalent_numeric": row.get("time_class_equivalent_numeric"),
        }
    if signal_id == "FRONT_SURVIVE_GAP05":
        return {
            "winner_gap_sec": _finite(row.get("winner_gap_sec")),
            "pace_balance_percentile": _finite(row.get("pace_balance_percentile")),
            "corner4_frontness": _finite(row.get("corner4_frontness")),
            "source_finish": _int(row.get("finish")),
            "source_won": _int(row.get("finish")) == 1,
        }
    if signal_id == "REAR_HIGH_LAST3F90":
        return {
            "last3f_speed_percentile": _finite(row.get("last3f_speed_percentile")),
            "winner_gap_sec": _finite(row.get("winner_gap_sec")),
            "pace_balance_percentile": _finite(row.get("pace_balance_percentile")),
            "corner4_frontness": _finite(row.get("corner4_frontness")),
        }
    if signal_id in {"HV01", "HV02"}:
        return {
            "performance_signal": perf,
            "performance_band": performance_band(perf),
            "source_finish": _int(row.get("finish")),
        }
    raise ValueError(f"unknown recommendation signal: {signal_id}")


def recommendation_payload(row: Mapping[str, object]) -> dict[str, object]:
    ids = matched_signals(row)
    return {
        "status": "MATCH" if ids else "NO_MATCH",
        "contract_version": VERSION,
        "grade": None,
        "grade_status": "DISABLED",
        "matched_signal_ids": ids,
        "matched_signal_count": len(ids),
        "signals": [
            {
                "signal_id": signal_id,
                "label": SIGNAL_LABELS[signal_id],
                "strength": signal_strength(signal_id, row),
            }
            for signal_id in ids
        ],
    }


def human_summary(row: Mapping[str, object]) -> str | None:
    payload = recommendation_payload(row)
    ids = payload["matched_signal_ids"]
    if not ids:
        return None
    phrases: list[str] = []
    for signal_id in ids:
        strength = signal_strength(signal_id, row)
        if signal_id == "TIME_CLASS_PLUS1":
            gap = strength.get("class_gap_numeric")
            phrases.append(
                f"上位クラス時計（クラス差 {gap:+.2f}）"
                if isinstance(gap, float)
                else "上位クラス時計"
            )
        elif signal_id == "FRONT_SURVIVE_GAP05":
            gap = strength.get("winner_gap_sec")
            phrases.append(
                f"前傾を前で受けて勝ち馬{gap:.2f}秒差"
                if isinstance(gap, float)
                else "前傾を前で受けて踏ん張る"
            )
        elif signal_id == "REAR_HIGH_LAST3F90":
            pct = strength.get("last3f_speed_percentile")
            phrases.append(
                f"後傾後方から上がり{pct:.0f}pct"
                if isinstance(pct, float)
                else "後傾後方から強い上がり"
            )
        elif signal_id in {"HV01", "HV02"}:
            band = strength.get("performance_band")
            finish = strength.get("source_finish")
            phrases.append(f"{finish}着から補正タイム{band}" if finish else f"補正タイム{band}")
    return " / ".join(phrases)
