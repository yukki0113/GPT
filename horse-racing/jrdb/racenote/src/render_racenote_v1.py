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
            f"{race.get('field_size')}頭"
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
        scope = ", ".join(
            f"{name}={value}"
            for name, value in (item.get("scope") or {}).items()
            if value is not None and value != ""
        )
        lines.append(
            f"- **{label}**: {item.get('status')} — "
            f"{scope or 'scopeなし'}"
        )
        sample = item.get("sample") or {}
        if sample.get("starts") is not None:
            sample_bits = [f"starts={sample.get('starts')}"]
            if sample.get("races") is not None:
                sample_bits.append(f"races={sample.get('races')}")
            if sample.get("editions") is not None:
                sample_bits.append(f"editions={sample.get('editions')}")
            if sample.get("period"):
                sample_bits.append(f"period={sample.get('period')}")
            lines.append("  - sample: " + " / ".join(sample_bits))
        if item.get("selected_level"):
            lines.append(f"  - selected_level: {item.get('selected_level')}")
        for fallback in item.get("fallback_levels") or []:
            fs = fallback.get("sample") or {}
            lines.append(
                f"  - fallback {fallback.get('level_id')}: "
                f"starts={fs.get('starts')} / races={fs.get('races')}"
            )
        for limitation in item.get("limitations") or []:
            lines.append(f"  - limitation: {limitation}")

        dimensions = item.get("dimensions") or {}
        for axis, dimension in dimensions.items():
            rows = (dimension or {}).get("rows") or []
            if not rows:
                continue
            lines.extend([
                "",
                f"### {label} — {(dimension or {}).get('label') or axis}",
                "",
                "| 条件 | 成績 | 勝率 | 3着内率 | 単回 | 複回 | n |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ])
            for row in rows:
                record = (row.get("finish_record") or {}).get("compact") or "—"
                win_rate = _dash(row.get("win_rate"))
                top3_rate = _dash(row.get("top3_rate"))
                win_roi = _dash(row.get("win_roi"))
                place_roi = _dash(row.get("place_roi"))
                lines.append(
                    f"| {_dash(row.get('item'))} | {record} | "
                    f"{win_rate}% | {top3_rate}% | "
                    f"{win_roi}% | {place_roi}% | {row.get('starts')} |"
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
