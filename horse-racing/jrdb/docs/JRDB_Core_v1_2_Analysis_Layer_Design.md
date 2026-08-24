# JRDB Core / Analysis Layer Design

## 1. Layer responsibilities

- Layer 0 Raw: canonical JRDB ZIP archives
- Layer 1 Core: complete normalized / auditable SQLite
- Layer 2A Analysis Lite: compact one-entry-per-row analytical SQLite for GPT/PWA
- Layer 2B Stats Mart: yearly pre-aggregated statistics for frequent queries
- Layer 3 Delivery: race- or condition-specific JSON/CSV/RaceNote outputs

The large Core is not the routine GPT query database. Analysis Lite is the flexible query layer; Stats Mart is the acceleration layer.

## 2. Production data flow

Routine analysis generation does **not** require Core as an intermediate artifact.

```text
canonical Raw ZIPs
  ├─> Core                    # audit / complete normalized history / reproducibility
  └─> Analysis Lite           # routine GPT/PWA use
        └─> Stats Mart
```

During the season:

```text
completed-date daily Raw
  -> Analysis incremental replace/add
  -> refresh current-year Stats Mart
```

At year-end:

```text
rolling Analysis window
  -> rebuild directly from next 10-year Raw window
  -> VACUUM/compact
  -> full Stats Mart rebuild
```

Core is maintained independently when audit/history work requires it.

## 3. Core lineage

### v1.1.2

Rollback baseline with validated normalization, duplicate handling, BAC->SED fallback, payouts, anomalies, and provenance.

### v1.2

Additive UKC horse-profile extension using confirmed 290-byte UKC offsets. Adds sire, dam, broodmare sire, birth date, owner/breeder and sire-line fields without replacing `horse_current / horse_history`.

### v1.2.1

Adds dimensions required by Analysis:

- `entry.frame_no` from KYI human position 324 / 0-based offset 323 / length 1
- `result.track_condition_code` from SED human position 70 / 0-based offset 69 / length 2

Important distinction:

- Core `race.condition_code` = BAC race condition/class
- Core `result.track_condition_code` = actual SED track condition

## 4. Analysis Lite v1.2

Analysis keeps one row per entry/result and omits provenance-heavy rows, comments, workouts, duplicate/anomaly metadata and the full 1-5 previous-link expansion.

Primary fields include:

- race_date / year / venue_code / race_no
- track_type / distance
- race_condition_code / track_condition_code / grade_code
- race_key / horse_no / frame_no
- horse_id / horse_name / sex / age
- sire / broodmare sire / sire-line codes
- jockey / running style / distance aptitude / uptrend
- training index
- finish / abnormal code / final odds / popularity
- win payout / place payout
- `prev_result_key_1`
- `prev_race_key_1`

The previous-link fields are read directly from JRDB KYI:

- previous-result key 1: 0-based offset 203, length 16
- previous-race key 1: 0-based offset 283, length 8

This preserves JRDB's explicit previous-race declaration rather than inferring the previous start only from horse/date order.

### Why only prev1 in Analysis

A 2016-2025 benchmark of a separate normalized previous-link 1-5 table produced roughly 1.78 million nonblank rows and ~81.9 MiB by itself. Adding that to the routine Analysis artifact would remove too much remote-delivery headroom.

Production compromise:

- Analysis: prev1 only for routine previous-race comparisons
- Raw/Core: all five links retained for detailed investigation/delivery

## 5. Raw/Core Analysis equivalence

Analysis v1.2 was compared across all 33 fact columns.

- 2016-2020: 243,849 rows, differences 0
- 2021-2025: 237,778 rows, differences 0
- combined 2016-2025: 481,627 rows, exact equivalence PASS

Thus `Raw -> Analysis` is the production route while `Core -> Analysis` remains the reference/regression route.

## 6. Ten-year Analysis capacity

2016-2025 Analysis v1.2 after prev1 addition, removal of unnecessary prev-key indexes, and VACUUM:

- rows: **481,627**
- sire nonblank: **481,519**
- prev1 populated: **434,622**
- SQLite: **182,439,936 bytes (~173.99 MiB)**
- integrity_check: **ok**

This remains below the 200 MiB routine target and the current ~256 MiB remote connector ceiling.

Prev-key indexes are intentionally omitted. Normal use starts from a current row, reads its explicit previous key, then resolves the target through existing fact/race-key paths; extra prev-key indexes cost useful headroom without helping the normal access pattern.

## 7. Incremental Analysis semantics

`src/update_jrdb_analysis_incremental.py` processes one or more completed race dates from daily BAC/KYI/SED/CYB/UKC ZIPs.

For each date:

1. validate all required ZIPs and expected TXT members
2. parse the complete date before mutating the DB
3. record source paths and SHA-256 values
4. delete existing rows for the target `race_date`
5. insert the parsed replacement rows inside a transaction
6. verify inserted row count
7. commit and mark the ingest batch SUCCESS

Re-running a date therefore safely applies later JRDB corrections.

Historical pseudo-daily regression using 2025-12-28:

- 24 races
- 356 rows before
- 356 rows after
- complete row hash identical
- integrity_check: ok

## 8. Stats Mart

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

Current-year mart refresh is performed by `src/refresh_jrdb_stats_mart_year.py` after Analysis increments. The selected year is fully recalculated from Analysis and atomically replaced; historical years remain untouched.

2025 refresh regression against the full-build mart produced zero differences in sire, jockey and frame tables.

## 9. Rolling production window

A recent ten-year Analysis shard is the normal flexible-query artifact.

Example:

```text
2016-2025 Analysis
  + completed 2026 dates incrementally during season
  -> 2016-2026 YTD temporary growth

at year end:
  rebuild directly from 2017-2026 Raw
  -> 2017-2026 rolling Analysis
```

The current year can temporarily extend the window beyond exactly ten calendar years; the year-end rebuild drops the oldest year and restores the intended rolling size.

## 10. Operational source of truth

- Raw ZIP: durable source data, Git-external
- Core: complete normalized/audit layer, Git-external SQLite
- Analysis: reproducible routine query artifact, Git-external SQLite
- Stats Mart: reproducible aggregate cache, Git-external SQLite
- Python/schema/docs: Git canonical source

Sire aggregation and explicit previous-race correctness remain mandatory capabilities.
