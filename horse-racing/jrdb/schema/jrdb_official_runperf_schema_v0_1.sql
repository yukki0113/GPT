PRAGMA foreign_keys=ON;

-- Official JRDB PWA RunPerf v0.1 materialization.
-- The score is T1|EXPANDING|RAW with annual as-of coefficient snapshots.

CREATE TABLE meta_official_runperf_build(
  build_id INTEGER PRIMARY KEY,
  builder_version TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  source_runperf_db_path TEXT NOT NULL,
  source_runperf_db_sha256 TEXT,
  official_candidate TEXT NOT NULL,
  baseline_method TEXT NOT NULL,
  first_model_year INTEGER NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  source_year_min INTEGER,
  source_year_max INTEGER,
  source_runner_count INTEGER,
  materialized_runner_count INTEGER,
  scored_runner_count INTEGER,
  message TEXT
);

CREATE TABLE runperf_coefficient_snapshot(
  target_year INTEGER PRIMARY KEY,
  coefficient_asof_through_year INTEGER NOT NULL,
  training_pair_count INTEGER NOT NULL,
  pair_count_by_target_year_json TEXT NOT NULL,
  intercept REAL NOT NULL,
  beta_time_raw_bias REAL NOT NULL,
  beta_margin_score REAL NOT NULL,
  fitter_version TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE official_runperf(
  race_key TEXT NOT NULL,
  race_date TEXT NOT NULL,
  year INTEGER NOT NULL,
  horse_no INTEGER NOT NULL,
  horse_id TEXT,
  source_calculation_status TEXT NOT NULL,
  score_status TEXT NOT NULL,
  expected_time_sec REAL,
  day_bias_raw_sec REAL,
  time_raw_bias_sec REAL,
  margin_score REAL,
  runperf_raw REAL,
  coefficient_snapshot_target_year INTEGER,
  coefficient_asof_through_year INTEGER,
  coefficient_intercept REAL,
  coefficient_beta_time REAL,
  coefficient_beta_margin REAL,
  score_provenance TEXT NOT NULL,
  PRIMARY KEY(race_key, horse_no)
);

CREATE INDEX ix_official_runperf_date ON official_runperf(race_date, race_key, horse_no);
CREATE INDEX ix_official_runperf_year ON official_runperf(year, score_status);
CREATE INDEX ix_official_runperf_horse ON official_runperf(horse_id, race_date, race_key);
CREATE INDEX ix_official_runperf_snapshot ON official_runperf(coefficient_snapshot_target_year);

CREATE VIEW v_official_runperf_scored AS
SELECT *
FROM official_runperf
WHERE score_status='OK'
  AND runperf_raw IS NOT NULL;
