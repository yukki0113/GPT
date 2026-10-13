"""Staged, read-only RRDB horse/course-fit research v0.1 (DuckDB/Parquet)."""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import duckdb

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools/data-storage"))
from data_storage.common import sha256_file, sql_literal as lit, write_json
from data_storage.validate import validate
from jrdb_course_profile_identity import course_key_from_observation
from jrdb_edge_v02_canonical import track_condition_bucket
from jrdb_postrace_review_reader import RaceReviewReader
from jrdb_postrace_review import parse_sed_time_seconds
from jrdb_recommendation_signals import performance_signal

VERSION = "rrdb-horse-course-fit-v0.1"
CONSTANTS = dict(LOOKBACK_YEARS=3, MAX_PREVIOUS_RUNS=10,
                 MIN_PREVIOUS_RUNS_FOR_BASELINE=3, SHRINKAGE_K=5,
                 STORE_MIN_SAMPLE=2, SIGNAL_MIN_SAMPLE=4,
                 HIGH_SUPPORT_MIN_SAMPLE=6,
                 CONFIDENCE_SAMPLE_DENOMINATOR=8,
                 FINAL_STRAIGHT_BUCKET_BOUNDARIES_M=[350, 450],
                 FINAL_STRAIGHT_SIMILAR_TOLERANCE_M=5,
                 DISTANCE_CHANGE_BOUNDARIES_M=[-400, -100, 100, 400])
GOING_COARSE = {s: {"1": "FIRM", "2": "SOFT", "3": "SOFT", "4": "SOFT"}
                for s in ("1", "2")}
PHYSICAL = {"TURN_DIRECTION", "FINAL_SLOPE", "FINAL_STRAIGHT_BUCKET", "COURSE_SIZE", "LAYOUT",
            "TURN_DIRECTION_CHANGE", "FINAL_SLOPE_CHANGE", "FINAL_STRAIGHT_CHANGE",
            "COURSE_SIZE_CHANGE", "LAYOUT_CHANGE", "COURSE_GEOMETRY_CHANGE"}
ABSOLUTE = {"TURN_DIRECTION": "turn_direction", "FINAL_SLOPE": "final_slope",
            "FINAL_STRAIGHT_BUCKET": "final_straight_bucket", "COURSE_SIZE": "course_size_class",
            "LAYOUT": "layout_variant", "PACE_PROFILE": "race_pace_code"}
TRANSITION = {"DISTANCE_CHANGE": "distance_change", "TURN_DIRECTION_CHANGE": "turn_direction",
              "FINAL_SLOPE_CHANGE": "final_slope", "FINAL_STRAIGHT_CHANGE": "final_straight_bucket",
              "COURSE_SIZE_CHANGE": "course_size_class", "LAYOUT_CHANGE": "layout_variant",
              "GOING_CHANGE": "going_coarse", "GOING_RAW_CHANGE": "track_condition_code",
              "COURSE_GEOMETRY_CHANGE": "geometry_key"}


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def three_years_before(value: str) -> str:
    d = date.fromisoformat(value)
    try:
        return d.replace(year=d.year - 3).isoformat()
    except ValueError:  # Calendar-year window, including leap-day targets.
        return d.replace(year=d.year - 3, day=28).isoformat()


def parquet_sql(paths):
    return "read_parquet([" + ",".join(lit(str(p)) for p in paths) + "],union_by_name=true,hive_partitioning=false)"


def require(con, sql, name):
    n = int(con.execute(sql).fetchone()[0])
    if n:
        raise ValueError(f"{name}: {n} violations")
    return n


def verify_course_master(master_dir: Path, official: Path):
    """Verify actual Phase3 outputs against official canonical geometry rows."""
    cfg = json.loads(official.read_text())
    expected = sorted([r for v in cfg["venues"].values() for r in v["geometry_configurations"]],
                      key=lambda r: (r["venue_code"], r["surface_code"], r["layout_variant"], r["rail_label"]))
    actual = [json.loads(x) for x in (master_dir / "course_geometry_configuration_v0_1.jsonl").read_text().splitlines()]
    if actual != expected:
        raise ValueError("Phase3 geometry differs from canonical config")
    masters = [json.loads(x) for x in (master_dir / "course_master_seed_v0_1.jsonl").read_text().splitlines()]
    if len({m["course_key"] for m in masters}) != len(masters):
        raise ValueError("duplicate CourseMaster key")
    for r in actual:
        if not r.get("physical_valid_from") or not r.get("physical_version_id"):
            raise ValueError("geometry lacks physical validity/version")
        start = date.fromisoformat(r["physical_valid_from"])
        end = r.get("physical_valid_to_exclusive")
        if end and date.fromisoformat(end) <= start:
            raise ValueError("invalid physical period")
    for m in masters:
        if not m["current_jra_official"] and m.get("physical_valid_from") is not None:
            raise ValueError("historical-only course assigned current physical epoch")
        rows = [r for r in actual if (r["venue_code"], r["surface_code"], r["layout_variant"]) ==
                (m["venue_code"], m["surface_code"], m["layout_variant"])] if m["current_jra_official"] else []
        for field in ("final_straight_m", "final_straight_slope_flag", "course_size_class", "physical_valid_from", "physical_version_id"):
            vals = {r.get(field) for r in rows if r.get(field) is not None}
            expected_value = next(iter(vals)) if len(vals) == 1 else None
            if m.get(field) != expected_value:
                raise ValueError(f"CourseMaster propagation mismatch: {m['course_key']} {field}")
    return {"status": "PASS", "master_rows": len(masters), "geometry_rows": len(actual),
            "geometry_slope_null": sum(r.get("final_straight_slope_flag") is None for r in actual),
            "geometry_size_null": sum(r.get("course_size_class") is None for r in actual),
            "physical_valid_from_values": sorted({r["physical_valid_from"] for r in actual})}


class Pipeline:
    def __init__(self, output: Path, as_of: str, inputs: dict, source_sha: str):
        date.fromisoformat(as_of)
        self.output = output
        self.output.mkdir(parents=True, exist_ok=True)
        self.as_of = as_of
        self.lookback = three_years_before(as_of)
        self.con = duckdb.connect()
        self.con.execute("SET threads=4")
        self.con.execute("SET memory_limit='2GB'")
        self.con.execute(f"SET temp_directory={lit(str(output / 'work/duckdb'))}")
        self.inputs = inputs
        self.source_sha = source_sha
        self.fingerprint = digest_json(dict(version=VERSION, as_of=as_of, inputs=inputs,
                                           constants=CONSTANTS, source_sha=source_sha,
                                           module_sha=sha256_file(Path(__file__))))
        self.artifacts = {}
        self.checks = {}
        self.reused = []

    def stage(self, name, sql, keys, dependencies=()):
        path = self.output / (name + ".parquet")
        receipt_path = path.with_suffix(".stage.json")
        token = digest_json(dict(pipeline=self.fingerprint, sql=sql,
                                 upstream={d: self.artifacts[d]["sha256"] for d in dependencies}))
        if path.exists() and receipt_path.exists():
            old = json.loads(receipt_path.read_text())
            if old.get("stage_fingerprint") == token and sha256_file(path) == old.get("sha256"):
                self.artifacts[name] = old
                self.reused.append(name)
                print(json.dumps({'stage':name,'status':'REUSED','row_count':old['row_count']}),flush=True)
                return path
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(".partial.parquet")
        start = time.monotonic()
        print(json.dumps({'stage':name,'status':'STARTED'}),flush=True)
        self.con.execute(f"COPY ({sql}) TO {lit(str(partial))} (FORMAT PARQUET,COMPRESSION ZSTD)")
        checked = validate({"source": {}, "target": {"path": str(partial)},
                            "keys": {"canonical": keys},
                            "validation": {"require_unique_key": True,
                                           "non_null_columns": [k for k in keys if k not in ('from_value','to_value')]}})
        if not checked["passed"]:
            partial.unlink()
            raise ValueError(f"artifact validation failed: {name}")
        partial.replace(path)
        meta = dict(path=str(path), row_count=checked["row_count_target"], schema_hash=checked["schema_hash"],
                    sha256=sha256_file(path), elapsed_seconds=time.monotonic() - start,
                    stage_fingerprint=token, dependencies=list(dependencies))
        write_json(receipt_path, meta)
        self.artifacts[name] = meta
        print(json.dumps({'stage':name,'status':'COMPLETE','row_count':meta['row_count'],
                          'elapsed_seconds':meta['elapsed_seconds']}),flush=True)
        return path

    def view(self, name, path):
        self.con.execute(f"CREATE OR REPLACE TEMP VIEW {name} AS SELECT * FROM {parquet_sql([path])}")

    def base(self, sed_paths, hp_paths, review_paths, master_dir):
        c = self.con
        c.create_function('canonical_performance', lambda v: performance_signal({'horse_adjusted_delta_per_1000m': v}),
                          ['DOUBLE'], 'DOUBLE', null_handling='special')
        c.create_function('canonical_going', track_condition_bucket, ['VARCHAR'], 'VARCHAR', null_handling='special')
        c.create_function('canonical_time', parse_sed_time_seconds, ['VARCHAR'], 'DOUBLE', null_handling='special')
        c.execute(f"CREATE TEMP VIEW sed_raw AS SELECT * FROM {parquet_sql(sed_paths)}")
        c.execute(f"CREATE TEMP VIEW hp AS SELECT * FROM {parquet_sql(hp_paths)}")
        c.execute(f"CREATE TEMP VIEW rr AS SELECT * FROM {parquet_sql(review_paths)}")
        # Corrections are selected only if available strictly before the target.
        c.execute(f"""CREATE TEMP VIEW sed AS SELECT * EXCLUDE(rn) FROM (
          SELECT *, row_number() OVER(PARTITION BY race_key_raw,horse_no
            ORDER BY source_member_date DESC,source_record_ordinal DESC) rn
          FROM sed_raw WHERE CAST(race_date AS DATE)<DATE {lit(self.as_of)}
            AND CAST(source_member_date AS DATE)<DATE {lit(self.as_of)}) WHERE rn=1""")
        require(c, "SELECT COUNT(*) FROM (SELECT race_horse_key FROM hp GROUP BY 1 HAVING COUNT(*)>1)", 'RRDB duplicate horse key')
        require(c, "SELECT COUNT(*) FROM (SELECT race_key FROM rr GROUP BY 1 HAVING COUNT(*)>1)", 'RRDB duplicate race key')
        # A latest snapshot cannot stand in for an earlier corrected SED version.
        require(c, """SELECT COUNT(*) FROM sed s JOIN hp h
          ON s.race_key_raw=h.race_key AND s.horse_no=h.horse_no
          WHERE h.horse_id IS DISTINCT FROM NULLIF(TRIM(s.blood_registration_no),'')
             OR h.race_date IS DISTINCT FROM CAST(s.race_date AS DATE)
             OR h.finish IS DISTINCT FROM s.finish
             OR h.surface_code IS DISTINCT FROM s.surface_code
             OR h.distance_m IS DISTINCT FROM s.distance_m
             OR h.first3f_sec IS DISTINCT FROM s.first3f_sec
             OR h.last3f_sec IS DISTINCT FROM s.last3f_sec""", 'SED/RRDB correction or identity mismatch')
        hp_columns = {r[0] for r in c.execute('DESCRIBE hp').fetchall()}
        if 'time_sec' in hp_columns:
            require(c, """SELECT COUNT(*) FROM sed s JOIN hp h ON s.race_key_raw=h.race_key AND s.horse_no=h.horse_no
              WHERE h.time_sec IS DISTINCT FROM canonical_time(s.time_raw)""", 'SED/RRDB corrected time mismatch')
        require(c, "SELECT COUNT(*) FROM rr WHERE standard_sample_end_date>=race_date", 'canonical performance future standard')
        c.execute(f"CREATE TEMP VIEW cm AS SELECT * FROM read_json_auto({lit(str(master_dir / 'course_master_seed_v0_1.jsonl'))})")
        c.execute(f"CREATE TEMP VIEW gm AS SELECT * FROM read_json_auto({lit(str(master_dir / 'course_geometry_configuration_v0_1.jsonl'))})")
        dims = c.execute("SELECT DISTINCT venue_code,surface_code,distance_m,turn_code,layout_code FROM sed").fetchall()
        dim_rows = []
        for venue, surface, distance, turn, layout in dims:
            key = course_key_from_observation(venue, surface, distance, turn, layout) if all(x is not None for x in (venue,surface,distance,turn,layout)) and surface in ('1','2') else None
            dim_rows.append((venue,surface,distance,turn,layout,key))
        c.execute("CREATE TEMP TABLE identity_map(venue_code VARCHAR,surface_code VARCHAR,distance_m BIGINT,turn_code VARCHAR,layout_code VARCHAR,course_key VARCHAR)")
        if dim_rows:
            c.executemany("INSERT INTO identity_map VALUES (?,?,?,?,?,?)", dim_rows)
        c.execute("""CREATE TEMP VIEW joined AS SELECT s.*,
          s.race_key_raw||LPAD(CAST(s.horse_no AS VARCHAR),2,'0') race_horse_key,
          i.course_key, m.layout_variant canonical_layout,
          CASE WHEN i.course_key IS NULL THEN 'UNRESOLVED_OR_UNSUPPORTED' ELSE 'RESOLVED' END identity_status,
          COALESCE(g.physical_valid_from,m.physical_valid_from) physical_valid_from,
          COALESCE(g.physical_valid_to_exclusive,m.physical_valid_to_exclusive) physical_valid_to_exclusive,
          COALESCE(g.physical_version_id,m.physical_version_id) resolved_physical_version_id,
          g.geometry_key resolved_geometry_key,
          COALESCE(g.final_straight_m,m.final_straight_m) resolved_final_straight_m,
          COALESCE(g.final_straight_slope_flag,m.final_straight_slope_flag) resolved_final_slope_flag,
          COALESCE(g.course_size_class,m.course_size_class) resolved_course_size_class,
          COALESCE(g.elevation_difference_m,m.elevation_difference_m) resolved_elevation,
          m.turn_direction resolved_turn_direction,
          canonical_performance(h.horse_adjusted_delta_per_1000m) performance_signal,
          r.standard_sample_end_date,
          r.time_delta_basis,
          CASE WHEN h.race_horse_key IS NULL THEN 'MISSING_RRDB' ELSE 'RRDB_CANONICAL' END performance_source_status
          FROM sed s LEFT JOIN identity_map i USING(venue_code,surface_code,distance_m,turn_code,layout_code)
          LEFT JOIN cm m ON i.course_key=m.course_key
          LEFT JOIN gm g ON m.current_jra_official AND s.venue_code=g.venue_code
            AND s.surface_code=g.surface_code AND m.layout_variant=g.layout_variant
            AND COALESCE(NULLIF(TRIM(s.course_code),''),'')=COALESCE(g.jrdb_course_code,'')
          LEFT JOIN hp h ON s.race_key_raw=h.race_key AND s.horse_no=h.horse_no
          LEFT JOIN rr r ON s.race_key_raw=r.race_key""")
        c.execute("""CREATE TEMP VIEW gated AS SELECT *,
          COALESCE(physical_valid_from IS NOT NULL AND resolved_physical_version_id IS NOT NULL
          AND CAST(physical_valid_from AS DATE)<=CAST(race_date AS DATE)
          AND (physical_valid_to_exclusive IS NULL OR CAST(race_date AS DATE)<CAST(physical_valid_to_exclusive AS DATE)),FALSE) physical_valid
          FROM joined""")
        sql = """SELECT CAST(race_date AS DATE) race_date,race_key_raw race_key,race_key_raw,race_horse_key,
          horse_no,NULLIF(TRIM(blood_registration_no),'') horse_id,horse_name,venue_code,surface_code,distance_m,
          course_key,identity_status,physical_valid,CAST(physical_valid_from AS DATE) physical_valid_from,
          CAST(physical_valid_to_exclusive AS DATE) physical_valid_to_exclusive,
          CASE WHEN physical_valid THEN resolved_physical_version_id END physical_version_id,
          CASE WHEN physical_valid THEN resolved_geometry_key END geometry_key,
          CASE WHEN physical_valid THEN UPPER(resolved_turn_direction) END turn_direction,
          CASE WHEN physical_valid THEN canonical_layout END layout_variant,
          CASE WHEN physical_valid THEN resolved_final_straight_m END final_straight_m,
          CASE WHEN physical_valid THEN resolved_final_slope_flag END final_straight_slope_flag,
          CASE WHEN physical_valid THEN resolved_course_size_class END course_size_class,
          CASE WHEN physical_valid THEN resolved_elevation END elevation_difference_m,
          track_condition_code,canonical_going(track_condition_code) going_bucket,
          finish,corner_4 corner4_position,first3f_sec,last3f_sec,
          CASE WHEN race_pace_code IN ('H','M','S') THEN race_pace_code END race_pace_code,
          abnormal_code,COALESCE(abnormal_code,'0') NOT IN ('1','2') started,
          performance_signal,performance_source_status,standard_sample_end_date,time_delta_basis,
          CAST(source_member_date AS DATE) source_available_date,source_record_sha256,
          CASE WHEN NOT physical_valid THEN 'UNVERIFIED_PHYSICAL_PERIOD_OR_IDENTITY' END physical_exclusion_reason
          FROM gated ORDER BY race_date,race_key_raw,horse_no"""
        path = self.stage('base/horse_race_course_ledger', sql, ['race_horse_key'])
        self.view('ledger', path)
        return path

    def residual(self):
        c = self.con
        c.execute(f"""CREATE TEMP VIEW prior_sources AS SELECT l.race_horse_key,
          p.race_date source_date,p.performance_signal,
          ROW_NUMBER() OVER(PARTITION BY l.race_horse_key ORDER BY p.race_date DESC,p.race_key DESC,p.horse_no DESC) rn
          FROM ledger l JOIN ledger p ON l.horse_id=p.horse_id
          AND p.started AND p.race_date<l.race_date AND p.race_date>=l.race_date-INTERVAL '{CONSTANTS['LOOKBACK_YEARS']} years'""")
        maximum=CONSTANTS['MAX_PREVIOUS_RUNS'];minimum=CONSTANTS['MIN_PREVIOUS_RUNS_FOR_BASELINE']
        sql = f"""WITH baseline AS (SELECT race_horse_key,COUNT(performance_signal) baseline_sample_count,
          AVG(performance_signal) horse_baseline_performance,MIN(source_date) baseline_source_min_date,
          MAX(source_date) baseline_source_max_date FROM prior_sources WHERE rn<={maximum} GROUP BY 1)
          SELECT l.*,COALESCE(b.baseline_sample_count,0) baseline_sample_count,
          CASE WHEN b.baseline_sample_count>={minimum} THEN b.horse_baseline_performance END horse_baseline_performance,
          b.baseline_source_min_date,b.baseline_source_max_date,
          CASE WHEN b.baseline_sample_count>={minimum} THEN 'READY' ELSE 'INSUFFICIENT_HISTORY' END baseline_status,
          CASE WHEN b.baseline_sample_count>={minimum} THEN l.performance_signal-b.horse_baseline_performance END performance_residual
          FROM ledger l LEFT JOIN baseline b USING(race_horse_key) ORDER BY l.race_date,l.race_key,l.horse_no"""
        path = self.stage('base/horse_performance_residual', sql, ['race_horse_key'], ['base/horse_race_course_ledger'])
        self.view('residual', path)
        require(c, "SELECT COUNT(*) FROM residual WHERE baseline_source_max_date>=race_date OR baseline_source_min_date<race_date-INTERVAL '3 years'", 'baseline future/window')
        require(c, "SELECT COUNT(*) FROM residual WHERE baseline_sample_count>10", 'baseline maximum runs')

    def features(self):
        c = self.con
        lo,hi=CONSTANTS['FINAL_STRAIGHT_BUCKET_BOUNDARIES_M']
        c.execute('CREATE TEMP TABLE going_coarse_map(surface_code VARCHAR,going_bucket VARCHAR,going_coarse VARCHAR)')
        c.executemany('INSERT INTO going_coarse_map VALUES (?,?,?)',[(s,b,v) for s,m in GOING_COARSE.items() for b,v in m.items()])
        c.execute(f"""CREATE TEMP VIEW feature_base AS SELECT r.*,
          CASE WHEN final_straight_slope_flag IS TRUE THEN 'PRESENT' WHEN final_straight_slope_flag IS FALSE THEN 'ABSENT' END final_slope,
          CASE WHEN final_straight_m<{lo} THEN 'SHORT' WHEN final_straight_m<{hi} THEN 'MEDIUM' WHEN final_straight_m>={hi} THEN 'LONG' END final_straight_bucket,
          g.going_coarse,
          COUNT(*) FILTER(WHERE started) OVER(PARTITION BY horse_id,race_date) horse_day_count
          FROM residual r LEFT JOIN going_coarse_map g USING(surface_code,going_bucket)""")
        prev_fields = ['race_date','race_key','distance_m','surface_code','physical_valid','physical_valid_from',
                       'physical_valid_to_exclusive','turn_direction','final_slope','final_straight_m',
                       'final_straight_bucket','course_size_class','layout_variant','going_coarse','track_condition_code',
                       'geometry_key','horse_day_count']
        lag = ','.join(f"LAG({f}) OVER w AS previous_{f}" for f in prev_fields)
        # Immediate previous actual start; cancellations remain in the base but are not starts.
        c.execute(f"""CREATE TEMP VIEW previous_starts AS SELECT race_horse_key,{lag} FROM feature_base
          WHERE started AND horse_id IS NOT NULL
          WINDOW w AS (PARTITION BY horse_id ORDER BY race_date,race_key,horse_no)""")
        shorten_large,shorten_small,extend_small,extend_large=CONSTANTS['DISTANCE_CHANGE_BOUNDARIES_M']
        c.execute(f"""CREATE TEMP VIEW transitions AS SELECT f.*,p.* EXCLUDE(race_horse_key),
          distance_m-previous_distance_m distance_delta_m,
          final_straight_m-previous_final_straight_m final_straight_delta_m,
          surface_code IS DISTINCT FROM previous_surface_code surface_changed,
          CASE WHEN distance_m-previous_distance_m<={shorten_large} THEN 'SHORTEN_LARGE'
            WHEN distance_m-previous_distance_m<={shorten_small} THEN 'SHORTEN_SMALL'
            WHEN distance_m-previous_distance_m<{extend_small} THEN 'SAME'
            WHEN distance_m-previous_distance_m<{extend_large} THEN 'EXTEND_SMALL'
            WHEN distance_m-previous_distance_m>={extend_large} THEN 'EXTEND_LARGE' END distance_change
          FROM feature_base f LEFT JOIN previous_starts p USING(race_horse_key)""")
        path = self.stage('base/horse_course_transition_ledger', 'SELECT * FROM transitions ORDER BY race_date,race_key,horse_no',
                          ['race_horse_key'], ['base/horse_performance_residual'])
        self.view('transitions', path)

    def fits(self, family, only=None):
        features = ABSOLUTE if family == 'ABSOLUTE' else TRANSITION
        for feature, field in features.items():
            if only and feature != only:
                continue
            physical = feature in PHYSICAL
            where = "started AND surface_code IN ('1','2') AND horse_id IS NOT NULL AND performance_residual IS NOT NULL"
            where += f" AND race_date>=DATE {lit(self.lookback)} AND race_date<DATE {lit(self.as_of)}"
            if physical:
                where += " AND physical_valid AND physical_valid_from<=race_date AND (physical_valid_to_exclusive IS NULL OR race_date<physical_valid_to_exclusive)"
            if family == 'ABSOLUTE':
                value = field
                extra = "NULL::VARCHAR from_value,NULL::VARCHAR to_value,NULL::VARCHAR transition_key"
            else:
                where += " AND previous_race_date<race_date AND horse_day_count=1 AND previous_horse_day_count=1"
                if physical:
                    where += " AND previous_physical_valid AND previous_physical_valid_from<=previous_race_date AND (previous_physical_valid_to_exclusive IS NULL OR previous_race_date<previous_physical_valid_to_exclusive)"
                if feature.startswith('GOING'):
                    where += " AND NOT surface_changed"
                if feature == 'DISTANCE_CHANGE':
                    value = 'distance_change'
                    frm, to = 'CAST(previous_distance_m AS VARCHAR)', 'CAST(distance_m AS VARCHAR)'
                    # Aggregate the specified distance-delta bucket, not individual exact distances.
                    frm, to = 'NULL::VARCHAR', 'NULL::VARCHAR'
                elif feature == 'FINAL_STRAIGHT_CHANGE':
                    tolerance=CONSTANTS['FINAL_STRAIGHT_SIMILAR_TOLERANCE_M']
                    value = f"CASE WHEN final_straight_delta_m < -{tolerance} THEN 'SHORTER' WHEN final_straight_delta_m > {tolerance} THEN 'LONGER' ELSE 'SIMILAR' END"
                    frm, to = 'NULL::VARCHAR', 'NULL::VARCHAR'
                    where += " AND final_straight_delta_m IS NOT NULL"
                elif feature == 'FINAL_SLOPE_CHANGE':
                    value = "CASE WHEN previous_final_slope=final_slope THEN 'SAME' WHEN previous_final_slope='ABSENT' THEN 'NO_SLOPE_TO_SLOPE' ELSE 'SLOPE_TO_NO_SLOPE' END"
                    frm, to = 'previous_final_slope','final_slope'
                    where += " AND previous_final_slope IS NOT NULL AND final_slope IS NOT NULL"
                else:
                    frm, to = 'previous_' + field, field
                    value = f"{frm}||'_TO_'||{to}"
                extra = f"CAST({frm} AS VARCHAR) from_value,CAST({to} AS VARCHAR) to_value,CAST({value} AS VARCHAR) transition_key"
            population = f"""SELECT *,CAST({value} AS VARCHAR) feature_value,{extra} FROM transitions WHERE {where}"""
            # Assert the actual selected source population, independently of aggregate output.
            self.con.execute('CREATE OR REPLACE TEMP VIEW selected AS ' + population)
            if physical:
                self.checks[feature+'_invalid_current_physical'] = require(self.con, "SELECT COUNT(*) FROM selected WHERE NOT physical_valid OR physical_valid_from IS NULL OR physical_valid_from>race_date OR (physical_valid_to_exclusive IS NOT NULL AND race_date>=physical_valid_to_exclusive)", 'current physical validity')
                if family == 'TRANSITION':
                    self.checks[feature+'_invalid_previous_physical'] = require(self.con, "SELECT COUNT(*) FROM selected WHERE NOT previous_physical_valid OR previous_physical_valid_from IS NULL OR previous_physical_valid_from>previous_race_date OR (previous_physical_valid_to_exclusive IS NOT NULL AND previous_race_date>=previous_physical_valid_to_exclusive)", 'previous physical validity')
            # Surface remains a grouping dimension in both families; distance has a change flag.
            grouping = "horse_id,surface_code,feature_value,from_value,to_value,transition_key"
            if family == 'TRANSITION':
                grouping += ',surface_changed'
            else:
                self.con.execute("CREATE OR REPLACE TEMP VIEW selected_with_surface AS SELECT * EXCLUDE(surface_changed),FALSE surface_changed FROM selected")
                grouping += ',surface_changed'
            source = 'selected' if family == 'TRANSITION' else 'selected_with_surface'
            sql = f"""WITH a AS (SELECT {grouping},COUNT(*) sample_count,
              AVG(horse_baseline_performance) baseline_mean,AVG(performance_signal) observed_mean,
              AVG(performance_residual) raw_delta,
              COUNT(*) FILTER(WHERE performance_residual>0) positive_count,
              COUNT(*) FILTER(WHERE performance_residual<0) negative_count,
              COUNT(*) FILTER(WHERE performance_residual=0) zero_count,
              MIN(race_date) source_min_date,MAX(race_date) source_max_date,
              AVG(distance_delta_m) distance_delta_m_mean,AVG(final_straight_delta_m) final_straight_delta_m_mean
              FROM {source} WHERE feature_value IS NOT NULL GROUP BY {grouping} HAVING COUNT(*)>={CONSTANTS['STORE_MIN_SAMPLE']})
              SELECT *,DATE {lit(self.as_of)} as_of_date,DATE {lit(self.lookback)} lookback_from,
              DATE {lit(self.as_of)} lookback_to_exclusive,{lit(family)} fit_family,{lit(feature)} feature_type,
              sample_count/(sample_count+{CONSTANTS['SHRINKAGE_K']}.0)*raw_delta shrunk_delta,
              positive_count::DOUBLE/sample_count positive_rate,
              LEAST(1.0,sample_count/{CONSTANTS['CONFIDENCE_SAMPLE_DENOMINATOR']}.0)*ABS(positive_count::DOUBLE/sample_count-0.5)*2 confidence,
              CASE WHEN sample_count<{CONSTANTS['STORE_MIN_SAMPLE']} THEN 'NO_DATA' WHEN sample_count<{CONSTANTS['SIGNAL_MIN_SAMPLE']} THEN 'LOW_SUPPORT'
                WHEN sample_count<{CONSTANTS['HIGH_SUPPORT_MIN_SAMPLE']} THEN 'MEDIUM_SUPPORT' ELSE 'HIGH_SUPPORT' END support_level
              FROM a ORDER BY horse_id,surface_code,feature_value,from_value,to_value,surface_changed"""
            name = f"{family.lower()}_fit/horse_{feature.lower()}_fit"
            self.stage(name, sql, ['horse_id','surface_code','feature_value','from_value','to_value','surface_changed'],
                       ['base/horse_course_transition_ledger'])

    def research(self):
        names = [n for n in self.artifacts if n.startswith(('absolute_fit/','transition_fit/'))]
        if len(names) != len(ABSOLUTE) + len(TRANSITION):
            raise ValueError('research requires all fit axes; run missing stages first')
        union = ' UNION ALL '.join('SELECT * FROM ' + parquet_sql([self.output / (n+'.parquet')]) for n in sorted(names))
        self.stage('research/candidate_fit_view', union + ' ORDER BY fit_family,feature_type,horse_id,surface_code,feature_value,from_value,to_value,surface_changed',
                   ['fit_family','feature_type','horse_id','surface_code','feature_value','from_value','to_value','surface_changed'], names)
        self.view('candidate', self.output / 'research/candidate_fit_view.parquet')
        self.stage('research/distance_change_same_surface_view',
                   "SELECT * FROM candidate WHERE feature_type='DISTANCE_CHANGE' AND NOT surface_changed ORDER BY horse_id,surface_code,feature_value",
                   ['horse_id','surface_code','feature_value'], ['research/candidate_fit_view'])

    def reports(self):
        c = self.con
        self.view('candidate', self.output / 'research/candidate_fit_view.parquet')
        sqls = {
            'distribution_summary': """SELECT fit_family,feature_type,COUNT(*) record_count,COUNT(DISTINCT horse_id) horse_count,
              MIN(sample_count) sample_min,MEDIAN(sample_count) sample_median,MAX(sample_count) sample_max,
              QUANTILE_CONT(shrunk_delta,0.05) delta_p05,MEDIAN(shrunk_delta) delta_median,QUANTILE_CONT(shrunk_delta,0.95) delta_p95,
              COUNT(*) FILTER(WHERE sample_count>=4) medium_or_higher_count,
              COUNT(*) FILTER(WHERE sample_count>=6) high_support_count
              FROM candidate GROUP BY 1,2 ORDER BY 1,2""",
            'support_summary': 'SELECT fit_family,feature_type,support_level,COUNT(*) record_count FROM candidate GROUP BY 1,2,3 ORDER BY 1,2,3',
            'feature_coverage': ' UNION ALL '.join(f"SELECT {lit(feature)} feature_type,COUNT(*) runner_count,COUNT(*) FILTER(WHERE {field} IS NULL) null_count,AVG(CASE WHEN {field} IS NULL THEN 1.0 ELSE 0.0 END) null_rate FROM transitions" for feature,field in ABSOLUTE.items())
        }
        for name, sql in sqls.items():
            path = self.output / ('reports/' + name + '.csv')
            path.parent.mkdir(parents=True, exist_ok=True)
            c.execute(f"COPY ({sql}) TO {lit(str(path))} (HEADER,DELIMITER ',')")
        transition_coverage=[]
        for feature,field in TRANSITION.items():
            needed=('distance_delta_m' if feature=='DISTANCE_CHANGE' else
                    'final_straight_delta_m' if feature=='FINAL_STRAIGHT_CHANGE' else field)
            previous = ('previous_'+field) if feature not in ('DISTANCE_CHANGE','FINAL_STRAIGHT_CHANGE') else needed
            row=c.execute(f"""SELECT COUNT(*),COUNT(*) FILTER(WHERE {needed} IS NULL OR {previous} IS NULL),
              COUNT(*) FILTER(WHERE previous_race_date IS NULL),
              COUNT(*) FILTER(WHERE NOT physical_valid OR NOT COALESCE(previous_physical_valid,FALSE))
              FROM transitions WHERE race_date>=DATE {lit(self.lookback)} AND race_date<DATE {lit(self.as_of)}""").fetchone()
            transition_coverage.append(dict(feature_type=feature,runner_count=row[0],null_endpoint_count=row[1],
                null_endpoint_rate=row[1]/row[0] if row[0] else None,missing_previous_count=row[2],
                invalid_physical_pair_count=row[3] if feature in PHYSICAL else None))
        write_json(self.output/'reports/transition_coverage.json',transition_coverage)
        inventory=[]
        for family, features in [('ABSOLUTE',ABSOLUTE),('TRANSITION',TRANSITION)]:
            for feature in features:
                row=c.execute("""SELECT COUNT(*),COUNT(DISTINCT horse_id),
                  COUNT(*) FILTER(WHERE sample_count>=4),COUNT(*) FILTER(WHERE sample_count>=6)
                  FROM candidate WHERE fit_family=? AND feature_type=?""",[family,feature]).fetchone()
                inventory.append(dict(fit_family=family,feature_type=feature,record_count=row[0],
                    horse_count=row[1],medium_or_higher_count=row[2],high_support_count=row[3]))
        write_json(self.output/'reports/feature_inventory.json',inventory)
        deltas=c.execute("""SELECT MIN(final_straight_delta_m),QUANTILE_CONT(final_straight_delta_m,0.25),
          MEDIAN(final_straight_delta_m),QUANTILE_CONT(final_straight_delta_m,0.75),MAX(final_straight_delta_m),
          COUNT(final_straight_delta_m),COUNT(*) FILTER(WHERE ABS(final_straight_delta_m)<=5)
          FROM transitions WHERE physical_valid AND previous_physical_valid""").fetchone()
        write_json(self.output/'reports/straight_delta_distribution.json',dict(
            min=deltas[0],p25=deltas[1],median=deltas[2],p75=deltas[3],max=deltas[4],sample_count=deltas[5],
            similar_count=deltas[6],tolerance_m=5,
            basis='Canonical geometry rail differences include 2.6m, 2.7m and 5m; fixed before outcome aggregation'))
        summary = c.execute("""SELECT COUNT(*) runners,COUNT(DISTINCT race_key) races,COUNT(DISTINCT horse_id) horses,
          COUNT(*) FILTER(WHERE baseline_status='READY') baseline_ready,
          COUNT(*) FILTER(WHERE baseline_status='INSUFFICIENT_HISTORY') baseline_insufficient,
          COUNT(*) FILTER(WHERE NOT physical_valid) physical_excluded,
          COUNT(*) FILTER(WHERE identity_status<>'RESOLVED') unresolved_or_unsupported,
          COUNT(*) FILTER(WHERE surface_code IN ('1','2') AND course_key IS NULL) flat_unresolved,
          COUNT(*) FILTER(WHERE performance_source_status='MISSING_RRDB') missing_rrdb,
          MIN(race_date),MAX(race_date) FROM residual""").fetchone()
        names = ['runner_count','race_count','horse_count','baseline_ready','baseline_insufficient','physical_excluded',
                 'unresolved_or_unsupported','flat_unresolved','missing_rrdb','race_date_min','race_date_max']
        checks = {
            'baseline_future_or_outside_window': "SELECT COUNT(*) FROM residual WHERE baseline_source_max_date>=race_date OR baseline_source_min_date<race_date-INTERVAL '3 years'",
            'fit_future_or_outside_window': 'SELECT COUNT(*) FROM candidate WHERE source_max_date>=as_of_date OR source_min_date<lookback_from',
            'ledger_future_or_unavailable': f"SELECT COUNT(*) FROM ledger WHERE race_date>=DATE {lit(self.as_of)} OR source_available_date>=DATE {lit(self.as_of)}",
            'physical_leak': "SELECT COUNT(*) FROM ledger WHERE (final_straight_m IS NOT NULL OR final_straight_slope_flag IS NOT NULL OR course_size_class IS NOT NULL OR layout_variant IS NOT NULL OR turn_direction IS NOT NULL OR geometry_key IS NOT NULL) AND NOT physical_valid",
            'fit_arithmetic': "SELECT COUNT(*) FROM candidate WHERE ABS(raw_delta-(observed_mean-baseline_mean))>1e-8 OR positive_count+negative_count+zero_count<>sample_count OR confidence<0 OR confidence>1 OR sample_count<2",
            'flat_unresolved': "SELECT COUNT(*) FROM ledger WHERE surface_code IN ('1','2') AND course_key IS NULL",
        }
        values = {name: int(c.execute(sql).fetchone()[0]) for name,sql in checks.items()}
        values.update(self.checks)
        dup_days = c.execute("SELECT COUNT(*) FROM (SELECT horse_id,race_date FROM ledger WHERE horse_id IS NOT NULL AND started GROUP BY 1,2 HAVING COUNT(*)>1)").fetchone()[0]
        audit = dict(status='PASS' if not any(values.values()) else 'FAIL', checks=values,
                     counts=dict(zip(names,summary)), same_day_multiple_start_groups=dup_days,
                     physical_transition_assertions='current AND immediate previous start each inside [valid_from,valid_to)',
                     obstacle_policy='retained base; excluded all fits', going_policy='same surface only; surface-separated',
                     distance_policy='surface change retained as separate grouping flag; same-surface view provided',
                     baseline_policy='last 10 actual starts within 3 calendar years; average available canonical values, minimum 3',
                     rrdb_v03_modified=False)
        audit['counts']['fit_window_runner_count']=c.execute(f"SELECT COUNT(*) FROM residual WHERE race_date>=DATE {lit(self.lookback)} AND race_date<DATE {lit(self.as_of)}").fetchone()[0]
        write_json(self.output / 'audit.json', audit)
        if audit['status'] != 'PASS':
            raise ValueError(f'audit failed: {values}')
        return audit

    def manifest(self, status='PASS'):
        write_json(self.output / 'manifest.json', dict(status=status,version=VERSION,source_git_sha=self.source_sha,
            module_sha256=sha256_file(Path(__file__)),input_fingerprint=self.fingerprint,inputs=self.inputs,
            as_of_date=self.as_of,lookback_from=self.lookback,lookback_to_exclusive=self.as_of,
            constants=CONSTANTS,going_coarse_mapping=GOING_COARSE,artifacts=self.artifacts,
            reused_stages=self.reused,rrdb_v03_modified=False,duckdb_version=duckdb.__version__))


def run(args):
    reader = RaceReviewReader(args.rrdb_root)
    hp = reader._paths('fact_horse_performance')
    rr = reader._paths('fact_race_review')
    sed = sorted((args.warehouse_root / 'sed').glob('year=*/*.parquet'))
    if not sed:
        raise ValueError('SED Warehouse input missing')
    inputs = {str(p): sha256_file(p) for p in sed + hp + rr}
    for rel, paths in [('fact_horse_performance',hp),('fact_race_review',rr)]:
        for meta,p in zip(reader.manifest['relations'][rel]['partitions'],paths):
            if inputs[str(p)] != meta['sha256'] or p.stat().st_size != meta['size_bytes']:
                raise ValueError(f'RRDB input integrity: {p}')
    for p in sorted(args.course_master_dir.glob('*.json*')):
        inputs[str(p)] = sha256_file(p)
    inputs['rrdb_generation'] = reader.generation_id
    check = verify_course_master(args.course_master_dir,args.official_config)
    inputs[str(args.official_config)] = sha256_file(args.official_config)
    source_sha = subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    pipeline = Pipeline(args.output_dir,args.as_of_date,inputs,source_sha)
    try:
        write_json(args.output_dir / 'reports/course_master_validation.json',check)
        # Calling upstream stages is cheap when completed receipts match; no implicit full rebuild.
        pipeline.base(sed,hp,rr,args.course_master_dir)
        if args.stage == 'base':
            return pipeline.manifest('STAGE_COMPLETE')
        pipeline.residual()
        if args.stage == 'residual':
            return pipeline.manifest('STAGE_COMPLETE')
        pipeline.features()
        if args.stage in ('all','absolute','research'):
            pipeline.fits('ABSOLUTE',args.feature)
        if args.stage in ('all','transition','research'):
            pipeline.fits('TRANSITION',args.feature)
        if args.stage in ('absolute','transition'):
            return pipeline.manifest('STAGE_COMPLETE')
        if args.feature:
            raise ValueError('--feature is only valid with absolute/transition stage')
        pipeline.research()
        audit = pipeline.reports()
        pipeline.manifest()
        print(json.dumps(audit,default=str))
    except Exception as exc:
        pipeline.manifest('FAIL')
        write_json(args.output_dir/'audit.json',{'status':'FAIL','error':str(exc),'rrdb_v03_modified':False})
        raise
    finally:
        pipeline.con.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--rrdb-root',type=Path,required=True,help='Extracted canonical CURRENT snapshot root')
    ap.add_argument('--warehouse-root',type=Path,required=True)
    ap.add_argument('--course-master-dir',type=Path,required=True)
    ap.add_argument('--official-config',type=Path,default=REPO/'horse-racing/jrdb/config/course_profile/official_current_course_geometry_v0_1.json')
    ap.add_argument('--as-of-date',required=True)
    ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--stage',choices=['all','base','residual','absolute','transition','research'],default='all')
    ap.add_argument('--feature',choices=sorted(set(ABSOLUTE)|set(TRANSITION)))
    args = ap.parse_args()
    if args.feature and args.stage not in ('absolute','transition'):
        ap.error('--feature requires absolute or transition')
    if args.feature and args.feature not in (ABSOLUTE if args.stage=='absolute' else TRANSITION):
        ap.error('--feature does not belong to the selected fit family')
    run(args)


if __name__ == '__main__':
    main()
