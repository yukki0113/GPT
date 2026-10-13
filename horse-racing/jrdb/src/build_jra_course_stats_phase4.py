#!/usr/bin/env python3
"""Build period-bounded JRA CourseStats from accepted Historical Warehouse SED."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import duckdb

from jrdb_course_profile_identity import course_key_from_observation, layout_from_observation

DEFINITION_VERSION = "jra-course-stats-definition-v0.1"
JRA_VENUES = tuple(f"{i:02d}" for i in range(1, 11))


def sql_literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, columns: list[str], rows: list[tuple]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(dict(zip(columns, row)), ensure_ascii=False, default=str) + "\n")


def fetch_rows(con: duckdb.DuckDBPyConnection, sql: str) -> tuple[list[str], list[tuple]]:
    cur = con.execute(sql)
    return [d[0] for d in cur.description], cur.fetchall()


def metric_aggregate_sql(keys: list[str], where_sql: str, min_geometry_races: int | None = None) -> str:
    key_sql = ", ".join(keys)
    using_sql = ", ".join(keys)
    eligible_sql = ""
    if min_geometry_races is not None:
        eligible_sql = f", (ra.sample_race_count >= {int(min_geometry_races)}) AS eligible_for_use"
    return f"""
WITH runner_agg AS (
  SELECT
    {key_sql},
    COUNT(*) AS sample_runner_count,
    AVG(CASE WHEN finish <= 3 THEN 1.0 ELSE 0.0 END) AS overall_top3_rate,
    COUNT(last3f_speed_percentile) AS last3f_sample_runner_count,
    AVG(last3f_speed_percentile) AS avg_all_last3f_percentile,
    AVG(CASE WHEN finish <= 3 THEN last3f_speed_percentile END) AS avg_top3_last3f_percentile,
    AVG(CASE WHEN finish <= 3 THEN last3f_sec END) AS avg_top3_last3f_sec,
    AVG(CASE WHEN finish <= 3 AND corner_4 > 0 THEN corner_4 END) AS avg_top3_position_4c,

    SUM(CASE WHEN style_group='front' THEN 1 ELSE 0 END) AS front_runner_count,
    AVG(CASE WHEN style_group='front' THEN CASE WHEN finish=1 THEN 1.0 ELSE 0.0 END END) AS front_win_rate,
    AVG(CASE WHEN style_group='front' THEN CASE WHEN finish<=3 THEN 1.0 ELSE 0.0 END END) AS front_top3_rate,

    SUM(CASE WHEN style_group='stalker' THEN 1 ELSE 0 END) AS stalker_runner_count,
    AVG(CASE WHEN style_group='stalker' THEN CASE WHEN finish=1 THEN 1.0 ELSE 0.0 END END) AS stalker_win_rate,
    AVG(CASE WHEN style_group='stalker' THEN CASE WHEN finish<=3 THEN 1.0 ELSE 0.0 END END) AS stalker_top3_rate,

    SUM(CASE WHEN style_group='midpack' THEN 1 ELSE 0 END) AS midpack_runner_count,
    AVG(CASE WHEN style_group='midpack' THEN CASE WHEN finish=1 THEN 1.0 ELSE 0.0 END END) AS midpack_win_rate,
    AVG(CASE WHEN style_group='midpack' THEN CASE WHEN finish<=3 THEN 1.0 ELSE 0.0 END END) AS midpack_top3_rate,

    SUM(CASE WHEN style_group='closer' THEN 1 ELSE 0 END) AS closer_runner_count,
    AVG(CASE WHEN style_group='closer' THEN CASE WHEN finish=1 THEN 1.0 ELSE 0.0 END END) AS closer_win_rate,
    AVG(CASE WHEN style_group='closer' THEN CASE WHEN finish<=3 THEN 1.0 ELSE 0.0 END END) AS closer_top3_rate,

    SUM(CASE WHEN draw_band IS NOT NULL THEN 1 ELSE 0 END) AS draw_sample_runner_count,
    AVG(CASE WHEN draw_band='inside' THEN CASE WHEN finish=1 THEN 1.0 ELSE 0.0 END END) AS inside_draw_win_rate,
    AVG(CASE WHEN draw_band='inside' THEN CASE WHEN finish<=3 THEN 1.0 ELSE 0.0 END END) AS inside_draw_top3_rate,
    AVG(CASE WHEN draw_band='middle' THEN CASE WHEN finish=1 THEN 1.0 ELSE 0.0 END END) AS middle_draw_win_rate,
    AVG(CASE WHEN draw_band='middle' THEN CASE WHEN finish<=3 THEN 1.0 ELSE 0.0 END END) AS middle_draw_top3_rate,
    AVG(CASE WHEN draw_band='outside' THEN CASE WHEN finish=1 THEN 1.0 ELSE 0.0 END END) AS outside_draw_win_rate,
    AVG(CASE WHEN draw_band='outside' THEN CASE WHEN finish<=3 THEN 1.0 ELSE 0.0 END END) AS outside_draw_top3_rate
  FROM runner_enriched
  WHERE normal_finish=1 AND ({where_sql})
  GROUP BY {key_sql}
),
race_agg AS (
  SELECT
    {key_sql},
    COUNT(*) AS sample_race_count,
    COUNT(race_first3f_sec) AS race_first3f_sample_count,
    AVG(race_first3f_sec) AS avg_race_first3f_sec,
    COUNT(winner_time_sec) AS race_time_sample_count,
    AVG(winner_time_sec) AS avg_winner_time_sec,
    AVG(winner_last3f_sec) AS avg_winner_last3f_sec,
    AVG(winner_corner_4) AS avg_winner_position_4c,
    AVG(winner_last3f_percentile) AS avg_winner_last3f_percentile,
    COUNT(race_pace_index) AS race_pace_index_sample_count,
    AVG(race_pace_index) AS avg_race_pace_index,
    SUM(CASE WHEN race_pace_code IN ('H','M','S') THEN 1 ELSE 0 END) AS race_pace_code_sample_count,
    AVG(CASE WHEN race_pace_code='H' THEN 1.0 WHEN race_pace_code IN ('H','M','S') THEN 0.0 END) AS high_pace_rate,
    AVG(CASE WHEN race_pace_code='M' THEN 1.0 WHEN race_pace_code IN ('H','M','S') THEN 0.0 END) AS middle_pace_rate,
    AVG(CASE WHEN race_pace_code='S' THEN 1.0 WHEN race_pace_code IN ('H','M','S') THEN 0.0 END) AS slow_pace_rate
  FROM race_enriched
  WHERE winner_found=1 AND ({where_sql})
  GROUP BY {key_sql}
)
SELECT
  {", ".join("ra." + k for k in keys)},
  ra.sample_race_count,
  ua.sample_runner_count,
  ua.overall_top3_rate,
  ra.race_first3f_sample_count,
  ra.avg_race_first3f_sec,
  ra.race_time_sample_count,
  ra.avg_winner_time_sec,
  ra.avg_winner_last3f_sec,
  ra.avg_winner_position_4c,
  ua.avg_top3_position_4c,
  ra.race_pace_index_sample_count,
  ra.avg_race_pace_index,
  ra.race_pace_code_sample_count,
  ra.high_pace_rate,
  ra.middle_pace_rate,
  ra.slow_pace_rate,
  ua.front_runner_count,
  ua.front_win_rate,
  ua.front_top3_rate,
  ua.stalker_runner_count,
  ua.stalker_win_rate,
  ua.stalker_top3_rate,
  ua.midpack_runner_count,
  ua.midpack_win_rate,
  ua.midpack_top3_rate,
  ua.closer_runner_count,
  ua.closer_win_rate,
  ua.closer_top3_rate,
  ua.last3f_sample_runner_count,
  ua.avg_top3_last3f_sec,
  ra.avg_winner_last3f_percentile,
  ua.avg_top3_last3f_percentile,
  ua.avg_all_last3f_percentile,
  ua.avg_top3_last3f_percentile - ua.avg_all_last3f_percentile AS late_speed_importance_delta,
  ua.draw_sample_runner_count,
  ua.inside_draw_win_rate,
  ua.inside_draw_top3_rate,
  ua.middle_draw_win_rate,
  ua.middle_draw_top3_rate,
  ua.outside_draw_win_rate,
  ua.outside_draw_top3_rate,
  ua.inside_draw_top3_rate - ua.overall_top3_rate AS inside_draw_advantage,
  ua.outside_draw_top3_rate - ua.overall_top3_rate AS outside_draw_advantage
  {eligible_sql}
FROM runner_agg ua
JOIN race_agg ra USING ({using_sql})
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sed-root", required=True, type=Path)
    ap.add_argument("--official-config", required=True, type=Path)
    ap.add_argument("--period-from", required=True)
    ap.add_argument("--period-to-exclusive", required=True)
    ap.add_argument("--source-generation", default="unknown")
    ap.add_argument("--min-geometry-races", type=int, default=30)
    ap.add_argument("--output-dir", required=True, type=Path)
    args = ap.parse_args()

    if args.period_from >= args.period_to_exclusive:
        raise SystemExit("period_from must be earlier than period_to_exclusive")
    if args.min_geometry_races < 1:
        raise SystemExit("min_geometry_races must be positive")

    generated_at = datetime.now(timezone.utc).isoformat()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    parquet_glob = str(args.sed_root / "sed" / "year=*" / "*.parquet")
    escaped_glob = parquet_glob.replace("'", "''")
    con = duckdb.connect()
    try:
        con.execute(
            f"CREATE TEMP VIEW sed_raw AS "
            f"SELECT * FROM read_parquet('{escaped_glob}', union_by_name=true)"
        )
        venues_sql = ",".join(sql_literal(x) for x in JRA_VENUES)
        con.execute("""
          CREATE TEMP VIEW sed_latest AS
          SELECT * EXCLUDE (_rn)
          FROM (
            SELECT *,
              ROW_NUMBER() OVER (
                PARTITION BY race_key_raw, horse_no
                ORDER BY source_member_date DESC NULLS LAST,
                         source_record_ordinal DESC NULLS LAST
              ) AS _rn
            FROM sed_raw
          )
          WHERE _rn=1
        """)
        con.execute(f"""
          CREATE TEMP VIEW sed_scope AS
          SELECT *
          FROM sed_latest
          WHERE venue_code IN ({venues_sql})
            AND surface_code IN ('1','2')
            AND race_date >= {sql_literal(args.period_from)}
            AND race_date < {sql_literal(args.period_to_exclusive)}
            AND distance_m IS NOT NULL
            AND turn_code IS NOT NULL
            AND layout_code IS NOT NULL
        """)

        identity_rows = con.execute("""
          SELECT DISTINCT venue_code, surface_code, distance_m, turn_code, layout_code
          FROM sed_scope
          ORDER BY 1,2,3,4,5
        """).fetchall()
        identity_map = []
        unresolved = []
        for venue, surface, distance, turn, layout in identity_rows:
            course_key = course_key_from_observation(venue, surface, distance, turn, layout)
            if course_key is None:
                unresolved.append((venue, surface, distance, turn, layout))
                continue
            layout_variant = layout_from_observation(venue, surface, distance, turn, layout)
            identity_map.append((venue, surface, int(distance), turn, layout, course_key, layout_variant))
        if unresolved:
            raise RuntimeError(f"unresolved flat identity tuples: {unresolved[:10]}")

        con.execute("""
          CREATE TEMP TABLE identity_map(
            venue_code VARCHAR,
            surface_code VARCHAR,
            distance_m BIGINT,
            turn_code VARCHAR,
            layout_code VARCHAR,
            course_key VARCHAR,
            layout_variant VARCHAR
          )
        """)
        con.executemany("INSERT INTO identity_map VALUES (?,?,?,?,?,?,?)", identity_map)

        official = load_json(args.official_config)
        geometry_rows = []
        for venue, cfg in official["venues"].items():
            for row in cfg["geometry_configurations"]:
                surface = str(row["surface_code"])
                if surface not in ("1", "2"):
                    continue
                geometry_rows.append((
                    str(venue),
                    surface,
                    str(row["layout_variant"]),
                    "" if row.get("jrdb_course_code") is None else str(row["jrdb_course_code"]),
                    str(row["geometry_key"]),
                    str(row["rail_label"]),
                ))
        con.execute("""
          CREATE TEMP TABLE geometry_map(
            venue_code VARCHAR,
            surface_code VARCHAR,
            layout_variant VARCHAR,
            course_code VARCHAR,
            geometry_key VARCHAR,
            rail_label VARCHAR
          )
        """)
        con.executemany("INSERT INTO geometry_map VALUES (?,?,?,?,?,?)", geometry_rows)

        con.execute("""
          CREATE TEMP VIEW runner_base AS
          SELECT
            s.*,
            im.course_key,
            im.layout_variant,
            gm.geometry_key,
            gm.rail_label,
            CASE
              WHEN COALESCE(NULLIF(TRIM(s.abnormal_code),''),'0')='0'
               AND s.finish BETWEEN 1 AND s.field_size
              THEN 1 ELSE 0
            END AS normal_finish,
            CASE s.race_running_style_code
              WHEN '1' THEN 'front'
              WHEN '2' THEN 'stalker'
              WHEN '5' THEN 'stalker'
              WHEN '3' THEN 'midpack'
              WHEN '4' THEN 'closer'
              ELSE NULL
            END AS style_group,
            CASE
              WHEN s.field_size > 0 AND s.horse_no BETWEEN 1 AND s.field_size THEN
                CASE
                  WHEN (s.horse_no - 0.5) / s.field_size <= 1.0/3.0 THEN 'inside'
                  WHEN (s.horse_no - 0.5) / s.field_size <= 2.0/3.0 THEN 'middle'
                  ELSE 'outside'
                END
              ELSE NULL
            END AS draw_band,
            CASE
              WHEN regexp_matches(TRIM(s.time_raw), '^[0-9]{4}$')
               AND TRIM(s.time_raw) <> '9999'
              THEN CAST(SUBSTR(TRIM(s.time_raw),1,1) AS INTEGER) * 60.0
                 + CAST(SUBSTR(TRIM(s.time_raw),2,3) AS INTEGER) / 10.0
              ELSE NULL
            END AS race_time_sec
          FROM sed_scope s
          JOIN identity_map im
            ON s.venue_code=im.venue_code
           AND s.surface_code=im.surface_code
           AND s.distance_m=im.distance_m
           AND s.turn_code=im.turn_code
           AND s.layout_code=im.layout_code
          LEFT JOIN geometry_map gm
            ON s.venue_code=gm.venue_code
           AND s.surface_code=gm.surface_code
           AND im.layout_variant=gm.layout_variant
           AND COALESCE(NULLIF(TRIM(s.course_code),''),'')=gm.course_code
        """)

        con.execute("""
          CREATE TEMP VIEW last3f_rank AS
          SELECT
            race_key_raw,
            horse_no,
            1.0 - PERCENT_RANK() OVER (
              PARTITION BY race_key_raw
              ORDER BY last3f_sec ASC
            ) AS last3f_speed_percentile
          FROM runner_base
          WHERE normal_finish=1
            AND last3f_sec IS NOT NULL
            AND last3f_sec > 0
        """)

        con.execute("""
          CREATE TEMP VIEW runner_enriched AS
          SELECT b.*, r.last3f_speed_percentile
          FROM runner_base b
          LEFT JOIN last3f_rank r
            ON b.race_key_raw=r.race_key_raw
           AND b.horse_no=r.horse_no
        """)

        con.execute("""
          CREATE TEMP VIEW race_enriched AS
          SELECT
            race_key_raw,
            course_key,
            geometry_key,
            rail_label,
            MAX(CASE WHEN finish=1 AND normal_finish=1 THEN 1 ELSE 0 END) AS winner_found,
            MIN(CASE WHEN normal_finish=1 AND first3f_sec > 0 THEN first3f_sec END) AS race_first3f_sec,
            MAX(CASE WHEN finish=1 AND normal_finish=1 THEN race_time_sec END) AS winner_time_sec,
            MAX(CASE WHEN finish=1 AND normal_finish=1 THEN last3f_sec END) AS winner_last3f_sec,
            MAX(CASE WHEN finish=1 AND normal_finish=1 AND corner_4 > 0 THEN corner_4 END) AS winner_corner_4,
            MAX(CASE WHEN finish=1 AND normal_finish=1 THEN last3f_speed_percentile END) AS winner_last3f_percentile,
            MAX(CASE WHEN finish=1 AND normal_finish=1 THEN metric_race_pace_index END) AS race_pace_index,
            MAX(CASE WHEN finish=1 AND normal_finish=1 THEN race_pace_code END) AS race_pace_code
          FROM runner_enriched
          GROUP BY race_key_raw, course_key, geometry_key, rail_label
        """)

        course_metric_sql = metric_aggregate_sql(["course_key"], "course_key IS NOT NULL")
        geometry_metric_sql = metric_aggregate_sql(
            ["course_key", "geometry_key", "rail_label"],
            "geometry_key IS NOT NULL",
            args.min_geometry_races,
        )
        con.execute("CREATE TEMP TABLE course_metrics AS " + course_metric_sql)
        con.execute("CREATE TEMP TABLE geometry_metrics AS " + geometry_metric_sql)

        period_from = sql_literal(args.period_from)
        period_to = sql_literal(args.period_to_exclusive)
        generation = sql_literal(args.source_generation)
        generated = sql_literal(generated_at)
        definition = sql_literal(DEFINITION_VERSION)

        course_select = f"""
          SELECT
            'CSTAT:' || course_key || ':' ||
              REPLACE({period_from},'-','') || '-' || REPLACE({period_to},'-','') ||
              ':v001' AS stats_id,
            course_key,
            {period_from} AS period_from,
            {period_to} AS period_to_exclusive,
            {definition} AS stats_definition_version,
            {generation} AS source_generation,
            {generated} AS generated_at,
            * EXCLUDE (course_key)
          FROM course_metrics
          ORDER BY course_key
        """
        geometry_select = f"""
          SELECT
            'GSTAT:' || course_key || ':' || geometry_key || ':' ||
              REPLACE({period_from},'-','') || '-' || REPLACE({period_to},'-','') ||
              ':v001' AS stats_id,
            course_key,
            geometry_key,
            rail_label,
            {period_from} AS period_from,
            {period_to} AS period_to_exclusive,
            {definition} AS stats_definition_version,
            {generation} AS source_generation,
            {generated} AS generated_at,
            * EXCLUDE (course_key, geometry_key, rail_label)
          FROM geometry_metrics
          ORDER BY course_key, geometry_key
        """

        course_columns, course_rows = fetch_rows(con, course_select)
        geometry_columns, geometry_stats_rows = fetch_rows(con, geometry_select)
        write_jsonl(out / "course_stats_v0_1.jsonl", course_columns, course_rows)
        write_jsonl(out / "course_geometry_stats_v0_1.jsonl", geometry_columns, geometry_stats_rows)

        course_parquet = str(out / "course_stats_v0_1.parquet").replace("'", "''")
        geometry_parquet = str(out / "course_geometry_stats_v0_1.parquet").replace("'", "''")
        con.execute(f"COPY ({course_select}) TO '{course_parquet}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        con.execute(f"COPY ({geometry_select}) TO '{geometry_parquet}' (FORMAT PARQUET, COMPRESSION ZSTD)")

        summary = {
            "schema_version": "jra-course-stats-phase4-build-v0.1",
            "stats_definition_version": DEFINITION_VERSION,
            "period_from": args.period_from,
            "period_to_exclusive": args.period_to_exclusive,
            "source_generation": args.source_generation,
            "obstacle_policy": "excluded",
            "sed_raw_rows": con.execute("SELECT COUNT(*) FROM sed_raw").fetchone()[0],
            "sed_latest_rows": con.execute("SELECT COUNT(*) FROM sed_latest").fetchone()[0],
            "scoped_flat_runner_rows": con.execute("SELECT COUNT(*) FROM runner_enriched").fetchone()[0],
            "scoped_flat_race_count": con.execute("SELECT COUNT(DISTINCT race_key_raw) FROM runner_enriched").fetchone()[0],
            "normal_finisher_rows": con.execute("SELECT COUNT(*) FROM runner_enriched WHERE normal_finish=1").fetchone()[0],
            "course_stats_rows": len(course_rows),
            "geometry_stats_rows": len(geometry_stats_rows),
            "geometry_eligible_rows": sum(
                1 for row in geometry_stats_rows
                if bool(dict(zip(geometry_columns, row)).get("eligible_for_use"))
            ),
            "geometry_unmapped_runner_rows": con.execute(
                "SELECT COUNT(*) FROM runner_enriched WHERE geometry_key IS NULL"
            ).fetchone()[0],
            "identity_tuple_count": len(identity_map),
            "unresolved_identity_tuple_count": 0,
            "minimum_geometry_races_for_use": args.min_geometry_races,
        }
        (out / "phase4_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"status": "PASS", **summary}, ensure_ascii=False))
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
