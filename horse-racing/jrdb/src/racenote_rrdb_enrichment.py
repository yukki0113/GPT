#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Formal RaceReviewDB enrichment for authoritative RaceNote v1.0.

This module projects historical RaceReviewDB evidence and the current
RRDB recommendation signals for each target horse into RaceNote. It never reads
the target result, market, current popularity, or future RRDB rows.

The former frozen Next-Watch contract may still be supplied by legacy callers,
but it is not required by current recommendation semantics.
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

from jrdb_recommendation_signals import (
    OPERATIONAL_LOOKBACK_DAYS,
    VERSION as RECOMMENDATION_VERSION,
    human_summary as recommendation_human_summary,
    recommendation_payload,
)
from jrdb_postrace_review_reader import RaceReviewReader
from jrdb_recommendation_reverse import (
    _course_profile_fit,
    _load_course_profile_sources,
    _load_rear_srb_contract,
    _parse_target_races,
    _rear_srb_evidence,
    _target_course_profile,
)
from jrdb_race_lap_reader import RaceLapReader
from racenote_jrdb import VENUES
from racenote_horse_evidence_card import build_horse_evidence_cards
from racenote_racereview_adapter import build_racereview_evidence
from racenote_racereview_current import (
    STABLE_CURRENT_FILE_ID,
    resolve_racereview_current,
)

VERSION = "RRDB-RaceNote-0.2"


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


def _course_profile_context(
    bundles: list[dict[str, object]],
    paci_path: Path,
    course_fit_root: Path,
) -> tuple[Path, dict[str, dict[str, object]]]:
    """Resolve target-course profile once per race and bind it to each target horse."""
    if not paci_path.is_file():
        raise RRDBEnrichmentError(f"PACI ZIP not found for RRDB v0.5: {paci_path}")
    if not course_fit_root.is_dir():
        raise RRDBEnrichmentError(
            f"Horse Course Fit root not found for RRDB v0.5: {course_fit_root}"
        )

    target_dates = {
        str((bundle.get("race") or {}).get("date") or "")
        for bundle in bundles
        if isinstance(bundle.get("race"), Mapping)
    }
    if len(target_dates) != 1 or not next(iter(target_dates)):
        raise RRDBEnrichmentError(
            f"RRDB v0.5 requires one target date: {sorted(target_dates)}"
        )
    target_date_only = next(iter(target_dates))

    target_races = _parse_target_races(paci_path)
    candidate_path, masters, geometry = _load_course_profile_sources(course_fit_root)
    race_lookup: dict[tuple[str, int], dict[str, object]] = {}
    for race_key, row in target_races.items():
        if str(row.get("date_raw") or "") != target_date_only.replace("-", ""):
            continue
        if len(race_key) < 8 or not race_key[6:8].isdigit():
            continue
        venue = VENUES.get(race_key[:2], race_key[:2])
        key = (venue, int(race_key[6:8]))
        if key in race_lookup:
            raise RRDBEnrichmentError(
                f"duplicate target BAC row for {venue}{key[1]}R on {target_date_only}"
            )
        race_lookup[key] = row

    profiles: dict[str, dict[str, object]] = {}
    for bundle in bundles:
        race = bundle.get("race")
        horses = bundle.get("horses")
        if not isinstance(race, Mapping) or not isinstance(horses, list):
            raise RRDBEnrichmentError("RaceNote bundle is missing race/horses")
        target_date = str(race.get("date") or "")
        key = (str(race.get("venue") or ""), int(race.get("race_no") or 0))
        target_race = race_lookup.get(key)
        if target_race is None:
            raise RRDBEnrichmentError(
                f"RRDB v0.5 target BAC row missing for {key[0]}{key[1]}R"
            )
        profile = _target_course_profile(
            target_race,
            target_date,
            masters,
            geometry,
        )
        for raw in horses:
            if not isinstance(raw, Mapping):
                continue
            basic = _horse_basic(raw)
            horse_id = str(basic.get("horse_id") or "").strip()
            if not horse_id:
                continue
            existing = profiles.get(horse_id)
            if existing is not None and existing != profile:
                raise RRDBEnrichmentError(
                    f"horse appears with multiple target course profiles: {horse_id}"
                )
            profiles[horse_id] = profile
    return candidate_path, profiles



def _attach_race_lap_contexts(
    bundles: list[dict[str, object]],
    race_lap_reader: RaceLapReader,
    target_date: str,
) -> dict[str, int]:
    """Attach historical source-race shape to PACI recent runs with one batch lookup."""
    refs: list[str] = []
    runs: list[dict[str, object]] = []
    for bundle in bundles:
        horses = bundle.get("horses")
        if not isinstance(horses, list):
            continue
        for horse in horses:
            if not isinstance(horse, dict):
                continue
            recent = horse.get("recent_runs")
            if not isinstance(recent, list):
                continue
            for run in recent:
                if not isinstance(run, dict):
                    continue
                race = run.get("race")
                if not isinstance(race, Mapping):
                    continue
                race_key = str(race.get("race_key") or "").strip()
                race_date = str(race.get("date") or "").strip()
                if not race_key:
                    continue
                if not race_date or race_date >= target_date:
                    raise RRDBEnrichmentError(
                        f"RaceLap recent-run leakage/invalid date: key={race_key} "
                        f"source_date={race_date!r} target_date={target_date}"
                    )
                refs.append(race_key)
                runs.append(run)

    contexts = race_lap_reader.get_race_contexts(refs)
    found = 0
    missing = 0
    for run in runs:
        race = run["race"]
        race_key = str(race["race_key"])
        race_date = str(race["date"])
        context = contexts.get(race_key)
        if context is None:
            run["race_structure"] = {
                "source": "JRDB_RaceLapReader_v0.1",
                "coverage": {"status": "NOT_FOUND"},
                "lap_shape": None,
                "srb_context": None,
            }
            missing += 1
            continue

        context_race = context.get("race")
        if not isinstance(context_race, Mapping):
            raise RRDBEnrichmentError(f"RaceLap context race missing: {race_key}")
        context_date = str(context_race.get("race_date") or "")
        if context_date != race_date or context_date >= target_date:
            raise RRDBEnrichmentError(
                f"RaceLap source binding mismatch/leakage: key={race_key} "
                f"recent_date={race_date} racelap_date={context_date} "
                f"target_date={target_date}"
            )
        run["race_structure"] = {
            "source": "JRDB_RaceLapReader_v0.1",
            "coverage": context.get("coverage"),
            "lap_shape": context.get("shape"),
            "srb_context": context.get("srb_context"),
            "policy": context.get("policy"),
            "provenance": context.get("provenance"),
        }
        found += 1

    return {
        "requested_run_count": len(runs),
        "unique_race_key_count": len(set(refs)),
        "found_run_count": found,
        "missing_run_count": missing,
    }

def _latest_recommendation(
    reader: RaceReviewReader,
    horse_ids: list[str],
    target_date: str,
    *,
    candidate_fit_path: Path,
    target_profiles: Mapping[str, Mapping[str, object]],
    race_lap_reader: RaceLapReader | None = None,
    rear_srb_contract: Mapping[str, object] | None = None,
) -> dict[str, dict[str, object]]:
    """Apply RRDB v0.5 signals to latest prior run plus target-course fit evidence."""
    hp = _table_sql(_relation_paths(reader, "fact_horse_performance"))
    rc = _table_sql(_relation_paths(reader, "fact_race_context"))
    con = duckdb.connect(":memory:")
    try:
        candidate_sql = str(candidate_fit_path).replace("'", "''")
        con.execute(
            f"CREATE TEMP VIEW course_fit AS "
            f"SELECT * FROM read_parquet('{candidate_sql}')"
        )
        con.execute(f"""
        CREATE TEMP VIEW hp_valid AS
        SELECT
          hp.*,
          rc.pace_balance_percentile,
          -hp.horse_adjusted_delta_per_1000m AS performance_signal
        FROM {hp} hp
        LEFT JOIN {rc} rc USING (race_key)
        WHERE hp.horse_id IS NOT NULL
          AND TRIM(hp.horse_id) <> ''
          AND COALESCE(hp.finish, 0) > 0
          AND COALESCE(hp.time_sec, 0) > 0
          AND COALESCE(hp.surface_code, '') <> '3'
        """)

        result: dict[str, dict[str, object]] = {}
        for horse_id in sorted(set(horse_ids)):
            profile = target_profiles.get(horse_id)
            if not isinstance(profile, Mapping):
                raise RRDBEnrichmentError(
                    f"RRDB v0.5 target course profile missing: {horse_id}"
                )
            fit = _course_profile_fit(
                con,
                horse_id=horse_id,
                surface_code=str(profile.get("surface_code") or ""),
                target_date=target_date,
            )
            if fit.get("as_of_date") is not None:
                fit["as_of_date"] = str(fit["as_of_date"])

            cur = con.execute(f"""
            SELECT *
            FROM hp_valid
            WHERE horse_id=?
              AND race_date < CAST(? AS DATE)
              AND race_date >= CAST(? AS DATE)
                  - INTERVAL '{OPERATIONAL_LOOKBACK_DAYS} days'
            ORDER BY race_date DESC, race_key DESC, horse_no DESC
            LIMIT 1
            """, [horse_id, target_date, target_date])
            row = cur.fetchone()
            if row is None:
                item: dict[str, object] = {}
                source_run = None
            else:
                names = [d[0] for d in cur.description]
                item = dict(zip(names, row))
                source_run = {
                    "race_date": str(item.get("race_date")),
                    "race_key": item.get("race_key"),
                    "surface_code": item.get("surface_code"),
                    "distance_m": item.get("distance_m"),
                    "finish": item.get("finish"),
                    "winner_gap_sec": item.get("winner_gap_sec"),
                    "pace_balance_percentile": item.get("pace_balance_percentile"),
                    "corner4_frontness": item.get("corner4_frontness"),
                    "last3f_speed_percentile": item.get("last3f_speed_percentile"),
                    "performance_signal": item.get("performance_signal"),
                    "time_class_equivalent": item.get("time_class_equivalent"),
                    "time_class_equivalent_numeric": item.get(
                        "time_class_equivalent_numeric"
                    ),
                }

            course_profile_match = bool(
                profile.get("eligible") and fit.get("match")
            )
            if race_lap_reader is not None and rear_srb_contract is not None:
                rear_srb = _rear_srb_evidence(
                    race_lap_reader,
                    dict(rear_srb_contract),
                    source_run,
                )
            else:
                rear_srb = {"match": False, "reason": "RACE_LAP_CONTEXT_NOT_PROVIDED"}
            item.update({
                "rear_srb_q20_match": rear_srb.get("match") is True,
                "rear_srb_early_late_delta_sec": rear_srb.get(
                    "early_late_delta_sec"
                ),
                "rear_srb_q20_sec": rear_srb.get("q20_sec"),
                "rear_srb_distance_bucket": rear_srb.get("distance_bucket"),
                "rear_srb_reference_race_count": rear_srb.get(
                    "reference_race_count"
                ),
                "course_profile_fit_match": course_profile_match,
                "target_course_size_class": profile.get("course_size_class"),
                "target_final_straight_bucket": profile.get(
                    "final_straight_bucket"
                ),
                "course_profile_large_sample_count": fit.get(
                    "large_sample_count"
                ),
                "course_profile_large_shrunk_delta": fit.get(
                    "large_shrunk_delta"
                ),
                "course_profile_large_confidence": fit.get("large_confidence"),
                "course_profile_long_sample_count": fit.get(
                    "long_sample_count"
                ),
                "course_profile_long_shrunk_delta": fit.get(
                    "long_shrunk_delta"
                ),
                "course_profile_long_confidence": fit.get("long_confidence"),
                "course_profile_fit_as_of_date": fit.get("as_of_date"),
            })
            payload = recommendation_payload(item)
            status = payload["status"]
            if row is None and status != "MATCH":
                status = "NO_PRIOR_HISTORY"
            result[horse_id] = {
                **payload,
                "status": status,
                "human_summary": recommendation_human_summary(item),
                "lookback_days": OPERATIONAL_LOOKBACK_DAYS,
                "source_run": source_run,
                "target_course_profile": dict(profile),
                "course_profile_fit": fit,
                "rear_srb": rear_srb,
            }
        return result
    finally:
        con.close()

def _apply_bundle_enrichment(
    bundle: dict[str, object],
    reader: RaceReviewReader,
    recommendation: Mapping[str, dict[str, object]],
    contract: Mapping[str, object] | None = None,
    *,
    per_horse_limit: int = 5,
) -> dict[str, object]:
    """Apply RRDB evidence using a precomputed target-date Next-Watch map."""
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
            "recommendation": recommendation.get(
                horse_id,
                {
                    "status": "NO_HORSE_ID" if not horse_id else "NO_PRIOR_HISTORY",
                    "contract_version": RECOMMENDATION_VERSION,
                    "grade": None,
                    "grade_status": "DISABLED",
                    "matched_signal_ids": [],
                    "matched_signal_count": 0,
                    "signals": [],
                    "human_summary": None,
                    "lookback_days": OPERATIONAL_LOOKBACK_DAYS,
                },
            ),
            "next_watch": {
                "status": "DEPRECATED_REPLACED_BY_RECOMMENDATION",
                "grade": None,
                "grade_status": "DISABLED",
                "replacement": "recommendation",
            },
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
        "recommendation_contract_version": RECOMMENDATION_VERSION,
        "recommendation_grade_status": "DISABLED",
        "operational_lookback_days": OPERATIONAL_LOOKBACK_DAYS,
        "legacy_next_watch_rule_version": (contract or {}).get("rule_version"),
        "legacy_next_watch_status": "HISTORICAL_COMPATIBILITY_ONLY",
        "as_of_exclusive": target_date,
        "horse_identity": "JRDB_BLOOD_REGISTRATION_NO",
        "name_fallback": False,
        "scoring": False,
        "target_result_exposed": False,
        "market_exposed": False,
    }
    return bundle


def enrich_bundle(
    bundle: dict[str, object],
    reader: RaceReviewReader,
    contract: Mapping[str, object] | None = None,
    *,
    paci_path: Path,
    course_fit_root: Path,
    race_lap_parquet: Path,
    per_horse_limit: int = 5,
) -> dict[str, object]:
    """Enrich one authoritative RaceNote bundle under the current RRDB contract."""
    return enrich_bundles(
        [bundle],
        reader,
        contract,
        paci_path=paci_path,
        course_fit_root=course_fit_root,
        race_lap_parquet=race_lap_parquet,
        per_horse_limit=per_horse_limit,
    )[0]


def enrich_bundles(
    bundles: list[dict[str, object]],
    reader: RaceReviewReader,
    contract: Mapping[str, object] | None = None,
    *,
    paci_path: Path,
    course_fit_root: Path,
    race_lap_parquet: Path,
    per_horse_limit: int = 5,
) -> list[dict[str, object]]:
    """Enrich one target day with RRDB v0.5 prior-run and Course Fit evidence."""
    if not bundles:
        return []

    if RECOMMENDATION_VERSION != "rrdb-recommendation-signals-v0.5":
        raise RRDBEnrichmentError(
            f"unsupported operational recommendation contract: {RECOMMENDATION_VERSION}"
        )

    target_dates: set[str] = set()
    horse_ids: list[str] = []
    for bundle in bundles:
        if str(bundle.get("schema_version")) != "1.0":
            raise RRDBEnrichmentError(
                "RRDB daily enrichment requires authoritative RaceNote v1.0"
            )
        race = bundle.get("race")
        horses = bundle.get("horses")
        if not isinstance(race, Mapping) or not isinstance(horses, list):
            raise RRDBEnrichmentError("RaceNote bundle missing race/horses")
        target_date = str(race.get("date") or "")
        if not target_date:
            raise RRDBEnrichmentError("RaceNote target date missing")
        target_dates.add(target_date)
        for raw in horses:
            if not isinstance(raw, Mapping):
                continue
            basic = _horse_basic(raw)
            horse_id = str(basic.get("horse_id") or "").strip()
            if horse_id:
                horse_ids.append(horse_id)

    if len(target_dates) != 1:
        raise RRDBEnrichmentError(
            f"daily RRDB enrichment requires one target date: {sorted(target_dates)}"
        )

    candidate_fit_path, target_profiles = _course_profile_context(
        bundles,
        paci_path,
        course_fit_root,
    )
    target_date = next(iter(target_dates))
    if not race_lap_parquet.is_file():
        raise RRDBEnrichmentError(
            f"RaceLap Parquet not found for RRDB v0.5: {race_lap_parquet}"
        )
    race_lap_reader = RaceLapReader.from_parquet(race_lap_parquet)
    race_lap_context_report = _attach_race_lap_contexts(
        bundles,
        race_lap_reader,
        target_date,
    )
    rear_srb_contract = _load_rear_srb_contract()
    recommendation = _latest_recommendation(
        reader,
        sorted(set(horse_ids)),
        target_date,
        candidate_fit_path=candidate_fit_path,
        target_profiles=target_profiles,
        race_lap_reader=race_lap_reader,
        rear_srb_contract=rear_srb_contract,
    )
    enriched = [
        _apply_bundle_enrichment(
            bundle,
            reader,
            recommendation,
            contract,
            per_horse_limit=per_horse_limit,
        )
        for bundle in bundles
    ]
    for bundle in enriched:
        meta = bundle.setdefault("metadata", {})
        if isinstance(meta, dict):
            meta["race_lap_enrichment"] = {
                "version": "RaceNote-SRB-RaceLap-Context-0.1",
                "reader_contract": "JRDB RaceLapReader v0.1",
                "as_of_exclusive": target_date,
                "source_run_context_only": True,
                "scoring": False,
                **race_lap_context_report,
            }
    return enriched
def main() -> int:
    p = argparse.ArgumentParser(description="Add formal RRDB evidence to RaceNote v1.0")
    p.add_argument("--bundle", type=Path, required=True)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument("--racereview-root", type=Path)
    source.add_argument("--racereview-current-cache", type=Path)
    p.add_argument("--racereview-drive-file-id", default=STABLE_CURRENT_FILE_ID)
    p.add_argument("--paci", type=Path, required=True)
    p.add_argument("--course-fit-root", type=Path, required=True)
    p.add_argument("--race-lap-parquet", type=Path, required=True)
    p.add_argument(
        "--next-watch-rules",
        type=Path,
        required=False,
        default=None,
        help="Deprecated legacy compatibility input; current RRDB recommendations do not require it.",
    )
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
        contract = (
            load_frozen_contract(args.next_watch_rules, work_root)
            if args.next_watch_rules is not None
            else None
        )
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
            paci_path=args.paci,
            course_fit_root=args.course_fit_root,
            race_lap_parquet=args.race_lap_parquet,
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
            "recommendation_contract_version": RECOMMENDATION_VERSION,
            "recommendation_grade_status": "DISABLED",
            "legacy_next_watch_rule_version": (contract or {}).get("rule_version"),
            "output": str(args.output),
        }, ensure_ascii=False, default=str))
        return 0
    finally:
        if temp is not None:
            temp.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
