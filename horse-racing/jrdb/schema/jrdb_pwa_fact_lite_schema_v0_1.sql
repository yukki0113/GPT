PRAGMA foreign_keys=OFF;

CREATE TABLE meta_pwa_fact_build(
  build_id INTEGER PRIMARY KEY,
  builder_version TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  source_analysis TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  status TEXT NOT NULL,
  row_count INTEGER,
  period_from TEXT,
  period_to TEXT
);

CREATE TABLE dim_sire(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE dim_bms(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE dim_jockey(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE fact_stats_entry(
  race_date_int INTEGER NOT NULL,
  year INTEGER NOT NULL,
  venue_code INTEGER NOT NULL,
  race_no INTEGER NOT NULL,
  track_type INTEGER NOT NULL,
  distance INTEGER NOT NULL,
  race_condition_code TEXT,
  track_condition_code INTEGER,
  grade_code INTEGER,
  frame_no INTEGER,
  sex_code INTEGER,
  age INTEGER,
  sire_id INTEGER,
  bms_id INTEGER,
  sire_line_code INTEGER,
  bms_line_code INTEGER,
  jockey_id INTEGER,
  running_style INTEGER,
  distance_aptitude INTEGER,
  uptrend INTEGER,
  training_index INTEGER,
  final_win_popularity INTEGER,
  finish INTEGER,
  win_payout INTEGER,
  place_payout INTEGER
);

CREATE INDEX ix_pwa_fact_course
ON fact_stats_entry(year, venue_code, track_type, distance, track_condition_code);

CREATE INDEX ix_pwa_fact_date
ON fact_stats_entry(race_date_int);
