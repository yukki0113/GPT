#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Current RaceReviewDB recommendation selector v0.3.

Select recommendation-signal horses from one completed source date.
No future result, market, or S/A grade is used.
"""
from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path

import duckdb

from jrdb_recommendation_signals import (
    VERSION as SIGNAL_VERSION,
    human_summary,
    newspaper_comment,
    recommendation_payload,
)

VERSION = "rrdb-recommendation-select-v0.3"


class RecommendationSelectorError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RecommendationSelectorError(f"JSON object required: {path}")
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
        raise RecommendationSelectorError(f"unique RaceReviewDB root required: {roots}")
    return roots[0]


def _relation_paths(root: Path, manifest: dict[str, object], relation: str) -> list[Path]:
    relations = manifest.get("relations")
    if not isinstance(relations, dict):
        raise RecommendationSelectorError("manifest relations missing")
    meta = relations.get(relation)
    if not isinstance(meta, dict):
        raise RecommendationSelectorError(f"relation missing: {relation}")
    paths: list[Path] = []
    for partition in meta.get("partitions") or []:
        if not isinstance(partition, dict):
            continue
        relative = partition.get("relative_path")
        if not isinstance(relative, str):
            continue
        path = root / relative
        if not path.is_file():
            raise RecommendationSelectorError(f"missing relation object: {path}")
        paths.append(path)
    if not paths:
        raise RecommendationSelectorError(f"no objects for {relation}")
    return paths


def _table_sql(paths: list[Path]) -> str:
    literals = ", ".join("'" + str(path).replace("'", "''") + "'" for path in paths)
    return f"read_parquet([{literals}], union_by_name=true, hive_partitioning=false)"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True)
    p.add_argument("--current-zip", type=Path, required=True)
    p.add_argument("--work-root", type=Path, required=True)
    p.add_argument("--output-json", type=Path, required=True)
    args = p.parse_args()

    root = _race_review_root(args.current_zip, args.work_root)
    current = _read_json(root / "current.json")
    manifest_ref = current.get("manifest")
    if not isinstance(manifest_ref, str):
        raise RecommendationSelectorError("CURRENT manifest missing")
    manifest = _read_json(root / manifest_ref)
    if manifest.get("validation_status") != "PASS":
        raise RecommendationSelectorError("CURRENT manifest is not PASS")
    if args.date > str(manifest.get("period_to") or ""):
        raise RecommendationSelectorError(
            f"requested date {args.date} exceeds CURRENT period_to {manifest.get('period_to')}"
        )

    hp_sql = _table_sql(_relation_paths(root, manifest, "fact_horse_performance"))
    rc_sql = _table_sql(_relation_paths(root, manifest, "fact_race_context"))

    con = duckdb.connect(":memory:")
    try:
        cur = con.execute(f"""
        SELECT
          hp.*,
          rc.pace_balance_percentile,
          -hp.horse_adjusted_delta_per_1000m AS performance_signal
        FROM {hp_sql} hp
        LEFT JOIN {rc_sql} rc USING (race_key)
        WHERE hp.race_date = CAST(? AS DATE)
          AND hp.horse_id IS NOT NULL
          AND TRIM(hp.horse_id) <> ''
          AND COALESCE(hp.finish, 0) > 0
          AND COALESCE(hp.time_sec, 0) > 0
          AND COALESCE(hp.surface_code, '') <> '3'
        ORDER BY hp.race_key, hp.horse_no
        """, [args.date])
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]

        recommendations: list[dict[str, object]] = []
        for values in rows:
            item = dict(zip(cols, values))
            payload = recommendation_payload(item)
            if payload["status"] != "MATCH":
                continue
            recommendations.append({
                "horse_id": item.get("horse_id"),
                "horse_name": item.get("horse_name"),
                "race_key": item.get("race_key"),
                "race_horse_key": item.get("race_horse_key"),
                "horse_no": item.get("horse_no"),
                "venue_code": item.get("venue_code"),
                "surface_code": item.get("surface_code"),
                "distance_m": item.get("distance_m"),
                "declared_class_group": item.get("declared_class_group"),
                "finish": item.get("finish"),
                **payload,
                "human_summary": human_summary(item),
                "newspaper_comment": newspaper_comment(item),
            })

        result = {
            "status": "PASS" if rows else "NO_SOURCE_RACES",
            "date": args.date,
            "version": VERSION,
            "recommendation_contract_version": SIGNAL_VERSION,
            "source_generation_id": manifest.get("generation_id"),
            "source_start_count": len(rows),
            "grade_status": "DISABLED",
            "recommendations": recommendations,
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
