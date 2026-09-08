PRAGMA foreign_keys=ON;

-- JRDB Edge Registry schema v0.1
-- Persistent statistical knowledge layer. Raw/JRDB databases remain source truth.

CREATE TABLE edge_registry_meta(
  registry_version TEXT PRIMARY KEY,
  policy_version TEXT NOT NULL,
  generated_at TEXT NOT NULL,
  source_scope TEXT NOT NULL,
  source_manifest_json TEXT,
  status TEXT NOT NULL CHECK(status IN ('BUILDING','VALID','INVALID')),
  message TEXT
);

CREATE TABLE edge_definition(
  edge_id TEXT PRIMARY KEY,
  registry_version TEXT NOT NULL,
  family TEXT NOT NULL CHECK(family IN ('COURSE','PEDIGREE','TRANSITION','HUMAN','RECENT')),
  anchor_type TEXT NOT NULL,
  anchor_id TEXT,
  anchor_name TEXT,
  validation_class TEXT NOT NULL CHECK(validation_class IN ('STRUCTURAL','LIFECYCLE','DYNAMIC','EMERGING')),
  policy_id TEXT NOT NULL,
  polarity TEXT NOT NULL CHECK(polarity IN ('POSITIVE','NEGATIVE','MIXED')),
  performance_signal TEXT NOT NULL CHECK(performance_signal IN ('POSITIVE','NEGATIVE','NEUTRAL','UNASSESSED')),
  value_signal TEXT NOT NULL CHECK(value_signal IN ('POSITIVE','NEGATIVE','NEUTRAL','UNASSESSED')),
  status TEXT NOT NULL CHECK(status IN ('WATCH','PROVISIONAL','ACTIVE','REVIEW_DUE','DECAYING','EXPIRED','RETIRED','REJECTED')),
  conditions_json TEXT NOT NULL,
  display_text TEXT NOT NULL,
  edge_cluster TEXT,
  parent_edge_id TEXT,
  specificity INTEGER NOT NULL DEFAULT 0,
  first_observed_date TEXT,
  last_observed_date TEXT,
  last_validated_at TEXT,
  next_review_at TEXT,
  expires_at TEXT,
  strength_score REAL,
  confidence_band TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(registry_version) REFERENCES edge_registry_meta(registry_version),
  FOREIGN KEY(parent_edge_id) REFERENCES edge_definition(edge_id)
);

CREATE TABLE edge_metric_snapshot(
  edge_id TEXT NOT NULL,
  snapshot_id TEXT NOT NULL,
  as_of_date TEXT NOT NULL,
  slice_kind TEXT NOT NULL CHECK(slice_kind IN ('ALL','SEGMENT','ROLLING_WINDOW','BASELINE')),
  slice_label TEXT NOT NULL,
  period_start TEXT,
  period_end TEXT,
  sample_n INTEGER NOT NULL,
  unique_horses INTEGER,
  unique_races INTEGER,
  win_rate REAL,
  place_rate REAL,
  win_roi REAL,
  place_roi REAL,
  baseline_win_rate REAL,
  baseline_place_rate REAL,
  performance_lift REAL,
  largest_return_share REAL,
  top3_return_share REAL,
  largest_horse_sample_share REAL,
  direction INTEGER CHECK(direction IN (-1,0,1)),
  metrics_json TEXT,
  PRIMARY KEY(edge_id, snapshot_id),
  FOREIGN KEY(edge_id) REFERENCES edge_definition(edge_id)
);

CREATE TABLE edge_validation_event(
  validation_id INTEGER PRIMARY KEY,
  edge_id TEXT NOT NULL,
  evaluated_at TEXT NOT NULL,
  policy_id TEXT NOT NULL,
  policy_version TEXT NOT NULL,
  decision TEXT NOT NULL CHECK(decision IN ('WATCH','PROVISIONAL','ACTIVATE','KEEP','REVIEW_DUE','DECAY','EXPIRE','RETIRE','REJECT')),
  failure_reason TEXT,
  evidence_json TEXT NOT NULL,
  FOREIGN KEY(edge_id) REFERENCES edge_definition(edge_id)
);

CREATE INDEX ix_edge_definition_active ON edge_definition(status, family, anchor_type);
CREATE INDEX ix_edge_definition_anchor ON edge_definition(anchor_type, anchor_id, anchor_name);
CREATE INDEX ix_edge_definition_review ON edge_definition(next_review_at, expires_at);
CREATE INDEX ix_edge_metric_asof ON edge_metric_snapshot(edge_id, as_of_date, slice_kind);
CREATE INDEX ix_edge_validation_event_time ON edge_validation_event(edge_id, evaluated_at);
