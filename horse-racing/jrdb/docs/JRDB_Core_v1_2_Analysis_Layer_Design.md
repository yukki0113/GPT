# JRDB Core v1.2 / Analysis Layer Design

## 1. Purpose

The existing JRDB Core v1.1.2 is a provenance-preserving normalized database for long-term retention and reproducibility. It is not intended to be the primary database that GPT reads directly for routine aggregation.

This document defines the next-stage architecture:

- Layer 0 Raw: canonical JRDB ZIP archives
- Layer 1 Core: complete normalized / auditable SQLite
- Layer 2A Analysis Lite: compact one-entry-per-row analytical SQLite for GPT/PWA
- Layer 2B Stats Mart: pre-aggregated yearly statistics for frequent queries
- Layer 3 Delivery: race- or condition-specific JSON/CSV/RaceNote outputs

Core v1.1.2 remains the current production baseline until v1.2 passes regression testing.

---

## 2. UKC fixed-width definition confirmed from JRDB-data/converter

The JRDB-data/converter repository defines UKC fields in the following order and byte widths:

`8 36 1 2 2 36 36 36 8 4 4 4 40 2 40 8 1 8 4 4 6`

Total fixed-width body length: **290 bytes**.

Derived offsets below are zero-based, matching the existing Python helper style used by `build_jrdb_core.py`.

| field | offset 0-based | length | human position |
|---|---:|---:|---:|
| horse_id / 血統登録番号 | 0 | 8 | 1-8 |
| horse_name / 馬名 | 8 | 36 | 9-44 |
| sex_code / 性別コード | 44 | 1 | 45 |
| coat_color_code / 毛色コード | 45 | 2 | 46-47 |
| horse_symbol_code / 馬記号コード | 47 | 2 | 48-49 |
| sire_name / 父馬名 | 49 | 36 | 50-85 |
| dam_name / 母馬名 | 85 | 36 | 86-121 |
| broodmare_sire_name / 母父馬名 | 121 | 36 | 122-157 |
| birth_date / 生年月日 | 157 | 8 | 158-165 |
| sire_birth_year / 父馬生年 | 165 | 4 | 166-169 |
| dam_birth_year / 母馬生年 | 169 | 4 | 170-173 |
| broodmare_sire_birth_year / 母父馬生年 | 173 | 4 | 174-177 |
| owner_name / 馬主名 | 177 | 40 | 178-217 |
| owner_group_code / 馬主会コード | 217 | 2 | 218-219 |
| breeder_name / 生産者名 | 219 | 40 | 220-259 |
| breeding_place / 産地名 | 259 | 8 | 260-267 |
| deregistered_flag / 登録抹消フラグ | 267 | 1 | 268 |
| data_date / データ年月日 | 268 | 8 | 269-276 |
| sire_line_code / 父系統コード | 276 | 4 | 277-280 |
| broodmare_sire_line_code / 母父系統コード | 280 | 4 | 281-284 |
| reserved / 予備 | 284 | 6 | 285-290 |

Source evidence:
- JRDB-data/converter `converter.sh` UKC header
- JRDB-data/converter `field_bytes()` UKC widths

No byte offsets should be guessed outside this confirmed definition.

---

## 3. Core v1.2 horse profile extension

Do not destructively replace `horse_current` / `horse_history` in the first v1.2 implementation. Add a richer UKC profile layer and retain the existing tables for regression compatibility.

### horse_profile_current

Recommended columns:

- horse_id TEXT PRIMARY KEY
- horse_name TEXT
- sex_code TEXT
- coat_color_code TEXT
- horse_symbol_code TEXT
- birth_date TEXT
- sire_name TEXT
- dam_name TEXT
- broodmare_sire_name TEXT
- sire_birth_year INTEGER
- dam_birth_year INTEGER
- broodmare_sire_birth_year INTEGER
- owner_name TEXT
- owner_group_code TEXT
- breeder_name TEXT
- breeding_place TEXT
- deregistered_flag TEXT
- data_date TEXT
- sire_line_code TEXT
- broodmare_sire_line_code TEXT
- semantic_hash TEXT
- source_file_id INTEGER
- source_record_no INTEGER
- valid_from TEXT

### horse_profile_history

Recommended columns:

- history_id INTEGER PRIMARY KEY
- horse_id TEXT
- valid_from TEXT
- valid_to TEXT
- semantic_hash TEXT
- source_file_id INTEGER
- source_record_no INTEGER
- plus the profile values needed to reconstruct the previous semantic state

The history table must preserve the semantic profile, not only its hash, if it is intended for historical reconstruction.

### Semantic hash

Include stable semantic attributes such as:

- horse_name
- sex_code
- coat_color_code
- horse_symbol_code
- birth_date
- sire_name
- dam_name
- broodmare_sire_name
- parent birth years
- owner / breeder / breeding place
- deregistered_flag
- sire_line_code / broodmare_sire_line_code

Exclude ingestion/provenance timestamps and source IDs:

- data_date may be stored but should not by itself force a semantic history version
- source_file_id
- source_record_no
- imported_at

The exact semantic hash field list must be frozen in the v1.2 README and covered by regression tests.

---

## 4. Analysis Lite

Analysis Lite is the main GPT/PWA query database. Its first fact table should be one row per race entry/result.

### fact_entry_result_lite

Initial recommended columns:

- race_date
- year
- venue_code
- race_no
- track_type
- distance
- condition_code
- grade_code
- race_key
- horse_no
- horse_id
- horse_name
- sex_code
- age
- sire_name
- broodmare_sire_name
- sire_line_code
- broodmare_sire_line_code
- jockey_name
- running_style
- distance_aptitude
- uptrend
- training_index
- finish
- abnormal_code
- final_win_odds
- final_win_popularity
- win_payout
- place_payout

Do not copy the following by default:

- source_file_id / source_record_no / record_hash
- meta_anomaly / meta_duplicate
- full workout rows
- full race comments
- entry_previous_result rows

`race_key` must remain so that an aggregated finding can be traced back to a detailed race delivery/Core record.

### Age rule

For JRA aggregation age should use calendar-year age:

`age = race_year - birth_year`

Do not calculate Western-style birthday-dependent age.

---

## 5. Stats Mart

Stats Mart is a cache / acceleration layer, not the only analytical source.

Keep `year` as the base time grain so arbitrary windows can be summed later.

Initial mart candidates:

1. `mart_jockey_yearly`
2. `mart_sire_yearly`
3. `mart_running_style_yearly`
4. `mart_gate_yearly`
5. `mart_popularity_yearly`

### mart_sire_yearly initial grain

Suggested dimensions:

- year
- venue_code
- track_type
- distance
- condition_code
- sire_name

Measures:

- starts
- wins
- seconds
- thirds
- top3
- win_payout_sum
- place_payout_sum

Do not pre-store fixed windows such as "last 5 years" or "last 10 years". Derive them by summing yearly rows.

---

## 6. Build paths

Analysis Lite should ultimately support both:

1. Core -> Analysis Lite
2. Raw ZIP -> Analysis Lite

Reason: the full Core may be too large for some remote connector download paths, while Raw ZIPs remain the durable source.

Do not immediately refactor the stable v1.1.2 parser. First implement and validate the Analysis path separately, then consider extracting shared parser functions only after output equivalence is proven.

---

## 7. Implementation order

### A. UKC / Core v1.2

1. Confirm UKC field offsets from JRDB-data/converter. **Done in this document.**
2. Validate several real UKC records against expected decoded values.
3. Add v1.2 schema as a new file; do not overwrite v1.1.2 schema.
4. Add horse profile current/history parsing.
5. Validate semantic hash behavior.
6. Run regression against known v1.1.2 race/entry/result counts and anomaly/duplicate behavior.

### B. Analysis Lite, after A is complete

1. Build 2021-2025 PoC including sire fields from the beginning.
2. Measure row count and SQLite size.
3. Target: < 200 MiB mandatory; < 100 MiB preferred.
4. Verify GPT/Drive connector accessibility.
5. Verify flexible SQL examples including sire aggregation.
6. Expand to 2010-2025 if accepted.
7. Add Stats Mart.

Sire aggregation is a required capability and must not be deferred beyond the Analysis Lite PoC.

---

## 8. Regression principles

Core v1.2 must preserve v1.1.2 behavior for:

- canonical filename filtering
- non-canonical source exclusion
- duplicate resolution
- BAC SED fallback
- payout parsing
- missing/orphan anomaly recording
- provenance

The v1.1.2 production builder remains the rollback baseline until v1.2 passes the full regression suite.
