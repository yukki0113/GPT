# JRDB Newspaper current publish request

This directory defines the small Git-side request that starts the Newspaper current-candidate build.

## Contract

Create or replace `current.json` only after the completed Newspaper day-package has been uploaded to Google Drive.

Required fields:

- `schema_version`: `"0.1"`
- `request_kind`: `"jrdb_newspaper_publish_request"`
- `date`: target date in `YYYY-MM-DD`
- `revision`: positive integer
- `drive_file_id`: Google Drive file ID for the single day-package JSON
- `source_filename`: JSON basename used when downloading
- `size_bytes`: exact source file size
- `sha256`: exact lowercase SHA-256 of the source bytes
- `expected_races`: expected race count, 1..36
- `source_commit`: 40-character Git commit SHA of the source/runtime used to build the day-package

`current.example.json` is illustrative only. Do not copy its placeholder hashes into `current.json`.

## Route

1. Generate and audit one `jrdb_pwa_newspaper_day_package` locally / in Work.
2. Upload that single JSON to Google Drive.
3. Record exact `size_bytes` and `sha256`.
4. Direct-commit `current.json`.
5. `.github/workflows/jrdb_newspaper_publish_current.yml` downloads the Drive file, verifies exact bytes, runs `jrdb_newspaper_publish_current.py`, validates date/revision/race count and every published race SHA/size, then uploads a 7-day candidate artifact.

Phase 2 intentionally stops at the validated candidate artifact. Release/current cache and GitHub Pages integration belong to Phase 3.

## Failure semantics

The workflow fails closed. A Drive permission page, stale file, wrong size/hash, mismatched race identity, revision/date mismatch, incomplete race count, or published SHA mismatch prevents a candidate artifact from being accepted.
