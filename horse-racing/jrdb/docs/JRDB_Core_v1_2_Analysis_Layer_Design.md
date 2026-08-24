# JRDB Core / Analysis Layer Design

## 1. Layer responsibilities

- Layer 0 Raw: canonical JRDB ZIP archives
- Layer 1 Core: complete normalized / auditable SQLite
- Layer 2A Analysis Lite: compact one-entry-per-row analytical SQLite for GPT/PWA
- Layer 2B Stats Mart: yearly pre-aggregated statistics for frequent queries
- Layer 3 Delivery: race- or condition-specific JSON/CSV/RaceNote outputs

The large Core is not the routine GPT query database. Analysis Lite is the flexible query layer; Stats Mart is the acceleration layer.

Operationally, Core is **not** a mandatory intermediate step for every Analysis rebuild.

Production paths are:

```text
Raw -> Core                  # audit / normalization / reproducibility, updated when needed
Raw -> Analysis -> Stats Mart # routine analytical production path
```

`Core -> Analysis` remains a reference/regression path and a convenient local build path when Core is already available.

## 2. Core lineage

### v1.1.2

Rollback baseline with validated normalization, duplicate handling, BAC->SED fallback, payouts, anomalies, and provenance.

### v1.2

Additive UKC horse-profile extension using confirmed 290-byte UKC offsets. Adds sire, dam, broodmare sire, birth date, owner/breeder and sire-line fields without replacing `horse_current / horse_history`.

Contiguous 2021-2025 additive regression passed with zero row-level differences in the pre-existing normalized tables.

### v1.2.1

Adds dimensions required by Analysis Lite v1.1:

- `entry.frame_no` from KYI human position 324 / 0-based offset 323 / length 1
- `result.track_condition_code` from SED human position 70 / 0-based offset 69 / length 2

Important semantic distinction:

- Core `race.condition_code` = BAC race condition/class
- Core `result.track_condition_code` = actual SED track condition

See `docs/README_build_jrdb_core_v1_2_1.md`.

## 3. Analysis Lite v1.1

Analysis Lite keeps one row per entry/result and intentionally omits provenance-heavy rows, comments, workouts, previous-result rows, duplicate metadata and anomaly metadata.

Primary dimensions/measures include:

- race_date / year / venue_code / race_no
- track_type / distance
- `race_condition_code`
- `track_condition_code`
- grade_code
- race_key / horse_no / `frame_no`
- horse_id / horse_name / sex / age
- sire / broodmare sire / sire-line codes
- jockey / running style / distance aptitude / uptrend
- training index
- finish / abnormal code / final odds / popularity
- win payout / place payout

`race_key` is retained for trace-back to detailed Core/Delivery data.

Age rule for JRA aggregation:

`age = race_year - birth_year`

## 4. Raw -> Analysis production path

`src/build_jrdb_analysis_from_raw.py` reads canonical annual:

- BAC
- KYI
- SED
- CYB
- UKC

and builds the same Analysis v1.1 fact shape as `Core -> Analysis`.

The Raw path preserves the established Core semantics needed by Analysis, including:

- canonical filename filtering
- BAC race fields
- BAC-missing race fallback from SED
- SED actual track condition
- KYI frame number / horse / jockey / style fields
- CYB training index
- UKC current pedigree/profile fields
- SED results / odds / payouts

For BAC->SED fallback races, unavailable BAC-only fields are stored as SQL `NULL`, matching the Core path. This detail was found by row-level regression and fixed before production promotion.

### Explicit equivalence validation — PASS

All **31 Analysis fact columns** were compared row-for-row between Core-derived and Raw-derived Analysis outputs.

2016-2020:

- rows: 243,849 vs 243,849
- Core minus Raw: 0
- Raw minus Core: 0
- key/value mismatches: 0

2021-2025:

- rows: 237,778 vs 237,778
- Core minus Raw: 0
- Raw minus Core: 0
- key/value mismatches: 0

Combined 2016-2025 coverage:

- **481,627 rows**
- **31 columns**
- differences: **0**

Reusable checker:

`tools/audit_jrdb_analysis_equivalence.py`

This equivalence result promotes `Raw -> Analysis` to the normal production path. `Core -> Analysis` is retained as a regression/reference path.

## 5. Corrected 10-year measurement

Analysis Lite v1.1 was measured for 2016-2025 using canonical annual Raw ZIPs.

- rows: **481,627**
- sire nonblank: **481,519**
- broodmare-sire nonblank: **481,519**
- frame non-null: **481,627**
- track condition nonblank: **481,627**
- SQLite: **177,328,128 bytes (~169.11 MiB)**
- ZIP: **44,011,036 bytes (~41.97 MiB)**
- integrity_check: **ok**

Representative direct Analysis query timings in the test runtime:

- Tokyo turf 1600m / good-family track condition / sire: ~8.05 ms
- Nakayama dirt 1800m / jockey: ~12.32 ms
- Kyoto turf / frame: ~11.30 ms

Conclusion: a single rolling ten-year Analysis Lite is viable below both the 200 MiB design target and the current ~256 MiB remote connector ceiling. A single full-history 2010+ Analysis database should not be assumed safe without sharding.

### Drive delivery validation — PASS

The generated 2016-2025 Analysis SQLite was uploaded to Google Drive and fetched back through the ChatGPT Drive connector.

- fetched size: **177,328,128 bytes**
- SQLite integrity: **ok**
- fact rows: **481,627**
- SHA-256 matched the generated artifact

Therefore the practical remote Analysis delivery path is validated, not merely inferred from nominal size limits.

## 6. Stats Mart v1.1

Default yearly marts:

- `mart_sire_yearly` — mandatory
- `mart_jockey_yearly`
- `mart_frame_yearly`

Default grain:

- year
- venue_code
- track_type
- distance
- track_condition_code
- sire/jockey/frame dimension

Measures:

- starts
- wins
- seconds
- thirds
- top3
- win_payout_sum
- place_payout_sum

Do not pre-store fixed windows such as last 5 or last 10 years. Sum yearly rows at query time.

Corrected 2016-2025 Stats Mart v1.1 measurement:

- sire rows: **194,656**
- jockey rows: **155,118**
- frame rows: **38,151**
- SQLite: **52,518,912 bytes (~50.09 MiB)**
- integrity_check: **ok**
- representative 10-year sire query: ~1.61 ms

Do not add every Analysis dimension to every Mart; keep Mart dimensions driven by frequent query patterns.

## 7. Production operation

### Routine analytical update

When the rolling window advances, build directly from Raw:

```text
annual/daily JRDB acquisition
        -> canonical Raw storage
        -> Raw -> rolling Analysis Lite
        -> Stats Mart
```

Example year-end rollover:

```text
2016-2025 Analysis
        -> rebuild from 2017-2026 Raw
        -> 2017-2026 Analysis
        -> rebuild/update Stats Mart
```

There is no requirement to rebuild Core first.

### Core update

Core is maintained independently for:

- auditability
- normalized complete history
- anomaly/duplicate investigation
- reproducibility
- future schema/mart development

It may be rebuilt or refreshed on a slower cadence than Analysis, because Raw remains the durable source of truth for data files.

## 8. Production delivery recommendation

1. Keep canonical Raw as the durable source data.
2. Keep one complete Core outside the direct GPT delivery path; update it when audit/history work requires it.
3. Maintain a **rolling recent ten-year Analysis Lite shard directly from Raw** for routine flexible queries.
4. Keep older years in one or more additional Analysis shards below the connector ceiling.
5. Maintain a full-history yearly Stats Mart for common aggregates.
6. Retain `race_key` so aggregate findings can be traced to detailed Core/Delivery records.

Sire aggregation remains a mandatory capability and must not be removed from Analysis or Stats Mart.

## 9. Remaining operational gate

The architecture itself is validated. The next operational item is defining the exact 2026/current-year acquisition and rollover schedule: when current-year Raw is considered complete enough to refresh the rolling ten-year Analysis, and whether interim in-season Analysis updates are produced before year-end.
