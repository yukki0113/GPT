#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build RaceNote-Evidence-1.0 from neutral pre-race assets.

Phase 2 v0.1 deliberately consumes only:
- the old Gen0.2 INDEPENDENT view, as a neutral source adapter;
- optional raw stable RaceReview evidence.

It does not consume:
- General Evidence / TrendFirst,
- Horse Evidence Card ranking/profile semantics,
- pairwise/synthesis/semantic ordering,
- Mark Policy / Best Bet,
- current market / current JRDB consensus / Training Edge / RL / EdgeDB.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "RaceNote-Evidence-1.0"


class BuildError(RuntimeError):
    """Raised when a safe RaceNote v1 evidence note cannot be assembled."""


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _semantic_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _finish(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 1 else None


def _flatten_recent_run(run: Mapping[str, object]) -> dict[str, object]:
    race = run.get("race") if isinstance(run.get("race"), Mapping) else {}
    result = (
        run.get("result")
        if isinstance(run.get("result"), Mapping)
        else {}
    )
    performance = (
        run.get("performance")
        if isinstance(run.get("performance"), Mapping)
        else {}
    )
    body = run.get("body") if isinstance(run.get("body"), Mapping) else {}
    notes = run.get("notes") if isinstance(run.get("notes"), Mapping) else {}

    return {
        "date": _text(race.get("date")),
        "venue": _text(race.get("venue")),
        "race_no": race.get("race_no"),
        "race_name": race.get("race_name"),
        "surface": _text(race.get("surface")),
        "distance_m": race.get("distance_m"),
        "class": _text(race.get("class")),
        "grade": race.get("grade"),
        "turn": race.get("turn"),
        "course_layout": race.get("course_layout"),
        "track_condition": race.get("track_condition"),
        "field_size": race.get("field_size"),
        "finish": _finish(result.get("finish")),
        "abnormal": result.get("abnormal"),
        "time_sec": result.get("time_sec"),
        "jockey": result.get("jockey"),
        "assigned_weight": result.get("carried_weight_kg"),
        "ability_value": performance.get("idm"),
        "corners": copy.deepcopy(performance.get("corners")),
        "first3f_sec": performance.get("first3f_sec"),
        "last3f_sec": performance.get("last3f_sec"),
        "race_pace": performance.get("race_pace"),
        "horse_pace": performance.get("horse_pace"),
        "course_lane": performance.get("course_lane"),
        "body_weight_kg": body.get("body_weight_kg"),
        "body_weight_change_kg": body.get("body_weight_change_kg"),
        "special_notes": copy.deepcopy(notes.get("special_notes") or []),
        "paddock_comment": notes.get("paddock_comment"),
        "leg_comment": notes.get("leg_comment"),
        "equipment_comment": notes.get("equipment_comment"),
        "race_comment": notes.get("race_comment"),
    }


def _racereview_by_horse(
    raw: Mapping[str, object] | None,
) -> dict[int, Mapping[str, object]]:
    output: dict[int, Mapping[str, object]] = {}
    if raw is None:
        return output
    horses = raw.get("horses")
    if not isinstance(horses, list):
        return output

    for horse in horses:
        if not isinstance(horse, Mapping):
            continue
        try:
            horse_no = int(horse.get("horse_no"))
        except (TypeError, ValueError):
            continue
        output[horse_no] = horse
    return output


def _neutral_racereview(
    horse: Mapping[str, object] | None,
) -> dict[str, object]:
    """Keep stable descriptive RaceReview observations only.

    Do not copy Horse Evidence Card direction/priority/strength, hidden-strength
    candidate labels, fragile-form candidate labels, or final profile ratings.
    """
    if horse is None:
        return {
            "status": "UNAVAILABLE",
            "runs": [],
            "pattern_counts": {},
            "repeated_patterns": [],
        }

    profile = (
        horse.get("profile")
        if isinstance(horse.get("profile"), Mapping)
        else {}
    )
    return {
        "status": horse.get("history_status", "AVAILABLE"),
        "coverage": {
            "observed_runs": profile.get("observed_runs"),
            "requested_runs": profile.get("requested_runs"),
            "coverage_status": profile.get("coverage_status"),
        },
        "runs": copy.deepcopy(horse.get("runs") or []),
        "pattern_counts": copy.deepcopy(
            profile.get("pattern_counts") or {}
        ),
        "repeated_patterns": copy.deepcopy(
            profile.get("repeated_patterns") or []
        ),
        "note": (
            "Run-level stable RaceReview observations only; "
            "no Horse Evidence Card ranking/profile semantics carried forward."
        ),
    }


def build(
    independent: Mapping[str, object],
    racereview: Mapping[str, object] | None = None,
) -> dict[str, object]:
    if _text(independent.get("view_kind")).upper() != "INDEPENDENT":
        raise BuildError("Gen0.2 INDEPENDENT view is required")

    policy = (
        independent.get("policy")
        if isinstance(independent.get("policy"), Mapping)
        else {}
    )
    hidden_flags = (
        "current_jrdb_consensus_visible",
        "current_market_visible",
        "training_edge_visible",
        "rl_index_visible",
        "edgedb_match_visible",
    )
    for key in hidden_flags:
        if policy.get(key) is not False:
            raise BuildError(f"unsafe firewall policy: {key}")

    race = (
        independent.get("race")
        if isinstance(independent.get("race"), Mapping)
        else None
    )
    horses = (
        independent.get("horses")
        if isinstance(independent.get("horses"), list)
        else None
    )
    if race is None or horses is None:
        raise BuildError("independent view is missing race/horses")

    metadata = (
        independent.get("metadata")
        if isinstance(independent.get("metadata"), Mapping)
        else {}
    )
    enrichment = (
        metadata.get("history_enrichment")
        if isinstance(metadata.get("history_enrichment"), Mapping)
        else {}
    )
    as_of = enrichment.get("as_of_exclusive") or race.get("date")

    rr_map = _racereview_by_horse(racereview)

    legacy_base = copy.deepcopy(race.get("race_trends") or {})
    periods: list[str] = []
    if isinstance(legacy_base, Mapping):
        for family in legacy_base.values():
            if not isinstance(family, Mapping):
                continue
            for value in family.values():
                if isinstance(value, Mapping) and value.get("period"):
                    periods.append(str(value["period"]))
    period = Counter(periods).most_common(1)[0][0] if periods else None

    runners: list[dict[str, object]] = []
    for raw_horse in horses:
        if not isinstance(raw_horse, Mapping):
            continue

        basic = (
            raw_horse.get("basic")
            if isinstance(raw_horse.get("basic"), Mapping)
            else {}
        )
        try:
            horse_no = int(basic.get("horse_no"))
        except (TypeError, ValueError) as exc:
            raise BuildError("horse_no is missing or invalid") from exc

        recent_runs = [
            _flatten_recent_run(run)
            for run in (raw_horse.get("recent_runs") or [])
            if isinstance(run, Mapping)
        ]

        run_values = []
        for run in recent_runs:
            if run.get("ability_value") is None:
                continue
            run_values.append(
                {
                    key: run.get(key)
                    for key in (
                        "date",
                        "venue",
                        "race_name",
                        "surface",
                        "distance_m",
                        "class",
                        "grade",
                        "ability_value",
                    )
                }
            )

        historical_profile = (
            raw_horse.get("historical_profile")
            if isinstance(raw_horse.get("historical_profile"), Mapping)
            else {}
        )
        rr_horse = rr_map.get(horse_no)

        gaps: list[str] = []
        if not recent_runs:
            gaps.append("NO_RECENT_RUNS")
        if not historical_profile:
            gaps.append("NO_HISTORICAL_PROFILE")
        if rr_horse is None or rr_horse.get("history_status") != "AVAILABLE":
            gaps.append("RACEREVIEW_HISTORY_UNAVAILABLE")
        if _text(race.get("class")).startswith("新馬"):
            gaps.append("NEWCOMER_RECENT_FORM_UNAVAILABLE_BY_DESIGN")

        runners.append(
            {
                "horse_no": horse_no,
                "horse_name": _text(basic.get("horse_name")),
                "identity": {
                    "frame_no": basic.get("frame_no"),
                    "horse_id": basic.get("horse_id"),
                    "jockey": basic.get("jockey"),
                    "trainer": basic.get("trainer"),
                    "trainer_base": basic.get("trainer_base"),
                    "apprentice": basic.get("apprentice"),
                },
                "current_entry": {
                    "assigned_weight_kg": basic.get("carried_weight_kg"),
                    "blinker": basic.get("blinker"),
                    "condition_facts": copy.deepcopy(
                        raw_horse.get("condition_facts") or {}
                    ),
                    "training_facts": copy.deepcopy(
                        raw_horse.get("training_facts") or {}
                    ),
                },
                "recent_runs": recent_runs,
                "ability_history": {
                    "run_values": run_values,
                    "summary_status": "RUN_CONTEXT_PRESERVED",
                },
                "horse_history": {
                    "historical_profile": copy.deepcopy(
                        historical_profile
                    ),
                    "older_runs": copy.deepcopy(
                        raw_horse.get("older_runs") or []
                    ),
                    "history_coverage": copy.deepcopy(
                        raw_horse.get("history_coverage") or {}
                    ),
                },
                "racereview": _neutral_racereview(rr_horse),
                "population_context": copy.deepcopy(
                    raw_horse.get("stats") or {}
                ),
                "data_gaps": gaps,
                "provenance_refs": (
                    ["P1_INDEPENDENT"]
                    + (["P2_RACEREVIEW"] if rr_horse is not None else [])
                ),
            }
        )

    note = {
        "schema_version": SCHEMA_VERSION,
        "metadata": {
            "note_kind": "EVIDENCE_NOTE",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "target_date": race.get("date"),
            "as_of": str(as_of),
            "result_visibility": "HIDDEN",
            "market_visibility": "HIDDEN",
            "source_snapshot": {
                "independent_semantic_sha256": _semantic_sha256(independent),
                "racereview_semantic_sha256": (
                    _semantic_sha256(racereview)
                    if racereview is not None
                    else None
                ),
            },
        },
        "race": {
            "date": race.get("date"),
            "venue": race.get("venue"),
            "race_no": race.get("race_no"),
            "race_name": race.get("race_name"),
            "surface": race.get("surface"),
            "distance_m": race.get("distance_m"),
            "field_size": race.get("field_size"),
            "class": race.get("class"),
            "grade": race.get("grade"),
            "turn": race.get("turn"),
            "course_layout": race.get("course_layout"),
            "course_rail": race.get("course_rail"),
            "race_type": race.get("race_type"),
            "race_conditions": copy.deepcopy(
                race.get("race_conditions") or []
            ),
            "weight_rule": race.get("weight_rule"),
            "meeting_id": _text(race.get("meeting")) or None,
            "meeting_day": race.get("day"),
            "source_codes": copy.deepcopy(race.get("source_codes") or {}),
            "is_newcomer": _text(race.get("class")).startswith("新馬"),
            "is_steeplechase": _text(race.get("surface")).startswith("障害"),
        },
        "race_day": {
            "status": "UNAVAILABLE",
            "weather": None,
            "track_condition": None,
            "as_of": None,
            "source": None,
            "limitations": [
                (
                    "Historical Phase-2 sample has no independently attached "
                    "race-day facts in this artifact."
                )
            ],
        },
        "trend_context": {
            "named_race": {
                "status": "UNAVAILABLE",
                "scope": {"race_name": race.get("race_name")},
                "sample": {"starts": 0, "editions": 0, "period": None},
                "dimensions": {},
                "provenance_refs": [],
                "limitations": [
                    (
                        "Named-race trend extractor is not implemented "
                        "in Phase 2 v0.1."
                    )
                ],
            },
            "local_context": {
                "status": "UNAVAILABLE",
                "scope": {
                    "venue": race.get("venue"),
                    "surface": race.get("surface"),
                    "distance_m": race.get("distance_m"),
                    "class": race.get("class"),
                    "meeting": race.get("meeting"),
                    "meeting_day": race.get("day"),
                },
                "sample": {"starts": 0, "editions": None, "period": None},
                "dimensions": {},
                "provenance_refs": [],
                "limitations": [
                    (
                        "Class-preserving local-context trend extractor "
                        "is not implemented in Phase 2 v0.1."
                    )
                ],
            },
            "base_context": {
                "status": "AVAILABLE" if legacy_base else "UNAVAILABLE",
                "scope": {
                    "venue": race.get("venue"),
                    "surface": race.get("surface"),
                    "distance_m": race.get("distance_m"),
                    "class_scope": "LEGACY_BROAD_ALL_CLASS_CONTEXT",
                    "period": period,
                },
                "sample": {
                    "starts": 0,
                    "editions": None,
                    "period": period,
                },
                "dimensions": legacy_base,
                "provenance_refs": ["P1_INDEPENDENT"],
                "limitations": [
                    (
                        "Legacy race_trends are retained only as broad Base "
                        "Context; they are not class-preserving Local Trend."
                    )
                ],
            },
            "comparison": {
                "status": "PARTIAL" if legacy_base else "UNAVAILABLE",
                "notes": [
                    (
                        "Local-vs-Base comparison awaits the Phase-2 "
                        "local/named trend extractor."
                    )
                ],
            },
        },
        "field_context": {
            "status": "PARTIAL",
            "running_style_distribution": None,
            "class_movers": [],
            "layoff_distribution": None,
            "notes": [
                (
                    "Current independent view does not expose a neutral "
                    "current-entry running-style field; no substitute was inferred."
                )
            ],
        },
        "runners": sorted(runners, key=lambda item: item["horse_no"]),
        "coverage": {
            "runner_count": len(runners),
            "missing_families": [
                "race_day",
                "named_race_trend",
                "local_context_trend",
            ],
            "limitations": [
                (
                    "Phase 2 v0.1 proves evidence-note assembly from "
                    "existing neutral assets."
                ),
                (
                    "Named/local class-preserving Trend generation remains "
                    "unimplemented."
                ),
                (
                    "Current market/JRDB consensus/Training Edge/RL/EdgeDB "
                    "are intentionally absent."
                ),
            ],
        },
        "provenance": [
            {
                "id": "P1_INDEPENDENT",
                "source": "RaceNote Gen0.2 independent view",
                "as_of": str(as_of),
                "snapshot": independent.get("source_semantic_sha256"),
                "transform_version": independent.get("firewall_version"),
            },
            *(
                [
                    {
                        "id": "P2_RACEREVIEW",
                        "source": "RaceReviewDB stable evidence adapter",
                        "as_of": str(as_of),
                        "snapshot": (
                            (racereview.get("source") or {}).get(
                                "generation_id"
                            )
                        ),
                        "transform_version": racereview.get(
                            "adapter_version"
                        ),
                    }
                ]
                if racereview is not None
                else []
            ),
        ],
    }
    return note


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--independent-view", type=Path, required=True)
    parser.add_argument("--racereview-evidence", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    independent = json.loads(
        args.independent_view.read_text(encoding="utf-8")
    )
    racereview = (
        json.loads(args.racereview_evidence.read_text(encoding="utf-8"))
        if args.racereview_evidence
        else None
    )
    if not isinstance(independent, Mapping):
        raise BuildError("independent view root must be object")
    if racereview is not None and not isinstance(racereview, Mapping):
        raise BuildError("RaceReview root must be object")

    note = build(independent, racereview)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(note, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "output": str(args.output),
                "runner_count": len(note["runners"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
