#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Current RRDB recommendation reverse lookup from a future PACI entry list.

For each entrant, find the latest completed flat JRA start within the canonical
730-day operational lookback and apply the current recommendation signals.
No S/A grade is produced.
"""
from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path

import duckdb

from jrdb_course_profile_identity import course_key_from_observation
from jrdb_raw import Parser, canonical_members, read_fixed_records
from jrdb_recommendation_signals import (
    OPERATIONAL_LOOKBACK_DAYS,
    VERSION as SIGNAL_VERSION,
    human_summary,
    newspaper_comment,
    recommendation_payload,
)

VERSION = "rrdb-recommendation-reverse-v0.4"
COURSE_PROFILE_MIN_SAMPLE = 4
COURSE_PROFILE_MIN_SHRUNK_DELTA = 0.10
COURSE_PROFILE_MIN_CONFIDENCE = 0.50


class RecommendationReverseError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RecommendationReverseError(f"JSON object required: {path}")
    return value


def _extract(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    with zipfile.ZipFile(source) as archive:
        archive.extractall(target)


def _race_review_root(current_zip: Path, work_root: Path) -> Path:
    target = work_root / "current"
    _extract(current_zip, target)
    roots: list[Path] = []
    for pointer in target.rglob("current.json"):
        current = _read_json(pointer)
        if current.get("artifact_type") == "jrdb_postrace_review":
            roots.append(pointer.parent)
    if len(roots) != 1:
        raise RecommendationReverseError(f"unique RaceReviewDB root required: {roots}")
    return roots[0]


def _relation_paths(root: Path, manifest: dict[str, object], relation: str) -> list[Path]:
    relations = manifest.get("relations")
    if not isinstance(relations, dict):
        raise RecommendationReverseError("manifest relations missing")
    meta = relations.get(relation)
    if not isinstance(meta, dict):
        raise RecommendationReverseError(f"relation missing: {relation}")
    paths: list[Path] = []
    for partition in meta.get("partitions") or []:
        if not isinstance(partition, dict):
            continue
        relative = partition.get("relative_path")
        if not isinstance(relative, str):
            continue
        path = root / relative
        if not path.is_file():
            raise RecommendationReverseError(f"missing relation object: {path}")
        paths.append(path)
    if not paths:
        raise RecommendationReverseError(f"no objects for {relation}")
    return paths


def _table_sql(paths: list[Path]) -> str:
    literals = ", ".join("'" + str(path).replace("'", "''") + "'" for path in paths)
    return f"read_parquet([{literals}], union_by_name=true, hive_partitioning=false)"


def _decode_name(raw: bytes) -> str:
    for encoding in ("cp932", "shift_jis"):
        try:
            return raw.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return raw.decode("cp932", errors="replace").strip()


def _parse_kyi(paci_zip: Path, work_root: Path) -> list[dict[str, object]]:
    target = work_root / "paci"
    _extract(paci_zip, target)
    files = sorted(
        path for path in target.rglob("*")
        if path.is_file() and path.name.upper().startswith("KYI")
    )
    if not files:
        raise RecommendationReverseError("PACI contains no KYI file")
    entrants: list[dict[str, object]] = []
    seen: set[str] = set()
    for path in files:
        with path.open("rb") as stream:
            for raw_line in stream:
                line = raw_line.rstrip(b"\r\n")
                if len(line) < 55:
                    continue
                venue = line[0:2].decode("ascii", errors="ignore")
                year2 = line[2:4].decode("ascii", errors="ignore")
                meeting = line[4:5].decode("ascii", errors="ignore")
                day_hex = line[5:6].decode("ascii", errors="ignore")
                race_no = line[6:8].decode("ascii", errors="ignore")
                horse_no = line[8:10].decode("ascii", errors="ignore")
                horse_id = line[10:18].decode("ascii", errors="ignore").strip()
                horse_name = _decode_name(line[18:54])
                if not horse_id:
                    continue
                race_key = venue + year2 + meeting + day_hex + race_no
                entry_key = race_key + horse_no
                if entry_key in seen:
                    continue
                seen.add(entry_key)
                entrants.append({
                    "target_race_key": race_key,
                    "target_race_horse_key": entry_key,
                    "venue_code": venue,
                    "race_no": int(race_no) if race_no.isdigit() else None,
                    "horse_no": int(horse_no) if horse_no.isdigit() else None,
                    "horse_id": horse_id,
                    "horse_name_paci": horse_name,
                })
    return entrants



def _unique_path(root: Path, name: str) -> Path:
    matches = sorted(path for path in root.rglob(name) if path.is_file())
    if len(matches) != 1:
        raise RecommendationReverseError(
            f"unique {name} required under {root}: {matches}"
        )
    return matches[0]


def _parse_target_races(
    paci_zip: Path,
) -> dict[str, dict[str, object]]:
    parser = Parser()
    races: dict[str, dict[str, object]] = {}
    with zipfile.ZipFile(paci_zip) as archive:
        members = canonical_members(archive, "BAC")
        if not members:
            raise RecommendationReverseError("PACI contains no BAC file")
        for member in members:
            for record in read_fixed_records(archive, member, "BAC"):
                row = parser.bac(record)
                key = str(row.get("race_key_raw") or "")
                if key:
                    races[key] = row
    return races


def _load_course_profile_sources(
    course_fit_root: Path,
) -> tuple[Path, list[dict[str, object]], list[dict[str, object]]]:
    candidate = _unique_path(course_fit_root, "candidate_fit_view.parquet")
    master_path = _unique_path(course_fit_root, "course_master_seed_v0_1.jsonl")
    geometry_path = _unique_path(
        course_fit_root, "course_geometry_configuration_v0_1.jsonl"
    )
    masters = [
        json.loads(line)
        for line in master_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    geometry = [
        json.loads(line)
        for line in geometry_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return candidate, masters, geometry


def _target_course_profile(
    race: dict[str, object],
    race_date: str,
    masters: list[dict[str, object]],
    geometry: list[dict[str, object]],
) -> dict[str, object]:
    venue = str(race.get("race_key_raw") or "")[:2]
    surface = str(race.get("surface_code") or "")
    distance_raw = str(race.get("distance_raw") or "")
    turn = str(race.get("turn_code") or "")
    layout = str(race.get("layout_code") or "")
    jrdb_course_code = str(race.get("course_code") or "").strip()
    if not distance_raw.isdigit():
        return {"eligible": False, "reason": "INVALID_DISTANCE"}
    course_key = course_key_from_observation(
        venue, surface, int(distance_raw), turn, layout
    )
    master = next(
        (row for row in masters if row.get("course_key") == course_key),
        None,
    )
    if master is None:
        return {"eligible": False, "reason": "COURSE_KEY_UNRESOLVED"}

    layout_variant = master.get("layout_variant")
    rows = [
        row for row in geometry
        if str(row.get("venue_code") or "") == venue
        and str(row.get("surface_code") or "") == surface
        and row.get("layout_variant") == layout_variant
        and str(row.get("jrdb_course_code") or "").strip() == jrdb_course_code
    ]
    size_values = {
        row.get("course_size_class") for row in rows
        if row.get("course_size_class") is not None
    }
    straight_values = {
        float(row["final_straight_m"]) for row in rows
        if row.get("final_straight_m") is not None
    }
    valid_from_values = {
        str(row.get("physical_valid_from")) for row in rows
        if row.get("physical_valid_from")
    }
    valid_to_values = {
        str(row.get("physical_valid_to_exclusive")) for row in rows
        if row.get("physical_valid_to_exclusive")
    }

    size = (
        next(iter(size_values)) if len(size_values) == 1
        else master.get("course_size_class")
    )
    straight = (
        next(iter(straight_values)) if len(straight_values) == 1
        else master.get("final_straight_m")
    )
    valid_from = (
        next(iter(valid_from_values)) if len(valid_from_values) == 1
        else master.get("physical_valid_from")
    )
    valid_to = (
        next(iter(valid_to_values)) if len(valid_to_values) == 1
        else master.get("physical_valid_to_exclusive")
    )
    if valid_from and race_date < str(valid_from):
        return {"eligible": False, "reason": "BEFORE_PHYSICAL_VALID_FROM"}
    if valid_to and race_date >= str(valid_to):
        return {"eligible": False, "reason": "AFTER_PHYSICAL_VALID_TO"}

    bucket = None
    if straight is not None:
        value = float(straight)
        bucket = "SHORT" if value < 350 else ("MEDIUM" if value < 450 else "LONG")
    return {
        "eligible": size == "LARGE" and bucket == "LONG",
        "course_key": course_key,
        "surface_code": surface,
        "course_size_class": size,
        "final_straight_m": straight,
        "final_straight_bucket": bucket,
        "physical_valid_from": valid_from,
        "physical_valid_to_exclusive": valid_to,
    }


def _course_profile_fit(
    con: duckdb.DuckDBPyConnection,
    *,
    horse_id: str,
    surface_code: str,
    target_date: str,
) -> dict[str, object]:
    cur = con.execute(
        """
        WITH paired AS (
          SELECT
            a.horse_id,
            a.surface_code,
            a.as_of_date,
            a.sample_count large_sample_count,
            a.shrunk_delta large_shrunk_delta,
            a.confidence large_confidence,
            b.sample_count long_sample_count,
            b.shrunk_delta long_shrunk_delta,
            b.confidence long_confidence
          FROM course_fit a
          JOIN course_fit b
            ON a.horse_id=b.horse_id
           AND a.surface_code=b.surface_code
           AND a.as_of_date=b.as_of_date
          WHERE a.fit_family='ABSOLUTE'
            AND a.feature_type='COURSE_SIZE'
            AND a.feature_value='LARGE'
            AND b.fit_family='ABSOLUTE'
            AND b.feature_type='FINAL_STRAIGHT_BUCKET'
            AND b.feature_value='LONG'
            AND a.horse_id=?
            AND a.surface_code=?
            AND a.as_of_date<=CAST(? AS DATE)
        )
        SELECT *
        FROM paired
        ORDER BY as_of_date DESC
        LIMIT 1
        """,
        [horse_id, surface_code, target_date],
    )
    row = cur.fetchone()
    if row is None:
        return {"match": False, "reason": "NO_PAIRED_FIT"}
    cols = [desc[0] for desc in cur.description]
    item = dict(zip(cols, row))
    match = (
        int(item["large_sample_count"] or 0) >= COURSE_PROFILE_MIN_SAMPLE
        and float(item["large_shrunk_delta"] or 0.0)
            >= COURSE_PROFILE_MIN_SHRUNK_DELTA
        and float(item["large_confidence"] or 0.0)
            >= COURSE_PROFILE_MIN_CONFIDENCE
        and int(item["long_sample_count"] or 0) >= COURSE_PROFILE_MIN_SAMPLE
        and float(item["long_shrunk_delta"] or 0.0)
            >= COURSE_PROFILE_MIN_SHRUNK_DELTA
        and float(item["long_confidence"] or 0.0)
            >= COURSE_PROFILE_MIN_CONFIDENCE
    )
    return {"match": match, **item}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--race-date", required=True)
    p.add_argument("--paci-zip", type=Path, required=True)
    p.add_argument("--current-zip", type=Path, required=True)
    p.add_argument("--course-fit-root", type=Path, required=True)
    p.add_argument("--work-root", type=Path, required=True)
    p.add_argument("--output-json", type=Path, required=True)
    args = p.parse_args()

    entrants = _parse_kyi(args.paci_zip, args.work_root)
    target_races = _parse_target_races(args.paci_zip)
    candidate_path, course_masters, course_geometry = _load_course_profile_sources(
        args.course_fit_root
    )
    root = _race_review_root(args.current_zip, args.work_root)
    current = _read_json(root / "current.json")
    manifest_ref = current.get("manifest")
    if not isinstance(manifest_ref, str):
        raise RecommendationReverseError("CURRENT manifest missing")
    manifest = _read_json(root / manifest_ref)
    if manifest.get("validation_status") != "PASS":
        raise RecommendationReverseError("CURRENT manifest is not PASS")

    hp_sql = _table_sql(_relation_paths(root, manifest, "fact_horse_performance"))
    rc_sql = _table_sql(_relation_paths(root, manifest, "fact_race_context"))

    con = duckdb.connect(":memory:")
    try:
        candidate_sql = str(candidate_path).replace("'", "''")
        con.execute(
            f"CREATE TEMP VIEW course_fit AS SELECT * FROM read_parquet('{candidate_sql}')"
        )
        con.execute(f"""
        CREATE TEMP VIEW hp_current AS
        SELECT
          hp.*,
          rc.pace_balance_percentile,
          -hp.horse_adjusted_delta_per_1000m AS performance_signal
        FROM {hp_sql} hp
        LEFT JOIN {rc_sql} rc USING (race_key)
        WHERE hp.horse_id IS NOT NULL
          AND TRIM(hp.horse_id) <> ''
          AND COALESCE(hp.finish, 0) > 0
          AND COALESCE(hp.time_sec, 0) > 0
          AND COALESCE(hp.surface_code, '') <> '3'
        """)

        recommendations: list[dict[str, object]] = []
        no_history: list[dict[str, object]] = []
        no_match: list[dict[str, object]] = []

        for entrant in entrants:
            target_race = target_races.get(str(entrant["target_race_key"]))
            if target_race is None:
                raise RecommendationReverseError(
                    f"target BAC row missing: {entrant['target_race_key']}"
                )
            target_profile = _target_course_profile(
                target_race,
                args.race_date,
                course_masters,
                course_geometry,
            )
            fit = _course_profile_fit(
                con,
                horse_id=str(entrant["horse_id"]),
                surface_code=str(target_profile.get("surface_code") or ""),
                target_date=args.race_date,
            )

            cur = con.execute(f"""
            SELECT *
            FROM hp_current
            WHERE horse_id=?
              AND race_date < CAST(? AS DATE)
              AND race_date >= CAST(? AS DATE) - INTERVAL '{OPERATIONAL_LOOKBACK_DAYS} days'
            ORDER BY race_date DESC, race_key DESC, horse_no DESC
            LIMIT 1
            """, [entrant["horse_id"], args.race_date, args.race_date])
            row = cur.fetchone()
            if row is None:
                item: dict[str, object] = {}
                source_run = None
            else:
                cols = [d[0] for d in cur.description]
                item = dict(zip(cols, row))
                source_run = {
                    "race_date": str(item.get("race_date")),
                    "race_key": item.get("race_key"),
                    "race_horse_key": item.get("race_horse_key"),
                    "finish": item.get("finish"),
                }

            course_profile_match = bool(
                target_profile.get("eligible") and fit.get("match")
            )
            item.update({
                "course_profile_fit_match": course_profile_match,
                "target_course_size_class": target_profile.get(
                    "course_size_class"
                ),
                "target_final_straight_bucket": target_profile.get(
                    "final_straight_bucket"
                ),
                "course_profile_large_sample_count": fit.get(
                    "large_sample_count"
                ),
                "course_profile_large_shrunk_delta": fit.get(
                    "large_shrunk_delta"
                ),
                "course_profile_large_confidence": fit.get(
                    "large_confidence"
                ),
                "course_profile_long_sample_count": fit.get(
                    "long_sample_count"
                ),
                "course_profile_long_shrunk_delta": fit.get(
                    "long_shrunk_delta"
                ),
                "course_profile_long_confidence": fit.get(
                    "long_confidence"
                ),
                "course_profile_fit_as_of_date": fit.get("as_of_date"),
            })
            payload = recommendation_payload(item)
            record = {
                **entrant,
                "status": payload["status"],
                "source_run": source_run,
                "target_course_profile": target_profile,
                "course_profile_fit": fit,
                **payload,
                "human_summary": human_summary(item),
                "newspaper_comment": newspaper_comment(item),
            }
            if payload["status"] == "MATCH":
                recommendations.append(record)
            elif row is None:
                no_history.append({
                    **record,
                    "status": "NO_PRIOR_HISTORY_NO_MATCH",
                    "lookback_days": OPERATIONAL_LOOKBACK_DAYS,
                })
            else:
                no_match.append(record)

        result = {
            "status": "PASS",
            "race_date": args.race_date,
            "version": VERSION,
            "recommendation_contract_version": SIGNAL_VERSION,
            "source_generation_id": manifest.get("generation_id"),
            "lookback_days": OPERATIONAL_LOOKBACK_DAYS,
            "grade_status": "DISABLED",
            "course_profile_fit_contract": {
                "min_sample_count": COURSE_PROFILE_MIN_SAMPLE,
                "min_shrunk_delta": COURSE_PROFILE_MIN_SHRUNK_DELTA,
                "min_confidence": COURSE_PROFILE_MIN_CONFIDENCE,
                "required_course_size": "LARGE",
                "required_final_straight_bucket": "LONG",
                "candidate_fit_path": str(candidate_path),
            },
            "entrant_count": len(entrants),
            "recommendation_count": len(recommendations),
            "no_match_count": len(no_match),
            "no_history_count": len(no_history),
            "recommendations": sorted(
                recommendations,
                key=lambda x: (
                    str(x.get("target_race_key") or ""),
                    int(x.get("horse_no") or 99),
                ),
            ),
            "no_match": no_match,
            "no_history": no_history,
        }
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(result, ensure_ascii=False, default=str))
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
