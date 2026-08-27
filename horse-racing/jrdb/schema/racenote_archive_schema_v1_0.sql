-- RaceNote Archive schema v1.0
--
-- Logical role:
--   Historical delivery cache for base RaceNote v0.2 bundles.
--
-- Storage unit:
--   One calendar month per SQLite file.
--   One race = one zlib-compressed UTF-8 JSON BLOB.
--
-- This schema intentionally does not normalize RaceNote JSON fields.
-- Raw/Core remain the authoritative rebuild sources.

PRAGMA foreign_keys = ON;

CREATE TABLE archive_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE source_input (
    source_id INTEGER PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_period TEXT NOT NULL,
    filename TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    role TEXT NOT NULL,
    UNIQUE (source_type, source_period, filename, role)
);

CREATE TABLE race_bundle (
    race_date TEXT NOT NULL,
    venue_code TEXT NOT NULL,
    venue TEXT NOT NULL,
    race_no INTEGER NOT NULL CHECK (race_no BETWEEN 1 AND 12),
    race_key TEXT NOT NULL,
    field_size INTEGER,
    base_schema_version TEXT NOT NULL,
    source_mode TEXT NOT NULL CHECK (
        source_mode IN ('paci', 'annual_raw_reconstruction')
    ),
    source_ref TEXT,
    bundle_zlib BLOB NOT NULL,
    bundle_json_bytes INTEGER NOT NULL CHECK (bundle_json_bytes >= 0),
    bundle_sha256 TEXT NOT NULL,
    semantic_sha256 TEXT NOT NULL,
    warning_count INTEGER NOT NULL DEFAULT 0 CHECK (warning_count >= 0),
    PRIMARY KEY (race_date, venue_code, race_no),
    UNIQUE (race_key)
);

CREATE INDEX idx_race_bundle_date
    ON race_bundle (race_date);

CREATE INDEX idx_race_bundle_date_venue
    ON race_bundle (race_date, venue_code, race_no);

-- Required archive_meta keys for v1.0:
--   archive_schema_version = 1.0
--   base_schema_version    = 0.2
--   target_month           = YYYYMM
--   converter_git_sha      = Git commit used for base conversion
--   compression            = zlib
--   semantic_hash_rule     = omit metadata.generated_at only
--   coverage_start         = YYYY-MM-DD
--   coverage_end           = YYYY-MM-DD
--   race_count             = decimal integer text
--   built_at               = ISO-8601 timestamp
--
-- Recommended validation before publishing a shard:
--   PRAGMA integrity_check = ok
--   no race rows outside target_month
--   duplicate PK = 0
--   duplicate race_key = 0
--   every bundle decompresses
--   every bundle_sha256 matches decompressed bytes
--   every bundle schema_version = 0.2
--   every JSON race date/venue/race matches index columns
--   all recent_runs dates < target race date
