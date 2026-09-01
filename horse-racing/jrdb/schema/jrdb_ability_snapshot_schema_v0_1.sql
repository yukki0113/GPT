PRAGMA foreign_keys=ON;

-- Pre-race Ability feature snapshot v0.1.  Target results are intentionally
-- separated from features; no market or result-derived target input is stored.
CREATE TABLE meta_ability_snapshot_build(
  build_id INTEGER PRIMARY KEY,
  builder_version TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  index_base_db_path TEXT NOT NULL,
  index_base_db_sha256 TEXT,
  official_runperf_db_path TEXT NOT NULL,
  official_runperf_db_sha256 TEXT,
  source_year_min INTEGER,
  source_year_max INTEGER,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  target_runner_count INTEGER,
  message TEXT
);

CREATE TABLE ability_target_runner(
  race_date TEXT NOT NULL,
  race_key TEXT NOT NULL,
  horse_no INTEGER NOT NULL,
  horse_id TEXT,
  year INTEGER NOT NULL,
  venue_code TEXT,
  surface_code TEXT,
  distance_m INTEGER,
  jockey_code TEXT,
  race_context_availability TEXT NOT NULL,
  current_carried_weight REAL,
  race_mean_carried_weight REAL,
  race_valid_weight_count INTEGER NOT NULL,
  weight_relative REAL,
  weight_relative_missing INTEGER NOT NULL,
  as_of_exclusive TEXT NOT NULL,
  feature_builder_version TEXT NOT NULL,
  formula_version TEXT NOT NULL,
  source_snapshot TEXT NOT NULL,
  calculated_at TEXT NOT NULL,
  validation_status TEXT NOT NULL,
  PRIMARY KEY(race_key,horse_no)
);

CREATE TABLE ability_feature_snapshot(
  race_key TEXT NOT NULL,
  horse_no INTEGER NOT NULL,
  career_scored_run_count INTEGER NOT NULL,
  recent_scored_run_count INTEGER NOT NULL,
  last_scored_run_date TEXT,
  rest_days INTEGER,
  is_debut INTEGER NOT NULL,
  recent_perf_d070 REAL, recent_perf_d070_n INTEGER NOT NULL, recent_perf_d070_neff REAL, recent_perf_d070_missing INTEGER NOT NULL,
  recent_perf_d080 REAL, recent_perf_d080_n INTEGER NOT NULL, recent_perf_d080_neff REAL, recent_perf_d080_missing INTEGER NOT NULL,
  recent_perf_d090 REAL, recent_perf_d090_n INTEGER NOT NULL, recent_perf_d090_neff REAL, recent_perf_d090_missing INTEGER NOT NULL,
  recent_perf_d100 REAL, recent_perf_d100_n INTEGER NOT NULL, recent_perf_d100_neff REAL, recent_perf_d100_missing INTEGER NOT NULL,
  peak_best1_last5 REAL, peak_best2_mean_last5 REAL,
  performance_mad_last5 REAL, performance_mad_last5_n INTEGER NOT NULL, performance_mad_last5_missing INTEGER NOT NULL,
  surface_same_mean_raw REAL, surface_overall_mean_raw REAL, surface_fit_delta_raw REAL, surface_fit_n INTEGER NOT NULL, surface_fit_neff REAL, surface_fit_missing INTEGER NOT NULL,
  distance_d200_mean_raw REAL, distance_d200_delta_raw REAL, distance_d200_n INTEGER NOT NULL, distance_d200_neff REAL, distance_d200_missing INTEGER NOT NULL,
  distance_d400_mean_raw REAL, distance_d400_delta_raw REAL, distance_d400_n INTEGER NOT NULL, distance_d400_neff REAL, distance_d400_missing INTEGER NOT NULL,
  distance_d600_mean_raw REAL, distance_d600_delta_raw REAL, distance_d600_n INTEGER NOT NULL, distance_d600_neff REAL, distance_d600_missing INTEGER NOT NULL,
  distance_d800_mean_raw REAL, distance_d800_delta_raw REAL, distance_d800_n INTEGER NOT NULL, distance_d800_neff REAL, distance_d800_missing INTEGER NOT NULL,
  exact_distance_count INTEGER NOT NULL, nearest_historical_distance_diff_m INTEGER,
  course_exact_mean_raw REAL, course_exact_delta_raw REAL, course_exact_n INTEGER NOT NULL, course_exact_neff REAL,
  course_surface_backoff_mean_raw REAL, course_fit_missing INTEGER NOT NULL,
  going_same_mean_raw REAL, going_same_n INTEGER NOT NULL, going_fit_missing INTEGER NOT NULL, going_target_availability TEXT NOT NULL,
  jockey_residual_mean_raw REAL, jockey_residual_n INTEGER NOT NULL, jockey_residual_last_date TEXT, jockey_residual_missing INTEGER NOT NULL,
  recent_history_max_date TEXT, aptitude_history_max_date TEXT, jockey_history_max_date TEXT,
  FOREIGN KEY(race_key,horse_no) REFERENCES ability_target_runner(race_key,horse_no)
);

CREATE TABLE ability_current_result(
  race_key TEXT NOT NULL,
  horse_no INTEGER NOT NULL,
  score_status TEXT,
  official_runperf_raw REAL,
  score_provenance TEXT,
  PRIMARY KEY(race_key,horse_no),
  FOREIGN KEY(race_key,horse_no) REFERENCES ability_target_runner(race_key,horse_no)
);

CREATE INDEX ix_ability_target_date ON ability_target_runner(race_date,race_key,horse_no);
CREATE INDEX ix_ability_target_horse ON ability_target_runner(horse_id,race_date,race_key);
CREATE INDEX ix_ability_target_jockey ON ability_target_runner(jockey_code,race_date);
