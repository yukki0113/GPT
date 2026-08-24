#!/usr/bin/env python3
"""Build compact JRDB Analysis Lite SQLite from Core v1.2.

The first implementation intentionally consumes Core v1.2. A Raw->Analysis
path may be added after output equivalence is proven.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import sqlite3
from pathlib import Path

VERSION = "1.0"
SCHEMA_VERSION = "v1"


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build(core: Path, out: Path, schema: Path) -> dict[str, object]:
    if out.exists():
        raise SystemExit(f"Refusing to overwrite existing DB: {out}")

    conn = sqlite3.connect(out)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=MEMORY")
    conn.execute("PRAGMA synchronous=OFF")
    conn.executescript(schema.read_text(encoding="utf-8"))
    build_id = conn.execute(
        "INSERT INTO meta_analysis_build(builder_version,schema_version,source_core_sha256,started_at,status) VALUES(?,?,?,?,?)",
        (VERSION, SCHEMA_VERSION, sha256_file(core), now(), "RUNNING"),
    ).lastrowid
    conn.execute("ATTACH DATABASE ? AS core", (str(core),))

    # Calendar-year age is used for JRA aggregation.
    conn.execute(
        """
        INSERT INTO fact_entry_result_lite(
          race_date,year,venue_code,race_no,track_type,distance,condition_code,grade_code,
          race_key,horse_no,horse_id,horse_name,sex_code,age,sire_name,broodmare_sire_name,
          sire_line_code,broodmare_sire_line_code,jockey_name,running_style,distance_aptitude,
          uptrend,training_index,finish,abnormal_code,final_win_odds,final_win_popularity,
          win_payout,place_payout
        )
        SELECT
          r.race_date,
          r.year,
          r.venue_code,
          r.race_no,
          r.track_type,
          r.distance,
          r.condition_code,
          r.grade_code,
          e.race_key,
          e.horse_no,
          e.horse_id,
          e.horse_name,
          hp.sex_code,
          CASE
            WHEN hp.birth_date GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'
            THEN r.year - CAST(substr(hp.birth_date,1,4) AS INTEGER)
            ELSE NULL
          END AS age,
          hp.sire_name,
          hp.broodmare_sire_name,
          hp.sire_line_code,
          hp.broodmare_sire_line_code,
          e.jockey_name,
          e.running_style,
          e.distance_aptitude,
          e.uptrend,
          ta.training_index,
          rs.finish,
          rs.abnormal_code,
          rs.final_win_odds,
          rs.final_win_popularity,
          rs.win_payout,
          rs.place_payout
        FROM core.entry e
        JOIN core.race r ON r.race_key=e.race_key
        LEFT JOIN core.result rs ON rs.race_key=e.race_key AND rs.horse_no=e.horse_no
        LEFT JOIN core.training_analysis ta ON ta.race_key=e.race_key AND ta.horse_no=e.horse_no
        LEFT JOIN core.horse_profile_current hp ON hp.horse_id=e.horse_id
        """
    )

    row_count = conn.execute("SELECT count(*) FROM fact_entry_result_lite").fetchone()[0]
    conn.execute(
        "UPDATE meta_analysis_build SET finished_at=?,status='SUCCESS',row_count=? WHERE build_id=?",
        (now(), row_count, build_id),
    )
    conn.commit()
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    sire_nonblank = conn.execute(
        "SELECT count(*) FROM fact_entry_result_lite WHERE trim(coalesce(sire_name,''))<>''"
    ).fetchone()[0]
    bms_nonblank = conn.execute(
        "SELECT count(*) FROM fact_entry_result_lite WHERE trim(coalesce(broodmare_sire_name,''))<>''"
    ).fetchone()[0]
    conn.close()

    return {
        "rows": row_count,
        "sire_nonblank": sire_nonblank,
        "broodmare_sire_nonblank": bms_nonblank,
        "integrity_check": integrity,
        "size_bytes": out.stat().st_size,
        "source_core_sha256": sha256_file(core),
        "analysis_sha256": sha256_file(out),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--core", type=Path, required=True, help="Core v1.2 SQLite")
    ap.add_argument("--db", type=Path, required=True, help="output Analysis Lite SQLite")
    ap.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "schema" / "jrdb_analysis_schema_v1.sql",
    )
    args = ap.parse_args()
    result = build(args.core, args.db, args.schema)
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
