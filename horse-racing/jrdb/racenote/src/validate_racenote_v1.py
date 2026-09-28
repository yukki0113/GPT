#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate the Phase-1 RaceNote v1 evidence boundary.

This is intentionally a boundary validator, not a full JSON-Schema engine.
It checks the core invariants that define the redesigned project:
- evidence note only;
- every runner present;
- no forecast marks/ranks/scores;
- result and current market hidden;
- Trend blocks coexist as descriptive context;
- provenance and missingness are explicit.

A later implementation may add full jsonschema validation.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path

SCHEMA_VERSION = "RaceNote-Evidence-1.0"

FORBIDDEN_KEYS = {
    "mark",
    "marks",
    "forecast_rank",
    "final_rank",
    "final_order",
    "candidate_cluster",
    "best_bet",
    "preferred_horse",
    "semantic_candidate_order",
    "betting_ticket",
    "betting_tickets",
    "prediction_score",
    "forecast_score",
}

FORBIDDEN_PREFIXES = (
    "current_odds",
    "current_popularity",
    "result_",
)


class RaceNoteV1Error(RuntimeError):
    pass


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RaceNoteV1Error(f"{field} must be an object")
    return value


def _list(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise RaceNoteV1Error(f"{field} must be an array")
    return value


def _walk_forbidden(value: object, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            lower = key.lower()
            if lower in FORBIDDEN_KEYS:
                hits.append(f"{path}.{key}")
            if any(lower.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
                hits.append(f"{path}.{key}")
            _child_path = f"{path}.{key}"
            hits.extend(_walk_forbidden(child, _child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_walk_forbidden(child, f"{path}[{index}]"))
    return hits


def validate(note: Mapping[str, object]) -> dict[str, object]:
    if note.get("schema_version") != SCHEMA_VERSION:
        raise RaceNoteV1Error("unsupported schema_version")

    metadata = _mapping(note.get("metadata"), "metadata")
    if metadata.get("note_kind") != "EVIDENCE_NOTE":
        raise RaceNoteV1Error("metadata.note_kind must be EVIDENCE_NOTE")
    if metadata.get("result_visibility") != "HIDDEN":
        raise RaceNoteV1Error("result_visibility must be HIDDEN")
    if metadata.get("market_visibility") not in {"HIDDEN", "SUPPLEMENT_ONLY"}:
        raise RaceNoteV1Error("market_visibility must be HIDDEN or SUPPLEMENT_ONLY")

    race = _mapping(note.get("race"), "race")
    field_size = race.get("field_size")
    try:
        field_size_int = int(field_size)
    except (TypeError, ValueError) as exc:
        raise RaceNoteV1Error("race.field_size must be integer") from exc

    runners = _list(note.get("runners"), "runners")
    if len(runners) != field_size_int:
        raise RaceNoteV1Error(
            f"runner coverage mismatch: field_size={field_size_int}, runners={len(runners)}"
        )

    horse_nos: list[int] = []
    for index, raw in enumerate(runners, start=1):
        runner = _mapping(raw, f"runners[{index}]")
        try:
            horse_no = int(runner.get("horse_no"))
        except (TypeError, ValueError) as exc:
            raise RaceNoteV1Error(f"runners[{index}].horse_no invalid") from exc
        horse_nos.append(horse_no)
        if not str(runner.get("horse_name") or "").strip():
            raise RaceNoteV1Error(f"runners[{index}].horse_name required")
        for required in (
            "identity",
            "current_entry",
            "recent_runs",
            "ability_history",
            "horse_history",
            "racereview",
            "population_context",
            "data_gaps",
            "provenance_refs",
        ):
            if required not in runner:
                raise RaceNoteV1Error(f"runners[{index}].{required} required")

    if len(horse_nos) != len(set(horse_nos)):
        raise RaceNoteV1Error("duplicate horse_no")

    trend = _mapping(note.get("trend_context"), "trend_context")
    for key in ("named_race", "local_context", "base_context", "comparison"):
        if key not in trend:
            raise RaceNoteV1Error(f"trend_context.{key} required")

    coverage = _mapping(note.get("coverage"), "coverage")
    if int(coverage.get("runner_count") or 0) != len(runners):
        raise RaceNoteV1Error("coverage.runner_count mismatch")

    provenance = _list(note.get("provenance"), "provenance")
    if not provenance:
        raise RaceNoteV1Error("provenance must not be empty")

    forbidden = sorted(set(_walk_forbidden(note)))
    if forbidden:
        raise RaceNoteV1Error(
            "forecast/market/result leakage keys detected: " + ", ".join(forbidden)
        )

    return {
        "status": "PASS",
        "schema_version": SCHEMA_VERSION,
        "runner_count": len(runners),
        "trend_blocks": ["named_race", "local_context", "base_context"],
        "forecast_fields_present": False,
        "result_visibility": metadata.get("result_visibility"),
        "market_visibility": metadata.get("market_visibility"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    note = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(note, Mapping):
        raise RaceNoteV1Error("root must be object")
    result = validate(note)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
