# JRDB Analysis Lite Builder v1.1

`build_jrdb_analysis.py` creates a compact one-entry-per-row analytical SQLite from Core v1.2.1.
`build_jrdb_analysis_from_raw.py` provides the remote-friendly Raw ZIP -> Analysis path.

The full provenance-preserving Core remains the durable normalized database; Analysis Lite is the routine GPT/PWA query layer.

## v1.1 field correction

The former `condition_code` name was ambiguous. In Core it represents the BAC race condition/class field, not the actual track condition.

Analysis v1.1 therefore uses distinct fields:

- `race_condition_code` — BAC race condition/class (`race.condition_code`)
- `track_condition_code` — actual SED track condition, 0-based byte offset 69, length 2
- `frame_no` — KYI frame number, 0-based byte offset 323, length 1

The source reference confirms KYI frame number at human position 324 and SED track condition at human position 70.

## Input

Core path:

- Core v1.2.1 SQLite containing `horse_profile_current`, `entry.frame_no`, and `result.track_condition_code`
- `schema/jrdb_analysis_schema_v1_1.sql`

Raw path:

- annual BAC/KYI/SED/CYB/UKC ZIPs
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

Core -> Analysis:

```bash
python src/build_jrdb_analysis.py \
  --core ./jrdb_core_v1_2_1.sqlite \
  --db ./jrdb_analysis.sqlite
```

Raw -> Analysis:

```bash
python src/build_jrdb_analysis_from_raw.py \
  --years 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 \
  --raw-root ./00_raw_local \
  --db ./jrdb_analysis_2016_2025.sqlite
```

The output path must not already exist.

## Age rule

For JRA aggregation:

```text
age = race_year - birth_year
```

This is calendar-year age, not birthday-dependent Western age.

## Validation history

### Analysis v1.0 contiguous 2021-2025 PoC

- fact rows: 237,778
- sire nonblank: 237,670
- SQLite size: 84,582,400 bytes (~80.7 MiB)
- ZIP: 22,687,297 bytes (~21.6 MiB)
- integrity_check: ok

This established the original five-year size target before the v1.1 field correction.

### Analysis v1.1 corrected 2016-2020

- rows: 243,849
- sire nonblank: 243,849
- broodmare-sire nonblank: 243,849
- frame non-null: 243,849
- track condition nonblank: 243,849
- missing horse profiles: 0
- SQLite: 92,082,176 bytes (~87.82 MiB)
- integrity_check: ok

### Analysis v1.1 corrected 2021-2025

- rows: 237,778
- sire nonblank: 237,670
- broodmare-sire nonblank: 237,670
- frame non-null: 237,778
- track condition nonblank: 237,778
- missing horse profiles: 108
- SQLite: 89,296,896 bytes (~85.16 MiB)
- integrity_check: ok

### Analysis v1.1 corrected 2016-2025 — 10-year measurement PASS

A single corrected ten-year Analysis Lite was measured from the two non-overlapping five-year shards.

- years: 2016-2025
- rows: **481,627**
- sire nonblank: **481,519**
- broodmare-sire nonblank: **481,519**
- frame non-null: **481,627**
- track condition nonblank: **481,627**
- SQLite: **177,328,128 bytes (~169.11 MiB)**
- ZIP: **44,011,036 bytes (~41.97 MiB)**
- integrity_check: **ok**
- measured SQLite SHA-256: `e33a5ec567e0431ec847855df9f224c5dda7fc7e328d53964b349d62c8ca3be6`

Representative 10-year query timings in the test runtime:

- Tokyo turf 1600m / good-family track condition / sire aggregation: ~8.05 ms
- Nakayama dirt 1800m / jockey aggregation: ~12.32 ms
- Kyoto turf / frame aggregation: ~11.30 ms

The corrected ten-year shard therefore passes:

- mandatory < 200 MiB Analysis target — **PASS**
- current remote connector ~256 MiB file ceiling — **PASS with useful headroom**

It does not pass the earlier preferred < 100 MiB target, which is expected for ten years. The practical conclusion is that a rolling ten-year Analysis shard is viable, while full 2010+ history should remain sharded and/or served through Stats Mart.

## Recommended production delivery layout

- keep Core as the complete auditable layer; do not require GPT to read it directly
- maintain one rolling recent-ten-year Analysis Lite shard for flexible routine queries
- keep older years in separate Analysis shard(s) below the connector ceiling
- maintain full-history yearly Stats Mart for frequent aggregate queries
- retain `race_key` so aggregate findings can be traced to detailed race delivery/Core records

## Remaining validation

1. Run explicit row-level equivalence for Core v1.2.1 -> Analysis v1.1 versus Raw -> Analysis v1.1.
2. Upload/fetch a real ~169 MiB Analysis shard through the Drive connector to confirm the practical remote path, not only the nominal size ceiling.
3. Keep the rolling ten-year shard under the configured safety ceiling as 2026+ is added.
