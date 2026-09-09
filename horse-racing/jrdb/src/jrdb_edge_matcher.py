#!/usr/bin/env python3
"""Consumer-neutral pre-race matcher for JRDB Edge Registry JSONL."""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

VERSION = "0.1.0"
DEFAULT_STATUSES = ("ACTIVE",)
STATUS_RANK = {"ACTIVE": 0, "PROVISIONAL": 1, "WATCH": 2, "DECAYING": 3}
CONDITION_FIELDS = {
    "venue_code", "surface_code", "distance_m", "turn_code", "frame_zone",
    "sire_name", "sire_line_code", "broodmare_sire_name", "broodmare_sire_line_code",
    "jockey_code", "trainer_code", "distance_change_bucket", "surface_transition",
    "frame_transition",
}
IDENTITY_FIELDS = ("race_key", "race_horse_key", "horse_id", "horse_no", "race_date")


def _validate_edge(edge: Mapping[str, Any], line_no: int | None = None) -> None:
    prefix = f"registry line {line_no}: " if line_no else ""
    for key in ("edge_id", "status", "display_text", "polarity", "conditions"):
        if key not in edge:
            raise ValueError(f"{prefix}missing {key}")
    conditions = edge["conditions"]
    if not isinstance(conditions, Mapping):
        raise ValueError(f"{prefix}conditions must be an object")
    for bucket in ("anchor", "modifiers"):
        values = conditions.get(bucket, {})
        if not isinstance(values, Mapping):
            raise ValueError(f"{prefix}conditions.{bucket} must be an object")
        bad = sorted(set(values) - CONDITION_FIELDS)
        if bad:
            raise ValueError(f"{prefix}unsupported condition field(s): {bad}")


def load_registry(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        row = json.loads(raw)
        if not isinstance(row, dict):
            raise ValueError(f"registry line {line_no} is not an object")
        _validate_edge(row, line_no)
        rows.append(row)
    return rows


def _equal(expected: Any, actual: Any) -> bool:
    if expected is None or actual is None:
        return expected is actual
    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected is actual
    if isinstance(expected, (int, float)):
        return isinstance(actual, (int, float)) and float(expected) == float(actual)
    return isinstance(actual, str) and str(expected) == actual


def _matches(values: Mapping[str, Any], runner: Mapping[str, Any]) -> bool:
    return all(field in runner and _equal(expected, runner.get(field)) for field, expected in values.items())


def _day(value: Any, field: str) -> date | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be ISO date text")
    return date.fromisoformat(value)


def edge_matches_runner(
    edge: Mapping[str, Any], runner: Mapping[str, Any], *, statuses: Sequence[str] = DEFAULT_STATUSES
) -> dict[str, Any] | None:
    _validate_edge(edge)
    if str(edge["status"]) not in set(statuses):
        return None
    target = _day(runner.get("race_date"), "race_date")
    expires = _day(edge.get("expires_at"), "expires_at")
    review = _day(edge.get("next_review_at"), "next_review_at")
    if target and expires and target > expires:
        return None
    conditions = edge["conditions"]
    anchor, modifiers = conditions.get("anchor", {}), conditions.get("modifiers", {})
    if not _matches(anchor, runner) or not _matches(modifiers, runner):
        return None
    evidence = {
        "family": edge.get("family"),
        "template_id": conditions.get("template_id"),
        "template_version": conditions.get("template_version"),
        "validation_class": edge.get("validation_class"),
        "policy_id": edge.get("policy_id"),
        "performance_signal": edge.get("performance_signal"),
        "value_signal": edge.get("value_signal"),
        "sample_n": edge.get("sample_n"),
        "unique_horses": edge.get("unique_horses"),
        "unique_races": edge.get("unique_races"),
        "place_rate": edge.get("place_rate"),
        "place_roi": edge.get("place_roi"),
        "baseline_place_rate": edge.get("baseline_place_rate"),
        "performance_lift": edge.get("performance_lift"),
        "last_validated_at": edge.get("last_validated_at"),
        "next_review_at": edge.get("next_review_at"),
        "expires_at": edge.get("expires_at"),
        "review_due": bool(target and review and target > review),
        "conditions": {"anchor": dict(anchor), "modifiers": dict(modifiers)},
    }
    return {
        "edge_id": edge["edge_id"], "display_text": edge["display_text"],
        "polarity": edge["polarity"], "status": edge["status"],
        "strength_score": edge.get("strength_score"), "confidence_band": edge.get("confidence_band"),
        "registry_version": edge.get("registry_version"), "evidence": evidence,
    }


def match_runner(
    registry: Iterable[Mapping[str, Any]], runner: Mapping[str, Any], *, statuses: Sequence[str] = DEFAULT_STATUSES
) -> list[dict[str, Any]]:
    rows = [m for edge in registry if (m := edge_matches_runner(edge, runner, statuses=statuses))]
    rows.sort(key=lambda r: (STATUS_RANK.get(str(r["status"]), 99), -float(r.get("strength_score") or 0), str(r["edge_id"])))
    return rows


def _load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--registry-jsonl", required=True)
    p.add_argument("--runner-jsonl", required=True)
    p.add_argument("--output-jsonl", required=True)
    p.add_argument("--statuses", default="ACTIVE")
    p.add_argument("--only-matched", action="store_true")
    args = p.parse_args()
    statuses = tuple(x.strip().upper() for x in args.statuses.split(",") if x.strip())
    bad = sorted(set(statuses) - set(STATUS_RANK))
    if not statuses or bad:
        raise ValueError(f"unsupported status(es): {bad}")
    registry, runners = load_registry(args.registry_jsonl), _load_jsonl(args.runner_jsonl)
    output_rows = []
    for runner in runners:
        matches = match_runner(registry, runner, statuses=statuses)
        if args.only_matched and not matches:
            continue
        key = {f: runner.get(f) for f in IDENTITY_FIELDS if f in runner}
        output_rows.append({"key": key, "edge_matches": matches})
    with Path(args.output_jsonl).open("w", encoding="utf-8", newline="\n") as fh:
        for row in output_rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "matcher_version": VERSION, "runner_rows": len(runners),
                      "matched_runners": sum(bool(r["edge_matches"]) for r in output_rows),
                      "matches": sum(len(r["edge_matches"]) for r in output_rows)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
