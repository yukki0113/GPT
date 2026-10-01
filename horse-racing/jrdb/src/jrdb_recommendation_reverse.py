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

from jrdb_recommendation_signals import (
    OPERATIONAL_LOOKBACK_DAYS,
    VERSION as SIGNAL_VERSION,
    human_summary,
    recommendation_payload,
)

VERSION = "rrdb-recommendation-reverse-v0.2"


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


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--race-date", required=True)
    p.add_argument("--paci-zip", type=Path, required=True)
    p.add_argument("--current-zip", type=Path, required=True)
    p.add_argument("--work-root", type=Path, required=True)
    p.add_argument("--output-json", type=Path, required=True)
    args = p.parse_args()

    entrants = _parse_kyi(args.paci_zip, args.work_root)
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
                no_history.append({
                    **entrant,
                    "status": "NO_PRIOR_HISTORY",
                    "lookback_days": OPERATIONAL_LOOKBACK_DAYS,
                })
                continue

            cols = [d[0] for d in cur.description]
            item = dict(zip(cols, row))
            payload = recommendation_payload(item)
            record = {
                **entrant,
                "status": payload["status"],
                "source_run": {
                    "race_date": str(item.get("race_date")),
                    "race_key": item.get("race_key"),
                    "race_horse_key": item.get("race_horse_key"),
                    "finish": item.get("finish"),
                },
                **payload,
                "human_summary": human_summary(item),
            }
            if payload["status"] == "MATCH":
                recommendations.append(record)
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
