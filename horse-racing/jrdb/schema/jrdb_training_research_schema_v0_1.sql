PRAGMA foreign_keys=ON;

-- JRDB Training Research Base v0.1
-- One row per JRA runner. Market variables are intentionally excluded.

CREATE TABLE meta_training_research_build(
  build_id INTEGER PRIMARY KEY,
  builder_version TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  source_git_commit TEXT NOT NULL,
  source_index_db_sha256 TEXT,
  source_official_runperf_db_sha256 TEXT,
  runperf_formula TEXT NOT NULL,
  runperf_version TEXT NOT NULL,
  period_from TEXT NOT NULL,
  period_to TEXT NOT NULL,
  holdout_from TEXT NOT NULL,
  holdout_to TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  runner_count INTEGER,
  message TEXT
);

CREATE TABLE source_archive(
  source_kind TEXT NOT NULL,
  source_year INTEGER NOT NULL,
  source_member_count INTEGER,
  archive_size_bytes INTEGER,
  archive_sha256 TEXT,
  PRIMARY KEY(source_kind, source_year)
);

CREATE TABLE training_runner(
  race_date TEXT NOT NULL,
  year INTEGER NOT NULL,
  data_split TEXT NOT NULL CHECK(data_split IN ('WARMUP','DEVELOPMENT','HOLDOUT')),
  race_key TEXT NOT NULL,
  horse_no INTEGER NOT NULL,
  horse_id TEXT,
  horse_name TEXT,
  trainer_code TEXT,
  trainer_name TEXT,
  jockey_code TEXT,
  jockey_name TEXT,

  venue_code TEXT,
  surface_code TEXT,
  distance_m INTEGER,
  race_type_code TEXT,
  race_condition_code TEXT,
  grade_code TEXT,
  carried_weight_kg REAL,
  body_weight_kg INTEGER,
  rotation_interval INTEGER,
  days_since_last_run INTEGER,
  career_run_count INTEGER NOT NULL,
  prior_run_count INTEGER NOT NULL,

  training_date TEXT,
  days_before_race INTEGER,
  workout_count INTEGER,
  course_code TEXT,
  effort_code TEXT,
  chase_state_code TEXT,
  rider_type_code TEXT,
  furlong_count INTEGER,
  first_segment_sec REAL,
  middle_segment_sec REAL,
  final_segment_sec REAL,
  pair_result_code TEXT,
  pair_effort_code TEXT,
  pair_age INTEGER,
  pair_class_code TEXT,

  jrdb_first_segment_index INTEGER,
  jrdb_middle_segment_index INTEGER,
  jrdb_final_segment_index INTEGER,
  jrdb_workout_index_cha INTEGER,

  training_type_code TEXT,
  training_course_type_code TEXT,
  used_slope INTEGER,
  used_wood INTEGER,
  used_dirt INTEGER,
  used_turf INTEGER,
  used_pool INTEGER,
  used_jump INTEGER,
  used_polytrack INTEGER,
  training_distance_code TEXT,
  training_focus_code TEXT,
  training_volume_code TEXT,
  week_ago_workout_index INTEGER,
  week_ago_course_code TEXT,

  jrdb_workout_index_cyb INTEGER,
  finish_index INTEGER,
  finish_change_code TEXT,
  training_evaluation_code TEXT,

  kyi_training_score REAL,
  kyi_training_arrow_code TEXT,
  finish INTEGER,
  valid_finisher_count INTEGER,
  finish_percentile REAL,
  official_runperf_raw REAL,
  runperf_score_status TEXT,
  runperf_formula TEXT,
  runperf_version TEXT,
  runperf_provenance TEXT,

  race_source_kind TEXT NOT NULL,
  race_source_member TEXT,
  kyi_source_member TEXT,
  cha_source_member TEXT,
  cyb_source_member TEXT,
  sed_source_member TEXT,
  source_record_hash BLOB NOT NULL CHECK(length(source_record_hash)=32),
  PRIMARY KEY(race_key, horse_no)
);

CREATE INDEX ix_training_horse_date
  ON training_runner(horse_id, race_date, race_key);
CREATE INDEX ix_training_horse_comparable
  ON training_runner(horse_id, course_code, furlong_count, race_date, race_key);
CREATE INDEX ix_training_trainer_date
  ON training_runner(trainer_code, race_date, race_key);
CREATE INDEX ix_training_trainer_course
  ON training_runner(trainer_code, course_code, race_date, race_key);
CREATE INDEX ix_training_year ON training_runner(year, race_date);
CREATE INDEX ix_training_rest ON training_runner(rotation_interval, trainer_code, race_date);
CREATE INDEX ix_training_cyb_course_use
  ON training_runner(training_course_type_code, used_slope, used_wood,
                     used_dirt, used_turf, used_polytrack, race_date);

CREATE VIEW v_training_development AS
SELECT * FROM training_runner WHERE data_split='DEVELOPMENT';

CREATE VIEW v_training_holdout_locked AS
SELECT race_date,year,race_key,horse_no,horse_id,horse_name,trainer_code,
       course_code,furlong_count,final_segment_sec,training_type_code,
       training_course_type_code,used_slope,used_wood,used_dirt,used_turf,
       used_pool,used_jump,used_polytrack,rotation_interval,days_since_last_run
FROM training_runner WHERE data_split='HOLDOUT';
