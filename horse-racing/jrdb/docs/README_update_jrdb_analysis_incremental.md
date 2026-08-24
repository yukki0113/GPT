# JRDB Analysis Lite Incremental Update

`src/update_jrdb_analysis_incremental.py` incrementally replaces completed race dates in an existing Analysis Lite v1.2 SQLite.

## Production use

Routine flow:

```text
JRDB completed-date sources
  -> Analysis Lite incremental replacement
  -> current-year Stats Mart refresh
```

Core is not required as an intermediate artifact.

## Recommended input: PACI + SED

For manual/ChatGPT operation, the preferred completed-date pair is:

- `PACIyymmdd.zip`
- `SEDyymmdd.zip`

PACI supplies the Analysis-required pre-race members:

- BAC
- KYI
- CYB
- UKC

SED supplies completed results, final odds/popularity, payouts, and actual track condition.

HJC/TYB are not required by the current Analysis Lite schema.

The updater infers the race date from the two ZIP filenames and rejects a PACI/SED date mismatch before touching the database.

Example:

```bash
python src/update_jrdb_analysis_incremental.py \
  --db ./jrdb_analysis.sqlite \
  --paci ./PACI260823.zip \
  --sed ./SED260823.zip
```

## Alternative input: individual daily-kind ZIPs

The fetcher-oriented layout remains supported:

- `BAC/BACyymmdd.zip`
- `KYI/KYIyymmdd.zip`
- `SED/SEDyymmdd.zip`
- `CYB/CYByymmdd.zip`
- `UKC/UKCyymmdd.zip`

Example:

```bash
python src/update_jrdb_analysis_incremental.py \
  --db ./jrdb_analysis.sqlite \
  --raw-root ./00_raw_local \
  --dates 20260822 20260823
```

In both modes, the expected daily TXT member names are validated exactly and ZIP integrity is checked before any Analysis rows are replaced.

Because SED is the result source, ingest a date only after JRDB has published the completed result-side SED for that race date.

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

Each batch records source paths, SHA-256 values, race/row counts, source mode, and the number of rows replaced.

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

## Validation

### Historical pseudo-daily regression

Canonical 2025-12-28 members:

- target rows before replacement: 356
- target rows after replacement: 356
- races: 24
- row hash before/after: identical
- `PRAGMA integrity_check`: `ok`
- batch status: SUCCESS

### Real 2026 PACI + SED operational test — 2026-08-23

Actual uploaded JRDB sources:

- `PACI260823.zip`
- `SED260823.zip`

Source validation:

- PACI BAC: 36 rows / 182-byte bodies
- PACI KYI: 466 rows / 1022-byte bodies
- PACI CYB: 466 rows / 94-byte bodies
- PACI UKC: 466 rows / 290-byte bodies
- SED: 466 rows / 374-byte bodies
- ZIP integrity: PASS

Incremental result against the accepted 2016-2025 Analysis v1.2 baseline:

- races added: **36**
- rows added: **466**
- missing UKC profiles: **0**
- frame populated: **466 / 466**
- track condition populated: **466 / 466**
- sire populated: **466 / 466**
- `prev_result_key_1` populated: **417 / 466**
- `prev_race_key_1` populated: **417 / 466**
- total Analysis rows after test: **482,093**
- batch status: **SUCCESS**
- `PRAGMA integrity_check`: **ok**

The date contained 12 races each at venue codes 01 / 04 / 07, with 154 / 161 / 151 entry rows respectively.

A full Stats Mart rebuild from the updated test Analysis also passed:

- 2026 sire mart rows: 403
- 2026 jockey mart rows: 366
- 2026 frame mart rows: 168
- mart `PRAGMA integrity_check`: `ok`

This confirms the intended live-season path:

```text
PACI + SED -> Analysis incremental replace/add -> current-year Stats Mart refresh
```

### Raw/Core equivalence baseline

Raw -> Analysis v1.2 versus Core -> Analysis v1.2 exact equivalence:

- 2016-2020: 243,849 rows x 33 columns, differences 0
- 2021-2025: 237,778 rows x 33 columns, differences 0

Thus the Raw production path preserves the Core reference result while allowing day-by-day updates without rebuilding Core.
