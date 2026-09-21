# JRDB Training Research Parquet Operation v0.1

> Current status — 2026-09-21  
> Parquet ZSTD canonical cutover is complete. Normal research resolves the current
> generation and reads `training_development.parquet` (2010–2023) with DuckDB.
> The SQLite source shown in the build command below is a transient regeneration /
> migration input only, not an analytical canonical or a normal research dependency.

## Canonical storage

The long-term analytical canonical is an immutable Parquet ZSTD generation.
SQLite is allowed only while building and comparing a generation; it is not a
published analytical artifact.

```text
20_mart/training_research/v0.1/
  build-<UTC build id>/
    training_runner.parquet
    training_development.parquet
    training_holdout_locked.parquet
    source_archive.parquet
    manifest.json
    conversion_audit.json
    scientific_regression.json
  current.json
```

`current.json` is changed only after every conversion, full row comparison,
holdout contract check, and Stage 1b SQLite/Parquet regression succeeds.

Logical URIs are:

- `jrdb://training-research/v0.1` → `training_runner.parquet`
- `jrdb://training-research/v0.1/development` → `training_development.parquet`
- `jrdb://training-research/v0.1/holdout-locked` → `training_holdout_locked.parquet`

Normal research consumers use `/development`. It physically contains only
2010–2023. The consumer additionally asserts `year <= 2023`.

## Build command

The source must be the completed 2010–2025 Training Research SQLite build.

```bash
PYTHONPATH=tools/data-storage:horse-racing/jrdb/src \
  python horse-racing/jrdb/src/migrate_jrdb_training_research_parquet.py \
  --source-sqlite /path/jrdb_training_research_2010_2025_v0_1.sqlite \
  --output-root /path/20_mart/training_research/v0.1 \
  --build-id 20260916T000000Z \
  --delete-source-after-success
```

The deletion flag is intentionally explicit. Before deletion, the audit records
the SQLite filename, bytes, and SHA-256. The caller must publish the complete
generation to Drive, fetch it again, and rerun validation before deleting the
Drive SQLite/SQLite ZIP objects.

## Gates

The migration runner uses `tools/data-storage` for all SQLite-to-Parquet
conversion and baseline validation. JRDB-specific gates add:

- exact ordered row equality for `training_runner`, including 32-byte
  `source_record_hash`;
- canonical-key, schema, NULL, range, and row-count checks;
- a separate WARMUP + DEVELOPMENT artifact (2010–2023);
- outcome-free 2024–2025 holdout schema assertion;
- source archive migration;
- complete Stage 1b SQLite vs Parquet comparison with an absolute floating
  tolerance of `1e-12`.

No generation is current when any gate fails.
