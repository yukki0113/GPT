#!/usr/bin/env python3
"""Build time-aware Debut/no-scored-history Ability feature snapshots from Index Base."""
from __future__ import annotations

import argparse
import bisect
import json
import math
import sqlite3
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

BANDWIDTHS = (200, 400, 600, 800)
BUILDER_VERSION = "build_jrdb_debut_ability_snapshot_v0_1"
SCHEMA_VERSION = "jrdb_debut_ability_snapshot_schema_v0_1"
FORMULA_VERSION = "Debut_Ability_Snapshot_Protocol_v0_1"


def _utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def _date_token(value: Any) -> str | None:
    """Normalize a date-like value to YYYYMMDD for strict chronology comparisons."""
    if value is None:
        return None
    text = str(value).strip().replace("-", "").replace("/", "")
    if len(text) < 8 or not text[:8].isdigit():
        return None
    return text[:8]


def _age_months(birth_date: Any, race_date: Any) -> float | None:
    """Calculate approximate calendar age in months from pre-race identity fields."""
    birth = _date_token(birth_date)
    target = _date_token(race_date)
    if birth is None or target is None:
        return None
    try:
        born = date(int(birth[:4]), int(birth[4:6]), int(birth[6:8]))
        raced = date(int(target[:4]), int(target[4:6]), int(target[6:8]))
    except ValueError:
        return None
    if born > raced:
        return None
    months = (raced.year - born.year) * 12 + (raced.month - born.month)
    day_fraction = (raced.day - born.day) / 31.0
    return float(months + day_fraction)


def _mean(stats: dict[Any, list[float]], key: Any) -> tuple[float | None, int]:
    """Return raw mean and sample count for one accumulated prior key."""
    values = stats.get(key)
    if not values:
        return None, 0
    return float(sum(values) / len(values)), len(values)


def _distance_kernel(
    values: list[tuple[int, float]] | None,
    target_distance: int | None,
    bandwidth: int,
) -> tuple[float | None, int, float | None]:
    """Return weighted prior mean, n and effective sample size for one distance bandwidth."""
    if not values or target_distance is None:
        return None, 0, None
    weighted_sum = 0.0
    weight_sum = 0.0
    weight_sq_sum = 0.0
    count = 0
    for history_distance, runperf in values:
        weight = math.exp(-abs(int(history_distance) - int(target_distance)) / float(bandwidth))
        if weight <= 0 or not math.isfinite(weight):
            continue
        weighted_sum += weight * float(runperf)
        weight_sum += weight
        weight_sq_sum += weight * weight
        count += 1
    if count == 0 or weight_sum <= 0 or weight_sq_sum <= 0:
        return None, 0, None
    mean = weighted_sum / weight_sum
    neff = (weight_sum * weight_sum) / weight_sq_sum
    return float(mean), count, float(neff)


def _profile_index(connection: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    """Load UKC profile observations by horse in chronological order."""
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT horse_id,data_date,horse_name,sex_code,sire_name,dam_name,
               broodmare_sire_name,birth_date,sire_line_code,broodmare_sire_line_code
        FROM horse_profile_observation
        WHERE horse_id IS NOT NULL AND horse_id<>''
        ORDER BY horse_id,data_date
        """
    ).fetchall()
    indexed: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        item = dict(row)
        item["date_token"] = _date_token(item.get("data_date"))
        if item["date_token"] is not None:
            indexed[str(item["horse_id"])].append(item)
    return dict(indexed)


def _resolve_profile(
    profiles: dict[str, list[dict[str, Any]]],
    horse_id: Any,
    race_date: Any,
) -> tuple[dict[str, Any] | None, int]:
    """Resolve latest strict-prior-day UKC profile and whether a same-day observation exists."""
    if horse_id is None:
        return None, 0
    observations = profiles.get(str(horse_id), [])
    target = _date_token(race_date)
    if not observations or target is None:
        return None, 0
    dates = [str(item["date_token"]) for item in observations]
    position = bisect.bisect_left(dates, target)
    prior = observations[position - 1] if position > 0 else None
    same_day_exists = 1 if position < len(dates) and dates[position] == target else 0
    return prior, same_day_exists


def _load_runner_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    """Load pre-race runners with target workout/training data only."""
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT
          r.race_date,r.race_key,r.year,r.venue_code,r.surface_code,r.distance_m,
          r.availability_class AS race_context_availability,
          p.horse_no,p.horse_id,p.sex_code AS pre_sex_code,p.jockey_code,p.trainer_code,
          p.carried_weight_kg,
          w.training_date,w.workout_count,w.course_code AS workout_course_code,
          w.effort_code,w.chase_state_code,w.rider_type_code,w.furlong_count,
          w.first_segment_sec,w.middle_segment_sec,w.final_segment_sec,
          w.jrdb_first_segment_index,w.jrdb_middle_segment_index,w.jrdb_final_segment_index,
          w.jrdb_workout_index AS jrdb_workout_index_cha,
          w.pair_result_code,w.pair_effort_code,w.pair_age,w.pair_class_code,
          t.training_type_code,t.training_course_type_code,
          t.used_slope,t.used_wood,t.used_dirt,t.used_turf,t.used_pool,t.used_jump,t.used_polytrack,
          t.training_distance_code,t.training_focus_code,
          t.jrdb_workout_index AS jrdb_workout_index_cyb,t.finish_index,
          t.training_volume_code,t.finish_change_code,t.training_evaluation_code,
          t.week_ago_workout_index,t.week_ago_course_code
        FROM race_context r
        JOIN runner_pre p ON p.race_key=r.race_key
        LEFT JOIN workout_main w ON w.race_key=p.race_key AND w.horse_no=p.horse_no
        LEFT JOIN training_analysis t ON t.race_key=p.race_key AND t.horse_no=p.horse_no
        ORDER BY r.race_date,r.race_key,p.horse_no
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _load_runperf(connection: sqlite3.Connection) -> dict[tuple[str, int], dict[str, Any]]:
    """Load official RunPerf labels/status keyed by race and horse."""
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT race_key,race_date,year,horse_no,horse_id,score_status,runperf_raw,score_provenance
        FROM official_runperf
        """
    ).fetchall()
    return {(str(row["race_key"]), int(row["horse_no"])): dict(row) for row in rows}


def build(index_db: Path, official_runperf_db: Path, output_db: Path, schema_path: Path) -> dict[str, Any]:
    """Build strict-prior-day pedigree and target PRE_RACE training snapshots."""
    if output_db.exists():
        output_db.unlink()

    index_connection = sqlite3.connect(f"file:{index_db}?mode=ro", uri=True)
    official_connection = sqlite3.connect(f"file:{official_runperf_db}?mode=ro", uri=True)
    output_connection = sqlite3.connect(output_db)
    try:
        runner_rows = _load_runner_rows(index_connection)
        runperf = _load_runperf(official_connection)
        profiles = _profile_index(index_connection)
        if not runner_rows:
            raise ValueError("Index Base contains no runner_pre rows")

        race_weights: dict[str, list[float]] = defaultdict(list)
        for row in runner_rows:
            weight = row.get("carried_weight_kg")
            if weight is not None and math.isfinite(float(weight)):
                race_weights[str(row["race_key"])].append(float(weight))
        race_mean_weight = {
            key: float(sum(values) / len(values)) for key, values in race_weights.items() if values
        }

        output_connection.executescript(schema_path.read_text(encoding="utf-8"))
        started_at = _utc_now()
        years = [int(row["year"]) for row in runner_rows]
        output_connection.execute(
            """
            INSERT INTO meta_debut_ability_snapshot_build(
              build_id,builder_version,schema_version,index_base_db_path,official_runperf_db_path,
              started_at,status,source_year_min,source_year_max
            ) VALUES(1,?,?,?,?,?,?,?,?)
            """,
            (
                BUILDER_VERSION,
                SCHEMA_VERSION,
                str(index_db),
                str(official_runperf_db),
                started_at,
                "BUILDING",
                min(years),
                max(years),
            ),
        )

        # Historical evidence is updated only after all targets on a date are built.
        prior_scored_count: dict[str, int] = defaultdict(int)
        prior_start_count: dict[str, int] = defaultdict(int)
        sire_stats: dict[str, list[float]] = defaultdict(list)
        damsire_stats: dict[str, list[float]] = defaultdict(list)
        sire_line_stats: dict[str, list[float]] = defaultdict(list)
        damsire_line_stats: dict[str, list[float]] = defaultdict(list)
        sire_surface_stats: dict[tuple[str, str], list[float]] = defaultdict(list)
        damsire_surface_stats: dict[tuple[str, str], list[float]] = defaultdict(list)
        sire_distance: dict[str, list[tuple[int, float]]] = defaultdict(list)
        damsire_distance: dict[str, list[tuple[int, float]]] = defaultdict(list)
        jockey_stats: dict[str, list[float]] = defaultdict(list)
        trainer_stats: dict[str, list[float]] = defaultdict(list)

        rows_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in runner_rows:
            rows_by_date[str(row["race_date"])].append(row)

        target_count = 0
        true_first_count = 0
        prior_start_no_scored_count = 0

        for race_date in sorted(rows_by_date):
            daily_rows = rows_by_date[race_date]
            daily_targets: list[tuple[dict[str, Any], dict[str, Any] | None]] = []

            for row in daily_rows:
                horse_id = row.get("horse_id")
                horse_key = str(horse_id) if horse_id not in (None, "") else ""
                scored_before = prior_scored_count.get(horse_key, 0) if horse_key else 0
                if scored_before > 0:
                    continue

                starts_before = prior_start_count.get(horse_key, 0) if horse_key else 0
                is_true_first = 1 if starts_before == 0 else 0
                if is_true_first:
                    true_first_count += 1
                else:
                    prior_start_no_scored_count += 1
                target_count += 1

                profile, same_day_profile = _resolve_profile(profiles, horse_id, race_date)
                sire = str(profile.get("sire_name") or "") if profile else ""
                damsire = str(profile.get("broodmare_sire_name") or "") if profile else ""
                sire_line = str(profile.get("sire_line_code") or "") if profile else ""
                damsire_line = str(profile.get("broodmare_sire_line_code") or "") if profile else ""
                surface = str(row.get("surface_code") or "")
                distance = int(row["distance_m"]) if row.get("distance_m") is not None else None

                sire_mean, sire_n = _mean(sire_stats, sire) if sire else (None, 0)
                damsire_mean, damsire_n = _mean(damsire_stats, damsire) if damsire else (None, 0)
                sire_line_mean, sire_line_n = _mean(sire_line_stats, sire_line) if sire_line else (None, 0)
                damsire_line_mean, damsire_line_n = _mean(damsire_line_stats, damsire_line) if damsire_line else (None, 0)
                sire_surface_mean, sire_surface_n = _mean(sire_surface_stats, (sire, surface)) if sire and surface else (None, 0)
                damsire_surface_mean, damsire_surface_n = _mean(damsire_surface_stats, (damsire, surface)) if damsire and surface else (None, 0)
                jockey_code = str(row.get("jockey_code") or "")
                trainer_code = str(row.get("trainer_code") or "")
                jockey_mean, jockey_n = _mean(jockey_stats, jockey_code) if jockey_code else (None, 0)
                trainer_mean, trainer_n = _mean(trainer_stats, trainer_code) if trainer_code else (None, 0)

                mean_weight = race_mean_weight.get(str(row["race_key"]))
                current_weight = float(row["carried_weight_kg"]) if row.get("carried_weight_kg") is not None else None
                weight_relative = (
                    current_weight - mean_weight
                    if current_weight is not None and mean_weight is not None
                    else None
                )
                profile_date = str(profile.get("data_date")) if profile else None
                validation_status = "OK" if horse_key else "HORSE_ID_MISSING"

                output_connection.execute(
                    """
                    INSERT INTO debut_target_runner(
                      race_date,race_key,horse_no,horse_id,year,venue_code,surface_code,distance_m,
                      jockey_code,trainer_code,current_carried_weight,race_mean_carried_weight,weight_relative,
                      prior_start_count,is_true_first_start,race_context_availability,
                      profile_data_date,profile_prior_day_available,profile_same_day_observation_exists,
                      sire_name,broodmare_sire_name,sire_line_code,broodmare_sire_line_code,dam_name,birth_date,sex_code,age_in_months,
                      as_of_exclusive,feature_builder_version,formula_version,source_snapshot,calculated_at,validation_status
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        race_date,str(row["race_key"]),int(row["horse_no"]),horse_id,int(row["year"]),row.get("venue_code"),
                        row.get("surface_code"),distance,row.get("jockey_code"),row.get("trainer_code"),current_weight,mean_weight,weight_relative,
                        starts_before,is_true_first,str(row["race_context_availability"]),profile_date,1 if profile else 0,same_day_profile,
                        sire or None,damsire or None,sire_line or None,damsire_line or None,
                        profile.get("dam_name") if profile else None,profile.get("birth_date") if profile else None,
                        profile.get("sex_code") if profile else row.get("pre_sex_code"),
                        _age_months(profile.get("birth_date") if profile else None,race_date),
                        race_date,BUILDER_VERSION,FORMULA_VERSION,f"{index_db.name}|{official_runperf_db.name}",_utc_now(),validation_status,
                    ),
                )

                pedigree_values: list[Any] = [
                    str(row["race_key"]),int(row["horse_no"]),
                    sire_mean,sire_n,1 if sire_n == 0 else 0,
                    damsire_mean,damsire_n,1 if damsire_n == 0 else 0,
                    sire_line_mean,sire_line_n,1 if sire_line_n == 0 else 0,
                    damsire_line_mean,damsire_line_n,1 if damsire_line_n == 0 else 0,
                    sire_surface_mean,sire_surface_n,1 if sire_surface_n == 0 else 0,
                    damsire_surface_mean,damsire_surface_n,1 if damsire_surface_n == 0 else 0,
                ]
                for bandwidth in BANDWIDTHS:
                    value, n, neff = _distance_kernel(sire_distance.get(sire), distance, bandwidth) if sire else (None, 0, None)
                    pedigree_values.extend([value,n,neff,1 if n == 0 else 0])
                for bandwidth in BANDWIDTHS:
                    value, n, neff = _distance_kernel(damsire_distance.get(damsire), distance, bandwidth) if damsire else (None, 0, None)
                    pedigree_values.extend([value,n,neff,1 if n == 0 else 0])
                placeholders = ",".join("?" for _ in pedigree_values)
                output_connection.execute(
                    f"INSERT INTO debut_pedigree_feature VALUES({placeholders})",
                    pedigree_values,
                )

                cha_present = row.get("training_date") is not None or row.get("jrdb_workout_index_cha") is not None
                cyb_present = row.get("training_type_code") is not None or row.get("jrdb_workout_index_cyb") is not None
                output_connection.execute(
                    """
                    INSERT INTO debut_training_feature VALUES(
                      ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                    )
                    """,
                    (
                        str(row["race_key"]),int(row["horse_no"]),row.get("training_date"),row.get("workout_count"),row.get("workout_course_code"),
                        row.get("effort_code"),row.get("chase_state_code"),row.get("rider_type_code"),row.get("furlong_count"),
                        row.get("first_segment_sec"),row.get("middle_segment_sec"),row.get("final_segment_sec"),
                        row.get("jrdb_first_segment_index"),row.get("jrdb_middle_segment_index"),row.get("jrdb_final_segment_index"),row.get("jrdb_workout_index_cha"),
                        row.get("pair_result_code"),row.get("pair_effort_code"),row.get("pair_age"),row.get("pair_class_code"),
                        row.get("training_type_code"),row.get("training_course_type_code"),row.get("used_slope"),row.get("used_wood"),row.get("used_dirt"),row.get("used_turf"),
                        row.get("used_pool"),row.get("used_jump"),row.get("used_polytrack"),row.get("training_distance_code"),row.get("training_focus_code"),
                        row.get("jrdb_workout_index_cyb"),row.get("finish_index"),row.get("training_volume_code"),row.get("finish_change_code"),
                        row.get("training_evaluation_code"),row.get("week_ago_workout_index"),row.get("week_ago_course_code"),
                        0 if cha_present else 1,0 if cyb_present else 1,
                    ),
                )
                output_connection.execute(
                    "INSERT INTO debut_people_prior_feature VALUES(?,?,?,?,?,?,?,?)",
                    (
                        str(row["race_key"]),int(row["horse_no"]),jockey_mean,jockey_n,1 if jockey_n == 0 else 0,
                        trainer_mean,trainer_n,1 if trainer_n == 0 else 0,
                    ),
                )
                label = runperf.get((str(row["race_key"]),int(row["horse_no"])))
                output_connection.execute(
                    "INSERT INTO debut_current_result VALUES(?,?,?,?,?)",
                    (
                        str(row["race_key"]),int(row["horse_no"]),
                        label.get("score_status") if label else None,
                        label.get("runperf_raw") if label else None,
                        label.get("score_provenance") if label else None,
                    ),
                )
                daily_targets.append((row, profile))

            # Only now make same-date starts/results available to future dates.
            for row in daily_rows:
                horse_id = row.get("horse_id")
                horse_key = str(horse_id) if horse_id not in (None, "") else ""
                if horse_key:
                    prior_start_count[horse_key] += 1
                label = runperf.get((str(row["race_key"]),int(row["horse_no"])))
                if horse_key and label and label.get("score_status") == "OK" and label.get("runperf_raw") is not None:
                    prior_scored_count[horse_key] += 1

            # Pedigree/people debut priors use true first-start labels only, after the full date is closed.
            for row, profile in daily_targets:
                horse_id = row.get("horse_id")
                horse_key = str(horse_id) if horse_id not in (None, "") else ""
                starts_before = prior_start_count.get(horse_key, 0) - (1 if horse_key else 0)
                if starts_before != 0:
                    continue
                label = runperf.get((str(row["race_key"]),int(row["horse_no"])))
                if not label or label.get("score_status") != "OK" or label.get("runperf_raw") is None:
                    continue
                runperf_value = float(label["runperf_raw"])
                if not math.isfinite(runperf_value):
                    continue
                surface = str(row.get("surface_code") or "")
                distance = int(row["distance_m"]) if row.get("distance_m") is not None else None
                if profile:
                    sire = str(profile.get("sire_name") or "")
                    damsire = str(profile.get("broodmare_sire_name") or "")
                    sire_line = str(profile.get("sire_line_code") or "")
                    damsire_line = str(profile.get("broodmare_sire_line_code") or "")
                    if sire:
                        sire_stats[sire].append(runperf_value)
                        if surface:
                            sire_surface_stats[(sire,surface)].append(runperf_value)
                        if distance is not None:
                            sire_distance[sire].append((distance,runperf_value))
                    if damsire:
                        damsire_stats[damsire].append(runperf_value)
                        if surface:
                            damsire_surface_stats[(damsire,surface)].append(runperf_value)
                        if distance is not None:
                            damsire_distance[damsire].append((distance,runperf_value))
                    if sire_line:
                        sire_line_stats[sire_line].append(runperf_value)
                    if damsire_line:
                        damsire_line_stats[damsire_line].append(runperf_value)
                jockey_code = str(row.get("jockey_code") or "")
                trainer_code = str(row.get("trainer_code") or "")
                if jockey_code:
                    jockey_stats[jockey_code].append(runperf_value)
                if trainer_code:
                    trainer_stats[trainer_code].append(runperf_value)

        output_connection.execute(
            """
            UPDATE meta_debut_ability_snapshot_build
            SET finished_at=?,status='COMPLETE',target_runner_count=?,true_first_start_count=?,
                prior_start_no_scored_history_count=?,message=? WHERE build_id=1
            """,
            (
                _utc_now(),target_count,true_first_count,prior_start_no_scored_count,
                "Strict-prior-day Debut Ability snapshot complete; same-day UKC remains diagnostic only",
            ),
        )
        output_connection.commit()
        return {
            "status":"COMPLETE",
            "target_runner_count":target_count,
            "true_first_start_count":true_first_count,
            "prior_start_no_scored_history_count":prior_start_no_scored_count,
        }
    except Exception:
        output_connection.rollback()
        raise
    finally:
        output_connection.close()
        official_connection.close()
        index_connection.close()


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-db",required=True,type=Path)
    parser.add_argument("--official-runperf-db",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).resolve().parents[1]/"schema"/"jrdb_debut_ability_snapshot_schema_v0_1.sql",
    )
    args = parser.parse_args()
    result = build(args.index_db,args.official_runperf_db,args.out,args.schema)
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
