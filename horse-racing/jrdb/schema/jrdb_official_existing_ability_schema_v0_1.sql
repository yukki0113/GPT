PRAGMA foreign_keys=ON;

-- Official Existing-Horse Ability v0.1 materialization.
-- Debut horses remain materialized but unscored until the dedicated debut model exists.

CREATE TABLE meta_official_existing_ability_build(
  build_id INTEGER PRIMARY KEY,
  builder_version TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  model_version TEXT NOT NULL,
  source_ability_snapshot_db_path TEXT NOT NULL,
  source_ability_snapshot_db_sha256 TEXT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  source_year_min INTEGER,
  source_year_max INTEGER,
  source_target_runner_count INTEGER,
  materialized_runner_count INTEGER,
  scored_runner_count INTEGER,
  debut_unscored_count INTEGER,
  context_unavailable_count INTEGER,
  warmup_unscored_count INTEGER,
  message TEXT
);

CREATE TABLE ability_model_snapshot(
  target_year INTEGER PRIMARY KEY,
  training_through_year INTEGER NOT NULL,
  training_row_count INTEGER NOT NULL,
  feature_names_json TEXT NOT NULL,
  train_medians_json TEXT NOT NULL,
  train_means_json TEXT NOT NULL,
  train_stds_json TEXT NOT NULL,
  zero_variance_columns_json TEXT NOT NULL,
  intercept REAL NOT NULL,
  coefficients_json TEXT NOT NULL,
  recent_decay TEXT NOT NULL,
  distance_bandwidth_m INTEGER NOT NULL,
  aptitude_shrink_k REAL NOT NULL,
  jockey_shrink_k REAL NOT NULL,
  alpha REAL NOT NULL,
  l1_ratio REAL NOT NULL,
  max_iter INTEGER NOT NULL,
  tolerance REAL NOT NULL,
  random_state INTEGER NOT NULL,
  fitter_version TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE official_existing_ability(
  race_key TEXT NOT NULL,
  race_date TEXT NOT NULL,
  year INTEGER NOT NULL,
  horse_no INTEGER NOT NULL,
  horse_id TEXT,
  career_scored_run_count INTEGER NOT NULL,
  race_context_availability TEXT NOT NULL,
  score_status TEXT NOT NULL,
  ability_raw REAL,
  model_snapshot_target_year INTEGER,
  training_through_year INTEGER,
  score_provenance TEXT NOT NULL,
  PRIMARY KEY(race_key, horse_no),
  FOREIGN KEY(model_snapshot_target_year) REFERENCES ability_model_snapshot(target_year)
);

CREATE INDEX ix_official_existing_ability_date
  ON official_existing_ability(race_date, race_key, horse_no);
CREATE INDEX ix_official_existing_ability_year
  ON official_existing_ability(year, score_status);
CREATE INDEX ix_official_existing_ability_horse
  ON official_existing_ability(horse_id, race_date, race_key);
CREATE INDEX ix_official_existing_ability_snapshot
  ON official_existing_ability(model_snapshot_target_year);

CREATE VIEW v_official_existing_ability_scored AS
SELECT *
FROM official_existing_ability
WHERE score_status='OK'
  AND ability_raw IS NOT NULL;
