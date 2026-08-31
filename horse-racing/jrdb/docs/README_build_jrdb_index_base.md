# JRDB PWA Index Base v0.1

## 1. Purpose

`build_jrdb_index_base_from_raw.py` builds the longitudinal research SQLite used by the PWA independent-index project.

This database is **not** a replacement for Analysis Lite, Stats Mart, Fact Lite, or RaceNote. It is a Raw-direct research layer whose job is to preserve enough pre-race and result detail to build and backtest:

- RunPerf
- Ability
- Edge
- debut / cold-start models
- JRDB Addition Tests

Design source of truth:

- `JRDB_PWA_Index_Design_v0_1.md`
- `JRDB_PWA_Index_Feature_Registry_v0_1.md`
- `JRDB_Training_Index_Definitions.md`

## 2. Why this is separate from Analysis Lite

Analysis Lite intentionally keeps a compact one-entry-per-row production schema. It does not retain several fields required by the independent-index research design, including full race time, first/last 3F, corner positions, carried weight, body weight, detailed workout data, and several SED diagnostic fields.

Index Base therefore reads annual Raw ZIPs directly instead of enlarging the production Analysis contract.

## 3. Input layout

The builder follows the existing JRDB annual Raw layout:

```text
<raw-root>/
  BAC/BAC_2010.zip
  KYI/KYI_2010.zip
  SED/SED_2010.zip
  UKC/UKC_2010.zip
  CHA/CHA_2010.zip   # optional
  CYB/CYB_2010.zip   # optional
  ...
  BAC/BAC_2025.zip
  ...
```

Required kinds:

- BAC
- KYI
- SED
- UKC

Optional kinds:

- CHA
- CYB

Canonical members are `KINDyymmdd.txt`. Non-canonical members are ignored.

## 4. Availability boundary

The schema deliberately separates information by when it becomes available.

### PRE_RACE

- `race_context` — BAC race conditions
- `runner_pre` — KYI runner information
- `runner_previous_link` — KYI previous 1-5 links
- `workout_main` — CHA selected main workout
- `training_analysis` — CYB intermediate training analysis
- `horse_profile_observation` — dated UKC pedigree/profile snapshot

### CURRENT_RESULT

- `race_result_context` — SED final track condition/weather
- `runner_result` — SED result/performance/material

`race_context.availability_class` is normally `PRE_RACE`.

If BAC is missing for a historical race, the builder can create a race header from SED so the result remains researchable. Such rows are explicitly marked:

```text
CURRENT_RESULT_FALLBACK
```

They must not be used as if they had been known pre-race.

## 5. Keys

The Raw keys are retained without numeric reconstruction.

```text
race_key        = venue + year + meeting + day(F) + race number
race_horse_key  = race_key + horse_no
result_key      = blood registration number + YYYYMMDD
```

`runner_previous_link` retains all KYI previous 1-5 result/race keys.

`runner_result.result_key` is UNIQUE so a previous-result key can resolve directly to the historical run.

## 6. Main tables

### `race_context`

Race-level pre-race conditions:

- date / venue / race number
- distance / surface
- turn / inner-outer / course
- race type / class / symbol / weight condition / grade
- race name / declared field size
- availability class and provenance

### `race_result_context`

Final race-level context from SED:

- final track condition
- weather

This is separated from `race_context` to keep current-result facts out of the pre-race contract.

### `runner_pre`

KYI pre-race runner information, including:

- horse / frame / sex
- jockey / trainer codes and names
- carried weight
- running style / JRDB aptitude/uptrend
- pre-race IDM and selected JRDB judgment fields
- pre-race body weight when present
- start index / slow-start rate
- stable-cycle fields
- JRDB expected ten/pace/last3f/position values for later Addition Tests

Popularity/reference-odds fields are intentionally not required by the Ability/Edge base contract.

### `runner_result`

SED result and one-run performance material, including:

- result key
- finish / abnormal code / time
- carried weight / jockey / trainer
- final market values for evaluation only
- IDM / raw score
- JRDB track/pace/start/position/trouble diagnostics
- first and last 3F
- corner positions
- leader gaps
- body weight/change
- payouts

These are CURRENT_RESULT fields and must never be joined into the target race's pre-race feature snapshot except as historical information from an earlier date.

### `workout_main`

CHA selected main workout:

- date / course / effort / chase state / rider / furlongs
- raw first/middle/final segment times
- JRDB prepared segment/workout indices
- paired-horse result and conditions

### `training_analysis`

CYB preparation process:

- training type / course type
- used course families
- training distance/focus
- JRDB workout / finish indices
- training volume / finish change / evaluation
- week-ago workout fields

### `horse_profile_observation`

Dated UKC observations, rather than a single latest profile. This supports time-aware pedigree joins.

If UKC `data_date` is blank, the canonical member business date is used as the observation date. No future profile observation should be selected for a historical target.

## 7. Research convenience view

`v_runner_longitudinal_base` joins race, runner, result, CHA and CYB at one-race-one-horse grain for exploration.

The view includes result columns by design and therefore **is not itself a pre-race feature table**.

Feature builders must apply the availability/as-of rules from the index design.

UKC profile is not joined into the view because the correct profile row depends on the target date. Use an as-of join against `horse_profile_observation`.

## 8. Build command

Example for the full design window:

```bash
python horse-racing/jrdb/src/build_jrdb_index_base_from_raw.py \
  --raw-root /path/to/jrdb/raw \
  --years 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025 \
  --db /path/to/jrdb_index_base_2010_2025_v0_1.sqlite
```

For exploratory builds where annual ZIP SHA-256 calculation is unnecessarily expensive:

```bash
... --no-archive-hash
```

Production/accepted research artifacts should normally retain archive hashes.

The builder refuses to overwrite an existing SQLite file.

## 9. Audit metadata

- `meta_index_base_build`
- `meta_index_base_source`
- `meta_index_base_anomaly`

The source manifest records archive path, optional SHA-256, size, member count, and imported time.

Missing CHA/CYB archives are warnings rather than fabricated values. Required BAC/KYI/SED/UKC archives fail the build.

A completed build must pass `PRAGMA integrity_check`.

## 10. Validation status

Implemented synthetic tests cover:

- BAC parser / PRE_RACE marking
- KYI pre-race fields and previous 1-5 links
- SED time, first/last 3F, JRDB diagnostics, result key
- separation of final track condition into `race_result_context`
- CHA / CYB workout fields
- UKC observation-date fallback
- schema availability tables
- one-year end-to-end synthetic ZIP -> SQLite build

Initial synthetic regression status: **7/7 PASS**.

A real 2010-2025 full build is still required against the external canonical Raw storage before this base is accepted as a validated research artifact. Synthetic success must not be presented as full historical validation.

## 11. Next phase

After real-data ingestion/audit, Phase B is:

1. build race representative times
2. rolling ExpectedTime candidates
3. DayTrackBias
4. B0/B1/T0/T1/T2/T3 RunPerf candidates
5. J0/J1 JRDB benchmark comparison
6. choose the RunPerf target before Ability training begins
