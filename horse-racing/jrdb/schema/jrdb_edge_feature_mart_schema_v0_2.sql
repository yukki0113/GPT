PRAGMA foreign_keys=ON;

CREATE TABLE meta_edge_feature_mart_build(
  build_id INTEGER PRIMARY KEY,
  builder_version TEXT NOT NULL,
  schema_version TEXT NOT NULL,
  source_path TEXT NOT NULL,
  built_at TEXT NOT NULL,
  row_count INTEGER NOT NULL,
  pre_race_eligible_count INTEGER NOT NULL,
  result_labeled_count INTEGER NOT NULL,
  anomaly_count INTEGER NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('VALID','INVALID')),
  message TEXT
);

CREATE TABLE edge_runner_fact(
  race_key TEXT NOT NULL,
  horse_no INTEGER NOT NULL,
  race_date TEXT NOT NULL,
  venue_code TEXT NOT NULL,
  race_no INTEGER NOT NULL,
  distance_m INTEGER,
  surface_code TEXT,
  turn_code TEXT,
  inner_outer_code TEXT,
  race_condition_code TEXT,
  grade_code TEXT,
  declared_field_size INTEGER,
  source_availability_class TEXT NOT NULL,
  is_pre_race_eligible INTEGER NOT NULL CHECK(is_pre_race_eligible IN (0,1)),
  frame_no INTEGER,
  frame_zone TEXT,
  horse_id TEXT,
  horse_name TEXT,
  sex_code TEXT,
  horse_age INTEGER,
  jockey_code TEXT,
  jockey_name TEXT,
  trainer_code TEXT,
  trainer_name TEXT,
  carried_weight_kg REAL,
  running_style_code TEXT,
  rotation_interval INTEGER,
  pre_idm REAL,
  training_score REAL,
  stable_score REAL,
  uptrend_code TEXT,
  training_arrow_code TEXT,
  stable_evaluation_code TEXT,
  body_weight_pre_kg INTEGER,
  body_weight_change_pre_kg INTEGER,
  condition_class_code TEXT,
  profile_asof_date TEXT,
  birth_date TEXT,
  sire_name TEXT,
  sire_line_code TEXT,
  broodmare_sire_name TEXT,
  broodmare_sire_line_code TEXT,
  prev1_result_key TEXT,
  prev1_race_key TEXT,
  prev1_race_date TEXT,
  prev1_venue_code TEXT,
  prev1_distance_m INTEGER,
  prev1_surface_code TEXT,
  prev1_turn_code TEXT,
  prev1_frame_no INTEGER,
  prev1_finish INTEGER,
  distance_change_m INTEGER,
  distance_change_bucket TEXT,
  surface_transition TEXT,
  frame_transition TEXT,
  label_finish INTEGER,
  label_abnormal_code TEXT,
  label_win_hit INTEGER CHECK(label_win_hit IN (0,1) OR label_win_hit IS NULL),
  label_place_hit INTEGER CHECK(label_place_hit IN (0,1) OR label_place_hit IS NULL),
  label_win_payout INTEGER,
  label_place_payout INTEGER,
  label_final_win_odds REAL,
  label_final_win_popularity INTEGER,
  calculation_status TEXT NOT NULL CHECK(calculation_status IN ('ELIGIBLE','NO_RESULT','ABNORMAL','SOURCE_NOT_PRE_RACE')),
  PRIMARY KEY(race_key, horse_no)
);

CREATE INDEX ix_edge_fact_date ON edge_runner_fact(race_date);
CREATE INDEX ix_edge_fact_course ON edge_runner_fact(venue_code, surface_code, distance_m, turn_code, frame_zone, frame_no);
CREATE INDEX ix_edge_fact_sire ON edge_runner_fact(sire_name, race_date);
CREATE INDEX ix_edge_fact_bms ON edge_runner_fact(broodmare_sire_name, race_date);
CREATE INDEX ix_edge_fact_sire_age ON edge_runner_fact(sire_name, horse_age, race_date);
CREATE INDEX ix_edge_fact_jockey ON edge_runner_fact(jockey_code, race_date);
CREATE INDEX ix_edge_fact_trainer ON edge_runner_fact(trainer_code, race_date);
CREATE INDEX ix_edge_fact_human_pair ON edge_runner_fact(jockey_code, trainer_code, race_date);
CREATE INDEX ix_edge_fact_recent ON edge_runner_fact(surface_code, distance_m, uptrend_code, training_arrow_code, stable_evaluation_code, rotation_interval, race_date);
CREATE INDEX ix_edge_fact_transition ON edge_runner_fact(distance_change_bucket, surface_transition, frame_transition, race_date);
