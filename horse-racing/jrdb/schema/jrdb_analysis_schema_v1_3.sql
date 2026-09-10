PRAGMA foreign_keys=ON;

-- JRDB Analysis Lite schema v1.3
-- v1.3 adds BAC WIN5 leg number while preserving v1.2 previous-result linkage,
-- incremental ingest metadata, and the horse-history access index.

CREATE TABLE meta_analysis_build(
  build_id INTEGER PRIMARY KEY,
  builder_version TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  source_core_sha256 TEXT,
  started_at TEXT,
  finished_at TEXT,
  status TEXT,
  row_count INTEGER
);

CREATE TABLE meta_analysis_ingest_batch(
  batch_id INTEGER PRIMARY KEY,
  target_date TEXT NOT NULL,
  builder_version TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  source_manifest TEXT,
  source_sha256s TEXT,
  race_count INTEGER,
  row_count INTEGER,
  replaced_row_count INTEGER,
  message TEXT
);

CREATE TABLE fact_entry_result_lite(
  race_date TEXT,
  year INTEGER,
  venue_code TEXT,
  race_no INTEGER,
  track_type TEXT,
  distance INTEGER,
  race_condition_code TEXT,
  track_condition_code TEXT,
  grade_code TEXT,
  win5_leg_no INTEGER CHECK(win5_leg_no IS NULL OR win5_leg_no BETWEEN 1 AND 5),
  race_key TEXT NOT NULL,
  horse_no INTEGER NOT NULL,
  frame_no INTEGER,
  horse_id TEXT,
  horse_name TEXT,
  sex_code TEXT,
  age INTEGER,
  sire_name TEXT,
  broodmare_sire_name TEXT,
  sire_line_code TEXT,
  broodmare_sire_line_code TEXT,
  jockey_name TEXT,
  running_style TEXT,
  distance_aptitude TEXT,
  uptrend TEXT,
  training_index REAL,
  finish INTEGER,
  abnormal_code TEXT,
  final_win_odds REAL,
  final_win_popularity INTEGER,
  win_payout INTEGER,
  place_payout INTEGER,
  prev_result_key_1 TEXT,
  prev_race_key_1 TEXT,
  PRIMARY KEY(race_key, horse_no)
);

CREATE INDEX ix_analysis_date ON fact_entry_result_lite(race_date);
CREATE INDEX ix_analysis_horse_history ON fact_entry_result_lite(horse_id,race_date DESC,race_no DESC);
CREATE INDEX ix_analysis_course ON fact_entry_result_lite(year,venue_code,track_type,distance,track_condition_code);
CREATE INDEX ix_analysis_sire ON fact_entry_result_lite(sire_name);
CREATE INDEX ix_analysis_bms ON fact_entry_result_lite(broodmare_sire_name);
CREATE INDEX ix_analysis_jockey ON fact_entry_result_lite(jockey_name);
CREATE INDEX ix_analysis_style ON fact_entry_result_lite(running_style);
CREATE INDEX ix_analysis_popularity ON fact_entry_result_lite(final_win_popularity);
CREATE INDEX ix_analysis_frame ON fact_entry_result_lite(frame_no);
CREATE INDEX ix_analysis_ingest_date ON meta_analysis_ingest_batch(target_date,status);
