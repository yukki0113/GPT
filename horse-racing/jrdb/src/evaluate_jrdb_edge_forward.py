#!/usr/bin/env python3
"""Settle pre-race JRDB Edge matches against post-race SED for shadow evaluation.

This module intentionally accepts *matcher output* and SED as separate inputs.
SED is used only after Edge matching has already been frozen; it never participates
in current-fact construction or Edge condition evaluation.
"""
from __future__ import annotations

import argparse
import json
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from jrdb_raw import Parser, read_fixed_records

VERSION = "0.2.0"


def _iso_date(raw: Any) -> str | None:
    value = "" if raw is None else str(raw).strip()
    if len(value) != 8 or not value.isdigit():
        return None
    return f"{value[:4]}-{value[4:6]}-{value[6:]}"


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def load_match_rows(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for line_no, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        row = json.loads(raw)
        if not isinstance(row, dict):
            raise ValueError(f"match line {line_no} is not an object")
        key = row.get("key")
        matches = row.get("edge_matches")
        if not isinstance(key, dict) or not isinstance(matches, list):
            raise ValueError(f"match line {line_no} requires key object and edge_matches array")
        race_key = str(key.get("race_key") or "")
        horse_no = key.get("horse_no")
        if len(race_key) != 8 or not isinstance(horse_no, int):
            raise ValueError(f"match line {line_no} has invalid race_key/horse_no identity")
        identity = (race_key, horse_no)
        if identity in seen:
            raise ValueError(f"duplicate matcher runner identity: {identity}")
        seen.add(identity)
        for match in matches:
            if not isinstance(match, dict) or not match.get("edge_id") or not match.get("polarity"):
                raise ValueError(f"match line {line_no} contains malformed Edge match")
            if not isinstance(match.get("evidence"), dict):
                raise ValueError(f"match line {line_no} Edge {match.get('edge_id')} lacks evidence")
        rows.append(row)
    return rows


def load_sed_outcomes(path: str | Path) -> dict[tuple[str, int], dict[str, Any]]:
    parser = Parser()
    outcomes: dict[tuple[str, int], dict[str, Any]] = {}
    with zipfile.ZipFile(path) as archive:
        members = [
            name for name in archive.namelist()
            if Path(name).name.upper().startswith("SED") and Path(name).name.upper().endswith(".TXT")
        ]
        if len(members) != 1:
            raise ValueError(f"expected exactly one SED*.txt member, found {len(members)}")
        records = read_fixed_records(archive, members[0], "SED")
        if not records:
            raise ValueError("SED member has no valid fixed-width records")
        for raw in records:
            parsed = parser.sed(raw)
            race_key = str(parsed.get("race_key_raw") or "")
            horse_no_raw = parsed.get("horse_no")
            try:
                horse_no = int(horse_no_raw) if horse_no_raw is not None else None
            except (TypeError, ValueError):
                horse_no = None
            if len(race_key) != 8 or horse_no is None:
                raise ValueError("SED row has invalid race_key/horse_no identity")
            identity = (race_key, horse_no)
            if identity in outcomes:
                raise ValueError(f"duplicate SED runner identity: {identity}")
            outcomes[identity] = {
                "race_key": race_key,
                "horse_no": horse_no,
                "horse_id": str(parsed.get("blood_registration_no") or ""),
                "race_date": _iso_date(parsed.get("date_raw")),
                "finish": parsed.get("finish"),
                "abnormal_code": str(parsed.get("abnormal_code") or ""),
                "final_win_odds": parsed.get("final_win_odds"),
                "final_win_popularity": parsed.get("final_popularity"),
                "win_payout": parsed.get("win_payout") or 0,
                "place_payout": parsed.get("place_payout") or 0,
            }
    return outcomes


def _eligibility(outcome: Mapping[str, Any]) -> str:
    if outcome.get("finish") is None:
        return "NO_RESULT"
    abnormal = str(outcome.get("abnormal_code") or "").strip()
    if abnormal not in {"", "0"}:
        return "ABNORMAL"
    return "ELIGIBLE"


def _mean_metric(rows: Iterable[Mapping[str, Any]], field: str) -> float | None:
    values = [_number(row.get("evidence", {}).get(field)) for row in rows]
    usable = [value for value in values if value is not None]
    return (sum(usable) / len(usable)) if usable else None


def summarize_occurrences(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [row for row in rows if row["eligibility"] == "ELIGIBLE"]
    count = len(eligible)
    result: dict[str, Any] = {
        "matches": len(rows),
        "eligible": count,
        "abnormal": sum(row["eligibility"] == "ABNORMAL" for row in rows),
        "no_result": sum(row["eligibility"] == "NO_RESULT" for row in rows),
        "unique_edges": len({row["edge_id"] for row in eligible}),
        "unique_runners": len({row["runner_identity"] for row in eligible}),
        "review_due_occurrences": sum(bool(row["review_due"]) for row in eligible),
    }
    if not count:
        return result
    win_hits = sum(int(int(row["outcome"]["finish"]) == 1) for row in eligible)
    place_hits = sum(int(float(row["outcome"].get("place_payout") or 0) > 0) for row in eligible)
    win_return = sum(float(row["outcome"].get("win_payout") or 0) for row in eligible)
    place_return = sum(float(row["outcome"].get("place_payout") or 0) for row in eligible)
    result.update({
        "win_hits": win_hits,
        "win_rate": win_hits / count,
        "place_hits": place_hits,
        "place_rate": place_hits / count,
        "win_return_yen": win_return,
        "place_return_yen": place_return,
        "win_roi": win_return / (count * 100.0),
        "place_roi": place_return / (count * 100.0),
        "historical_place_rate_weighted": _mean_metric(eligible, "place_rate"),
        "historical_place_roi_weighted": _mean_metric(eligible, "place_roi"),
        "baseline_place_rate_weighted": _mean_metric(eligible, "baseline_place_rate"),
    })
    return result


def evaluate(
    match_rows: list[dict[str, Any]],
    outcomes: Mapping[tuple[str, int], Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    occurrences: list[dict[str, Any]] = []
    joined_runners = 0
    abnormal_runners = 0
    for row in match_rows:
        key = row["key"]
        identity = (str(key["race_key"]), int(key["horse_no"]))
        outcome = outcomes.get(identity)
        if outcome is None:
            raise ValueError(f"SED is missing matcher runner identity: {identity}")
        joined_runners += 1
        expected_horse = str(key.get("horse_id") or "")
        actual_horse = str(outcome.get("horse_id") or "")
        if expected_horse and actual_horse and expected_horse != actual_horse:
            raise ValueError(f"horse_id mismatch for {identity}: {expected_horse} != {actual_horse}")
        expected_date = str(key.get("race_date") or "")
        actual_date = str(outcome.get("race_date") or "")
        if expected_date and actual_date and expected_date != actual_date:
            raise ValueError(f"race_date mismatch for {identity}: {expected_date} != {actual_date}")
        runner_eligibility = _eligibility(outcome)
        abnormal_runners += int(runner_eligibility == "ABNORMAL")
        for match in row["edge_matches"]:
            evidence = match["evidence"]
            occurrences.append({
                "runner_identity": f"{identity[0]}:{identity[1]:02d}",
                "race_date": actual_date or expected_date or None,
                "horse_id": actual_horse or expected_horse or None,
                "edge_id": str(match["edge_id"]),
                "evaluator_version": VERSION,
                "display_text": match.get("display_text"),
                "registry_version": match.get("registry_version"),
                "strength_score": match.get("strength_score"),
                "confidence_band": match.get("confidence_band"),
                "family": evidence.get("family"),
                "polarity": match.get("polarity"),
                "status": match.get("status"),
                "review_due": bool(evidence.get("review_due")),
                "eligibility": runner_eligibility,
                "evidence": evidence,
                "outcome": dict(outcome),
            })

    def grouped(field: str) -> dict[str, Any]:
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for occurrence in occurrences:
            buckets[str(occurrence.get(field))].append(occurrence)
        return {key: summarize_occurrences(buckets[key]) for key in sorted(buckets)}

    cross: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for occurrence in occurrences:
        cross[f"{occurrence.get('polarity')}|{occurrence.get('family')}"].append(occurrence)

    report = {
        "status": "PASS",
        "evaluator_version": VERSION,
        "semantics": "edge-occurrence shadow settlement; 100 JPY hypothetical stake per matched Edge occurrence",
        "runner_audit": {
            "matcher_rows": len(match_rows),
            "sed_joined_rows": joined_runners,
            "abnormal_rows": abnormal_runners,
        },
        "overall": summarize_occurrences(occurrences),
        "by_family": grouped("family"),
        "by_polarity": grouped("polarity"),
        "by_review_due": grouped("review_due"),
        "by_polarity_family": {
            key: summarize_occurrences(cross[key]) for key in sorted(cross)
        },
    }
    return report, occurrences


def run(
    *,
    matches_jsonl: str | Path,
    sed_path: str | Path,
    output_json: str | Path,
    audit_jsonl: str | Path | None = None,
) -> dict[str, Any]:
    match_rows = load_match_rows(matches_jsonl)
    outcomes = load_sed_outcomes(sed_path)
    report, occurrences = evaluate(match_rows, outcomes)
    output = Path(output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if audit_jsonl is not None:
        audit = Path(audit_jsonl)
        audit.parent.mkdir(parents=True, exist_ok=True)
        with audit.open("w", encoding="utf-8", newline="\n") as handle:
            for occurrence in occurrences:
                handle.write(json.dumps(occurrence, ensure_ascii=False, sort_keys=True) + "\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matches-jsonl", required=True, help="Frozen output from run_jrdb_edge_match_current.py")
    parser.add_argument("--sed", required=True, help="Post-race SEDyymmdd.zip used only for settlement")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--audit-jsonl")
    args = parser.parse_args()
    report = run(
        matches_jsonl=args.matches_jsonl,
        sed_path=args.sed,
        output_json=args.output_json,
        audit_jsonl=args.audit_jsonl,
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
