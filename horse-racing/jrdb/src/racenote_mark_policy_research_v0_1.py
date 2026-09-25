#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Result-blind Mark Policy research v0.1 for RaceNote.

Roles are intentionally separate from full-order ranking:
- ◎ Forecast Best
- ○ Stability Partner
- ▲ Upside Partner

The policy always emits exactly one ◎, one ○, and one ▲ when the field has
at least three runners. It does not use current odds, popularity, results,
current JRDB consensus, Training Edge, or value signals.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping

POLICY_VERSION = "RaceNote-Mark-Policy-Research-v0.1"

BAND_ORDER = {
    "": 0,
    "none": 0,
    "small": 1,
    "moderate": 2,
    "sufficient": 3,
}

DIRECT_CODES = {"SAME_DISTANCE", "SAME_SURFACE", "SAME_VENUE"}


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


def _signal_tuple(signal: object, metric: str) -> tuple[int, int, float] | None:
    item = _mapping(signal)
    if not item:
        return None
    code = _text(item.get("code"))
    direct = 1 if code in DIRECT_CODES else 0
    band = BAND_ORDER.get(_text(item.get("sample_size_band")).lower(), 0)
    key = "win_delta_pp" if metric == "WIN" else "top3_delta_pp"
    delta = _number(item.get(key))
    if delta is None:
        delta = 0.0
    return direct, band, delta


def _compare_tuple(
    a: tuple[int, int, float] | None,
    b: tuple[int, int, float] | None,
) -> str:
    if a is None and b is None:
        return "EVEN"
    if a is None:
        return "B"
    if b is None:
        return "A"
    if a == b:
        return "EVEN"
    return "A" if a > b else "B"


def _compare_number(
    a: float | None,
    b: float | None,
    *,
    higher_better: bool,
) -> str:
    if a is None and b is None:
        return "EVEN"
    if a is None:
        return "B"
    if b is None:
        return "A"
    if a == b:
        return "EVEN"
    if higher_better:
        return "A" if a > b else "B"
    return "A" if a < b else "B"


def _scenario_index(scenario: Mapping[str, object]) -> dict[int, Mapping[str, object]]:
    output: dict[int, Mapping[str, object]] = {}
    for raw in _list(scenario.get("horse_sensitivity")):
        item = _mapping(raw)
        output[int(item["horse_no"])] = item
    return output


def _review_flags(profile: Mapping[str, object]) -> dict[str, object]:
    review = _mapping(profile.get("racereview"))
    transfer = _mapping(review.get("transferability"))
    return {
        "hidden": _text(review.get("hidden_strength_status")).upper() == "CANDIDATE",
        "fragile": _text(review.get("fragile_form_status")).upper() == "CANDIDATE",
        "contradiction": _text(review.get("contradiction_status")).upper() == "MIXED",
        "concern_count": len(_list(review.get("concern_codes"))),
        "positive_count": (
            len(_list(review.get("primary_positive_codes")))
            + len(_list(review.get("supporting_positive_codes")))
        ),
        "exact_transfer": int(transfer.get("exact_surface_distance_count") or 0),
        "partial_transfer": int(transfer.get("partial_exact_match_count") or 0),
    }


def _scenario_stability(item: Mapping[str, object]) -> tuple[int, int]:
    pairwise_rank = int(item.get("pairwise_rank") or 999)
    worst_rank = int(item.get("worst_rank") or pairwise_rank)
    rank_span = int(item.get("rank_span") or 0)
    adverse_drop = max(0, worst_rank - pairwise_rank)
    return adverse_drop, rank_span


def _scenario_upside(item: Mapping[str, object]) -> tuple[int, int]:
    pairwise_rank = int(item.get("pairwise_rank") or 999)
    best_rank = int(item.get("best_rank") or pairwise_rank)
    upward_move = max(0, pairwise_rank - best_rank)
    rank_span = int(item.get("rank_span") or 0)
    return upward_move, rank_span


def compare_stability(
    a: Mapping[str, object],
    b: Mapping[str, object],
    scenario_a: Mapping[str, object],
    scenario_b: Mapping[str, object],
) -> dict[str, object]:
    trend_a = _mapping(a.get("trend"))
    trend_b = _mapping(b.get("trend"))
    top3 = _compare_tuple(
        _signal_tuple(trend_a.get("best_top3_stability_signal"), "TOP3"),
        _signal_tuple(trend_b.get("best_top3_stability_signal"), "TOP3"),
    )
    if top3 in {"A", "B"}:
        return {
            "relation": top3,
            "basis": "TOP3_TREND",
            "summary": "Target-relevant top3 Trend is the primary stability evidence.",
        }

    sa = _scenario_stability(scenario_a)
    sb = _scenario_stability(scenario_b)
    if sa != sb:
        relation = "A" if sa < sb else "B"
        return {
            "relation": relation,
            "basis": "SCENARIO_DOWNSIDE",
            "summary": "Prefer the runner with less adverse scenario movement.",
        }

    ability_a = _mapping(a.get("ability"))
    ability_b = _mapping(b.get("ability"))

    mad = _compare_number(
        _number(ability_a.get("mad")),
        _number(ability_b.get("mad")),
        higher_better=False,
    )
    if mad in {"A", "B"}:
        return {
            "relation": mad,
            "basis": "ABILITY_STABILITY",
            "summary": "Lower Ability dispersion is used as stability context.",
        }

    minimum = _compare_number(
        _number(ability_a.get("minimum")),
        _number(ability_b.get("minimum")),
        higher_better=True,
    )
    if minimum in {"A", "B"}:
        return {
            "relation": minimum,
            "basis": "ABILITY_DOWNSIDE",
            "summary": "Higher observed Ability floor is preferred for ○.",
        }

    ra = _review_flags(a)
    rb = _review_flags(b)
    burden_a = (
        1 if ra["fragile"] else 0,
        1 if ra["contradiction"] else 0,
        int(ra["concern_count"]),
    )
    burden_b = (
        1 if rb["fragile"] else 0,
        1 if rb["contradiction"] else 0,
        int(rb["concern_count"]),
    )
    if burden_a != burden_b:
        return {
            "relation": "A" if burden_a < burden_b else "B",
            "basis": "RACEREVIEW_DOWNSIDE",
            "summary": "Lower RaceReview fragility/contradiction burden is preferred.",
        }

    typical = _compare_number(
        _number(ability_a.get("typical")),
        _number(ability_b.get("typical")),
        higher_better=True,
    )
    return {
        "relation": typical,
        "basis": "ABILITY_BASELINE" if typical != "EVEN" else "BASELINE_ORDER",
        "summary": "Historical baseline is the final ○ tie-break only.",
    }


def compare_upside(
    a: Mapping[str, object],
    b: Mapping[str, object],
    scenario_a: Mapping[str, object],
    scenario_b: Mapping[str, object],
) -> dict[str, object]:
    trend_a = _mapping(a.get("trend"))
    trend_b = _mapping(b.get("trend"))
    win = _compare_tuple(
        _signal_tuple(trend_a.get("best_win_upside_signal"), "WIN"),
        _signal_tuple(trend_b.get("best_win_upside_signal"), "WIN"),
    )
    if win in {"A", "B"}:
        return {
            "relation": win,
            "basis": "WIN_TREND",
            "summary": "Target-relevant win-rate upside is the primary ▲ evidence.",
        }

    ra = _review_flags(a)
    rb = _review_flags(b)
    hidden_a = (
        1 if ra["hidden"] else 0,
        int(ra["exact_transfer"]),
        int(ra["partial_transfer"]),
        int(ra["positive_count"]),
    )
    hidden_b = (
        1 if rb["hidden"] else 0,
        int(rb["exact_transfer"]),
        int(rb["partial_transfer"]),
        int(rb["positive_count"]),
    )
    if hidden_a != hidden_b:
        return {
            "relation": "A" if hidden_a > hidden_b else "B",
            "basis": "RACEREVIEW_UPSIDE",
            "summary": "Transferable hidden-strength/positive review evidence supports ▲.",
        }

    aa = _mapping(a.get("ability"))
    ab = _mapping(b.get("ability"))
    improvement = _compare_number(
        _number(aa.get("latest_minus_typical")),
        _number(ab.get("latest_minus_typical")),
        higher_better=True,
    )
    if improvement in {"A", "B"}:
        return {
            "relation": improvement,
            "basis": "ABILITY_IMPROVEMENT",
            "summary": "Latest-versus-typical improvement is used as upside context.",
        }

    upside_a = _scenario_upside(scenario_a)
    upside_b = _scenario_upside(scenario_b)
    if upside_a != upside_b:
        return {
            "relation": "A" if upside_a > upside_b else "B",
            "basis": "SCENARIO_UPSIDE",
            "summary": "Potential upward scenario movement supports ▲.",
        }

    peak = _compare_number(
        _number(aa.get("peak")),
        _number(ab.get("peak")),
        higher_better=True,
    )
    return {
        "relation": peak,
        "basis": "ABILITY_CEILING" if peak != "EVEN" else "BASELINE_ORDER",
        "summary": "Ability ceiling is the final ▲ tie-break only.",
    }


def _select_role(
    candidates: list[int],
    profiles: Mapping[int, Mapping[str, object]],
    scenarios: Mapping[int, Mapping[str, object]],
    comparator,
) -> tuple[int, list[dict[str, object]]]:
    selected = candidates[0]
    audit: list[dict[str, object]] = []
    for challenger in candidates[1:]:
        judgment = comparator(
            profiles[selected],
            profiles[challenger],
            scenarios.get(selected, {}),
            scenarios.get(challenger, {}),
        )
        audit.append(
            {
                "current": selected,
                "challenger": challenger,
                **judgment,
            }
        )
        if judgment["relation"] == "B":
            selected = challenger
    return selected, audit


def build_marks(
    packet: Mapping[str, object],
    semantic_author: Mapping[str, object],
    scenario: Mapping[str, object],
) -> dict[str, object]:
    if _text(packet.get("result_visibility_status")).upper() != "HIDDEN":
        raise RuntimeError("packet result visibility must be HIDDEN")
    if _text(semantic_author.get("result_visibility_status")).upper() != "HIDDEN":
        raise RuntimeError("semantic author result visibility must be HIDDEN")

    profiles: dict[int, Mapping[str, object]] = {}
    for raw in _list(packet.get("profiles")):
        item = _mapping(raw)
        profiles[int(item["horse_no"])] = item

    order = [
        int(value)
        for value in _list(semantic_author.get("semantic_candidate_order"))
    ]
    if len(order) < 3:
        raise RuntimeError("mark policy requires at least three candidates")

    scenarios = _scenario_index(scenario)
    axis = order[0]
    remaining = order[1:]

    circle, circle_audit = _select_role(
        remaining,
        profiles,
        scenarios,
        compare_stability,
    )
    triangle_candidates = [
        horse_no for horse_no in remaining if horse_no != circle
    ]
    triangle, triangle_audit = _select_role(
        triangle_candidates,
        profiles,
        scenarios,
        compare_upside,
    )

    return {
        "policy_version": POLICY_VERSION,
        "target": dict(_mapping(packet.get("target"))),
        "result_visibility_status": "HIDDEN",
        "market_visibility_status": "HIDDEN",
        "marks": {
            "◎": axis,
            "○": circle,
            "▲": triangle,
        },
        "role_definition": {
            "◎": "Forecast Best",
            "○": "Stability Partner",
            "▲": "Upside Partner",
        },
        "candidate_order": order,
        "circle_audit": circle_audit,
        "triangle_audit": triangle_audit,
        "betting_diagnostics_contract": {
            "unit_yen": 100,
            "tickets": [
                "WIN_◎",
                "QUINELLA_◎-○",
                "QUINELLA_◎-▲",
                "QUINELLA_◎-○▲_2POINT",
                "QUINELLA_BOX_◎○▲_3POINT",
            ],
        },
    }


def run_day(
    packet_root: Path,
    semantic_root: Path,
    baseline_root: Path,
    output_root: Path,
) -> dict[str, object]:
    packet_paths = sorted(packet_root.rglob("semantic_pairwise_packet_v0_2.json"))
    if not packet_paths:
        raise RuntimeError("no semantic packets found")

    rows: list[dict[str, object]] = []
    for packet_path in packet_paths:
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        target = _mapping(packet.get("target"))
        venue = _text(target.get("venue"))
        race_no = int(target["race_no"])
        race_dir = f"{venue}_{race_no:02d}R"

        semantic_path = semantic_root / race_dir / "semantic_author_v0_2.json"
        scenario_path = baseline_root / race_dir / "scenario_audit.json"
        if not semantic_path.is_file():
            raise RuntimeError(f"missing semantic author: {semantic_path}")
        if not scenario_path.is_file():
            raise RuntimeError(f"missing scenario audit: {scenario_path}")

        semantic_author = json.loads(semantic_path.read_text(encoding="utf-8"))
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
        marks = build_marks(packet, semantic_author, scenario)

        out_dir = output_root / race_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "mark_policy_v0_1.json").write_text(
            json.dumps(marks, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        rows.append(
            {
                "target": dict(target),
                "marks": marks["marks"],
                "candidate_order": marks["candidate_order"],
            }
        )

    summary = {
        "status": "PASS",
        "policy_version": POLICY_VERSION,
        "race_count": len(rows),
        "result_visibility_status": "HIDDEN",
        "market_visibility_status": "HIDDEN",
        "races": rows,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "mark_policy_day_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet-root", type=Path, required=True)
    parser.add_argument("--semantic-root", type=Path, required=True)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    summary = run_day(
        args.packet_root,
        args.semantic_root,
        args.baseline_root,
        args.output_root,
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
