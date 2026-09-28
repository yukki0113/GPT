#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render RaceNote-Evidence-1.0 as a GPT/human-readable Markdown note."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _dash(value: object) -> str:
    if value is None or value == "" or value == []:
        return "—"
    return str(value)


def _scope_summary(scope: dict) -> str:
    labels = {
        "venue": "会場",
        "surface": "馬場",
        "distance_m": "距離",
        "race_name": "レース",
        "class": "クラス",
        "grade": "Grade",
        "class_scope": "クラス母集団",
        "target_class": "対象クラス",
        "target_grade": "対象Grade",
        "month": "月",
        "course_rail": "コース",
        "meeting_day_band": "開催日帯",
    }
    pieces: list[str] = []
    for key, value in scope.items():
        if key == "period" or value is None or value == "":
            continue
        label = labels.get(key, key)
        if key == "distance_m":
            value = f"{value}m"
        elif key == "month":
            value = f"{value}月"
        elif key == "meeting_day_band" and isinstance(value, list) and len(value) == 2:
            value = f"{value[0]}-{value[1]}日目"
        pieces.append(f"{label}={value}")
    return " / ".join(pieces) if pieces else "—"


def _history_summary(horse: dict) -> str:
    profile = (
        horse.get("horse_history", {})
        .get("historical_profile", {})
    )
    pieces: list[str] = []
    for key, label in (
        ("career", "通算"),
        ("same_surface", "同馬場種"),
        ("same_distance", "同距離"),
        ("same_venue", "同場"),
    ):
        item = profile.get(key) or {}
        if item.get("starts") is None:
            continue
        pieces.append(
            f"{label} {item.get('starts')}戦 "
            f"{item.get('wins')}勝 3着内{item.get('top3')}回"
        )
    return " / ".join(pieces) if pieces else "履歴集計なし"


def render(note: dict) -> str:
    race = note["race"]
    lines = [
        (
            f"# RaceNote v1 — {race['date']} "
            f"{race['venue']}{race['race_no']}R "
            f"{race.get('race_name') or ''}"
        ).rstrip(),
        "",
        (
            f"- 条件: {race.get('surface')}{race.get('distance_m')}m / "
            f"{race.get('class')} / {_dash(race.get('grade'))}"
        ),
        (
            f"- コース: {_dash(race.get('turn'))} / "
            f"{_dash(race.get('course_layout'))} / "
            f"{_dash(race.get('field_size'))}頭"
        ),
        (
            "- 情報境界: "
            f"結果={note['metadata']['result_visibility']} / "
            f"現行市場={note['metadata']['market_visibility']}"
        ),
        "",
        "## Trend context",
        "",
    ]

    for key, label in (
        ("named_race", "Named"),
        ("local_context", "Local"),
        ("base_context", "Base"),
    ):
        item = note["trend_context"][key]
        scope = item.get("scope") or {}
        sample = item.get("sample") or {}
        if key == "named_race":
            title = f"Named Race Trend — {race.get('race_name') or '名称なし'}"
        elif key == "local_context":
            title = "Local Trend"
        else:
            title = "Base Trend"

        lines.extend([
            f"### {title}",
            "",
            f"- Status: {item.get('status')}",
            f"- Scope: {_scope_summary(scope)}",
            f"- Period: {_dash(sample.get('period') or scope.get('period'))}",
        ])
        sample_bits = []
        if sample.get("starts") is not None:
            sample_bits.append(f"{sample.get('starts')} starts")
        if sample.get("races") is not None:
            sample_bits.append(f"{sample.get('races')} races")
        if sample.get("editions") is not None:
            sample_bits.append(f"{sample.get('editions')} editions")
        if sample_bits:
            lines.append("- Sample: " + " / ".join(sample_bits))
        if item.get("selected_level"):
            lines.append(f"- Selected: {item.get('selected_level')}")
        fallbacks = []
        for fallback in item.get("fallback_levels") or []:
            fs = fallback.get("sample") or {}
            fallbacks.append(
                f"{fallback.get('level_id')} "
                f"({fs.get('starts')} starts / {fs.get('races')} races)"
            )
        if fallbacks:
            lines.append("- Levels: " + " → ".join(fallbacks))
        for limitation in item.get("limitations") or []:
            lines.append(f"- Limitation: {limitation}")

        dimensions = item.get("dimensions") or {}
        for axis, dimension in dimensions.items():
            rows = (dimension or {}).get("rows") or []
            if not rows:
                continue
            lines.extend([
                "",
                f"#### {label} — {(dimension or {}).get('label') or axis}",
                "",
                "| 条件 | 成績・回収率 | 勝率 | 3着内率 | n |",
                "|---|---:|---:|---:|---:|",
            ])
            for row in rows:
                record = (row.get("finish_record") or {}).get("compact") or "—"
                win_rate = _dash(row.get("win_rate"))
                top3_rate = _dash(row.get("top3_rate"))
                win_roi = _dash(row.get("win_roi"))
                place_roi = _dash(row.get("place_roi"))
                compact = f"{record} / 単回{win_roi}% / 複回{place_roi}%"
                lines.append(
                    f"| {_dash(row.get('item'))} | {compact} | "
                    f"{win_rate}% | {top3_rate}% | {row.get('starts')} |"
                )

    lines.extend(["", "## Runners", ""])

    for horse in note["runners"]:
        identity = horse["identity"]
        current = horse["current_entry"]
        condition = current.get("condition_facts") or {}
        training = current.get("training_facts") or {}

        lines.extend(
            [
                f"### {horse['horse_no']} {horse['horse_name']}",
                (
                    f"- 枠: {_dash(identity.get('frame_no'))} / "
                    f"騎手: {_dash(identity.get('jockey'))} / "
                    f"斤量: {_dash(current.get('assigned_weight_kg'))}kg / "
                    f"厩舎: {_dash(identity.get('trainer'))}"
                ),
                (
                    f"- 状態: 改善={_dash(condition.get('improvement'))} / "
                    f"間隔={_dash(condition.get('rotation_interval'))} / "
                    f"調教矢印={_dash(training.get('jrdb_training_arrow'))}"
                ),
                f"- 条件別履歴: {_history_summary(horse)}",
            ]
        )

        traits = condition.get("horse_traits") or []
        if traits:
            lines.append("- 特性: " + " / ".join(map(str, traits)))

        lines.extend(
            [
                "",
                "| 日付 | 会場 | レース | 格 | 距離 | 着 | IDM | 騎手 |",
                "|---|---|---|---|---:|---:|---:|---|",
            ]
        )
        for run in horse["recent_runs"]:
            grade = run.get("grade") or run.get("class") or "—"
            lines.append(
                f"| {_dash(run.get('date'))} "
                f"| {_dash(run.get('venue'))} "
                f"| {_dash(run.get('race_name'))} "
                f"| {grade} "
                f"| {_dash(run.get('distance_m'))} "
                f"| {_dash(run.get('finish'))} "
                f"| {_dash(run.get('ability_value'))} "
                f"| {_dash(run.get('jockey'))} |"
            )

        repeated = (horse.get("racereview") or {}).get(
            "repeated_patterns"
        ) or []
        if repeated:
            lines.append(
                "- RaceReview反復観測: "
                + ", ".join(
                    f"{item.get('tag')}×{item.get('count')}"
                    for item in repeated[:8]
                )
            )

        if horse.get("data_gaps"):
            lines.append(
                "- Data gaps: " + ", ".join(horse["data_gaps"])
            )
        lines.append("")

    lines.extend(["## Coverage", ""])
    for limitation in note["coverage"].get("limitations") or []:
        lines.append(f"- {limitation}")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    note = json.loads(args.input.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(note), encoding="utf-8")
    print(str(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
