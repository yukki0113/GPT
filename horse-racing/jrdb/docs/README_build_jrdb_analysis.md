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

- fact rows: 95,705
- sire nonblank: 95,593
- broodmare-sire nonblank: 95,593
- unmatched horse profile rows: 112
- SQLite size: 34,004,992 bytes (~32.4 MiB)
- `PRAGMA integrity_check`: `ok`

### Contiguous 2021-2025 PoC — PASS

Source years: 2021, 2022, 2023, 2024, 2025.

- fact rows: **237,778**
- yearly rows:
  - 2021: 47,821
  - 2022: 47,220
  - 2023: 47,672
  - 2024: 47,181
  - 2025: 47,884
- sire nonblank: **237,670**
- broodmare-sire nonblank: **237,670**
- unmatched horse profile rows: **108**
- SQLite size: **84,582,400 bytes (~80.7 MiB)**
- ZIP size (deflate level 9): **22,687,297 bytes (~21.6 MiB)**
- `PRAGMA integrity_check`: `ok`
- Analysis SQLite SHA-256: `72b8953311de95abf45387e00c88a6d1d21680edc319f04027471896014d9451`
- ZIP SHA-256: `de9127e3d9ced8aff35bccac70391763f0400364bd83d9136e8775ed0d50e2e1`

Representative query timings in the test runtime:

- sire aggregation, venue 05 / distance 1600: ~267 ms
- jockey aggregation, venue 06 / distance 1800: ~239 ms
- compound sire filter with venue/track/distance/popularity/style: ~47 ms

The contiguous five-year build therefore passes both size targets:

- mandatory: < 200 MiB — **PASS**
- preferred: < 100 MiB — **PASS**

## Core v1.2 regression used for the PoC

The contiguous 2021-2025 Core v1.2 candidate preserved all existing v1.1.2 normalized rows exactly for:

- race: 17,277
- entry/result/training/workout: 237,778 each
- result_extension: 236,764
- entry_previous_result: 1,188,890
- horse_current: 31,010
- horse_history: 1,007

Semantic metadata comparison also matched for archive/source-file/anomaly rows. v1.2 added:

- horse_profile_current: 31,010
- horse_profile_history: 2,773
- BAC fallback: 53
- MANUAL_REQUIRED: 0
- non-canonical source files: 1
- integrity_check: `ok`

## Capacity implication

The five-year size is small enough for routine GPT/PWA use. Linear extrapolation suggests a single 2010-2025 Analysis Lite could approach or exceed the current ~256 MiB remote connector download ceiling, so the 16-year delivery layout must be measured rather than assumed.

The preferred next design is:

1. keep a recent analytical shard large enough for routine 5-10 year queries;
2. keep older years in one or more additional shard(s) below the connector limit;
3. maintain a tiny full-history Stats Mart for frequent aggregate queries;
4. use `race_key` to trace aggregate findings back to detailed delivery/Core records.

## Next validation

1. Measure a 10-year Analysis Lite shard (target use case: routine "past 10 years" queries).
2. Decide the production shard boundary using actual size, leaving growth headroom for 2026+.
3. Add Stats Mart, including mandatory `mart_sire_yearly`.
4. Verify an uploaded Analysis Lite shard can actually be fetched through the Drive connector.
5. Add Raw ZIP -> Analysis only after equivalence with Core -> Analysis is proven.

## Future Raw -> Analysis path

The first implementation consumes Core v1.2 intentionally. A direct Raw ZIP -> Analysis path is planned because the full Core may be too large for some remote connector paths. It must not be added by duplicating normalization rules casually; output equivalence against Core -> Analysis must be proven first.
