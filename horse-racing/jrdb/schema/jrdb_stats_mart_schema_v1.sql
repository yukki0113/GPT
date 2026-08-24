PRAGMA foreign_keys=ON;

CREATE TABLE meta_mart_build(
  build_id INTEGER PRIMARY KEY,
  builder_version TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  source_files TEXT NOT NULL,
  source_years TEXT NOT NULL,
  status TEXT NOT NULL
);

CREATE TABLE mart_sire_yearly(
  year INTEGER NOT NULL,
  venue_code TEXT NOT NULL,
  track_type TEXT,
  distance INTEGER,
  condition_code TEXT,
  sire_name TEXT NOT NULL,
  starts INTEGER NOT NULL,
  wins INTEGER NOT NULL,
  seconds INTEGER NOT NULL,
  thirds INTEGER NOT NULL,
  top3 INTEGER NOT NULL,
  win_payout_sum INTEGER NOT NULL,
  place_payout_sum INTEGER NOT NULL,
  PRIMARY KEY(year,venue_code,track_type,distance,condition_code,sire_name)
);

CREATE TABLE mart_jockey_yearly(
  year INTEGER NOT NULL,
  venue_code TEXT NOT NULL,
  track_type TEXT,
  distance INTEGER,
  condition_code TEXT,
  jockey_name TEXT NOT NULL,
  starts INTEGER NOT NULL,
  wins INTEGER NOT NULL,
  seconds INTEGER NOT NULL,
  thirds INTEGER NOT NULL,
  top3 INTEGER NOT NULL,
  win_payout_sum INTEGER NOT NULL,
  place_payout_sum INTEGER NOT NULL,
  PRIMARY KEY(year,venue_code,track_type,distance,condition_code,jockey_name)
);

CREATE INDEX ix_mart_sire_query ON mart_sire_yearly(venue_code,track_type,distance,sire_name,year);
CREATE INDEX ix_mart_jockey_query ON mart_jockey_yearly(venue_code,track_type,distance,jockey_name,year);
