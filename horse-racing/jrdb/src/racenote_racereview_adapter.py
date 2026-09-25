#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a RaceReviewDB evidence sidecar for RaceNote.

This adapter deliberately consumes only stable, as-of-safe RaceReviewDB fields.
It does not use RaceReviewDB's unfinished semantic labels, calibrated track-bias
signals, market data, or current-entry JRDB consensus.

The authoritative RaceNote bundle / independent view remains unchanged. This
module emits a separate evidence sidecar that can later be merged into the GPT
input contract.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from jrdb_postrace_review_reader import RaceReviewReader

ADAPTER_VERSION = "0.1"
EVIDENCE_SCHEMA_VERSION = "RaceReview-Evidence-0.1"

CLASS_ORDER = {
    "NEWCOMER": 0,
    "MAIDEN": 1,
    "CLASS_1": 2,
    "CLASS_2": 3,
    "CLASS_3": 4,
    "OPEN": 5,
    "G3": 6,
    "G2": 7,
    "G1": 8,
}

STABLE_RUN_FIELDS = (
    "race_key",
    "race_date",
    "venue_code",
    "surface_code",
    "distance_m",
    "field_size",
    "declared_class_group",
    "finish",
    "winner_gap_sec",
    "horse_adjusted_delta_sec",
    "horse_adjusted_delta_per_1000m",
    "time_class_equivalent",
    "time_class_equivalent_numeric",
    "pace_shape",
    "last3f_rank",
    "last3f_speed_percentile",
    "closing_gain_sec",
    "corner1_frontness",
    "corner2_frontness",
    "corner3_frontness",
    "corner4_frontness",
    "early_position_gain",
    "middle_position_gain",
    "late_position_gain",
    "overall_position_gain",
    "jrdb_track_diff",
    "jrdb_pace_score",
    "jrdb_late_break_score",
    "jrdb_position_score",
    "jrdb_trouble_score",
    "jrdb_prev_trouble_score",
    "jrdb_mid_trouble_score",
    "jrdb_late_trouble_score",
)


class RaceReviewAdapterError(RuntimeError):
    """Raised when RaceReviewDB evidence cannot be joined safely."""


def _text(value: object) -> str:
    """Return stripped text or an empty string."""
    if value is None:
        return ""
    return str(value).strip()


def _finite(value: object) -> float | None:
    """Return a finite float or None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _positive_int(value: object, field: str) -> int:
    """Return a positive integer and fail closed otherwise."""
    if isinstance(value, bool):
        raise RaceReviewAdapterError(f"{field} must be a positive integer")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise RaceReviewAdapterError(
            f"{field} must be a positive integer"
        ) from exc
    if number < 1:
        raise RaceReviewAdapterError(f"{field} must be a positive integer")
    return number


def _date_text(value: object) -> str:
    """Normalize a date-like value to YYYY-MM-DD without guessing."""
    text = _text(value)
    digits = "".join(character for character in text if character.isdigit())
    if len(digits) != 8:
        raise RaceReviewAdapterError(f"invalid race date: {value!r}")
    return f"{digits[:4]}-{digits[4:6]}-{digits[6:]}"


def _stable_projection(row: Mapping[str, object]) -> dict[str, object]:
    """Project one RaceReviewDB row onto the adapter's frozen stable field set."""
    projected: dict[str, object] = {}
    for field in STABLE_RUN_FIELDS:
        projected[field] = row.get(field)
    return projected


def _class_tag(row: Mapping[str, object]) -> str | None:
    """Compare discrete RaceReviewDB time class with declared class."""
    declared = _text(row.get("declared_class_group")).upper()
    equivalent = _text(row.get("time_class_equivalent")).upper()
    if declared not in CLASS_ORDER or equivalent not in CLASS_ORDER:
        return None

    declared_rank = CLASS_ORDER[declared]
    equivalent_rank = CLASS_ORDER[equivalent]
    if equivalent_rank > declared_rank:
        return "TIME_ABOVE_DECLARED_CLASS"
    if equivalent_rank < declared_rank:
        return "TIME_BELOW_DECLARED_CLASS"
    return "TIME_AT_DECLARED_CLASS"


def _signed_tag(
    value: object,
    positive_tag: str,
    negative_tag: str,
) -> str | None:
    """Create an observed-direction tag without magnitude calibration."""
    number = _finite(value)
    if number is None:
        return None
    if number > 0.0:
        return positive_tag
    if number < 0.0:
        return negative_tag
    return None


def _review_tags(row: Mapping[str, object]) -> list[str]:
    """Create threshold-free deterministic tags from stable Review fields."""
    tags: list[str] = []

    class_tag = _class_tag(row)
    if class_tag is not None:
        tags.append(class_tag)

    signed_specs = (
        (
            "early_position_gain",
            "EARLY_POSITION_GAIN",
            "EARLY_POSITION_LOSS",
        ),
        (
            "middle_position_gain",
            "MIDDLE_POSITION_GAIN",
            "MIDDLE_POSITION_LOSS",
        ),
        (
            "late_position_gain",
            "LATE_POSITION_GAIN",
            "LATE_POSITION_LOSS",
        ),
        (
            "closing_gain_sec",
            "CLOSING_GAIN",
            "CLOSING_LOSS",
        ),
    )
    for field, positive_tag, negative_tag in signed_specs:
        tag = _signed_tag(row.get(field), positive_tag, negative_tag)
        if tag is not None:
            tags.append(tag)

    early = _finite(row.get("early_position_gain"))
    middle = _finite(row.get("middle_position_gain"))
    late = _finite(row.get("late_position_gain"))
    moved_forward = False
    if early is not None and early > 0.0:
        moved_forward = True
    if middle is not None and middle > 0.0:
        moved_forward = True
    if moved_forward and late is not None and late < 0.0:
        tags.append("MOVE_THEN_FADE")

    last3f_rank = row.get("last3f_rank")
    try:
        rank = int(last3f_rank)
    except (TypeError, ValueError):
        rank = 0
    if rank == 1:
        tags.append("FASTEST_LAST3F")

    pace_shape = _text(row.get("pace_shape")).upper()
    if pace_shape:
        tags.append(f"PACE_{pace_shape}")

    return list(dict.fromkeys(tags))


def _run_evidence(row: Mapping[str, object]) -> dict[str, object]:
    """Build one stable historical-run evidence item."""
    projected = _stable_projection(row)
    return {
        "race_key": projected["race_key"],
        "race_date": projected["race_date"],
        "finish": projected["finish"],
        "families": {
            "ability": {
                "declared_class_group": projected["declared_class_group"],
                "time_class_equivalent": projected["time_class_equivalent"],
                "time_class_equivalent_numeric": projected[
                    "time_class_equivalent_numeric"
                ],
                "horse_adjusted_delta_sec": projected[
                    "horse_adjusted_delta_sec"
                ],
                "horse_adjusted_delta_per_1000m": projected[
                    "horse_adjusted_delta_per_1000m"
                ],
            },
            "pace": {
                "pace_shape": projected["pace_shape"],
            },
            "position": {
                "corner1_frontness": projected["corner1_frontness"],
                "corner2_frontness": projected["corner2_frontness"],
                "corner3_frontness": projected["corner3_frontness"],
                "corner4_frontness": projected["corner4_frontness"],
                "early_position_gain": projected["early_position_gain"],
                "middle_position_gain": projected["middle_position_gain"],
                "late_position_gain": projected["late_position_gain"],
                "overall_position_gain": projected["overall_position_gain"],
            },
            "finish": {
                "last3f_rank": projected["last3f_rank"],
                "last3f_speed_percentile": projected[
                    "last3f_speed_percentile"
                ],
                "closing_gain_sec": projected["closing_gain_sec"],
                "winner_gap_sec": projected["winner_gap_sec"],
            },
            "trouble": {
                "calibration_status": "RAW_ONLY_UNCALIBRATED",
                "jrdb_track_diff": projected["jrdb_track_diff"],
                "jrdb_pace_score": projected["jrdb_pace_score"],
                "jrdb_late_break_score": projected["jrdb_late_break_score"],
                "jrdb_position_score": projected["jrdb_position_score"],
                "jrdb_trouble_score": projected["jrdb_trouble_score"],
                "jrdb_prev_trouble_score": projected[
                    "jrdb_prev_trouble_score"
                ],
                "jrdb_mid_trouble_score": projected[
                    "jrdb_mid_trouble_score"
                ],
                "jrdb_late_trouble_score": projected[
                    "jrdb_late_trouble_score"
                ],
            },
        },
        "review_tags": _review_tags(projected),
    }


def _profile(runs: list[dict[str, object]], requested_runs: int) -> dict[str, object]:
    """Summarize repeated deterministic patterns without scoring them."""
    counter: Counter[str] = Counter()
    for run in runs:
        raw_tags = run.get("review_tags")
        if not isinstance(raw_tags, list):
            continue
        for raw_tag in raw_tags:
            tag = _text(raw_tag)
            if tag:
                counter[tag] += 1

    repeated_patterns = [
        {"tag": tag, "count": count}
        for tag, count in sorted(counter.items())
        if count >= 2
    ]

    observed_runs = len(runs)
    coverage_status = "NONE"
    if observed_runs > 0:
        coverage_status = "PARTIAL"
    if observed_runs >= requested_runs:
        coverage_status = "FULL"

    return {
        "observed_runs": observed_runs,
        "requested_runs": requested_runs,
        "coverage_status": coverage_status,
        "pattern_counts": dict(sorted(counter.items())),
        "repeated_patterns": repeated_patterns,
        "hidden_strength_signals": [],
        "fragile_form_signals": [],
        "composite_signal_status": "NOT_DERIVED_V0_1",
    }


def _target(independent_view: Mapping[str, object]) -> dict[str, object]:
    """Validate and extract the RaceNote independent-view target."""
    if _text(independent_view.get("view_kind")).upper() != "INDEPENDENT":
        raise RaceReviewAdapterError(
            "RaceReview adapter requires a RaceNote INDEPENDENT view"
        )

    race = independent_view.get("race")
    if not isinstance(race, Mapping):
        raise RaceReviewAdapterError("independent view is missing race")

    target_date = _date_text(race.get("date"))
    race_no = _positive_int(race.get("race_no"), "race.race_no")
    return {
        "date": target_date,
        "venue": _text(race.get("venue")),
        "race_no": race_no,
        "race_name": _text(race.get("race_name")),
    }


def build_racereview_evidence(
    independent_view: Mapping[str, object],
    reader: RaceReviewReader,
    *,
    per_horse_limit: int = 5,
) -> dict[str, object]:
    """Build one RaceReviewDB sidecar for a RaceNote independent view."""
    if per_horse_limit < 1:
        raise ValueError("per_horse_limit must be positive")

    target = _target(independent_view)
    raw_horses = independent_view.get("horses")
    if not isinstance(raw_horses, list) or not raw_horses:
        raise RaceReviewAdapterError("independent view is missing horses")

    identities: list[dict[str, object]] = []
    horse_ids: list[str] = []
    for index, raw_horse in enumerate(raw_horses, start=1):
        if not isinstance(raw_horse, Mapping):
            raise RaceReviewAdapterError(f"horses[{index}] must be an object")
        basic = raw_horse.get("basic")
        if not isinstance(basic, Mapping):
            raise RaceReviewAdapterError(
                f"horses[{index}].basic must be an object"
            )

        horse_no = _positive_int(
            basic.get("horse_no"),
            f"horses[{index}].basic.horse_no",
        )
        horse_id = _text(basic.get("horse_id"))
        horse_name = _text(basic.get("horse_name"))
        identities.append(
            {
                "horse_no": horse_no,
                "horse_name": horse_name,
                "horse_id": horse_id,
            }
        )
        if horse_id:
            horse_ids.append(horse_id)

    history_by_horse = reader.histories_for_horses(
        horse_ids,
        before_date=target["date"],
        per_horse_limit=per_horse_limit,
    )

    output_horses: list[dict[str, object]] = []
    for identity in identities:
        horse_id = _text(identity["horse_id"])
        history_status = "NO_HORSE_ID"
        raw_history: list[dict[str, object]] = []
        if horse_id:
            history_status = "NO_HISTORY"
            rows = history_by_horse.get(horse_id, [])
            if rows:
                history_status = "AVAILABLE"
                raw_history = rows

        runs: list[dict[str, object]] = []
        for row in raw_history:
            race_date = _date_text(row.get("race_date"))
            if race_date >= target["date"]:
                raise RaceReviewAdapterError(
                    "RaceReviewDB history violated as-of-exclusive policy: "
                    f"horse_id={horse_id} race_date={race_date} "
                    f"target_date={target['date']}"
                )
            runs.append(_run_evidence(row))

        output_horses.append(
            {
                **identity,
                "history_status": history_status,
                "runs": runs,
                "profile": _profile(runs, per_horse_limit),
            }
        )

    metadata = reader.metadata()
    return {
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "source": {
            "kind": "RaceReviewDB",
            **metadata,
        },
        "target": target,
        "policy": {
            "as_of_exclusive": True,
            "horse_identity": "JRDB_BLOOD_REGISTRATION_NO",
            "name_fallback": False,
            "stable_fields_only": True,
            "performance_label_status": "NOT_USED_UNSTABLE",
            "reason_codes_status": "NOT_USED_UNSTABLE",
            "track_bias_status": "NOT_USED_UNCALIBRATED_V0_1",
            "market_visibility_status": "NOT_APPLICABLE",
        },
        "horses": sorted(
            output_horses,
            key=lambda horse: int(horse["horse_no"]),
        ),
    }


def main() -> int:
    """Build a RaceReviewDB sidecar JSON from an independent view."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--independent-view", type=Path, required=True)
    parser.add_argument("--racereview-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-horse-limit", type=int, default=5)
    args = parser.parse_args()

    independent_view = json.loads(
        args.independent_view.read_text(encoding="utf-8")
    )
    reader = RaceReviewReader(args.racereview_root)
    sidecar = build_racereview_evidence(
        independent_view,
        reader,
        per_horse_limit=args.per_horse_limit,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "adapter_version": ADAPTER_VERSION,
                "source_generation_id": sidecar["source"].get(
                    "generation_id"
                ),
                "horse_count": len(sidecar["horses"]),
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
