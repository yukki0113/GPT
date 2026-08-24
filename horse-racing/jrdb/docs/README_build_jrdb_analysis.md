# JRDB Analysis Lite Builder v1.1

`build_jrdb_analysis.py` creates a compact one-entry-per-row analytical SQLite from Core v1.2.1.
`build_jrdb_analysis_from_raw.py` is the normal production path from canonical Raw ZIPs.

The full provenance-preserving Core remains the durable normalized/audit database; Analysis Lite is the routine GPT/PWA query layer.

## v1.1 field correction

The former `condition_code` name was ambiguous. In Core it represents the BAC race condition/class field, not the actual track condition.

Analysis v1.1 therefore uses distinct fields:

- `race_condition_code` — BAC race condition/class (`race.condition_code`)
- `track_condition_code` — actual SED track condition, 0-based byte offset 69, length 2
- `frame_no` — KYI frame number, 0-based byte offset 323, length 1

## Input

### Production Raw path

- annual BAC/KYI/SED/CYB/UKC ZIPs
- `schema/jrdb_analysis_schema_v1_1.sql`

### Reference Core path

- Core v1.2.1 SQLite containing `horse_profile_current`, `entry.frame_no`, and `result.track_condition_code`
- `schema/jrdb_analysis_schema_v1_1.sql`

## Output

Main table: `fact_entry_result_lite`.

Important dimensions/measures include:

- race date / year / venue / race no
- track type / distance
- race condition/class / actual track condition / grade
- race key / horse no / frame no / horse id / horse name
- sex / calendar-year age
- sire / broodmare sire / sire-line codes
- jockey / running style / distance aptitude / uptrend
- training index
- finish / abnormal code
- final win odds / popularity
- win payout / place payout

Provenance-heavy fields, full comments, workout rows, previous-result rows and duplicate/anomaly metadata are intentionally omitted.

## Run

Raw -> Analysis — production routine path:

```bash
python src/build_jrdb_analysis_from_raw.py \
  --years 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 \
  --raw-root ./00_raw_local \
  --db ./jrdb_analysis_2016_2025.sqlite
```

Core -> Analysis — regression/reference path:

```bash
python src/build_jrdb_analysis.py \
  --core ./jrdb_core_v1_2_1.sqlite \
  --db ./jrdb_analysis.sqlite
```

The output path must not already exist.

## Age rule

For JRA aggregation:

```text
age = race_year - birth_year
```

This is calendar-year age, not birthday-dependent Western age.

## Explicit Core/Raw path equivalence — PASS

The two build routes were compared across all **31 columns** in `fact_entry_result_lite`.

### 2016-2020

- Core-derived rows: 243,849
- Raw-derived rows: 243,849
- Core minus Raw: 0
- Raw minus Core: 0
- key/value mismatches: 0

### 2021-2025

- Core-derived rows: 237,778
- Raw-derived rows: 237,778
- Core minus Raw: 0
- Raw minus Core: 0
- key/value mismatches: 0

Combined validated coverage:

- years: **2016-2025**
- rows: **481,627**
- columns compared: **31**
- differences: **0**

During this regression, 735 rows in 2025 BAC->SED fallback races initially differed only because Raw->Analysis emitted empty strings for unavailable BAC-only `race_condition_code` / `grade_code`, while Core correctly used SQL NULL. Raw->Analysis was corrected to use NULL, after which equivalence became exact.

Reusable checker:

```bash
python tools/audit_jrdb_analysis_equivalence.py \
  --left ./analysis_from_core.sqlite \
  --right ./analysis_from_raw.sqlite
```

This PASS promotes `build_jrdb_analysis_from_raw.py` to the normal production route.

## Corrected 10-year measurement — PASS

Analysis Lite v1.1 for 2016-2025:

- rows: **481,627**
- sire nonblank: **481,519**
- broodmare-sire nonblank: **481,519**
- frame non-null: **481,627**
- track condition nonblank: **481,627**
- SQLite: **177,328,128 bytes (~169.11 MiB)**
- ZIP: **44,011,036 bytes (~41.97 MiB)**
- integrity_check: **ok**
- measured SQLite SHA-256: `e33a5ec567e0431ec847855df9f224c5dda7fc7e328d53964b349d62c8ca3be6`

Representative 10-year direct query timings in the test runtime:

- Tokyo turf 1600m / good-family track condition / sire aggregation: ~8.05 ms
- Nakayama dirt 1800m / jockey aggregation: ~12.32 ms
- Kyoto turf / frame aggregation: ~11.30 ms

The ten-year shard passes the < 200 MiB Analysis design target and remains below the current ~256 MiB remote connector ceiling.

## Drive delivery validation — PASS

The 2016-2025 Analysis SQLite was uploaded to Google Drive and fetched back through the ChatGPT Drive connector.

Confirmed after fetch:

- size: **177,328,128 bytes**
- integrity_check: **ok**
- rows: **481,627**
- SHA-256 matched the generated artifact

Therefore the practical remote path is validated.

## Recommended production operation

Routine analytical refresh:

```text
Raw -> rolling 10-year Analysis Lite -> Stats Mart
```

Core is maintained independently for auditability, complete normalized history, anomaly/duplicate investigation, and reproducibility. Rebuilding Core is **not** required before refreshing Analysis.

Example rollover:

```text
2016-2025 Analysis
    -> rebuild directly from 2017-2026 Raw
    -> 2017-2026 Analysis
```

## Remaining operational decision

Define the exact 2026/current-year refresh cadence: year-end-only rollover versus interim in-season Analysis refreshes. The Raw-direct architecture itself has passed equivalence and Drive-delivery validation.
