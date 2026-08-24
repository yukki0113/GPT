# JRDB Analysis Lite Builder v1.2

`build_jrdb_analysis_from_raw.py` is the normal production rebuild path from canonical Raw ZIPs.
`update_jrdb_analysis_incremental.py` is the normal in-season daily replacement path.
`build_jrdb_analysis.py` remains the Core v1.2.1 reference/regression path.

The full provenance-preserving Core remains the durable normalized/audit database; Analysis Lite is the routine GPT/PWA query layer.

## Field lineage

Analysis v1.1 separated the formerly ambiguous condition field into:

- `race_condition_code` — BAC race condition/class (`race.condition_code`)
- `track_condition_code` — actual SED track condition, 0-based byte offset 69, length 2
- `frame_no` — KYI frame number, 0-based byte offset 323, length 1

Analysis v1.2 additionally stores the JRDB-declared first previous-race link:

- `prev_result_key_1` — KYI previous-result key 1, 0-based offset 203, length 16
- `prev_race_key_1` — KYI previous-race key 1, 0-based offset 283, length 8

The first previous link is sufficient for routine previous-race analysis and preserves size headroom. All five previous links remain available in canonical Raw and Core.

## Input

### Production full rebuild path

- annual BAC/KYI/SED/CYB/UKC ZIPs
- `schema/jrdb_analysis_schema_v1_2.sql`

### Production incremental path

For each completed target race date:

- BACyymmdd.zip
- KYIyymmdd.zip
- SEDyymmdd.zip
- CYByymmdd.zip
- UKCyymmdd.zip

Increment only after the result-side SED Raw has been published.

### Reference Core path

- Core v1.2.1 SQLite containing `horse_profile_current`, `entry.frame_no`, `result.track_condition_code`, and `entry_previous_result`
- `schema/jrdb_analysis_schema_v1_2.sql`

## Output

Main table: `fact_entry_result_lite`, one row per entry/result.

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
- explicit JRDB previous-result/race key 1

Provenance-heavy fields, comments, workout rows, full previous-result 1-5 expansion, duplicate metadata and anomaly metadata remain outside the routine Analysis file.

## Run

Raw -> Analysis full rebuild:

```bash
python src/build_jrdb_analysis_from_raw.py \
  --years 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 \
  --raw-root ./00_raw_local \
  --db ./jrdb_analysis_2016_2025.sqlite
```

Incremental replacement:

```bash
python src/update_jrdb_analysis_incremental.py \
  --db ./jrdb_analysis.sqlite \
  --raw-root ./00_raw_local \
  --dates 20260822 20260823
```

Existing v1.1 DB upgrade:

```bash
python src/upgrade_jrdb_analysis_v1_1_to_v1_2.py \
  --db ./jrdb_analysis_2016_2025.sqlite \
  --raw-root ./00_raw_local \
  --years 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025
```

Core -> Analysis reference path:

```bash
python src/build_jrdb_analysis.py \
  --core ./jrdb_core_v1_2_1.sqlite \
  --db ./jrdb_analysis.sqlite
```

## Age rule

For JRA aggregation:

```text
age = race_year - birth_year
```

## Core/Raw path equivalence — v1.2 PASS

All **33 fact columns** were compared.

### 2016-2020

- rows: 243,849
- prev1 populated: 220,525
- Core minus Raw: 0
- Raw minus Core: 0

### 2021-2025

- rows: 237,778
- prev1 populated: 214,097
- Core minus Raw: 0
- Raw minus Core: 0

Combined validated coverage:

- years: **2016-2025**
- rows: **481,627**
- prev1 populated: **434,622**
- columns compared: **33**
- differences: **0**

Blank Core previous-link strings are normalized to SQL NULL so both routes are exactly equivalent.

## Previous-link size decision

A benchmark of a separate normalized table containing all available previous links 1-5 for 2016-2025 produced:

- nonblank previous-link rows: ~1.78 million
- standalone SQLite size: ~81.9 MiB

Adding this to the routine ten-year Analysis artifact would consume too much connector headroom. A prev1-only representation is therefore the production Analysis design; full 1-5 linkage stays in Raw/Core and can be used for detailed delivery when required.

## Analysis v1.2 ten-year measurement — PASS

2016-2025 after prev1 addition, removal of unnecessary prev-key indexes, and VACUUM:

- rows: **481,627**
- sire nonblank: **481,519**
- prev1 populated: **434,622**
- SQLite: **182,439,936 bytes (~173.99 MiB)**
- ZIP (`zip -1`): **50,801,391 bytes (~48.45 MiB)**
- `PRAGMA integrity_check`: **ok**
- SQLite SHA-256: `a9ebbd03c327e37384aa73593c2049c1f7efd0b5f3faf55449f6560763faf579`
- ZIP SHA-256: `69955c3e2930def2f47a88676c955bc610e6a31fd275dd1570c97921631af3f9`

This remains below the 200 MiB routine Analysis design target and below the current ~256 MiB remote connector ceiling.

Prev-key indexes are intentionally omitted: normal previous-race retrieval starts from a selected current row, reads its explicit previous key, then resolves the target through the existing fact primary key/race key path. Avoiding two low-value indexes preserves about 18 MiB of delivery headroom.

## Incremental replacement regression — PASS

Historical pseudo-daily test using canonical 2025-12-28 Raw members:

- races: 24
- rows before replacement: 356
- rows after replacement: 356
- complete row hash before/after: identical
- batch status: SUCCESS
- `PRAGMA integrity_check`: `ok`

The updater parses all five required daily Raw archives before opening the replacement transaction. Re-running a date safely replaces that date and records source SHA-256 values in `meta_analysis_ingest_batch`.

## Drive delivery

The earlier v1.1 2016-2025 Analysis SQLite (~169 MiB) was uploaded and fetched through the ChatGPT Drive connector with size/row count/integrity/SHA matching. v1.2 remains in the same practical size class and below the connector ceiling.

## Recommended production operation

During the season:

```text
JRDB completed-date Raw
  -> Analysis incremental replace/add
  -> refresh the current-year Stats Mart
```

At year-end:

```text
2016-2026 YTD Analysis
  -> rebuild rolling window directly from 2017-2026 Raw
  -> compact/VACUUM
  -> rebuild full yearly Stats Mart
```

Core is maintained independently for auditability, full normalized history, anomaly/duplicate investigation, and reproducibility. Rebuilding Core is not required before Analysis refresh.

See `docs/README_update_jrdb_analysis_incremental.md` for the operational details.
