-- BRDB ① stallion feature master proposal, research only, not a CURRENT schema migration.
-- JRDB lineage_code_master remains authoritative for the line taxonomy.
-- horse_id is NOT substituted with a locally allocated subject key.
CREATE TABLE stallion_subject_candidate (
  subject_key TEXT PRIMARY KEY,
  canonical_name TEXT NOT NULL,
  jrdb_horse_id TEXT UNIQUE,
  identity_status TEXT NOT NULL CHECK(identity_status IN
    ('JRDB_VERIFIED','EXTERNAL_VERIFIED','PENDING','CONFLICT')),
  identity_source TEXT NOT NULL,
  identity_source_version TEXT,
  identity_source_record_key TEXT,
  observed_from TEXT,
  effective_from TEXT,
  source_generation TEXT NOT NULL,
  CHECK(jrdb_horse_id IS NULL OR
    (length(jrdb_horse_id)=8 AND jrdb_horse_id NOT GLOB '*[^0-9]*')),
  CHECK(identity_status <> 'JRDB_VERIFIED' OR jrdb_horse_id IS NOT NULL),
  CHECK(identity_status <> 'EXTERNAL_VERIFIED'
    OR (identity_source_record_key IS NOT NULL AND identity_source_version IS NOT NULL))
);

CREATE TABLE stallion_official_line_candidate (
  subject_key TEXT NOT NULL REFERENCES stallion_subject_candidate(subject_key),
  jrdb_lineage_code TEXT NOT NULL REFERENCES lineage_code_master(lineage_code),
  official_source_generation TEXT NOT NULL,
  evidence_ref TEXT NOT NULL,
  verification_status TEXT NOT NULL CHECK (verification_status IN
    ('REVIEWED','CANDIDATE','CONFLICT')),
  PRIMARY KEY(subject_key, jrdb_lineage_code, official_source_generation)
);

-- Each row represents ONE certified ancestor-person identity + ONE exact S/D path.
-- A speculative ancestor match is retained outside this table, in a staging queue.
CREATE TABLE stallion_ancestor_path_candidate (
  subject_key TEXT NOT NULL REFERENCES stallion_subject_candidate(subject_key),
  ancestor_subject_key TEXT NOT NULL REFERENCES stallion_subject_candidate(subject_key),
  path TEXT NOT NULL,
  depth INTEGER NOT NULL CHECK(depth BETWEEN 1 AND 5),
  evidence_ref TEXT NOT NULL,
  pedigree_source_version TEXT NOT NULL,
  identity_verification_status TEXT NOT NULL CHECK(identity_verification_status IN
    ('JRDB_VERIFIED','EXTERNAL_VERIFIED')),
  historical_asof_status TEXT NOT NULL CHECK(historical_asof_status IN
    ('AS_OF_VERIFIED','AS_OF_UNVERIFIED')),
  observed_from TEXT,
  source_generation TEXT NOT NULL,
  PRIMARY KEY (subject_key, ancestor_subject_key, path, source_generation),
  CHECK(length(path)=depth AND path NOT GLOB '*[^SD]*'),
  CHECK(subject_key <> ancestor_subject_key)
);

-- Regional roots are reviewed descriptors, never nationalities, inferred genes,
-- lineage-code synonyms or suitability scores.
CREATE TABLE stallion_regional_root_candidate (
  subject_key TEXT NOT NULL REFERENCES stallion_subject_candidate(subject_key),
  region_tag TEXT NOT NULL CHECK(region_tag IN
    ('JP_RACING','US_RACING','EU_RACING','SOUTHERN_HEMISPHERE_RACING')),
  taxonomy_version TEXT NOT NULL,
  taxonomy_review_status TEXT NOT NULL CHECK(taxonomy_review_status IN
    ('CANDIDATE','REVIEWED')),
  pedigree_path TEXT,
  evidence_ref TEXT NOT NULL,
  effective_from TEXT,
  PRIMARY KEY(subject_key, region_tag, taxonomy_version, evidence_ref),
  CHECK(pedigree_path IS NULL OR
    (length(pedigree_path) BETWEEN 1 AND 5 AND pedigree_path NOT GLOB '*[^SD]*'))
);

-- Incomplete coverage must remain unknown, including mother-of-dam lineage.
CREATE TABLE stallion_feature_snapshot_candidate (
  subject_key TEXT NOT NULL REFERENCES stallion_subject_candidate(subject_key),
  build_generation TEXT NOT NULL,
  source_generation TEXT NOT NULL,
  observed_depth INTEGER NOT NULL CHECK(observed_depth BETWEEN 0 AND 5),
  resolved_paths INTEGER NOT NULL CHECK(resolved_paths >= 0),
  expected_paths INTEGER NOT NULL CHECK(expected_paths >= resolved_paths),
  historic_asof_status TEXT NOT NULL CHECK(historic_asof_status IN
    ('AS_OF_VERIFIED','AS_OF_UNVERIFIED')),
  prediction_safe INTEGER NOT NULL CHECK(prediction_safe=0),
  PRIMARY KEY(subject_key, build_generation)
);
