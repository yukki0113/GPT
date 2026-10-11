#!/usr/bin/env python3
"""Lint RaceNote v0.5.3 Decision Core reasoning capture.

This is an authoring-quality lint, not a prediction validator. It never changes
marks or candidate membership and is intentionally separate from Freeze verify
so older frozen cohorts remain reproducible.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


KEEP_BOILERPLATE = (
    "異なる勝ち筋はあるが",
    "追加価値が上回るまでは",
    "5頭を維持する",
)
ADMIT_BOILERPLATE = (
    "別経路は",
    "交換価値が高い",
    "最終比較で",
    "採用する",
)
RANKING_BOILERPLATE = (
    "安定感より",
    "勝ち切り可能性を優先",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def lint_core(core: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    venue = _text(core.get("venue"))
    race_no = core.get("race_no")
    prefix = f"{venue}{race_no}R"

    compression = core.get("candidate_compression") or {}
    boundary = core.get("boundary_review") or {}
    role = core.get("role_assignment") or {}

    decision = compression.get("decision")
    challenger = compression.get("external_challenger_horse_no")
    c_reason = _text(compression.get("reason"))
    b_reason = _text(boundary.get("reason"))
    ranking = _text(role.get("ranking_reason"))

    # Six-plus-runner comparisons have an explicit challenger. The two reason
    # fields may overlap, but identical text usually means the direct exchange
    # was not separately captured.
    if challenger is not None and c_reason == b_reason:
        errors.append(
            f"{prefix}: candidate_compression.reason and boundary_review.reason "
            "must not be identical; preserve the direct comparison explicitly"
        )

    if decision == "KEEP_ORDINARY_FIVE" and all(x in c_reason for x in KEEP_BOILERPLATE):
        errors.append(
            f"{prefix}: KEEP reason is generic boilerplate; record a concrete "
            "challenger strength, boundary-horse strength, and exchange basis"
        )

    if decision == "ADMIT_CHALLENGER" and all(x in c_reason for x in ADMIT_BOILERPLATE):
        errors.append(
            f"{prefix}: ADMIT reason is generic boilerplate; record a concrete "
            "challenger strength, displaced-horse strength, and exchange basis"
        )

    if all(x in ranking for x in RANKING_BOILERPLATE):
        errors.append(
            f"{prefix}: ranking_reason is generic win-first boilerplate; record "
            "at least one race-specific reason why ◎ outranks ○"
        )

    return errors


def lint_decisions(decisions: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for core in decisions:
        if not isinstance(core, dict):
            errors.append("Decision Core entry must be an object")
            continue
        errors.extend(lint_core(core))
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--decisions", required=True, type=Path)
    args = ap.parse_args()

    value = json.loads(args.decisions.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("--decisions must contain a JSON array")

    errors = lint_decisions(value)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"reasoning_capture_lint=FAIL errors={len(errors)}")
        return 1

    print(f"reasoning_capture_lint=PASS decisions={len(value)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
