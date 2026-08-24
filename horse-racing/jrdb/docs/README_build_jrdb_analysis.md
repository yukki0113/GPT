# JRDB Analysis Lite Builder v1

`build_jrdb_analysis.py` creates a compact one-entry-per-row analytical SQLite from Core v1.2.
It is intended for routine GPT/PWA aggregation while the full provenance-preserving Core remains the durable normalized database.

## Input

- Core v1.2 SQLite containing `horse_profile_current`
- `schema/jrdb_analysis_schema_v1.sql`

## Output

Main table: `fact_entry_result_lite`

Included dimensions/measures:

- race date / year / venue / race no
- track type / distance / condition / grade
- race key / horse no / horse id / horse name
- sex / calendar-year age
- sire / broodmare sire / sire-line codes
- jockey / running style / distance aptitude / uptrend
- training index
- finish / abnormal code
- final win odds / popularity
- win payout / place payout

Provenance-heavy fields, full comments, workout rows, previous-result rows and duplicate/anomaly metadata are intentionally omitted.

## Run

```bash
python src/build_jrdb_analysis.py \
  --core ./jrdb_core_v1_2.sqlite \
  --db ./jrdb_analysis.sqlite \
  --schema ./schema/jrdb_analysis_schema_v1.sql
```

The output path must not already exist.

## Age rule

For JRA aggregation:

```text
age = race_year - birth_year
```

This is calendar-year age, not birthday-dependent Western age.

## Validation / pilot

### 2025 single-year pilot

- fact rows: 47,884
- sire nonblank: 47,772
- broodmare-sire nonblank: 47,772
- unmatched horse profile rows: 112
- SQLite size: 16,961,536 bytes (~16.2 MiB)
- `PRAGMA integrity_check`: `ok`

### 2021 + 2025 two-year pilot

This is a non-contiguous pilot used to validate growth and multi-year joins before the planned contiguous 2021-2025 PoC.

- fact rows: 95,705
- sire nonblank: 95,593
- broodmare-sire nonblank: 95,593
- unmatched horse profile rows: 112
- SQLite size: 34,004,992 bytes (~32.4 MiB)
- `PRAGMA integrity_check`: `ok`
- sample sire/jockey aggregation queries: ~74-84 ms in the test runtime

The two-year result implies that the planned contiguous 2021-2025 PoC is likely to remain comfortably below the 200 MiB hard target and plausibly near/below the preferred 100 MiB target, but this must be confirmed by the actual five-year build.

## Required next validation

1. Build contiguous 2021-2025 Core v1.2 / Analysis Lite.
2. Confirm sire/broodmare-sire coverage.
3. Record actual SQLite and ZIP sizes.
4. Verify connector download/access under the remote file-size limit.
5. Run sire/jockey/style/popularity aggregation regression queries.
6. Only then expand to 2010-2025 and add Stats Mart.

## Future Raw -> Analysis path

The first implementation consumes Core v1.2 intentionally. A direct Raw ZIP -> Analysis path is planned because the full Core may be too large for some remote connector paths. It must not be added by duplicating normalization rules casually; output equivalence against Core -> Analysis must be proven first.
