#!/usr/bin/env python3
"""Replay JRDB Edge v0.3 SHADOW_ONLY serving against frozen pre-race Current Facts.

Stage-D compares the frozen v0.2 STANDARD match outputs with the isolated v0.3
shadow serving catalog on exactly the same runner facts. It is diagnostic only:
no production matcher, v0.2 catalog, thresholds, Newspaper, or RaceNote route is
modified.
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics
from pathlib import Path
from typing import Any, Iterable, Mapping

import jrdb_edge_matcher_v0_2 as v02

VERSION = "0.1.0-stage-d"
PM = {"POSITIVE", "NEGATIVE"}
TARGET_TEMPLATES = {
    "COURSE_FRAME_V1",
    "COURSE_EXACT_FRAME_V2",
    "SIRE_SURFACE_DISTANCE_V1",
    "SIRE_TURN_DISTANCE_V1",
    "SIRE_VENUE_SURFACE_DISTANCE_V2",
}


class ReplayAuditError(RuntimeError):
    pass


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ReplayAuditError(f"{path}:{line_no}: object required")
        rows.append(value)
    return rows


def _key(row: Mapping[str, Any]) -> str:
    key = row.get("race_horse_key")
    if key not in (None, ""):
        return str(key)
    race_key = row.get("race_key")
    horse_no = row.get("horse_no")
    if race_key in (None, "") or horse_no in (None, ""):
        raise ReplayAuditError("runner identity missing")
    return f"{race_key}:{horse_no}"


def _match_key(row: Mapping[str, Any]) -> str:
    key = row.get("key")
    if not isinstance(key, Mapping):
        raise ReplayAuditError("match row key missing")
    return _key(key)


def _template_from_match(match: Mapping[str, Any]) -> str:
    evidence = match.get("evidence")
    return str(evidence.get("template_id") or "") if isinstance(evidence, Mapping) else ""


def _v02_signal(match: Mapping[str, Any], channel: str) -> str:
    evidence = match.get("evidence")
    if not isinstance(evidence, Mapping):
        return "NEUTRAL"
    return str(evidence.get(f"{channel}_signal") or "NEUTRAL").upper()


def _v02_level(match: Mapping[str, Any], channel: str) -> str:
    return str(match.get(f"{channel}_evidence_level") or "NONE").upper()


def _v03_signal(match: Mapping[str, Any], channel: str) -> str:
    shadow = match.get("v03_shadow")
    if not isinstance(shadow, Mapping):
        return "NEUTRAL"
    return str(shadow.get(f"{channel}_signal") or "NEUTRAL").upper()


def _shadow_display_text(edge: Mapping[str, Any], signal: str) -> str:
    """Build a v0.3 shadow-only display label without rewriting v0.2 provenance."""
    symbol = {"POSITIVE": "＋", "NEGATIVE": "－", "NEUTRAL": "・"}.get(signal, "・")
    original = str(edge.get("display_text") or "").strip()
    if original[:1] in {"＋", "－", "+", "-"}:
        original = original[1:].lstrip()
    return f"{symbol} {original}".rstrip()


def _v03_cluster(match: Mapping[str, Any]) -> str:
    shadow = match.get("v03_shadow")
    if isinstance(shadow, Mapping):
        hierarchy = str(shadow.get("hierarchy") or "")
        if hierarchy:
            return f"H:{hierarchy}"
    group = str(match.get("redundancy_group_id") or "")
    if group:
        return f"G:{group}"
    return f"T:{_template_from_match(match)}"


def _load_shadow_catalog(path: Path) -> list[dict[str, Any]]:
    rows = _read_jsonl(path)
    for row in rows:
        shadow = row.get("v03_shadow")
        if not isinstance(shadow, Mapping):
            raise ReplayAuditError(f"{row.get('edge_id')}: v03_shadow missing")
        if shadow.get("mode") != "SHADOW_ONLY" or shadow.get("reader_facing") is not True:
            raise ReplayAuditError(f"{row.get('edge_id')}: non-reader-facing shadow row in serving catalog")
    return rows


def _match_shadow(registry: Iterable[Mapping[str, Any]], runner: Mapping[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for edge in registry:
        status = str(edge.get("status") or edge.get("registry_status") or "")
        base_match = v02.base.edge_matches_runner(edge, runner, statuses=(status,))
        if base_match is None:
            continue
        shadow = dict(edge.get("v03_shadow") or {})
        performance_signal = str(shadow.get("performance_signal") or "NEUTRAL").upper()
        shadow["presentation"] = {
            "contract": "V03_SHADOW_PRESENTATION",
            "performance_signal": performance_signal,
            "polarity_symbol": {"POSITIVE": "＋", "NEGATIVE": "－", "NEUTRAL": "・"}.get(
                performance_signal, "・"
            ),
            "display_text": _shadow_display_text(edge, performance_signal),
        }
        base_match["v03_shadow"] = shadow
        base_match["redundancy_group_id"] = edge.get("redundancy_group_id")
        evidence = base_match.setdefault("evidence", {})
        if isinstance(evidence, dict):
            evidence["performance_signal"] = shadow.get("performance_signal")
            evidence["value_signal"] = shadow.get("value_signal")
        output.append(base_match)
    output.sort(key=lambda row: str(row.get("edge_id") or ""))
    return output


def _density(matches: list[Mapping[str, Any]], signal_fn) -> dict[str, Any]:
    pm = [m for m in matches if signal_fn(m, "performance") in PM]
    pos = sum(signal_fn(m, "performance") == "POSITIVE" for m in pm)
    neg = sum(signal_fn(m, "performance") == "NEGATIVE" for m in pm)
    return {
        "all_matches": len(matches),
        "performance_matches": len(pm),
        "positive": pos,
        "negative": neg,
        "mixed": bool(pos and neg),
    }


def _summarize_runner_rows(rows: list[dict[str, Any]], *, shadow: bool) -> dict[str, Any]:
    pm_counts: list[int] = []
    cluster_counts: list[int] = []
    matched = pm_matched = mixed = value_matched = reversal_matches = 0
    total_matches = performance_matches = value_matches = 0
    target_pm_matches = 0
    signal_with_level_none = 0
    non_target_signal_with_level_none = 0
    for row in rows:
        matches = row["matches"]
        fn = _v03_signal if shadow else _v02_signal
        d = _density(matches, fn)
        total_matches += d["all_matches"]
        performance_matches += d["performance_matches"]
        pm_counts.append(d["performance_matches"])
        if matches:
            matched += 1
        if d["performance_matches"]:
            pm_matched += 1
        if d["mixed"]:
            mixed += 1
        values = [m for m in matches if fn(m, "value") in PM]
        value_matches += len(values)
        if values:
            value_matched += 1
        target_pm_matches += sum(
            _template_from_match(m) in TARGET_TEMPLATES and fn(m, "performance") in PM
            for m in matches
        )
        if not shadow:
            for match in matches:
                if _v02_signal(match, "performance") not in PM:
                    continue
                if _v02_level(match, "performance") != "NONE":
                    continue
                signal_with_level_none += 1
                if _template_from_match(match) not in TARGET_TEMPLATES:
                    non_target_signal_with_level_none += 1
        if shadow:
            clusters = {_v03_cluster(m) for m in matches if fn(m, "performance") in PM}
            cluster_counts.append(len(clusters))
            reversal_matches += sum(
                bool((m.get("v03_shadow") or {}).get("is_reversal_vs_v02"))
                for m in matches
                if isinstance(m.get("v03_shadow"), Mapping)
            )

    runners = len(rows)
    summary = {
        "runners": runners,
        "matched_runners": matched,
        "total_matches": total_matches,
        "performance_matches": performance_matches,
        "performance_matched_runners": pm_matched,
        "mixed_direction_runners": mixed,
        "mixed_direction_rate_all": mixed / runners if runners else 0.0,
        "mixed_direction_rate_pm_matched": mixed / pm_matched if pm_matched else 0.0,
        "performance_hit_mean": statistics.fmean(pm_counts) if pm_counts else 0.0,
        "runners_with_3plus": sum(v >= 3 for v in pm_counts),
        "runners_with_5plus": sum(v >= 5 for v in pm_counts),
        "runners_with_6plus": sum(v >= 6 for v in pm_counts),
        "target_hierarchy_performance_matches": target_pm_matches,
        "value_matches": value_matches,
        "value_matched_runners": value_matched,
    }
    if not shadow:
        summary.update({
            "performance_signal_with_evidence_level_none": signal_with_level_none,
            "non_target_performance_signal_with_evidence_level_none": non_target_signal_with_level_none,
        })
    if shadow:
        summary.update({
            "semantic_cluster_mean": statistics.fmean(cluster_counts) if cluster_counts else 0.0,
            "semantic_cluster_3plus_runners": sum(v >= 3 for v in cluster_counts),
            "incremental_reversal_matches": reversal_matches,
        })
    return summary


def _day_rows(
    facts: list[dict[str, Any]],
    v02_rows: list[dict[str, Any]],
    shadow_registry: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    facts_by_key = {_key(row): row for row in facts}
    if len(facts_by_key) != len(facts):
        raise ReplayAuditError("duplicate Current Facts runner key")
    v02_by_key = {_match_key(row): row for row in v02_rows}
    if set(facts_by_key) != set(v02_by_key):
        missing_matches = sorted(set(facts_by_key) - set(v02_by_key))[:5]
        missing_facts = sorted(set(v02_by_key) - set(facts_by_key))[:5]
        raise ReplayAuditError(
            f"Current Facts/v0.2 matcher key mismatch: no_match={missing_matches} no_fact={missing_facts}"
        )

    v02_out: list[dict[str, Any]] = []
    v03_out: list[dict[str, Any]] = []
    absorbed = collections.Counter()
    for key in sorted(facts_by_key):
        fact = facts_by_key[key]
        old_matches = [m for m in v02_by_key[key].get("edge_matches", []) if isinstance(m, Mapping)]
        new_matches = _match_shadow(shadow_registry, fact)
        new_ids = {str(m.get("edge_id") or "") for m in new_matches}
        for match in old_matches:
            template = _template_from_match(match)
            if template not in TARGET_TEMPLATES or _v02_signal(match, "performance") not in PM:
                continue
            if str(match.get("edge_id") or "") not in new_ids:
                absorbed[template] += 1
        v02_out.append({"key": v02_by_key[key]["key"], "matches": old_matches})
        v03_out.append({"key": v02_by_key[key]["key"], "matches": new_matches})
    return v02_out, v03_out, {
        "absorbed_target_performance_matches": sum(absorbed.values()),
        "absorbed_target_template_counts": dict(sorted(absorbed.items())),
    }


def run(
    *,
    days: list[tuple[str, Path, Path]],
    shadow_catalog: Path,
    output_matches: Path,
    output_summary: Path,
) -> dict[str, Any]:
    registry = _load_shadow_catalog(shadow_catalog)
    all_v02: list[dict[str, Any]] = []
    all_v03: list[dict[str, Any]] = []
    per_day: dict[str, Any] = {}
    absorbed_total = collections.Counter()

    with output_matches.open("w", encoding="utf-8", newline="\n") as handle:
        for date, facts_path, v02_path in days:
            facts = _read_jsonl(facts_path)
            v02_rows = _read_jsonl(v02_path)
            v02_out, v03_out, absorption = _day_rows(facts, v02_rows, registry)
            all_v02.extend(v02_out)
            all_v03.extend(v03_out)
            for template, count in absorption["absorbed_target_template_counts"].items():
                absorbed_total[template] += int(count)
            per_day[date] = {
                "v02": _summarize_runner_rows(v02_out, shadow=False),
                "v03": _summarize_runner_rows(v03_out, shadow=True),
                "absorption": absorption,
            }
            for row in v03_out:
                handle.write(
                    json.dumps(
                        {"date": date, "key": row["key"], "edge_matches": row["matches"]},
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    + "\n"
                )

    v02_summary = _summarize_runner_rows(all_v02, shadow=False)
    v03_summary = _summarize_runner_rows(all_v03, shadow=True)
    summary = {
        "status": "PASS",
        "version": VERSION,
        "stage": "D_OPERATIONAL_REPLAY",
        "mode": "SHADOW_ONLY",
        "days": [date for date, _, _ in days],
        "v02": v02_summary,
        "v03": v03_summary,
        "delta": {
            "performance_matches": v03_summary["performance_matches"] - v02_summary["performance_matches"],
            "performance_matched_runners": (
                v03_summary["performance_matched_runners"] - v02_summary["performance_matched_runners"]
            ),
            "mixed_direction_runners": (
                v03_summary["mixed_direction_runners"] - v02_summary["mixed_direction_runners"]
            ),
            "runners_with_3plus": v03_summary["runners_with_3plus"] - v02_summary["runners_with_3plus"],
            "runners_with_5plus": v03_summary["runners_with_5plus"] - v02_summary["runners_with_5plus"],
            "runners_with_6plus": v03_summary["runners_with_6plus"] - v02_summary["runners_with_6plus"],
            "value_matches": v03_summary["value_matches"] - v02_summary["value_matches"],
        },
        "context_absorption": {
            "target_performance_matches": sum(absorbed_total.values()),
            "template_counts": dict(sorted(absorbed_total.items())),
        },
        "channel_normalization": {
            "v02_performance_signal_with_evidence_level_none":
                v02_summary["performance_signal_with_evidence_level_none"],
            "non_target_performance_signal_with_evidence_level_none":
                v02_summary["non_target_performance_signal_with_evidence_level_none"],
            "contract": "V03_ORTHOGONAL_PERFORMANCE_NEUTRAL_WHEN_EVIDENCE_LEVEL_NONE",
        },
        "per_day": per_day,
        "production_serving_changed": False,
        "note": (
            "Stage-D replays the isolated v0.3 shadow serving catalog against the same pre-race Current Facts "
            "used by frozen v0.2 STANDARD outputs. Match-count reduction is diagnostic, not itself a promotion criterion."
        ),
    }
    output_summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def _parse_day(value: str) -> tuple[str, Path, Path]:
    parts = value.split("|", 2)
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("--day must be DATE|FACTS_JSONL|V02_MATCHES_JSONL")
    return parts[0], Path(parts[1]), Path(parts[2])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", action="append", type=_parse_day, required=True)
    parser.add_argument("--shadow-catalog", type=Path, required=True)
    parser.add_argument("--output-matches", type=Path, required=True)
    parser.add_argument("--output-summary", type=Path, required=True)
    args = parser.parse_args()
    result = run(
        days=args.day,
        shadow_catalog=args.shadow_catalog,
        output_matches=args.output_matches,
        output_summary=args.output_summary,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
