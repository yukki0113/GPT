#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Formal RaceReviewDB enrichment for authoritative RaceNote v1.0.

This module projects historical RaceReviewDB evidence and the frozen
Next-Watch judgement for each target horse into RaceNote. It never reads the
target result, market, current popularity, or future RRDB rows.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import duckdb

from jrdb_next_watch_rules import (
    VERSION as GRADE_VERSION,
    grade_matched_rules,
    human_summary,
    reason_groups,
)
from jrdb_postrace_review_reader import RaceReviewReader
from racenote_horse_evidence_card import build_horse_evidence_cards
from racenote_racereview_adapter import build_racereview_evidence
from racenote_racereview_current import (
    STABLE_CURRENT_FILE_ID,
    resolve_racereview_current,
)

VERSION = "RRDB-RaceNote-0.1"


class RRDBEnrichmentError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RRDBEnrichmentError(f"JSON object required: {path}")
    return value


def _horse_basic(horse: Mapping[str, object]) -> Mapping[str, object]:
    basic = horse.get("basic")
    if isinstance(basic, Mapping):
        return basic
    return horse


def _independent_view(bundle: Mapping[str, object]) -> dict[str, object]:
    race = bundle.get("race")
    horses = bundle.get("horses")
    if not isinstance(race, Mapping) or not isinstance(horses, list):
        raise RRDBEnrichmentError("RaceNote bundle is missing race/horses")
    projected: list[dict[str, object]] = []
    for raw in horses:
        if not isinstance(raw, Mapping):
            continue
        basic = _horse_basic(raw)
        projected.append({
            "basic": {
                "horse_no": basic.get("horse_no"),
                "horse_name": basic.get("horse_name"),
                "horse_id": basic.get("horse_id"),
            }
        })
    return {
        "view_kind": "INDEPENDENT",
        "race": {
            "date": race.get("date"),
            "venue": race.get("venue"),
            "race_no": race.get("race_no"),
            "race_name": race.get("race_name"),
        },
        "horses": projected,
    }


def load_frozen_contract(source: Path, work_root: Path) -> dict[str, Any]:
    if source.suffix.lower() == ".json":
        contract = _read_json(source)
    else:
        target = work_root / "next_watch_rules"
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        with zipfile.ZipFile(source) as archive:
            archive.extractall(target)
        candidates = list(target.rglob("next_watch_candidate_rules_frozen.json"))
        if len(candidates) != 1:
            raise RRDBEnrichmentError("unique frozen Next-Watch contract required")
        contract = _read_json(candidates[0])
    if contract.get("status") != "CANDIDATE_RULES_FROZEN":
        raise RRDBEnrichmentError("Next-Watch contract is not frozen")
    return contract


def _relation_paths(reader: RaceReviewReader, relation: str) -> list[Path]:
    relations = reader.manifest.get("relations")
    if not isinstance(relations, Mapping):
        raise RRDBEnrichmentError("RRDB manifest relations missing")
    meta = relations.get(relation)
    if not isinstance(meta, Mapping):
        raise RRDBEnrichmentError(f"RRDB relation missing: {relation}")
    result: list[Path] = []
    for part in meta.get("partitions") or []:
        if not isinstance(part, Mapping):
            continue
        rel = part.get("relative_path")
        if isinstance(rel, str):
            path = reader.root / rel
            if not path.is_file():
                raise RRDBEnrichmentError(f"RRDB object missing: {path}")
            result.append(path)
    if not result:
        raise RRDBEnrichmentError(f"RRDB relation empty: {relation}")
    return result


def _table_sql(paths: list[Path]) -> str:
    values = ", ".join("'" + str(p).replace("'", "''") + "'" for p in paths)
    return f"read_parquet([{values}], union_by_name=true, hive_partitioning=false)"


def _latest_next_watch(
    reader: RaceReviewReader,
    contract: Mapping[str, object],
    horse_ids: list[str],
    target_date: str,
) -> dict[str, dict[str, object]]:
    """Reconstruct frozen Next-Watch on each horse's latest prior flat JRA run."""
    frozen = contract.get("frozen_rules")
    if not isinstance(frozen, list):
        raise RRDBEnrichmentError("frozen_rules missing")
    hidden = [
        x for x in frozen
        if isinstance(x, Mapping) and x.get("track") == "hidden_value"
    ]
    if not hidden:
        raise RRDBEnrichmentError("no hidden-value rules")
    rule_ids = [str(x.get("rule_id")) for x in hidden]
    expr = ",\n".join(
        f"CASE WHEN {str(x.get('condition'))} THEN TRUE ELSE FALSE END AS match_{str(x.get('rule_id'))}"
        for x in hidden
    )
    hp = _table_sql(_relation_paths(reader, "fact_horse_performance"))
    con = duckdb.connect(":memory:")
    try:
        con.execute(f"""
        CREATE TEMP VIEW hp_valid AS
        SELECT *,
          -horse_adjusted_delta_per_1000m AS performance_signal,
          AVG(-horse_adjusted_delta_per_1000m) OVER (
            PARTITION BY horse_id
            ORDER BY race_date, race_key, horse_no
            ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
          ) AS prior3_performance_mean,
          AVG(last3f_speed_percentile) OVER (
            PARTITION BY horse_id
            ORDER BY race_date, race_key, horse_no
            ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
          ) AS prior3_last3f_pct_mean
        FROM {hp}
        WHERE horse_id IS NOT NULL
          AND TRIM(horse_id) <> ''
          AND COALESCE(finish, 0) > 0
          AND COALESCE(time_sec, 0) > 0
          AND COALESCE(surface_code, '') <> '3'
        """)
        result: dict[str, dict[str, object]] = {}
        for horse_id in sorted(set(horse_ids)):
            cur = con.execute(f"""
            WITH prior AS (
              SELECT *,
                performance_signal - prior3_performance_mean AS performance_vs_prior3,
                last3f_speed_percentile - prior3_last3f_pct_mean AS last3f_pct_vs_prior3,
                ROW_NUMBER() OVER (
                  ORDER BY race_date DESC, race_key DESC, horse_no DESC
                ) AS rn
              FROM hp_valid
              WHERE horse_id=? AND race_date < CAST(? AS DATE)
            )
            SELECT *, {expr}
            FROM prior
            WHERE rn=1
            """, [horse_id, target_date])
            row = cur.fetchone()
            if row is None:
                result[horse_id] = {
                    "status": "NO_PRIOR_HISTORY",
                    "grade": None,
                    "rule_version": contract.get("rule_version"),
                    "matched_rule_ids": [],
                    "matched_rule_count": 0,
                    "reason_groups": [],
                    "human_summary": None,
                }
                continue
            names = [d[0] for d in cur.description]
            item = dict(zip(names, row))
            matched = [rid for rid in rule_ids if bool(item.get(f"match_{rid}"))]
            grade = grade_matched_rules(matched)
            result[horse_id] = {
                "status": "MATCH" if grade else "NO_MATCH",
                "grade": grade,
                "rule_version": contract.get("rule_version"),
                "grade_logic_version": GRADE_VERSION,
                "matched_rule_ids": sorted(matched),
                "matched_rule_count": len(matched),
                "reason_groups": reason_groups(matched),
                "human_summary": human_summary(matched),
                "source_run": {
                    "race_date": str(item.get("race_date")),
                    "race_key": item.get("race_key"),
                    "finish": item.get("finish"),
                    "performance_signal": item.get("performance_signal"),
                    "last3f_speed_percentile": item.get("last3f_speed_percentile"),
                    "overall_position_gain": item.get("overall_position_gain"),
                    "performance_vs_prior3": item.get("performance_vs_prior3"),
                    "last3f_pct_vs_prior3": item.get("last3f_pct_vs_prior3"),
                },
            }
        return result
    finally:
        con.close()


def enrich_bundle(
    bundle: dict[str, object],
    reader: RaceReviewReader,
    contract: Mapping[str, object],
    *,
    per_horse_limit: int = 5,
) -> dict[str, object]:
    independent = _independent_view(bundle)
    sidecar = build_racereview_evidence(
        independent,
        reader,
        per_horse_limit=per_horse_limit,
    )
    cards = build_horse_evidence_cards(sidecar)

    race = bundle.get("race")
    horses = bundle.get("horses")
    if not isinstance(race, Mapping) or not isinstance(horses, list):
        raise RRDBEnrichmentError("RaceNote bundle missing race/horses")
    target_date = str(race.get("date") or "")
    sidecar_by_no = {int(x["horse_no"]): x for x in sidecar["horses"]}
    card_by_no = {int(x["horse_no"]): x for x in cards["horses"]}

    ids: list[str] = []
    for raw in horses:
        if not isinstance(raw, Mapping):
            continue
        basic = _horse_basic(raw)
        horse_id = str(basic.get("horse_id") or "").strip()
        if horse_id:
            ids.append(horse_id)
    next_watch = _latest_next_watch(reader, contract, ids, target_date)

    for raw in horses:
        if not isinstance(raw, dict):
            continue
        basic = _horse_basic(raw)
        horse_no = int(basic.get("horse_no") or 0)
        horse_id = str(basic.get("horse_id") or "").strip()
        review = sidecar_by_no.get(horse_no)
        card = card_by_no.get(horse_no)

        latest_prior = None
        if isinstance(review, Mapping):
            runs = review.get("runs")
            if isinstance(runs, list) and runs:
                latest_prior = runs[0]

        raw["racereview"] = {
            "history_status": (
                review.get("history_status") if isinstance(review, Mapping)
                else ("NO_HORSE_ID" if not horse_id else "NO_HISTORY")
            ),
            "source_generation_id": reader.generation_id,
            "as_of_exclusive": target_date,
            "latest_prior_run": latest_prior,
            "next_watch": next_watch.get(
                horse_id,
                {
                    "status": "NO_HORSE_ID" if not horse_id else "NO_PRIOR_HISTORY",
                    "grade": None,
                    "rule_version": contract.get("rule_version"),
                    "matched_rule_ids": [],
                    "matched_rule_count": 0,
                    "reason_groups": [],
                    "human_summary": None,
                },
            ),
            "history_profile": (
                {
                    "repeated_patterns": review.get("profile", {}).get("repeated_patterns", []),
                    "hidden_strength": card.get("profile", {}).get("hidden_strength", {}),
                    "fragile_form": card.get("profile", {}).get("fragile_form", {}),
                    "contradiction": card.get("profile", {}).get("contradiction", {}),
                    "primary_positive": card.get("primary_positive", []),
                    "concerns": card.get("concerns", []),
                    "mixed_context": card.get("mixed_context", []),
                }
                if isinstance(review, Mapping) and isinstance(card, Mapping)
                else {}
            ),
            "scoring": False,
            "deduplication_policy": (
                "same source run across recent_runs and RRDB is corroborating detail, not additive votes"
            ),
        }

    meta = bundle.setdefault("metadata", {})
    if not isinstance(meta, dict):
        raise RRDBEnrichmentError("metadata must be an object")
    source_meta = sidecar.get("source") if isinstance(sidecar.get("source"), Mapping) else {}
    meta["racereview_enrichment"] = {
        "version": VERSION,
        "status": "ACTIVE",
        "current_generation_id": reader.generation_id,
        "review_schema_version": source_meta.get("review_schema_version"),
        "review_logic_version": source_meta.get("review_logic_version"),
        "baseline_version": source_meta.get("baseline_version"),
        "next_watch_rule_version": contract.get("rule_version"),
        "as_of_exclusive": target_date,
        "horse_identity": "JRDB_BLOOD_REGISTRATION_NO",
        "name_fallback": False,
        "scoring": False,
        "target_result_exposed": False,
        "market_exposed": False,
    }
    return bundle


def main() -> int:
    p = argparse.ArgumentParser(description="Add formal RRDB evidence to RaceNote v1.0")
    p.add_argument("--bundle", type=Path, required=True)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--racereview-root", type=Path)
    source.add_argument("--racereview-current-cache", type=Path)
    p.add_argument("--racereview-drive-file-id", default=STABLE_CURRENT_FILE_ID)
    p.add_argument("--next-watch-rules", type=Path, required=True)
    p.add_argument("--work-root", type=Path, default=None)
    p.add_argument("--per-horse-limit", type=int, default=5)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    bundle = _read_json(args.bundle)
    if str(bundle.get("schema_version")) != "1.0":
        raise SystemExit("RRDB enrichment requires authoritative RaceNote v1.0")

    work_root = args.work_root
    temp = None
    if work_root is None:
        temp = tempfile.TemporaryDirectory(prefix="racenote-rrdb-")
        work_root = Path(temp.name)
    else:
        work_root.mkdir(parents=True, exist_ok=True)

    try:
        contract = load_frozen_contract(args.next_watch_rules, work_root)
        if args.racereview_root is not None:
            reader = RaceReviewReader(args.racereview_root)
        else:
            resolved = resolve_racereview_current(
                args.racereview_current_cache,
                file_id=args.racereview_drive_file_id,
            )
            reader = resolved.reader

        enriched = enrich_bundle(
            bundle,
            reader,
            contract,
            per_horse_limit=args.per_horse_limit,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(enriched, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({
            "status": "PASS",
            "version": VERSION,
            "race": enriched["race"],
            "horse_count": len(enriched["horses"]),
            "rrdb_generation_id": reader.generation_id,
            "next_watch_rule_version": contract.get("rule_version"),
            "output": str(args.output),
        }, ensure_ascii=False, default=str))
        return 0
    finally:
        if temp is not None:
            temp.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
