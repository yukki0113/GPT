PRAGMA foreign_keys=ON;

-- Blood Review DB pedigree fact schema v0.1.
-- FACT, relation resolution, lineage taxonomy, aliases, and later REVIEW remain separated.

CREATE TABLE meta_brdb_pedigree_generation(
  generation_id TEXT PRIMARY KEY,
  schema_version TEXT NOT NULL,
  source_family TEXT NOT NULL,
  source_generation TEXT,
  source_min_data_date TEXT,
  source_max_data_date TEXT,
  built_at TEXT NOT NULL,
  validation_status TEXT NOT NULL CHECK(validation_status IN ('PASS','FAIL')),
  row_count INTEGER NOT NULL,
  message TEXT
);

CREATE TABLE pedigree_fact(
  horse_id TEXT PRIMARY KEY,
  horse_name TEXT NOT NULL,
  birth_date TEXT,
  sex_code TEXT,
  sire_name TEXT,
  sire_birth_year INTEGER,
  dam_name TEXT,
  dam_birth_year INTEGER,
  broodmare_sire_name TEXT,
  broodmare_sire_birth_year INTEGER,
  sire_line_code TEXT,
  broodmare_sire_line_code TEXT,
  breeding_place TEXT,
  profile_data_date TEXT NOT NULL,
  semantic_hash TEXT NOT NULL,
  source_family TEXT NOT NULL DEFAULT 'UKC',
  source_generation TEXT NOT NULL
);

CREATE INDEX ix_brdb_pedigree_name_birth
  ON pedigree_fact(horse_name, substr(birth_date,1,4));
CREATE INDEX ix_brdb_pedigree_sire
  ON pedigree_fact(sire_name, sire_birth_year);
CREATE INDEX ix_brdb_pedigree_dam
  ON pedigree_fact(dam_name, dam_birth_year);
CREATE INDEX ix_brdb_pedigree_bms
  ON pedigree_fact(broodmare_sire_name, broodmare_sire_birth_year);

CREATE TABLE pedigree_name_alias(
  observed_name TEXT NOT NULL,
  canonical_name TEXT NOT NULL,
  birth_year INTEGER NOT NULL,
  lineage_code TEXT NOT NULL,
  evidence_type TEXT NOT NULL,
  evidence_count INTEGER NOT NULL CHECK(evidence_count > 0),
  first_observed TEXT,
  last_observed TEXT,
  alias_version TEXT NOT NULL,
  source_generation TEXT NOT NULL,
  PRIMARY KEY(observed_name, canonical_name, birth_year, lineage_code, alias_version)
);

CREATE TABLE parent_relation(
  child_horse_id TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('sire','dam','broodmare_sire')),
  parent_name TEXT NOT NULL,
  parent_birth_year INTEGER,
  parent_lineage_code TEXT,
  resolved_parent_horse_id TEXT,
  resolution_status TEXT NOT NULL CHECK(resolution_status IN (
    'RESOLVED_EXACT',
    'RESOLVED_ALIAS',
    'NO_CANDIDATE',
    'MULTIPLE_CANDIDATES',
    'INSUFFICIENT_KEY',
    'INSUFFICIENT_GUARD',
    'CONFLICT'
  )),
  resolution_method TEXT CHECK(resolution_method IN (
    'UKC_EXACT_NAME_BIRTH_YEAR',
    'UKC_ALIAS_NAME_BIRTH_YEAR'
  ) OR resolution_method IS NULL),
  candidate_count INTEGER NOT NULL DEFAULT 0,
  guard_result TEXT,
  resolver_version TEXT NOT NULL,
  source_generation TEXT NOT NULL,
  PRIMARY KEY(child_horse_id, role),
  FOREIGN KEY(child_horse_id) REFERENCES pedigree_fact(horse_id)
);

CREATE INDEX ix_brdb_parent_resolved
  ON parent_relation(resolved_parent_horse_id);
CREATE INDEX ix_brdb_parent_status
  ON parent_relation(resolution_status, role);

CREATE TABLE lineage_code_master(
  lineage_code TEXT PRIMARY KEY,
  major_code TEXT NOT NULL,
  major_name TEXT NOT NULL,
  minor_name TEXT NOT NULL,
  source_name TEXT NOT NULL,
  source_version TEXT NOT NULL
);
