PRAGMA foreign_keys=ON;

CREATE TABLE meta_analysis_build(
  build_id INTEGER PRIMARY KEY,
  builder_version TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  years TEXT NOT NULL,
  row_count INTEGER,
  db_size_bytes INTEGER,
  status TEXT NOT NULL
);

CREATE TABLE fact_entry_result_lite(
  race_date TEXT NOT NULL,
  year INTEGER NOT NULL,
  venue_code TEXT NOT NULL,
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
CREATE INDEX ix_analysis_course ON fact_entry_result_lite(venue_code,track_type,distance);
CREATE INDEX ix_analysis_sire ON fact_entry_result_lite(sire_name);
CREATE INDEX ix_analysis_bms ON fact_entry_result_lite(broodmare_sire_name);
CREATE INDEX ix_analysis_jockey ON fact_entry_result_lite(jockey_name);
CREATE INDEX ix_analysis_horse ON fact_entry_result_lite(horse_id);
