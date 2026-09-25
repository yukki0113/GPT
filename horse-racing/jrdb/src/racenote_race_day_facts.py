#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate and attach independent pre-result RaceNote race-day facts.

Race-day facts are deliberately separate from result-derived JRDB data.
The module only accepts an explicit provenance assertion with a timezone-aware
as-of timestamp, and it never converts weather or track condition into a rank.
"""
from __future__ import annotations

import argparse
import copy
import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path


ALLOWED_KEYS = {
    "source_kind",
    "as_of",
    "weather",
    "track_condition",
    "result_independent",
}


class RaceDayFactsError(RuntimeError):
    """Raised when race-day facts violate the pre-result contract."""


def _text(value: object) -> str:
    """Return stripped text or an empty string."""
    if value is None:
        return ""
    return str(value).strip()


def _aware_datetime(value: object, field: str) -> datetime:
    """Parse one timezone-aware ISO datetime."""
    text = _text(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise RaceDayFactsError(
            f"{field} must be an ISO datetime"
        ) from exc
    if parsed.tzinfo is None:
        raise RaceDayFactsError(
            f"{field} must include timezone"
        )
    return parsed


def validate_race_day_facts(
    raw: Mapping[str, object],
) -> dict[str, object]:
    """Validate one explicit independent race-day fact payload."""
    unknown = sorted(
        str(key)
        for key in raw.keys()
        if str(key) not in ALLOWED_KEYS
    )
    if unknown:
        raise RaceDayFactsError(
            f"unsupported race-day fact fields: {unknown}"
        )

    if raw.get("result_independent") is not True:
        raise RaceDayFactsError(
            "result_independent must be true"
        )

    source_kind = _text(raw.get("source_kind"))
    if not source_kind:
        raise RaceDayFactsError(
            "source_kind is required"
        )
    if len(source_kind) > 120:
        raise RaceDayFactsError(
            "source_kind is too long"
        )

    as_of = _text(raw.get("as_of"))
    if not as_of:
        raise RaceDayFactsError(
            "as_of is required"
        )
    _aware_datetime(as_of, "as_of")

    weather = _text(raw.get("weather"))
    track_condition = _text(raw.get("track_condition"))
    if not weather and not track_condition:
        raise RaceDayFactsError(
            "weather or track_condition is required"
        )
    if len(weather) > 80:
        raise RaceDayFactsError(
            "weather is too long"
        )
    if len(track_condition) > 80:
        raise RaceDayFactsError(
            "track_condition is too long"
        )

    return {
        "source_kind": source_kind,
        "as_of": as_of,
        "weather": weather or None,
        "track_condition": track_condition or None,
        "result_independent": True,
    }


def attach_race_day_facts(
    independent_view: Mapping[str, object],
    raw_facts: Mapping[str, object],
) -> dict[str, object]:
    """Attach validated facts to an INDEPENDENT RaceNote view."""
    if _text(independent_view.get("view_kind")).upper() != "INDEPENDENT":
        raise RaceDayFactsError(
            "race-day facts require an INDEPENDENT view"
        )

    race = independent_view.get("race")
    if not isinstance(race, Mapping):
        raise RaceDayFactsError(
            "independent view race must be an object"
        )

    facts = validate_race_day_facts(raw_facts)
    output = copy.deepcopy(dict(independent_view))
    output_race = output.get("race")
    if not isinstance(output_race, dict):
        raise RaceDayFactsError(
            "independent view race must be mutable object"
        )
    output_race["race_day_facts"] = facts
    return output


def main() -> int:
    """Validate facts and attach them to an independent view."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--independent-view",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--race-day-facts",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    args = parser.parse_args()

    independent = json.loads(
        args.independent_view.read_text(encoding="utf-8")
    )
    raw_facts = json.loads(
        args.race_day_facts.read_text(encoding="utf-8")
    )
    if not isinstance(raw_facts, Mapping):
        raise RaceDayFactsError(
            "race-day facts input must be an object"
        )

    output = attach_race_day_facts(
        independent,
        raw_facts,
    )
    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    args.output.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    facts = output["race"]["race_day_facts"]
    print(
        json.dumps(
            {
                "status": "PASS",
                "source_kind": facts["source_kind"],
                "as_of": facts["as_of"],
                "weather": facts["weather"],
                "track_condition": facts["track_condition"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
