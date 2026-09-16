"""Deterministic pre-result Shadow overlay for ForwardTrial Ver0.2-alpha1.

This module intentionally reuses ForwardTrial_Ver0.1 axis/judgment parsing and
changes only the research layers approved on 2026-09-16:
- OpponentScore OS-alpha1 weights
- Q0 Pair-risk gate
- simplified 4-factor sales score
- product-volume allocation without CSV-only

It consumes only an official BOAT RACE racelist CSV. It does not read results,
odds, exhibition, or other post-freeze information. Control Ver0.1 artifacts
are not modified.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Mapping, Sequence

from forward_trial_predict import (
    CLASS_RANK,
    choose_axis_and_judgment,
    normalize,
    parse_boats,
    validate_input,
)

SHADOW_VERSION = "ForwardTrial_Ver0.2-alpha1"
CONTROL_VERSION = "ForwardTrial_Ver0.1"

OS_ALPHA1_WEIGHTS = {
    "全国勝率": 0.35,
    "当地勝率": 0.15,
    "平均ST": 0.05,
    "モーター2連率": 0.15,
    "今節平均着順": 0.15,
    "級別": 0.15,
}

SHADOW_COLUMNS = [
    "日付", "会場", "R", "ShadowVer", "ControlVer", "正式判定", "1着軸",
    "2着本線", "2着押さえ", "追加3着候補", "2着候補分離度",
    "2連単1点対象", "2連単1点", "軸警戒", "比較支持項目数", "全国勝率差",
    "Q0_PairRisk", "販売スコア", "Shadow順位", "掲載区分", "選別理由",
    "Shadow確定日時", "結果参照状態",
]


def opponent_scores_alpha1(boats: Mapping[int, Mapping[str, object]]) -> dict[int, float]:
    national = normalize({lane: boat["national"] for lane, boat in boats.items()})
    local = normalize({lane: boat["local"] for lane, boat in boats.items()})
    st = normalize({lane: boat["st"] for lane, boat in boats.items()}, False)
    motor = normalize({lane: boat["motor"] for lane, boat in boats.items()})
    form = normalize({lane: boat["form"] for lane, boat in boats.items()}, False)
    klass = normalize({lane: float(CLASS_RANK[boat["class"]]) for lane, boat in boats.items()})
    return {
        lane:
        OS_ALPHA1_WEIGHTS["全国勝率"] * national[lane]
        + OS_ALPHA1_WEIGHTS["当地勝率"] * local[lane]
        + OS_ALPHA1_WEIGHTS["平均ST"] * st[lane]
        + OS_ALPHA1_WEIGHTS["モーター2連率"] * motor[lane]
        + OS_ALPHA1_WEIGHTS["今節平均着順"] * form[lane]
        + OS_ALPHA1_WEIGHTS["級別"] * klass[lane]
        for lane in boats
    }


def pair_risk_q0(separation: float, warning: bool, support_count: int) -> bool:
    return separation < 0.08 and not warning and support_count != 4


def shadow_sales_score(
    *, national_gap: float | None, separation: float, inner: int, second_main: int
) -> int:
    score = 0
    if national_gap is not None and national_gap >= 0.50:
        score += 1
    if separation >= 0.08:
        score += 1
    if 2 <= inner <= 4:
        score += 1
    if inner == second_main:
        score += 1
    return score


def product_split(eligible_count: int) -> tuple[int, int, bool]:
    """Return paid, free, sellable-day for the approved product-volume rule."""
    if eligible_count <= 5:
        return 0, 0, False
    if eligible_count == 6:
        return 4, 2, True
    if eligible_count == 7:
        return 5, 2, True
    if eligible_count == 8:
        return 5, 3, True
    if eligible_count == 9:
        return 6, 3, True
    return 7, 3, True


def _national_gap(one: Mapping[str, object], strongest: Mapping[str, object]) -> float | None:
    a, b = one.get("national"), strongest.get("national")
    if a is None or b is None:
        return None
    return float(a) - float(b)


def generate_shadow(
    rows: Sequence[Mapping[str, str]], columns: Sequence[str], shadow_time: str
) -> dict[str, object]:
    target_date, venues, groups = validate_input(rows, columns)
    venue_order = {venue: index for index, venue in enumerate(venues)}
    output: list[dict[str, object]] = []

    for venue in venues:
        for race in range(1, 13):
            boats = parse_boats(groups[(venue, race)])
            axis, strongest, judgment, warning, flags = choose_axis_and_judgment(boats)
            axis_lane = int(axis["lane"])
            support_count = sum(flags.values())
            scores = opponent_scores_alpha1(boats)

            row: dict[str, object] = {
                "日付": target_date,
                "会場": venue,
                "R": race,
                "ShadowVer": SHADOW_VERSION,
                "ControlVer": CONTROL_VERSION,
                "正式判定": judgment,
                "1着軸": axis_lane if judgment != "C" else "",
                "2着本線": "",
                "2着押さえ": "",
                "追加3着候補": "",
                "2着候補分離度": "",
                "2連単1点対象": "対象外",
                "2連単1点": "",
                "軸警戒": "あり" if warning else "なし",
                "比較支持項目数": support_count,
                "全国勝率差": "",
                "Q0_PairRisk": "対象外",
                "販売スコア": "",
                "Shadow順位": "",
                "掲載区分": "対象外",
                "選別理由": "2連単1点対象外",
                "Shadow確定日時": shadow_time,
                "結果参照状態": "未参照",
                "_venue_order": venue_order[venue],
            }

            if judgment != "C":
                opponents = sorted(
                    (lane for lane in boats if lane != axis_lane),
                    key=lambda lane: (-scores[lane], lane),
                )
                first, second, third = opponents[:3]
                row["2着本線"] = first
                row["2着押さえ"] = second
                row["追加3着候補"] = third

                if judgment == "A" and axis_lane == 1:
                    separation = float(scores[second] - scores[third])
                    inner = min(first, second)
                    gap = _national_gap(boats[1], strongest)
                    q0 = pair_risk_q0(separation, warning, support_count)
                    sales_score = shadow_sales_score(
                        national_gap=gap,
                        separation=separation,
                        inner=inner,
                        second_main=first,
                    )
                    row.update({
                        "2着候補分離度": round(separation, 6),
                        "2連単1点対象": "対象",
                        "2連単1点": f"1→{inner}",
                        "全国勝率差": "" if gap is None else round(gap, 3),
                        "Q0_PairRisk": "Q0" if q0 else "通過",
                        "販売スコア": sales_score,
                        "掲載区分": "非掲載" if q0 else "選別待ち",
                        "選別理由": (
                            "Q0: 分離度<0.08 AND 軸警戒なし AND 比較支持項目数!=4"
                            if q0 else "Q0通過・日次商品構成待ち"
                        ),
                    })
            output.append(row)

    eligible = [
        row for row in output
        if row["2連単1点対象"] == "対象" and row["Q0_PairRisk"] == "通過"
    ]
    eligible.sort(
        key=lambda row: (
            -int(row["販売スコア"]),
            -float(row["2着候補分離度"]),
            int(row["_venue_order"]),
            int(row["R"]),
        )
    )

    paid_count, free_count, sellable = product_split(len(eligible))
    for rank, row in enumerate(eligible, start=1):
        row["Shadow順位"] = rank
        if not sellable:
            row["掲載区分"] = "販売見送り"
            row["選別理由"] = f"Q0通過だが掲載候補{len(eligible)}R<=5のため通常販売見送り"
        elif rank <= paid_count:
            row["掲載区分"] = "有料"
            row["選別理由"] = f"Q0通過・Shadow順位{rank}位・有料枠"
        elif rank <= paid_count + free_count:
            row["掲載区分"] = "無料"
            row["選別理由"] = f"Q0通過・Shadow順位{rank}位・無料枠"
        else:
            row["掲載区分"] = "非掲載"
            row["選別理由"] = f"Q0通過だが日次掲載上限外（Shadow順位{rank}位）"

    for row in output:
        row.pop("_venue_order", None)

    return {
        "date": target_date,
        "shadow_version": SHADOW_VERSION,
        "rows": output,
        "summary": {
            "target_count": sum(row["2連単1点対象"] == "対象" for row in output),
            "q0_count": sum(row["Q0_PairRisk"] == "Q0" for row in output),
            "eligible_count": len(eligible),
            "paid_count": sum(row["掲載区分"] == "有料" for row in output),
            "free_count": sum(row["掲載区分"] == "無料" for row in output),
            "nonpublished_count": sum(row["掲載区分"] == "非掲載" for row in output),
            "sellable": sellable,
        },
    }


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def write_shadow_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SHADOW_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--shadow-time", required=True)
    args = parser.parse_args()

    rows, columns = read_csv(args.input)
    result = generate_shadow(rows, columns, args.shadow_time)
    write_shadow_csv(args.output, result["rows"])
    print(result["summary"])


if __name__ == "__main__":
    main()
