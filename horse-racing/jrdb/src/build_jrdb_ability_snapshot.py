#!/usr/bin/env python3
"""Build leakage-safe pre-race Ability feature snapshots from audited inputs."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import math
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

VERSION = "0.1.0"
FORMULA_VERSION = "ability_snapshot_pre_model_v0.1"
GOING_AVAILABILITY = "UNAVAILABLE_NO_VERIFIED_PRE_RACE_TARGET_GOING"


def _sha256(path: Path) -> str:
    """Return a deterministic checksum for recorded source provenance."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _finite(value: Any) -> bool:
    """Return whether a nullable value is a finite numeric value."""
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _mean(values: list[float]) -> float | None:
    """Return a nullable arithmetic mean."""
    return sum(values) / len(values) if values else None


def _weighted(values: list[tuple[float, float]]) -> tuple[float | None, float | None]:
    """Return weighted mean and effective sample size for positive weights."""
    total = sum(weight for _, weight in values)
    squared = sum(weight * weight for _, weight in values)
    if total <= 0.0 or squared <= 0.0:
        return None, None
    return sum(value * weight for value, weight in values) / total, total * total / squared


def _median(values: list[float]) -> float | None:
    """Return the conventional median without introducing a numpy dependency."""
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _days_between(older: str | None, newer: str) -> int | None:
    """Return calendar rest days when both ISO dates are available."""
    if not older:
        return None
    return (dt.date.fromisoformat(newer) - dt.date.fromisoformat(older)).days


def _candidate_recent(history: list[dict[str, Any]], decay: float) -> tuple[float | None, int, float | None, int]:
    """Calculate one newest-first geometric recent-performance candidate."""
    rows = history[-5:]
    weighted = [(float(row["score"]), decay ** index) for index, row in enumerate(reversed(rows))]
    value, neff = _weighted(weighted)
    return value, len(rows), neff, 0 if value is not None else 1


def _features(history: list[dict[str, Any]], target: sqlite3.Row, jockey: dict[str, Any]) -> dict[str, Any]:
    """Build only transparent, strictly prior-date feature candidates for one runner."""
    recent = history[-5:]
    aptitude = history[-12:]
    values = [float(row["score"]) for row in recent]
    all_values = [float(row["score"]) for row in aptitude]
    result: dict[str, Any] = {
        "career_scored_run_count": len(history), "recent_scored_run_count": len(recent),
        "last_scored_run_date": history[-1]["race_date"] if history else None,
        "rest_days": _days_between(history[-1]["race_date"], target["race_date"]) if history else None,
        "is_debut": 1 if not history else 0,
        "peak_best1_last5": max(values) if values else None,
        "peak_best2_mean_last5": _mean(sorted(values, reverse=True)[:2]),
        "performance_mad_last5": None, "performance_mad_last5_n": len(recent),
        "performance_mad_last5_missing": 1,
        "surface_same_mean_raw": None, "surface_overall_mean_raw": _mean(all_values),
        "surface_fit_delta_raw": None, "surface_fit_n": 0, "surface_fit_neff": None, "surface_fit_missing": 1,
        "exact_distance_count": 0, "nearest_historical_distance_diff_m": None,
        "course_exact_mean_raw": None, "course_exact_delta_raw": None, "course_exact_n": 0,
        "course_exact_neff": None, "course_surface_backoff_mean_raw": None, "course_fit_missing": 1,
        "going_same_mean_raw": None, "going_same_n": 0, "going_fit_missing": 1,
        "going_target_availability": GOING_AVAILABILITY,
        "jockey_residual_mean_raw": jockey["mean"], "jockey_residual_n": jockey["n"],
        "jockey_residual_last_date": jockey["last_date"], "jockey_residual_missing": 0 if jockey["mean"] is not None else 1,
        "recent_history_max_date": history[-1]["race_date"] if history else None,
        "aptitude_history_max_date": aptitude[-1]["race_date"] if aptitude else None,
        "jockey_history_max_date": jockey["last_date"],
    }
    for decay, label in ((0.70, "d070"), (0.80, "d080"), (0.90, "d090"), (1.00, "d100")):
        value, n, neff, missing = _candidate_recent(history, decay)
        result[f"recent_perf_{label}"] = value
        result[f"recent_perf_{label}_n"] = n
        result[f"recent_perf_{label}_neff"] = neff
        result[f"recent_perf_{label}_missing"] = missing
    if len(values) >= 3:
        center = _median(values)
        result["performance_mad_last5"] = _median([abs(value - float(center)) for value in values])
        result["performance_mad_last5_missing"] = 0
    surface = str(target["surface_code"] or "")
    same_surface = [float(row["score"]) for row in aptitude if str(row["surface_code"] or "") == surface]
    if same_surface:
        result["surface_same_mean_raw"] = _mean(same_surface)
        result["surface_fit_delta_raw"] = result["surface_same_mean_raw"] - float(result["surface_overall_mean_raw"])
        result["surface_fit_n"] = len(same_surface)
        result["surface_fit_neff"] = float(len(same_surface))
        result["surface_fit_missing"] = 0
    distance = target["distance_m"]
    differences = [abs(int(row["distance_m"]) - int(distance)) for row in aptitude if row["distance_m"] is not None and distance is not None]
    result["exact_distance_count"] = sum(1 for diff in differences if diff == 0)
    result["nearest_historical_distance_diff_m"] = min(differences) if differences else None
    for bandwidth in (200, 400, 600, 800):
        label = f"d{bandwidth}"
        weighted = []
        for row in aptitude:
            if row["distance_m"] is None or distance is None:
                continue
            weight = math.exp(-abs(int(row["distance_m"]) - int(distance)) / bandwidth)
            weighted.append((float(row["score"]), weight))
        mean, neff = _weighted(weighted)
        result[f"distance_{label}_mean_raw"] = mean
        result[f"distance_{label}_delta_raw"] = mean - float(result["surface_overall_mean_raw"]) if mean is not None and result["surface_overall_mean_raw"] is not None else None
        result[f"distance_{label}_n"] = len(weighted)
        result[f"distance_{label}_neff"] = neff
        result[f"distance_{label}_missing"] = 0 if mean is not None else 1
    venue = str(target["venue_code"] or "")
    exact = [float(row["score"]) for row in aptitude if str(row["venue_code"] or "") == venue and str(row["surface_code"] or "") == surface]
    backoff = [float(row["score"]) for row in aptitude if str(row["surface_code"] or "") == surface]
    if exact:
        result["course_exact_mean_raw"] = _mean(exact)
        result["course_exact_delta_raw"] = result["course_exact_mean_raw"] - float(result["surface_overall_mean_raw"])
        result["course_exact_n"] = len(exact)
        result["course_exact_neff"] = float(len(exact))
    if backoff:
        result["course_surface_backoff_mean_raw"] = _mean(backoff)
        result["course_fit_missing"] = 0
    return result


def _load_targets(index: sqlite3.Connection) -> list[sqlite3.Row]:
    """Load the full pre-race runner universe without target result columns."""
    return index.execute("""
      SELECT r.race_date,r.year,r.race_key,r.venue_code,r.surface_code,r.distance_m,
             r.availability_class,p.horse_no,p.horse_id,p.jockey_code,p.carried_weight_kg
      FROM race_context r JOIN runner_pre p ON p.race_key=r.race_key
      ORDER BY r.race_date,r.race_key,p.horse_no
    """).fetchall()


def _load_events(index: sqlite3.Connection, official: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    """Load scored historical outcomes with only context required for history features."""
    source = official.execute("""
      SELECT race_key,race_date,horse_no,horse_id,runperf_raw
      FROM official_runperf WHERE score_status='OK' AND runperf_raw IS NOT NULL
      ORDER BY race_date,race_key,horse_no
    """).fetchall()
    context = {
        (str(row[0]), int(row[1])): row
        for row in index.execute("""
          SELECT p.race_key,p.horse_no,r.venue_code,r.surface_code,r.distance_m,p.jockey_code
          FROM runner_pre p JOIN race_context r ON r.race_key=p.race_key
        """).fetchall()
    }
    events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source:
        item = context.get((str(row["race_key"]), int(row["horse_no"])))
        if item is None or not row["horse_id"]:
            continue
        events[str(row["race_date"])].append({
            "race_key": str(row["race_key"]), "race_date": str(row["race_date"]), "horse_no": int(row["horse_no"]),
            "horse_id": str(row["horse_id"]), "score": float(row["runperf_raw"]),
            "venue_code": item[2], "surface_code": item[3], "distance_m": item[4], "jockey_code": item[5],
        })
    return events


def build(index_db: Path, official_db: Path, output_db: Path, schema: Path) -> dict[str, Any]:
    """Materialize a snapshot using date-batched updates to exclude same-day results."""
    if output_db.exists():
        output_db.unlink()
    index = sqlite3.connect(f"file:{index_db}?mode=ro", uri=True)
    index.row_factory = sqlite3.Row
    official = sqlite3.connect(f"file:{official_db}?mode=ro", uri=True)
    official.row_factory = sqlite3.Row
    target = sqlite3.connect(output_db)
    target.row_factory = sqlite3.Row
    try:
        target.executescript(schema.read_text(encoding="utf-8"))
        targets = _load_targets(index)
        events = _load_events(index, official)
        by_date: dict[str, list[sqlite3.Row]] = defaultdict(list)
        for row in targets:
            by_date[str(row["race_date"])].append(row)
        snapshot = f"index_base:{_sha256(index_db)};official_runperf:{_sha256(official_db)}"
        now = dt.datetime.now().isoformat(timespec="seconds")
        source_years = [int(row["year"]) for row in targets]
        target.execute("""INSERT INTO meta_ability_snapshot_build(
          build_id,builder_version,schema_version,index_base_db_path,index_base_db_sha256,
          official_runperf_db_path,official_runperf_db_sha256,source_year_min,source_year_max,started_at,status
        ) VALUES(1,?,?,?,?,?,?,?,?,?,?)""", (VERSION,"0.1",str(index_db),_sha256(index_db),str(official_db),_sha256(official_db),min(source_years),max(source_years),now,"RUNNING"))
        horse_history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        jockey_state: dict[str, dict[str, Any]] = defaultdict(lambda: {"sum": 0.0, "n": 0, "last_date": None})
        for race_date in sorted(by_date):
            weights: dict[str, tuple[float | None, int]] = {}
            grouped: dict[str, list[sqlite3.Row]] = defaultdict(list)
            for row in by_date[race_date]:
                grouped[str(row["race_key"])].append(row)
            for race_key, runners in grouped.items():
                valid = [float(r["carried_weight_kg"]) for r in runners if _finite(r["carried_weight_kg"])]
                mean = _mean(valid)
                for r in runners:
                    weights[f"{race_key}:{r['horse_no']}"] = (mean, len(valid))
            for row in by_date[race_date]:
                horse_id = str(row["horse_id"] or "")
                hist = horse_history[horse_id] if horse_id else []
                state = jockey_state[str(row["jockey_code"] or "")]
                jockey = {"mean": state["sum"] / state["n"] if state["n"] else None, "n": state["n"], "last_date": state["last_date"]}
                feature = _features(hist, row, jockey)
                mean_weight, weight_n = weights[f"{row['race_key']}:{row['horse_no']}"]
                current_weight = float(row["carried_weight_kg"]) if _finite(row["carried_weight_kg"]) else None
                relative = current_weight - mean_weight if current_weight is not None and mean_weight is not None else None
                valid_context = str(row["availability_class"]) == "PRE_RACE"
                status = "OK" if valid_context else "EXCLUDED_CURRENT_RESULT_FALLBACK"
                target.execute("""INSERT INTO ability_target_runner VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    row["race_date"],row["race_key"],row["horse_no"],row["horse_id"],row["year"],row["venue_code"],row["surface_code"],row["distance_m"],row["jockey_code"],row["availability_class"],current_weight,mean_weight,weight_n,relative,0 if relative is not None else 1,row["race_date"],VERSION,FORMULA_VERSION,snapshot,now,status))
                columns = list(feature)
                target.execute(f"INSERT INTO ability_feature_snapshot(race_key,horse_no,{','.join(columns)}) VALUES ({','.join('?' for _ in range(2+len(columns)))})", (row["race_key"],row["horse_no"],*(feature[key] for key in columns)))
            for event in events.get(race_date, []):
                prior = horse_history[event["horse_id"]]
                baseline = _mean([float(item["score"]) for item in prior[-5:]])
                if baseline is not None and event["jockey_code"]:
                    residual = event["score"] - baseline
                    state = jockey_state[str(event["jockey_code"])]
                    state["sum"] += residual
                    state["n"] += 1
                    state["last_date"] = race_date
                horse_history[event["horse_id"]].append(event)
        target.executemany(
            "INSERT INTO ability_current_result(race_key,horse_no,score_status,official_runperf_raw,score_provenance) VALUES(?,?,?,?,?)",
            official.execute("SELECT race_key,horse_no,score_status,runperf_raw,score_provenance FROM official_runperf").fetchall(),
        )
        target.execute("UPDATE meta_ability_snapshot_build SET finished_at=?,status='SUCCESS',target_runner_count=?,message=? WHERE build_id=1", (dt.datetime.now().isoformat(timespec="seconds"),len(targets),"Strict prior-date Ability snapshot; target going unavailable by verified PRE_RACE source."))
        target.commit()
        return {"status":"SUCCESS","target_runner_count":len(targets),"going_target_availability":GOING_AVAILABILITY}
    except Exception:
        target.rollback()
        raise
    finally:
        index.close(); official.close(); target.close()


def main() -> int:
    """Run the builder from the command line."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-db", required=True, type=Path)
    parser.add_argument("--official-runperf-db", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--schema", type=Path, default=Path(__file__).resolve().parents[1] / "schema/jrdb_ability_snapshot_schema_v0_1.sql")
    args = parser.parse_args()
    print(build(args.index_db,args.official_runperf_db,args.out,args.schema))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
