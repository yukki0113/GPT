#!/usr/bin/env python3
"""Build compact yearly JRDB stats marts from one or more Analysis Lite v1.1 shards."""
from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
from pathlib import Path

VERSION = "1.1"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--analysis", nargs="+", type=Path, required=True)
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument(
        "--schema",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "schema" / "jrdb_stats_mart_schema_v1_1.sql",
    )
    args = ap.parse_args()

    if args.db.exists():
        raise SystemExit(f"Refusing to overwrite existing DB: {args.db}")

    years_by_file: list[tuple[Path, set[int]]] = []
    all_years: set[int] = set()
    for path in args.analysis:
        conn = sqlite3.connect(path)
        years = {row[0] for row in conn.execute("SELECT DISTINCT year FROM fact_entry_result_lite")}
        conn.close()
        overlap = all_years & years
        if overlap:
            raise SystemExit(f"Overlapping years across Analysis shards: {sorted(overlap)}")
        all_years |= years
        years_by_file.append((path, years))

    out = sqlite3.connect(args.db)
    out.executescript(args.schema.read_text(encoding="utf-8"))
    build_id = out.execute(
        "INSERT INTO meta_mart_build(builder_version,started_at,source_files,source_years,status) VALUES(?,?,?,?,?)",
        (
            VERSION,
            dt.datetime.now().isoformat(timespec="seconds"),
            ",".join(str(path) for path, _ in years_by_file),
            ",".join(map(str, sorted(all_years))),
            "RUNNING",
        ),
    ).lastrowid

    base_measures = """
      count(*),sum(finish=1),sum(finish=2),sum(finish=3),sum(finish between 1 and 3),
      sum(coalesce(win_payout,0)),sum(coalesce(place_payout,0))
    """
    sire_sql = f"""
      SELECT year,venue_code,track_type,distance,coalesce(track_condition_code,''),sire_name,
             {base_measures}
      FROM fact_entry_result_lite
      WHERE trim(coalesce(sire_name,''))<>''
      GROUP BY year,venue_code,track_type,distance,coalesce(track_condition_code,''),sire_name
    """
    jockey_sql = f"""
      SELECT year,venue_code,track_type,distance,coalesce(track_condition_code,''),jockey_name,
             {base_measures}
      FROM fact_entry_result_lite
      WHERE trim(coalesce(jockey_name,''))<>''
      GROUP BY year,venue_code,track_type,distance,coalesce(track_condition_code,''),jockey_name
    """
    frame_sql = f"""
      SELECT year,venue_code,track_type,distance,coalesce(track_condition_code,''),frame_no,
             {base_measures}
      FROM fact_entry_result_lite
      WHERE frame_no IS NOT NULL
      GROUP BY year,venue_code,track_type,distance,coalesce(track_condition_code,''),frame_no
    """

    sire_rows = []
    jockey_rows = []
    frame_rows = []
    for path, _ in years_by_file:
        conn = sqlite3.connect(path)
        sire_rows.extend(conn.execute(sire_sql))
        jockey_rows.extend(conn.execute(jockey_sql))
        frame_rows.extend(conn.execute(frame_sql))
        conn.close()

    out.executemany(
        "INSERT INTO mart_sire_yearly VALUES(" + ",".join("?" * 13) + ")",
        sire_rows,
    )
    out.executemany(
        "INSERT INTO mart_jockey_yearly VALUES(" + ",".join("?" * 13) + ")",
        jockey_rows,
    )
    out.executemany(
        "INSERT INTO mart_frame_yearly VALUES(" + ",".join("?" * 13) + ")",
        frame_rows,
    )
    out.execute(
        "UPDATE meta_mart_build SET finished_at=?,status='SUCCESS' WHERE build_id=?",
        (dt.datetime.now().isoformat(timespec="seconds"), build_id),
    )
    out.commit()
    integrity = out.execute("PRAGMA integrity_check").fetchone()[0]
    print(
        {
            "years": sorted(all_years),
            "sire_rows": len(sire_rows),
            "jockey_rows": len(jockey_rows),
            "frame_rows": len(frame_rows),
            "size_bytes": args.db.stat().st_size,
            "integrity_check": integrity,
        }
    )
    out.close()


if __name__ == "__main__":
    main()
