PRAGMA foreign_keys=ON;

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

CREATE TABLE fact_entry_result_lite(
  race_date TEXT,
  year INTEGER,
  venue_code TEXT,
  race_no INTEGER,
  track_type TEXT,
  distance INTEGER,
  condition_code TEXT,
  grade_code TEXT,
  race_key TEXT NOT NULL,
  horse_no INTEGER NOT NULL,
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
  PRIMARY KEY(race_key, horse_no)
);

CREATE INDEX ix_analysis_date ON fact_entry_result_lite(race_date);
CREATE INDEX ix_analysis_course ON fact_entry_result_lite(year,venue_code,track_type,distance);
CREATE INDEX ix_analysis_sire ON fact_entry_result_lite(sire_name);
CREATE INDEX ix_analysis_bms ON fact_entry_result_lite(broodmare_sire_name);
CREATE INDEX ix_analysis_jockey ON fact_entry_result_lite(jockey_name);
CREATE INDEX ix_analysis_style ON fact_entry_result_lite(running_style);
CREATE INDEX ix_analysis_popularity ON fact_entry_result_lite(final_win_popularity);
