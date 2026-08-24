# JRDB Core v1.2 / Analysis Layer Design

## 1. Purpose

The existing JRDB Core v1.1.2 is a provenance-preserving normalized database for long-term retention and reproducibility. It is not intended to be the primary database that GPT reads directly for routine aggregation.

This document defines the next-stage architecture:

- Layer 0 Raw: canonical JRDB ZIP archives
- Layer 1 Core: complete normalized / auditable SQLite
- Layer 2A Analysis Lite: compact one-entry-per-row analytical SQLite for GPT/PWA
- Layer 2B Stats Mart: pre-aggregated yearly statistics for frequent queries
- Layer 3 Delivery: race- or condition-specific JSON/CSV/RaceNote outputs

Core v1.1.2 remains the rollback baseline. Core v1.2 has passed additive regression on the contiguous 2021-2025 PoC range; full-history production promotion is still separate from this PoC.

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

### 2025 Raw validation

The canonical Drive Raw `UKC_2025.zip` was checked against the above definition.

- canonical daily UKC files: 109
- parsed body records: 47,239
- record lengths other than 290 bytes: 0
- CP932 replacement/decode errors: 0
- invalid birth/data dates: 0
- missing sire names: 0

---

## 3. Core v1.2 horse profile extension

Do not destructively replace `horse_current` / `horse_history`. Core v1.2 adds the richer UKC profile layer while retaining the existing tables for regression compatibility.

### horse_profile_current

Implemented in `schema/jrdb_core_schema_v1_2.sql` with:

- horse_id TEXT PRIMARY KEY
- horse_name TEXT
- sex_code TEXT
- coat_color_code TEXT
- horse_symbol_code TEXT
- sire_name TEXT
- dam_name TEXT
- broodmare_sire_name TEXT
- birth_date TEXT
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

Implemented as a full previous semantic-state snapshot including the profile values, valid_from/valid_to, hash, and provenance.

### Semantic hash

Implemented in `src/jrdb_ukc.py`.

Included:

- horse_name
- sex_code
- coat_color_code
- horse_symbol_code
- sire / dam / broodmare sire
- birth_date and parent birth years
- owner / owner-group
- breeder / breeding place
- deregistration flag
- sire-line / broodmare-sire-line codes

Excluded from semantic version triggering:

- data_date
- source_file_id
- source_record_no
- imported_at
- reserved bytes

2025 Raw check:

- repeated snapshots with unchanged semantic hash: 35,115
- repeated snapshots with changed semantic hash: 306

---

## 4. v1.2 implementation strategy

`src/build_jrdb_core_v1_2.py` is an additive wrapper rather than a rewrite.

1. Run the proven `src/build_jrdb_core.py` v1.1.2 logic unchanged against `schema/jrdb_core_schema_v1_2.sql`.
2. Scan canonical UKC members again through `src/jrdb_ukc.py`.
3. Populate `horse_profile_current / horse_profile_history`.
4. Promote builder/schema metadata to v1.2 after enrichment succeeds.

This design intentionally minimizes regression risk in duplicate resolution, BAC fallback, payouts, anomalies, and provenance.

### Contiguous 2021-2025 Core regression — PASS

Existing v1.1.2 rows were preserved exactly for:

- race: 17,277
- entry: 237,778
- result: 237,778
- training_analysis: 237,778
- workout: 237,778
- result_extension: 236,764
- entry_previous_result: 1,188,890
- horse_current: 31,010
- horse_history: 1,007

Semantic archive/source-file/anomaly metadata also matched. Added v1.2 profile rows:

- horse_profile_current: 31,010
- horse_profile_history: 2,773
- unmatched entry -> profile rows: 108
- sire-populated entry rows: 237,670
- BAC fallback: 53
- MANUAL_REQUIRED: 0
- non-canonical source files: 1
- `PRAGMA integrity_check`: `ok`

`tools/audit_jrdb_core_v1_2_regression.py` is the reusable regression checker.

---

## 5. Analysis Lite

Analysis Lite is the main GPT/PWA query database. `src/build_jrdb_analysis.py` and `schema/jrdb_analysis_schema_v1.sql` implement the first Core -> Analysis path.

### fact_entry_result_lite

Columns:

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

Omitted by default:

- source_file_id / source_record_no / record_hash
- meta_anomaly / meta_duplicate
- full workout rows
- full race comments
- entry_previous_result rows

`race_key` remains so aggregate findings can be traced back to a detailed race delivery/Core record.

### Age rule

For JRA aggregation:

`age = race_year - birth_year`

### Contiguous 2021-2025 Analysis Lite PoC — PASS

- rows: **237,778**
- sire nonblank: **237,670**
- broodmare-sire nonblank: **237,670**
- unmatched profile rows: **108**
- SQLite: **84,582,400 bytes (~80.7 MiB)**
- ZIP: **22,687,297 bytes (~21.6 MiB)**
- integrity: `ok`
- typical tested aggregation queries: roughly **47-267 ms**

This passes both capacity targets:

- < 200 MiB mandatory: PASS
- < 100 MiB preferred: PASS

See `docs/README_build_jrdb_analysis.md` for detailed pilot results and hashes.

---

## 6. Stats Mart

Stats Mart is a cache / acceleration layer, not the only analytical source.

Keep `year` as the base time grain so arbitrary windows can be summed later.

Initial mart candidates:

1. `mart_jockey_yearly`
2. `mart_sire_yearly`
3. `mart_running_style_yearly`
4. `mart_gate_yearly`
5. `mart_popularity_yearly`

### mart_sire_yearly initial grain

Dimensions:

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

Sire aggregation is mandatory and must remain in the production mart.

---

## 7. Build paths

Analysis Lite should ultimately support both:

1. Core -> Analysis Lite — **implemented and validated**
2. Raw ZIP -> Analysis Lite — future path

Reason: the full Core may be too large for some remote connector download paths, while Raw ZIPs remain the durable source.

Do not refactor the stable v1.1.2 parser merely to add the Raw path. First prove Raw -> Analysis output equivalence against Core -> Analysis.

---

## 8. Production delivery / sharding implication

The contiguous five-year Analysis SQLite is ~80.7 MiB. A naive linear extrapolation to all 2010-2025 years would approach or exceed the current ~256 MiB remote connector limit.

Therefore do not assume one 16-year Analysis SQLite is the final delivery shape.

Preferred next experiment:

1. build/measure a recent **10-year** Analysis shard because "past 10 years" is a routine query requirement;
2. retain growth headroom for 2026+ rather than sizing exactly to the connector ceiling;
3. place older years in one or more separate shard(s);
4. keep a tiny full-history Stats Mart for common aggregate queries across all years.

The full Core remains one logical complete database outside the direct GPT delivery path.

---

## 9. Implementation order / current status

### A. UKC / Core v1.2

1. UKC offsets confirmed. **DONE**
2. Real Raw validation. **DONE**
3. v1.2 schema. **DONE**
4. UKC parser/current/history. **DONE**
5. Semantic hash validation. **DONE**
6. Contiguous 2021-2025 additive Core regression. **DONE / PASS**

### B. Analysis Lite

1. Contiguous 2021-2025 PoC including sire. **DONE / PASS**
2. Size/integrity/query timing. **DONE / PASS**
3. 10-year shard capacity measurement. **NEXT**
4. Drive connector fetch validation for the resulting delivery file. **NEXT**
5. Production shard boundary decision. **NEXT**
6. Stats Mart implementation, with `mart_sire_yearly` mandatory. **NEXT**
7. Raw ZIP -> Analysis equivalence path. **LATER**

---

## 10. Regression principles

Core v1.2 must preserve v1.1.2 behavior for:

- canonical filename filtering
- non-canonical source exclusion
- duplicate resolution
- BAC SED fallback
- payout parsing
- missing/orphan anomaly recording
- provenance

The v1.1.2 production builder remains the rollback baseline even after v1.2 PoC success until full production promotion is explicitly completed.
