# JRDB Analysis Lite Incremental Update

`src/update_jrdb_analysis_incremental.py` incrementally replaces completed race dates in an existing Analysis Lite v1.2 SQLite.

## Production use

Routine flow:

```text
JRDB daily Raw ZIPs
  -> Analysis Lite incremental replacement
  -> Stats Mart refresh
```

Core is not required as an intermediate artifact.

## Required daily Raw

For each target date, all of the following are required:

- BACyymmdd.zip
- KYIyymmdd.zip
- SEDyymmdd.zip
- CYByymmdd.zip
- UKCyymmdd.zip

The updater validates that each archive contains exactly the expected daily TXT member before changing the database.

Because SED is the result source, a date should be ingested only after JRDB has published the completed result-side Raw for that race date.

## Replacement semantics

The updater parses and validates the complete target date first, then performs:

1. record a RUNNING batch in `meta_analysis_ingest_batch`
2. `BEGIN IMMEDIATE`
3. delete existing Analysis rows for the target `race_date`
4. insert the newly parsed rows
5. verify inserted row count
6. COMMIT
7. mark the batch SUCCESS

Re-running the same race date therefore replaces it instead of duplicating it. This is intentional so later JRDB corrections can be re-applied safely.

Each batch records source paths, SHA-256 values, race/row counts and the number of rows replaced.

## Previous-race linkage

Analysis v1.2 stores the JRDB-declared first previous-race linkage directly on each fact row:

- `prev_result_key_1` — KYI previous-result key 1, 0-based offset 203, length 16
- `prev_race_key_1` — KYI previous-race key 1, 0-based offset 283, length 8

All five previous-result links remain available in Raw/Core. Only the first link is promoted into routine Analysis Lite because it covers normal previous-race analysis without exploding the delivery database.

A benchmark of a fully normalized 1-5 previous-link child table for 2016-2025 produced ~1.78 million nonblank link rows and ~81.9 MiB by itself, which would remove too much connector headroom. Keeping prev1 on the fact row is therefore the production compromise.

## Upgrade existing v1.1 Analysis

Use:

```bash
python src/upgrade_jrdb_analysis_v1_1_to_v1_2.py \
  --db ./jrdb_analysis_2016_2025.sqlite \
  --raw-root ./00_raw_local \
  --years 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025
```

This adds the v1.2 columns/batch table and backfills prev1 from annual KYI Raw.

## Incremental run

```bash
python src/update_jrdb_analysis_incremental.py \
  --db ./jrdb_analysis.sqlite \
  --raw-root ./00_raw_local \
  --dates 20260822 20260823
```

## Validation

Historical pseudo-daily regression using the canonical 2025-12-28 members:

- target rows before replacement: 356
- target rows after replacement: 356
- races: 24
- row hash before/after: identical
- `PRAGMA integrity_check`: `ok`
- batch status: SUCCESS

Raw -> Analysis v1.2 versus Core -> Analysis v1.2 exact equivalence:

- 2016-2020: 243,849 rows x 33 columns, differences 0
- 2021-2025: 237,778 rows x 33 columns, differences 0

Thus the Raw production path preserves the Core reference result while allowing day-by-day updates without rebuilding Core.
