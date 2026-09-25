#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build result-blind semantic Pairwise research packets.

This module does not rank horses and does not read results, odds, current JRDB
consensus, Training Edge, or value signals.  It expands the compressed
DayRehearsal-v0.1 comparison back into content-level evidence so the next
authoring layer can compare meaning rather than coarse state labels.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping

PACKET_VERSION = "RaceNote-Semantic-Pairwise-Research-v0.2"

SAMPLE_BAND_ORDER = {
    "none": 0,
    "small": 1,
    "moderate": 2,
    "sufficient": 3,
}


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}


def _list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return []


def _number(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _horse_index(general: Mapping[str, object]) -> dict[int, Mapping[str, object]]:
    output: dict[int, Mapping[str, object]] = {}
    for raw in _list(general.get("horses")):
        horse = _mapping(raw)
        output[int(horse["horse_no"])] = horse
    return output


def _trend_profile(horse: Mapping[str, object]) -> dict[str, object]:
    lanes = _mapping(horse.get("evidence_lanes"))
    lane = _mapping(lanes.get("data_trend"))
    history = _mapping(lane.get("horse_history"))
    interpretation = _mapping(horse.get("prediction_interpretation"))
    trend_read = _mapping(interpretation.get("data_trend"))

    signals: list[dict[str, object]] = []
    for raw in _list(history.get("observations")):
        item = _mapping(raw)
        delta = _mapping(item.get("delta_pp"))
        condition = _mapping(item.get("condition"))
        signals.append(
            {
                "code": _text(item.get("code")),
                "label": _text(item.get("label")),
                "redundancy_group_id": _text(item.get("redundancy_group_id")),
                "direction": _text(item.get("direction")).upper(),
                "sample_size_band": _text(item.get("sample_size_band")).lower(),
                "starts": condition.get("starts"),
                "win_delta_pp": _number(delta.get("win_rate")),
                "top3_delta_pp": _number(delta.get("top3_rate")),
            }
        )

    directional = [
        item for item in signals
        if item["direction"] in {"SUPPORTIVE", "OPPOSED"}
    ]

    win_support = sorted(
        [
            item for item in directional
            if item["direction"] == "SUPPORTIVE"
            and item["win_delta_pp"] is not None
            and float(item["win_delta_pp"]) > 0
        ],
        key=lambda item: (
            SAMPLE_BAND_ORDER.get(str(item["sample_size_band"]), 0),
            float(item["win_delta_pp"]),
        ),
        reverse=True,
    )
    top3_support = sorted(
        [
            item for item in directional
            if item["direction"] == "SUPPORTIVE"
            and item["top3_delta_pp"] is not None
            and float(item["top3_delta_pp"]) > 0
        ],
        key=lambda item: (
            SAMPLE_BAND_ORDER.get(str(item["sample_size_band"]), 0),
            float(item["top3_delta_pp"]),
        ),
        reverse=True,
    )

    return {
        "coarse_state": _text(trend_read.get("state")).upper(),
        "best_directional_sample_band": _text(
            trend_read.get("best_directional_sample_band")
        ).lower(),
        "small_sample_only": bool(trend_read.get("small_sample_only", False)),
        "signals": signals,
        "best_win_upside_signal": win_support[0] if win_support else None,
        "best_top3_stability_signal": (
            top3_support[0] if top3_support else None
        ),
    }


def _review_profile(horse: Mapping[str, object]) -> dict[str, object]:
    lanes = _mapping(horse.get("evidence_lanes"))
    lane = _mapping(lanes.get("racereview"))
    interpretation = _mapping(horse.get("prediction_interpretation"))
    review_read = _mapping(interpretation.get("racereview"))
    transfer = _mapping(review_read.get("transferability"))

    def codes(field: str) -> list[str]:
        output: list[str] = []
        for raw in _list(lane.get(field)):
            item = _mapping(raw)
            code = _text(item.get("code"))
            if code and code not in output:
                output.append(code)
        return output

    return {
        "coarse_state": _text(review_read.get("state")).upper(),
        "hidden_strength_status": _text(
            review_read.get("hidden_strength_status")
        ).upper(),
        "fragile_form_status": _text(
            review_read.get("fragile_form_status")
        ).upper(),
        "contradiction_status": _text(
            review_read.get("contradiction_status")
        ).upper(),
        "repeatability_codes": [
            _text(value)
            for value in _list(review_read.get("repeatability_codes"))
            if _text(value)
        ],
        "transferability": {
            "state": _text(transfer.get("state")).upper(),
            "selected_source_run_count": transfer.get("selected_source_run_count"),
            "exact_surface_distance_count": transfer.get(
                "exact_surface_distance_count"
            ),
            "partial_exact_match_count": transfer.get(
                "partial_exact_match_count"
            ),
        },
        "primary_positive_codes": codes("primary_positive"),
        "supporting_positive_codes": codes("supporting_positive"),
        "concern_codes": codes("concerns"),
        "mixed_context_codes": codes("mixed_context"),
    }


def _ability_profile(horse: Mapping[str, object]) -> dict[str, object]:
    interpretation = _mapping(horse.get("prediction_interpretation"))
    ability = _mapping(interpretation.get("ability_anchor"))
    profile = _mapping(ability.get("profile"))

    latest = _number(profile.get("latest"))
    typical = _number(profile.get("typical_median"))
    peak = _number(profile.get("peak"))
    minimum = _number(profile.get("minimum"))
    mad = _number(profile.get("mad"))

    latest_minus_typical = None
    if latest is not None and typical is not None:
        latest_minus_typical = latest - typical

    return {
        "typical": typical,
        "latest": latest,
        "peak": peak,
        "minimum": minimum,
        "mad": mad,
        "latest_minus_typical": latest_minus_typical,
        "role_notes": {
            "typical": "historical baseline",
            "latest": "current expression",
            "peak": "ceiling",
            "minimum": "downside",
            "mad": "dispersion/stability context",
        },
    }


def _structure_profile(horse: Mapping[str, object]) -> dict[str, object]:
    interpretation = _mapping(horse.get("prediction_interpretation"))
    structure = _mapping(interpretation.get("race_structure"))
    position = _mapping(structure.get("horse_historical_position"))
    return {
        "pace_pressure": _text(structure.get("pace_pressure")).upper(),
        "historical_position_tendency": _text(
            position.get("tendency")
        ).upper(),
        "position_variability_status": _text(
            position.get("variability_status")
        ).upper(),
        "position_confidence": _text(position.get("confidence")).upper(),
        "dominant_share": _number(position.get("dominant_share")),
    }


def _profile(horse: Mapping[str, object]) -> dict[str, object]:
    return {
        "horse_no": int(horse["horse_no"]),
        "horse_name": _text(horse.get("horse_name")),
        "trend": _trend_profile(horse),
        "racereview": _review_profile(horse),
        "ability": _ability_profile(horse),
        "race_structure": _structure_profile(horse),
    }


def _comparison_prompts(
    a: Mapping[str, object],
    b: Mapping[str, object],
) -> list[str]:
    return [
        (
            "DATA_TREND: coarse stateだけでなく、どの条件コードで、"
            "勝率上振れか3着内安定か、sample bandまで比較する。"
        ),
        (
            "RACEREVIEW: label順位ではなく、positive/concernの内容、"
            "repeatability、今回surface-distanceへのtransferabilityを比較する。"
        ),
        (
            "ABILITY: typical/latest/peak/MADを別概念として読み、"
            "今回どの役割を重視すべきかを説明する。"
        ),
        (
            "RACE_STRUCTURE: historical positionは今日の位置取り確定ではない。"
            "狭い展開依存か複数シナリオ対応かだけを確認する。"
        ),
        (
            "FINAL: 数値加算せず、どのEvidenceが今回の直接比較で"
            "最も判別力を持つかを明記して preferred horse を決める。"
        ),
    ]


def build_packet(
    general: Mapping[str, object],
    frozen_summary: Mapping[str, object],
) -> dict[str, object]:
    index = _horse_index(general)
    order = [int(value) for value in _list(frozen_summary.get("final_order"))]
    if not order:
        raise RuntimeError("frozen summary missing final_order")

    candidate_nos = order[: min(5, len(order))]
    profiles = {horse_no: _profile(index[horse_no]) for horse_no in candidate_nos}

    pairs: list[dict[str, object]] = []
    axis = candidate_nos[0]
    pair_keys: set[tuple[int, int]] = set()

    for challenger in candidate_nos[1:]:
        pair_keys.add((axis, challenger))
    for upper, lower in zip(candidate_nos, candidate_nos[1:]):
        pair_keys.add((upper, lower))

    for horse_a, horse_b in sorted(pair_keys):
        pairs.append(
            {
                "horse_a": horse_a,
                "horse_b": horse_b,
                "profile_a": profiles[horse_a],
                "profile_b": profiles[horse_b],
                "reading_prompts": _comparison_prompts(
                    profiles[horse_a],
                    profiles[horse_b],
                ),
                "research_policy": {
                    "no_numeric_score": True,
                    "coarse_state_is_not_final_relation": True,
                    "ability_typical_is_not_automatic_tiebreak": True,
                    "racereview_state_is_not_scalar_rating": True,
                    "result_visible": False,
                },
            }
        )

    return {
        "packet_version": PACKET_VERSION,
        "target": dict(_mapping(general.get("target"))),
        "baseline_profile": "DayRehearsal-v0.1",
        "baseline_final_order": order,
        "candidate_cluster": candidate_nos,
        "profiles": [profiles[horse_no] for horse_no in candidate_nos],
        "comparisons": pairs,
        "result_visibility_status": "HIDDEN",
    }


def run_day(
    prepared_root: Path,
    author_root: Path,
    output_root: Path,
) -> dict[str, object]:
    general_paths = sorted(prepared_root.rglob("general_evidence.json"))
    if not general_paths:
        raise RuntimeError("no general_evidence.json found")

    rows: list[dict[str, object]] = []
    for general_path in general_paths:
        general = json.loads(general_path.read_text(encoding="utf-8"))
        target = _mapping(general.get("target"))
        venue = _text(target.get("venue"))
        race_no = int(target["race_no"])
        author_dir = author_root / f"{venue}_{race_no:02d}R"
        frozen_path = author_dir / "forecast_frozen.json"
        if not frozen_path.is_file():
            raise RuntimeError(f"missing frozen forecast: {frozen_path}")
        frozen = json.loads(frozen_path.read_text(encoding="utf-8"))

        packet = build_packet(general, frozen)
        out_dir = output_root / f"{venue}_{race_no:02d}R"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "semantic_pairwise_packet_v0_2.json").write_text(
            json.dumps(packet, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        rows.append(
            {
                "target": dict(target),
                "candidate_cluster": packet["candidate_cluster"],
                "comparison_count": len(packet["comparisons"]),
            }
        )

    summary = {
        "status": "PASS",
        "packet_version": PACKET_VERSION,
        "race_count": len(rows),
        "result_visibility_status": "HIDDEN",
        "races": rows,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "semantic_pairwise_day_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared-root", type=Path, required=True)
    parser.add_argument("--author-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    summary = run_day(
        args.prepared_root,
        args.author_root,
        args.output_root,
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
