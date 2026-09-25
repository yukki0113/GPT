#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Blind semantic author research for RaceNote Pairwise v0.2.

The input is a result-hidden semantic comparison packet.  The author uses
qualitative dominance rules only.  It never sums evidence into a numeric score.
Unresolved or conflicting comparisons preserve the baseline order.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping

AUTHOR_VERSION = "RaceNote-Semantic-Author-Research-v0.3"

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


def _cmp_number(a: float | None, b: float | None, higher_better: bool = True) -> str:
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


def _signal_strength(signal: object) -> tuple[int, int, float, float] | None:
    item = _mapping(signal)
    if not item:
        return None
    code = _text(item.get("code"))
    direct = 1 if code in DIRECT_CODES else 0
    band = BAND_ORDER.get(_text(item.get("sample_size_band")).lower(), 0)
    win_delta = _number(item.get("win_delta_pp")) or 0.0
    top3_delta = _number(item.get("top3_delta_pp")) or 0.0
    return direct, band, win_delta, top3_delta


def _compare_signal(a: object, b: object, metric: str) -> str:
    sa = _signal_strength(a)
    sb = _signal_strength(b)
    if sa is None and sb is None:
        return "EVEN"
    if sa is None:
        return "B"
    if sb is None:
        return "A"

    # Prefer target-direct evidence before broad range evidence.
    if sa[0] != sb[0]:
        return "A" if sa[0] > sb[0] else "B"

    # Sample reliability is compared before delta magnitude.
    if sa[1] != sb[1]:
        return "A" if sa[1] > sb[1] else "B"

    index = 2 if metric == "WIN" else 3
    if sa[index] == sb[index]:
        return "EVEN"
    return "A" if sa[index] > sb[index] else "B"


def _combine_relations(values: list[str]) -> str:
    directional = {value for value in values if value in {"A", "B"}}
    if directional == {"A"}:
        return "A"
    if directional == {"B"}:
        return "B"
    if directional == {"A", "B"}:
        return "MIXED"
    return "EVEN"


def _trend_relation(a: Mapping[str, object], b: Mapping[str, object]) -> dict[str, object]:
    ta = _mapping(a.get("trend"))
    tb = _mapping(b.get("trend"))
    win = _compare_signal(
        ta.get("best_win_upside_signal"),
        tb.get("best_win_upside_signal"),
        "WIN",
    )
    top3 = _compare_signal(
        ta.get("best_top3_stability_signal"),
        tb.get("best_top3_stability_signal"),
        "TOP3",
    )
    relation = _combine_relations([win, top3])
    return {
        "relation": relation,
        "win_upside_relation": win,
        "top3_stability_relation": top3,
        "summary": (
            "Trend content compares target-directness, sample band, then "
            "win/top3 delta without collapsing them into one score."
        ),
    }


def _transfer_level(review: Mapping[str, object]) -> tuple[int, int, int]:
    transfer = _mapping(review.get("transferability"))
    exact = int(transfer.get("exact_surface_distance_count") or 0)
    partial = int(transfer.get("partial_exact_match_count") or 0)
    runs = int(transfer.get("selected_source_run_count") or 0)
    return exact, partial, runs


def _review_side(profile: Mapping[str, object]) -> dict[str, object]:
    review = _mapping(profile.get("racereview"))
    positive_count = (
        len(_list(review.get("primary_positive_codes")))
        + len(_list(review.get("supporting_positive_codes")))
    )
    concern_count = len(_list(review.get("concern_codes")))
    hidden = _text(review.get("hidden_strength_status")).upper() == "CANDIDATE"
    fragile = _text(review.get("fragile_form_status")).upper() == "CANDIDATE"
    contradiction = _text(review.get("contradiction_status")).upper() == "MIXED"
    return {
        "positive_count": positive_count,
        "concern_count": concern_count,
        "hidden": hidden,
        "fragile": fragile,
        "contradiction": contradiction,
        "transfer": _transfer_level(review),
    }


def _review_relation(a: Mapping[str, object], b: Mapping[str, object]) -> dict[str, object]:
    ra = _review_side(a)
    rb = _review_side(b)

    # A clear positive edge requires transferable positive evidence and no
    # clearly worse fragility/contradiction burden.
    a_positive = (
        ra["positive_count"] > 0
        and ra["transfer"] > rb["transfer"]
        and not (ra["fragile"] and not rb["fragile"])
    )
    b_positive = (
        rb["positive_count"] > 0
        and rb["transfer"] > ra["transfer"]
        and not (rb["fragile"] and not ra["fragile"])
    )

    if a_positive and not b_positive:
        relation = "A"
    elif b_positive and not a_positive:
        relation = "B"
    elif ra["hidden"] and not rb["hidden"] and not ra["contradiction"]:
        relation = "A"
    elif rb["hidden"] and not ra["hidden"] and not rb["contradiction"]:
        relation = "B"
    elif ra["fragile"] and not rb["fragile"] and not rb["contradiction"]:
        relation = "B"
    elif rb["fragile"] and not ra["fragile"] and not ra["contradiction"]:
        relation = "A"
    else:
        relation = "EVEN"

    return {
        "relation": relation,
        "profile_a": ra,
        "profile_b": rb,
        "summary": (
            "RaceReview compares transferable positive content, fragility, "
            "hidden strength, and contradiction; coarse state is not ranked."
        ),
    }


def _ability_relation(a: Mapping[str, object], b: Mapping[str, object]) -> dict[str, object]:
    aa = _mapping(a.get("ability"))
    ab = _mapping(b.get("ability"))

    dimensions = {
        "typical": _cmp_number(_number(aa.get("typical")), _number(ab.get("typical"))),
        "latest": _cmp_number(_number(aa.get("latest")), _number(ab.get("latest"))),
        "peak": _cmp_number(_number(aa.get("peak")), _number(ab.get("peak"))),
        "stability": _cmp_number(_number(aa.get("mad")), _number(ab.get("mad")), False),
    }
    relation = _combine_relations(list(dimensions.values()))
    return {
        "relation": relation,
        "dimensions": dimensions,
        "summary": (
            "Ability uses Pareto-style dominance across baseline, current "
            "expression, ceiling, and dispersion. No fixed typical-first tuple."
        ),
    }


def judge_pair(a: Mapping[str, object], b: Mapping[str, object]) -> dict[str, object]:
    trend = _trend_relation(a, b)
    review = _review_relation(a, b)
    ability = _ability_relation(a, b)

    trend_rel = _text(trend.get("relation"))
    review_rel = _text(review.get("relation"))
    ability_rel = _text(ability.get("relation"))

    # Trend remains the first lane, but only content-level direction is
    # protected. RaceReview alone may not dethrone the current order in v0.3.
    # It must be corroborated by Ability or agree with Trend. This keeps
    # retrospective review context from becoming an automatic scalar rating.
    if trend_rel in {"A", "B"} and review_rel in {trend_rel, "EVEN"}:
        final = trend_rel
        decisive = "DATA_TREND_CONTENT"
    elif trend_rel == review_rel and trend_rel in {"A", "B"}:
        final = trend_rel
        decisive = "TREND_REVIEW_AGREEMENT"
    elif (
        trend_rel in {"EVEN", "MIXED"}
        and review_rel in {"A", "B"}
        and ability_rel == review_rel
    ):
        final = review_rel
        decisive = "REVIEW_ABILITY_CORROBORATION"
    elif (
        trend_rel in {"EVEN", "MIXED"}
        and review_rel in {"EVEN", "MIXED"}
        and ability_rel in {"A", "B"}
    ):
        final = ability_rel
        decisive = "ABILITY_DOMINANCE"
    else:
        final = "EVEN"
        decisive = "UNRESOLVED_OR_CONFLICT"

    return {
        "relation": final,
        "decisive_basis": decisive,
        "trend": trend,
        "racereview": review,
        "ability": ability,
    }


def _reorder_cluster(packet: Mapping[str, object]) -> dict[str, object]:
    profiles: dict[int, Mapping[str, object]] = {}
    for raw in _list(packet.get("profiles")):
        profile = _mapping(raw)
        profiles[int(profile["horse_no"])] = profile

    baseline = [int(value) for value in _list(packet.get("candidate_cluster"))]
    order: list[int] = []
    judgments: list[dict[str, object]] = []

    # Stable insertion: a challenger moves upward only when the semantic
    # comparison explicitly prefers it.  EVEN/conflict preserves baseline.
    for horse_no in baseline:
        order.append(horse_no)
        index = len(order) - 1
        while index > 0:
            upper_no = order[index - 1]
            lower_no = order[index]
            judgment = judge_pair(profiles[upper_no], profiles[lower_no])
            judgments.append(
                {
                    "horse_a": upper_no,
                    "horse_b": lower_no,
                    **judgment,
                }
            )
            if judgment["relation"] == "B":
                order[index - 1], order[index] = order[index], order[index - 1]
                index -= 1
                continue
            break

    return {
        "baseline_candidate_cluster": baseline,
        "semantic_candidate_order": order,
        "axis_changed": bool(order and baseline and order[0] != baseline[0]),
        "judgments": judgments,
    }


def run_day(input_root: Path, output_root: Path) -> dict[str, object]:
    packet_paths = sorted(input_root.rglob("semantic_pairwise_packet_v0_2.json"))
    if not packet_paths:
        raise RuntimeError("no semantic pairwise packets found")

    rows: list[dict[str, object]] = []
    for path in packet_paths:
        packet = json.loads(path.read_text(encoding="utf-8"))
        if _text(packet.get("result_visibility_status")).upper() != "HIDDEN":
            raise RuntimeError("research author requires result-hidden packet")
        result = _reorder_cluster(packet)
        target = dict(_mapping(packet.get("target")))
        venue = _text(target.get("venue"))
        race_no = int(target["race_no"])
        out_dir = output_root / f"{venue}_{race_no:02d}R"
        out_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "author_version": AUTHOR_VERSION,
            "packet_version": packet.get("packet_version"),
            "target": target,
            "result_visibility_status": "HIDDEN",
            **result,
        }
        (out_dir / "semantic_author_v0_2.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        rows.append(
            {
                "target": target,
                "baseline_candidate_cluster": result["baseline_candidate_cluster"],
                "semantic_candidate_order": result["semantic_candidate_order"],
                "axis_changed": result["axis_changed"],
            }
        )

    summary = {
        "status": "PASS",
        "author_version": AUTHOR_VERSION,
        "race_count": len(rows),
        "axis_changed_count": sum(1 for row in rows if row["axis_changed"]),
        "result_visibility_status": "HIDDEN",
        "races": rows,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "semantic_author_day_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    summary = run_day(args.input_root, args.output_root)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
