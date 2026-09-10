# JRDB Newspaper current publish request

This directory defines the small Git-side request that publishes the current Newspaper day from a canonical Google Drive day-package.

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
5. `.github/workflows/jrdb_newspaper_publish_current.yml` downloads the Drive file and verifies the exact source bytes.
6. The workflow runs `jrdb_newspaper_publish_current.py`, validates date/revision/race count and every published race SHA/size, and keeps a 7-day candidate artifact.
7. Only after that validation passes, the workflow builds a deterministic `jrdb_newspaper_current.tar.xz` plus release metadata and replaces the assets of the mutable `jrdb-newspaper-current` GitHub Release cache.
8. Successful completion triggers `JRDB PWA Pages`; the Pages workflow downloads the release cache, verifies archive SHA/size, safely extracts it, re-verifies manifest and all race SHA/size values, and places it under `data/newspaper/current/`.

The Google Drive day-package remains the canonical daily asset. The GitHub Release is a mutable delivery cache, not the historical source of truth.

## Release cache

Tag:

`jrdb-newspaper-current`

Assets:

- `jrdb_newspaper_current.tar.xz`: compact transport containing `manifest.json` and `races/*.json`.
- `jrdb_newspaper_current_release.json`: exact archive/source/manifest hashes, date, revision and race count.
- `candidate-audit.json`: validation record from the publish workflow.

Normal PWA source-only deploys also restore the latest Newspaper cache from this Release, so UI changes do not remove the current newspaper data.

## Failure semantics

The route fails closed. A Drive permission page, stale file, wrong size/hash, mismatched race identity, revision/date mismatch, incomplete race count, published SHA mismatch, corrupt release archive, unsafe archive member, or release metadata mismatch prevents the cache from being accepted by the publisher or Pages deployment.

The existing successfully published Release remains untouched until a new candidate has passed source and candidate validation. If Pages cannot validate the Release cache, deployment fails rather than serving partially verified Newspaper data.
