#!/usr/bin/env python3
"""Audit real-operation JRDB Edge v0.2 match density and conflict structure.

Diagnostic only: this module does not change Registry status, serving
eligibility, matcher semantics, thresholds, or presentation.
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
import statistics
from pathlib import Path
from typing import Any, Iterable, Mapping

VERSION = "0.1.0"
MEANINGFUL = {"POSITIVE", "NEGATIVE"}
SEMANTIC_TEMPLATE_PAIRS = (
    ("COURSE_FRAME_V1", "COURSE_EXACT_FRAME_V2", "exact_frame_refines_frame_zone"),
    ("SIRE_SURFACE_DISTANCE_V1", "SIRE_VENUE_SURFACE_DISTANCE_V2", "venue_refines_surface_distance"),
    ("SIRE_SURFACE_DISTANCE_V1", "SIRE_TURN_DISTANCE_V1", "shared_sire_distance_siblings"),
    ("SIRE_DISTANCE_CHANGE_V1", "SIRE_SURFACE_TRANSITION_V1", "transition_siblings"),
)


class OperationalAuditError(RuntimeError):
    pass


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        row = json.loads(raw)
        if not isinstance(row, dict) or not isinstance(row.get("edge_matches"), list):
            raise OperationalAuditError(f"{path}:{line_no}: invalid matcher row")
        rows.append(row)
    return rows


def _evidence(match: Mapping[str, Any]) -> Mapping[str, Any]:
    value = match.get("evidence")
    return value if isinstance(value, Mapping) else {}


def _signal(match: Mapping[str, Any], channel: str) -> str:
    return str(_evidence(match).get(f"{channel}_signal") or "UNASSESSED").upper()


def _level(match: Mapping[str, Any], channel: str) -> str:
    return str(match.get(f"{channel}_evidence_level") or "NONE").upper()


def _template(match: Mapping[str, Any]) -> str:
    return str(_evidence(match).get("template_id") or "UNKNOWN")


def _family(match: Mapping[str, Any]) -> str:
    return str(_evidence(match).get("family") or "UNKNOWN")


def _group(match: Mapping[str, Any]) -> str:
    return str(match.get("redundancy_group_id") or match.get("edge_id") or "UNKNOWN")


def _role(match: Mapping[str, Any], channel: str) -> str:
    presentation = match.get("presentation")
    if not isinstance(presentation, Mapping):
        return "LEGACY"
    item = presentation.get(channel)
    if not isinstance(item, Mapping):
        return "NONE"
    return str(item.get("role") or "NONE").upper()


def _conditions(match: Mapping[str, Any]) -> dict[str, Any]:
    raw = _evidence(match).get("conditions")
    if not isinstance(raw, Mapping):
        return {}
    out: dict[str, Any] = {}
    for bucket in ("anchor", "modifiers"):
        values = raw.get(bucket)
        if isinstance(values, Mapping):
            for key, value in values.items():
                out[str(key)] = value
    return out


def _strict_subset(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return len(left) < len(right) and all(
        key in right and right[key] == value for key, value in left.items()
    )


def _quantile(values: list[int], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    pos = (len(ordered) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


def _counter_dict(counter: collections.Counter[Any]) -> dict[str, int]:
    return {
        str(key): int(value)
        for key, value in sorted(counter.items(), key=lambda item: str(item[0]))
    }


def _top_counter(counter: collections.Counter[Any], limit: int = 30) -> list[dict[str, Any]]:
    return [{"key": key, "count": int(count)} for key, count in counter.most_common(limit)]


def audit(paths: Iterable[Path]) -> dict[str, Any]:
    day_rows: list[tuple[str, dict[str, Any]]] = []
    for path in paths:
        rows = _read_jsonl(path)
        dates = {
            str((row.get("key") or {}).get("race_date") or "")
            for row in rows
            if isinstance(row.get("key"), Mapping)
        }
        dates.discard("")
        if len(dates) != 1:
            raise OperationalAuditError(
                f"{path}: expected exactly one race_date, got {sorted(dates)}"
            )
        race_date = next(iter(dates))
        day_rows.extend((race_date, row) for row in rows)

    if not day_rows:
        raise OperationalAuditError("no matcher rows")

    total_hit_counts: list[int] = []
    pm_hit_counts: list[int] = []
    group_counts: list[int] = []
    primary_counts: list[int] = []

    total_hit_dist: collections.Counter[int] = collections.Counter()
    pm_hit_dist: collections.Counter[int] = collections.Counter()
    composition: collections.Counter[str] = collections.Counter()
    template_freq: collections.Counter[str] = collections.Counter()
    family_freq: collections.Counter[str] = collections.Counter()
    template_pairs: collections.Counter[str] = collections.Counter()
    family_pairs: collections.Counter[str] = collections.Counter()
    evidence_levels: collections.Counter[str] = collections.Counter()
    condition_cardinality: collections.Counter[int] = collections.Counter()
    semantic_pair_counts: dict[str, collections.Counter[str]] = {
        label: collections.Counter()
        for _, _, label in SEMANTIC_TEMPLATE_PAIRS
    }
    day_summary: dict[str, collections.Counter[str]] = collections.defaultdict(
        collections.Counter
    )

    matched_runners = pm_matched_runners = mixed_runners = 0
    parent_child_runners = parent_child_pairs = 0
    same_signal_parent_child_pairs = opposite_signal_parent_child_pairs = 0
    within_group_extra_matches = multi_group_runners = multi_primary_runners = 0
    total_matches = pm_matches = pos_matches = neg_matches = 0
    high_hit_examples: list[dict[str, Any]] = []

    for race_date, row in day_rows:
        matches = [m for m in row["edge_matches"] if isinstance(m, Mapping)]
        total_matches += len(matches)
        total_hit_counts.append(len(matches))
        total_hit_dist[len(matches)] += 1
        if matches:
            matched_runners += 1
            day_summary[race_date]["matched_runners"] += 1
        day_summary[race_date]["runners"] += 1
        day_summary[race_date]["matches"] += len(matches)

        pm = [m for m in matches if _signal(m, "performance") in MEANINGFUL]
        pos = [m for m in pm if _signal(m, "performance") == "POSITIVE"]
        neg = [m for m in pm if _signal(m, "performance") == "NEGATIVE"]
        pm_matches += len(pm)
        pos_matches += len(pos)
        neg_matches += len(neg)
        pm_hit_counts.append(len(pm))
        pm_hit_dist[len(pm)] += 1
        if pm:
            pm_matched_runners += 1
            day_summary[race_date]["pm_matched_runners"] += 1
        day_summary[race_date]["pm_matches"] += len(pm)
        day_summary[race_date]["positive_matches"] += len(pos)
        day_summary[race_date]["negative_matches"] += len(neg)

        composition[f"+{len(pos)}/-{len(neg)}"] += 1
        if pos and neg:
            mixed_runners += 1
            day_summary[race_date]["mixed_runners"] += 1

        for match in pm:
            template_freq[_template(match)] += 1
            family_freq[_family(match)] += 1
            evidence_levels[_level(match, "performance")] += 1
            condition_cardinality[len(_conditions(match))] += 1

        templates = sorted({_template(m) for m in pm})
        families = sorted({_family(m) for m in pm})

        by_template: dict[str, list[Mapping[str, Any]]] = collections.defaultdict(list)
        for match in pm:
            by_template[_template(match)].append(match)
        for left_template, right_template, label in SEMANTIC_TEMPLATE_PAIRS:
            for left in by_template.get(left_template, []):
                for right in by_template.get(right_template, []):
                    left_signal = _signal(left, "performance")
                    right_signal = _signal(right, "performance")
                    semantic_pair_counts[label]["cooccurrences"] += 1
                    if left_signal == right_signal:
                        semantic_pair_counts[label]["same_direction"] += 1
                    else:
                        semantic_pair_counts[label]["opposite_direction"] += 1
                    semantic_pair_counts[label][
                        f"{left_signal}->{right_signal}"
                    ] += 1
        for a, b in itertools.combinations(templates, 2):
            template_pairs[f"{a} x {b}"] += 1
        for a, b in itertools.combinations(families, 2):
            family_pairs[f"{a} x {b}"] += 1

        groups = {_group(m) for m in pm}
        group_counts.append(len(groups))
        within_group_extra_matches += max(0, len(pm) - len(groups))
        if len(groups) >= 2:
            multi_group_runners += 1

        primary_like = [
            m
            for m in pm
            if _role(m, "performance") in {"PRIMARY", "CONFLICT", "LEGACY"}
        ]
        primary_counts.append(len(primary_like))
        if len(primary_like) >= 2:
            multi_primary_runners += 1

        subset_pairs = subset_same = subset_opposite = 0
        for left, right in itertools.combinations(pm, 2):
            lc, rc = _conditions(left), _conditions(right)
            if not lc or not rc:
                continue
            if not (_strict_subset(lc, rc) or _strict_subset(rc, lc)):
                continue
            subset_pairs += 1
            if _signal(left, "performance") == _signal(right, "performance"):
                subset_same += 1
            else:
                subset_opposite += 1
        if subset_pairs:
            parent_child_runners += 1
            parent_child_pairs += subset_pairs
            same_signal_parent_child_pairs += subset_same
            opposite_signal_parent_child_pairs += subset_opposite
            day_summary[race_date]["parent_child_runners"] += 1

        if len(pm) >= 5:
            key = row.get("key") if isinstance(row.get("key"), Mapping) else {}
            high_hit_examples.append(
                {
                    "race_date": race_date,
                    "race_key": key.get("race_key"),
                    "race_horse_key": key.get("race_horse_key"),
                    "horse_no": key.get("horse_no"),
                    "performance_hits": len(pm),
                    "positive": len(pos),
                    "negative": len(neg),
                    "redundancy_groups": len(groups),
                    "primary_or_conflict": len(primary_like),
                    "templates": templates,
                }
            )

    runners = len(day_rows)
    return {
        "status": "PASS",
        "version": VERSION,
        "purpose": (
            "JRDB Edge v0.2 operational density/conflict audit; "
            "no serving semantics changed"
        ),
        "days": sorted(day_summary),
        "runners": runners,
        "matched_runners": matched_runners,
        "matched_runner_rate": matched_runners / runners,
        "total_matches": total_matches,
        "performance_pm": {
            "matched_runners": pm_matched_runners,
            "matched_runner_rate": pm_matched_runners / runners,
            "matches": pm_matches,
            "positive_matches": pos_matches,
            "negative_matches": neg_matches,
            "mixed_direction_runners": mixed_runners,
            "mixed_direction_rate_all_runners": mixed_runners / runners,
            "mixed_direction_rate_pm_matched": (
                mixed_runners / pm_matched_runners if pm_matched_runners else 0.0
            ),
            "hit_count_distribution": _counter_dict(pm_hit_dist),
            "composition_distribution": _counter_dict(composition),
            "hit_count_mean": statistics.fmean(pm_hit_counts),
            "hit_count_median": statistics.median(pm_hit_counts),
            "hit_count_p90": _quantile(pm_hit_counts, 0.90),
            "runners_with_3plus": sum(value >= 3 for value in pm_hit_counts),
            "runners_with_5plus": sum(value >= 5 for value in pm_hit_counts),
            "runners_with_6plus": sum(value >= 6 for value in pm_hit_counts),
        },
        "all_matches": {
            "hit_count_distribution": _counter_dict(total_hit_dist),
            "hit_count_mean": statistics.fmean(total_hit_counts),
            "hit_count_median": statistics.median(total_hit_counts),
            "hit_count_p90": _quantile(total_hit_counts, 0.90),
        },
        "existing_redundancy": {
            "within_group_extra_matches": within_group_extra_matches,
            "runners_with_multiple_groups": multi_group_runners,
            "runners_with_multiple_primary_or_conflict": multi_primary_runners,
            "group_count_mean": statistics.fmean(group_counts),
            "primary_or_conflict_count_mean": statistics.fmean(primary_counts),
        },
        "condition_nesting": {
            "runners_with_parent_child_relation": parent_child_runners,
            "runner_rate": parent_child_runners / runners,
            "parent_child_pairs": parent_child_pairs,
            "same_signal_pairs": same_signal_parent_child_pairs,
            "opposite_signal_pairs": opposite_signal_parent_child_pairs,
        },
        "performance_evidence_levels": _counter_dict(evidence_levels),
        "condition_cardinality_distribution": _counter_dict(condition_cardinality),
        "template_frequency": _counter_dict(template_freq),
        "family_frequency": _counter_dict(family_freq),
        "top_template_cooccurrence": _top_counter(template_pairs),
        "top_family_cooccurrence": _top_counter(family_pairs),
        "semantic_template_pairs": {
            label: _counter_dict(counter)
            for label, counter in semantic_pair_counts.items()
        },
        "high_hit_examples": sorted(
            high_hit_examples,
            key=lambda row: (-int(row["performance_hits"]), str(row["race_horse_key"])),
        )[:50],
        "per_day": {
            day: {key: int(value) for key, value in sorted(counter.items())}
            for day, counter in sorted(day_summary.items())
        },
    }


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def markdown(result: Mapping[str, Any]) -> str:
    pm = result["performance_pm"]
    redundancy = result["existing_redundancy"]
    nesting = result["condition_nesting"]
    lines = [
        "# JRDB Edge v0.2 実運用ヒット密度・競合監査",
        "",
        f"- 監査version: {result['version']}",
        f"- 対象日: {', '.join(result['days'])}",
        "- 目的: 現行v0.2 STANDARDの過剰ヒット・＋/－混在・条件重複を測定する",
        "- 注意: この監査ではRegistry、閾値、serving、matcherの意味論を変更しない",
        "",
        "## 1. 全体",
        "",
        f"- runner: **{result['runners']:,}**",
        f"- 何らかのEdgeが一致: **{result['matched_runners']:,}** ({_pct(result['matched_runner_rate'])})",
        f"- 全match: **{result['total_matches']:,}**",
        f"- Performance +/- match: **{pm['matches']:,}** (+ {pm['positive_matches']:,} / - {pm['negative_matches']:,})",
        f"- Performance +/-が1件以上のrunner: **{pm['matched_runners']:,}** ({_pct(pm['matched_runner_rate'])})",
        "",
        "## 2. 1頭あたりのPerformance +/-ヒット密度",
        "",
        f"- 平均: **{pm['hit_count_mean']:.2f}件**",
        f"- 中央値: **{pm['hit_count_median']:.1f}件**",
        f"- 90%点: **{pm['hit_count_p90']:.1f}件**",
        f"- 3件以上: **{pm['runners_with_3plus']:,}頭**",
        f"- 5件以上: **{pm['runners_with_5plus']:,}頭**",
        f"- 6件以上: **{pm['runners_with_6plus']:,}頭**",
        "",
        "| ヒット数 | runner数 |",
        "|---:|---:|",
    ]
    for hits, count in pm["hit_count_distribution"].items():
        lines.append(f"| {hits} | {count:,} |")

    lines += [
        "",
        "## 3. ＋ / －同時発生",
        "",
        f"- 同一runnerで＋と－が同時発生: **{pm['mixed_direction_runners']:,}頭**",
        f"- 全runner比: **{_pct(pm['mixed_direction_rate_all_runners'])}**",
        f"- Performance +/-一致runner内: **{_pct(pm['mixed_direction_rate_pm_matched'])}**",
        "",
        "頻出する生の構成（最終符号ではなく件数構成）:",
        "",
        "| 構成 | runner数 |",
        "|---|---:|",
    ]
    compositions = sorted(
        pm["composition_distribution"].items(),
        key=lambda item: (-item[1], item[0]),
    )[:20]
    for key, count in compositions:
        lines.append(f"| {key} | {count:,} |")

    lines += [
        "",
        "## 4. 現行redundancy_groupで吸収できている範囲",
        "",
        f"- 同一group内の追加match: **{redundancy['within_group_extra_matches']:,}件**",
        f"- 複数redundancy groupが同時に刺さるrunner: **{redundancy['runners_with_multiple_groups']:,}頭**",
        f"- PRIMARY / CONFLICT相当が複数残るrunner: **{redundancy['runners_with_multiple_primary_or_conflict']:,}頭**",
        "",
        "## 5. 条件包含（Parent / Child候補）",
        "",
        f"- strict subset/supersetがあるrunner: **{nesting['runners_with_parent_child_relation']:,}頭** ({_pct(nesting['runner_rate'])})",
        f"- Parent/Child候補pair: **{nesting['parent_child_pairs']:,}組**",
        f"- 同方向pair: **{nesting['same_signal_pairs']:,}組**",
        f"- 逆方向pair: **{nesting['opposite_signal_pairs']:,}組**",
        "",
        "ここでは包含関係だけを測り、Childの追加効果はまだ判定しない。",
        "",
        "## 6. Template頻度",
        "",
        "| Template | match数 |",
        "|---|---:|",
    ]
    for key, count in sorted(
        result["template_frequency"].items(), key=lambda item: (-item[1], item[0])
    ):
        lines.append(f"| {key} | {count:,} |")

    lines += [
        "",
        "## 7. Template共起 上位",
        "",
        "| Template pair | 同一runner共起数 |",
        "|---|---:|",
    ]
    for item in result["top_template_cooccurrence"]:
        lines.append(f"| {item['key']} | {item['count']:,} |")

    lines += [
        "",
        "## 8. 主要な意味的重複候補",
        "",
        "| 関係 | 共起 | 同方向 | 逆方向 |",
        "|---|---:|---:|---:|",
    ]
    for label, counts in result["semantic_template_pairs"].items():
        lines.append(
            f"| {label} | {counts.get('cooccurrences', 0):,} | "
            f"{counts.get('same_direction', 0):,} | "
            f"{counts.get('opposite_direction', 0):,} |"
        )

    lines += [
        "",
        "## 9. 5件以上ヒットしたrunner例",
        "",
        "| 日付 | race_key | 馬番 | +/- | group数 | primary/conflict | Template |",
        "|---|---|---:|---|---:|---:|---|",
    ]
    for row in result["high_hit_examples"][:30]:
        lines.append(
            f"| {row['race_date']} | {row['race_key']} | {row['horse_no']} | "
            f"+{row['positive']}/-{row['negative']} | {row['redundancy_groups']} | "
            f"{row['primary_or_conflict']} | {', '.join(row['templates'])} |"
        )

    lines += [
        "",
        "## 10. この監査でまだ決めないこと",
        "",
        "- +件数と-件数を足し引きして最終scoreを作らない",
        "- 2,773件を一括削除しない",
        "- specificityが高いだけでNiche Edgeへ昇格しない",
        "- Performance-positiveをValue-positiveとみなさない",
        "",
        "次段階ではParent/Child階層を定義し、ChildがParentに対して追加的なPerformance / Market情報を持つかshadow評価する。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matches-jsonl", action="append", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    args = parser.parse_args()
    result = audit(Path(value) for value in args.matches_jsonl)
    Path(args.output_json).write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    Path(args.output_md).write_text(markdown(result), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result["status"],
                "days": result["days"],
                "runners": result["runners"],
                "performance_matches": result["performance_pm"]["matches"],
                "mixed_runners": result["performance_pm"]["mixed_direction_runners"],
                "five_plus_runners": result["performance_pm"]["runners_with_5plus"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
