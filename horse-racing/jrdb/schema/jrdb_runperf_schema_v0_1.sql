PRAGMA foreign_keys=ON;

-- JRDB PWA independent RunPerf feature schema v0.1
-- Purpose: build transparent, time-aware RunPerf candidate inputs from Index Base.
-- This database intentionally excludes odds/popularity from RunPerf construction.

CREATE TABLE meta_runperf_build(
  build_id INTEGER PRIMARY KEY,
  builder_version TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  source_index_db_path TEXT NOT NULL,
  source_index_db_sha256 TEXT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  methods_json TEXT NOT NULL,
  race_observation_count INTEGER,
  expected_time_count INTEGER,
  day_bias_count INTEGER,
  runner_feature_count INTEGER,
  message TEXT
);

CREATE TABLE race_runperf_observation(
  race_key TEXT PRIMARY KEY,
  race_date TEXT NOT NULL,
  year INTEGER NOT NULL,
  venue_code TEXT NOT NULL,
  surface_code TEXT,
  distance_m INTEGER,
  race_type_code TEXT,
  race_condition_code TEXT,
  condition_group_code TEXT,
  grade_code TEXT,
  class_key_v0 TEXT,
  race_context_availability TEXT NOT NULL,
  valid_finisher_count INTEGER NOT NULL,
  winner_time_sec REAL,
  representative_time_sec REAL,
  calculation_status TEXT NOT NULL
);

CREATE TABLE race_expected_time(
  baseline_method TEXT NOT NULL,
  race_key TEXT NOT NULL,
  course_history_count INTEGER NOT NULL,
  course_history_last_date TEXT,
  course_base_time_sec REAL,
  class_history_count INTEGER NOT NULL,
  class_history_last_date TEXT,
  class_adjustment_sec REAL,
  expected_time_sec REAL,
  race_bias_sec REAL,
  calculation_status TEXT NOT NULL,
  PRIMARY KEY(baseline_method, race_key),
  FOREIGN KEY(race_key) REFERENCES race_runperf_observation(race_key)
);

CREATE TABLE race_day_track_bias(
  baseline_method TEXT NOT NULL,
  race_date TEXT NOT NULL,
  venue_code TEXT NOT NULL,
  surface_code TEXT NOT NULL,
  race_bias_count INTEGER NOT NULL,
  raw_median_bias_sec REAL NOT NULL,
  shrink_k2_bias_sec REAL NOT NULL,
  shrink_k4_bias_sec REAL NOT NULL,
  shrink_k8_bias_sec REAL NOT NULL,
  PRIMARY KEY(baseline_method, race_date, venue_code, surface_code)
);

CREATE TABLE runner_runperf_features(
  baseline_method TEXT NOT NULL,
  race_key TEXT NOT NULL,
  horse_no INTEGER NOT NULL,
  horse_id TEXT,
  finish INTEGER,
  abnormal_code TEXT,
  actual_time_sec REAL,
  valid_finisher_count INTEGER NOT NULL,
  winner_time_sec REAL,
  margin_sec REAL,
  margin_per_1000m_sec REAL,
  finish_percentile REAL,
  carried_weight_kg REAL,
  race_mean_carried_weight_kg REAL,
  weight_relative_kg REAL,
  expected_time_sec REAL,
  day_bias_raw_sec REAL,
  day_bias_k2_sec REAL,
  day_bias_k4_sec REAL,
  day_bias_k8_sec REAL,
  time_residual_no_bias_sec REAL,
  time_residual_raw_bias_sec REAL,
  time_residual_k2_bias_sec REAL,
  time_residual_k4_bias_sec REAL,
  time_residual_k8_bias_sec REAL,
  jrdb_raw_score REAL,
  jrdb_idm REAL,
  calculation_status TEXT NOT NULL,
  PRIMARY KEY(baseline_method, race_key, horse_no),
  FOREIGN KEY(race_key) REFERENCES race_runperf_observation(race_key)
);

CREATE INDEX ix_runperf_obs_date ON race_runperf_observation(race_date);
CREATE INDEX ix_runperf_obs_course ON race_runperf_observation(venue_code, surface_code, distance_m, race_date);
CREATE INDEX ix_runperf_expected_race ON race_expected_time(race_key, baseline_method);
CREATE INDEX ix_runperf_day_bias_date ON race_day_track_bias(race_date, venue_code, surface_code);
CREATE INDEX ix_runperf_runner_horse ON runner_runperf_features(horse_id, race_key);
CREATE INDEX ix_runperf_runner_status ON runner_runperf_features(baseline_method, calculation_status);

CREATE VIEW v_runperf_candidate_matrix AS
SELECT
  f.baseline_method,
  o.race_date,
  o.year,
  o.venue_code,
  o.surface_code,
  o.distance_m,
  o.class_key_v0,
  f.race_key,
  f.horse_no,
  f.horse_id,
  f.finish,
  f.finish_percentile AS b0_finish_percentile,
  CASE WHEN f.margin_per_1000m_sec IS NULL THEN NULL ELSE -f.margin_per_1000m_sec END AS b1_margin_score,
  f.time_residual_no_bias_sec,
  f.time_residual_raw_bias_sec,
  f.time_residual_k2_bias_sec,
  f.time_residual_k4_bias_sec,
  f.time_residual_k8_bias_sec,
  f.margin_per_1000m_sec,
  f.weight_relative_kg,
  f.jrdb_raw_score AS j0_jrdb_raw_score,
  f.jrdb_idm AS j1_jrdb_idm,
  f.calculation_status
FROM runner_runperf_features f
JOIN race_runperf_observation o ON o.race_key=f.race_key;
