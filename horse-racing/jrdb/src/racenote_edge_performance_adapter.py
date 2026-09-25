#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adapt JRDB Edge v0.2 matcher rows to RaceNote Gen0.3 performance evidence.

This adapter does not rematch or rescore Edge conditions.
It only projects the matcher output's performance channel and deliberately
drops all Value-channel fields before Forecast.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path

ADAPTER_VERSION = "RaceNote-Edge-Performance-Adapter-0.1"


class EdgePerformanceAdapterError(RuntimeError):
    """Raised when matcher output cannot be projected safely."""


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise EdgePerformanceAdapterError(f"{field} must be object")
    return value


def _list(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise EdgePerformanceAdapterError(f"{field} must be array")
    return value


def adapt_matcher_row(
    row: Mapping[str, object],
    *,
    serving_profile: str = "STANDARD",
) -> dict[str, object]:
    """Project one operational matcher row into performance-only evidence."""
    key = _mapping(row.get("key"), "row.key")
    horse_no_raw = key.get("horse_no")
    try:
        horse_no = int(horse_no_raw)
    except (TypeError, ValueError) as exc:
        raise EdgePerformanceAdapterError("row.key.horse_no required") from exc
    if horse_no < 1:
        raise EdgePerformanceAdapterError("row.key.horse_no must be positive")

    projected: list[dict[str, object]] = []
    for index, raw_match in enumerate(
        _list(row.get("edge_matches", []), "row.edge_matches"),
        start=1,
    ):
        match = _mapping(raw_match, f"row.edge_matches[{index}]")
        level = _text(match.get("performance_evidence_level")).upper()
        if level == "NONE":
            continue
        if level not in {"CONFIRMED", "SUGGESTIVE"}:
            raise EdgePerformanceAdapterError(
                f"unsupported performance evidence level: {level}"
            )

        evidence = _mapping(
            match.get("evidence"),
            f"row.edge_matches[{index}].evidence",
        )
        signal = _text(evidence.get("performance_signal")).upper()
        if signal not in {"POSITIVE", "NEGATIVE", "MIXED", "NEUTRAL"}:
            raise EdgePerformanceAdapterError(
                f"unsupported performance signal: {signal}"
            )

        presentation = _mapping(
            match.get("presentation"),
            f"row.edge_matches[{index}].presentation",
        )
        perf_presentation = _mapping(
            presentation.get("performance"),
            f"row.edge_matches[{index}].presentation.performance",
        )
        role = _text(perf_presentation.get("role")).upper()
        if role not in {"PRIMARY", "SECONDARY", "CONFLICT"}:
            raise EdgePerformanceAdapterError(
                f"unsupported performance presentation role: {role}"
            )

        edge_id = _text(match.get("edge_id"))
        family = _text(evidence.get("family"))
        if not edge_id or not family:
            raise EdgePerformanceAdapterError(
                "edge_id and performance family are required"
            )

        group = _text(match.get("redundancy_group_id")) or edge_id
        projected.append(
            {
                "edge_id": edge_id,
                "family": family,
                "performance_evidence_level": level,
                "signal": signal,
                "presentation_role": role,
                "conflict": bool(
                    perf_presentation.get("conflict", False)
                ),
                "redundancy_group_id": group,
            }
        )

    return {
        "adapter_version": ADAPTER_VERSION,
        "horse_no": horse_no,
        "race_horse_key": _text(key.get("race_horse_key")),
        "serving_profile": serving_profile,
        "status": "USED" if projected else "NO_MATCH",
        "matches": projected,
        "value_channel_status": "DROPPED_BEFORE_FORECAST",
        "consumer_recomputed_edge_conditions": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matcher-jsonl", required=True)
    parser.add_argument("--output-jsonl", required=True)
    parser.add_argument("--serving-profile", default="STANDARD")
    args = parser.parse_args()

    output: list[dict[str, object]] = []
    for line_no, raw_line in enumerate(
        Path(args.matcher_jsonl).read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not raw_line.strip():
            continue
        raw = json.loads(raw_line)
        if not isinstance(raw, Mapping):
            raise EdgePerformanceAdapterError(
                f"matcher line {line_no} must be object"
            )
        output.append(
            adapt_matcher_row(
                raw,
                serving_profile=args.serving_profile,
            )
        )

    with Path(args.output_jsonl).open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as handle:
        for row in output:
            handle.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )

    print(
        json.dumps(
            {
                "status": "PASS",
                "adapter_version": ADAPTER_VERSION,
                "runner_rows": len(output),
                "matched_runners": sum(
                    row["status"] == "USED"
                    for row in output
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
