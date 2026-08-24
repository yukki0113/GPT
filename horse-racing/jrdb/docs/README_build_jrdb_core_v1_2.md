# JRDB Core Builder v1.2

`build_jrdb_core_v1_2.py` is an additive wrapper around the proven v1.1.2 Core Builder.
It deliberately keeps the v1.1.2 normalization / duplicate / fallback behavior unchanged,
then enriches the resulting database with full UKC horse profile current/history tables.

## Status

Experimental / regression phase. v1.1.2 remains the production rollback baseline until full regression passes.

## Inputs

- Raw ZIP layout: `<raw-root>/<TYPE>/<TYPE>_<YYYY>.zip`
- Base builder: `src/build_jrdb_core.py`
- UKC parser: `src/jrdb_ukc.py`
- Schema: `schema/jrdb_core_schema_v1_2.sql`

## Added tables

- `horse_profile_current`
- `horse_profile_history`

The legacy-compatible `horse_current` / `horse_history` tables remain present.

## UKC source fields

The v1.2 parser uses the 290-byte UKC definition confirmed from JRDB-data/converter:

- horse id / horse name
- sex / coat color / horse symbol
- sire / dam / broodmare sire
- birth date
- sire / dam / broodmare sire birth years
- owner / owner group
- breeder / breeding place
- deregistration flag
- data date
- sire-line / broodmare-sire-line codes

`data_date`, source IDs, record number, and reserved bytes do not by themselves create a semantic history version.

## Run

```bash
python src/build_jrdb_core_v1_2.py \
  --years 2021 2022 2023 2024 2025 \
  --raw-root ./00_raw_local \
  --db ./jrdb_history_2021_2025_v1_2.sqlite \
  --schema ./schema/jrdb_core_schema_v1_2.sql
```

For the final full build, expand `--years` to 2010-2025 after regression acceptance.

## Regression gates before production promotion

1. `PRAGMA integrity_check = ok`
2. race / entry / result / training / workout / result_extension / previous-result counts match v1.1.2 for the same Raw set
3. duplicate resolutions and known anomaly counts remain compatible with v1.1.2
4. SED payout regression remains unchanged
5. BAC fallback remains unchanged
6. UKC profile parsing has 290-byte record compliance
7. sire / broodmare-sire population rates are reported
8. semantic history ignores data-date-only snapshot repetition
9. real semantic changes create `horse_profile_history` rows
10. after A passes, proceed directly to Analysis Lite PoC with sire fields included

## 2025 UKC parser validation

Using the canonical `UKC_2025.zip` Raw archive:

- canonical daily UKC files: 109
- parsed body records: 47,239
- body-length errors: 0
- CP932 replacement/decode errors: 0
- invalid `birth_date` / `data_date`: 0
- missing sire name: 0
- repeated records with unchanged semantic hash: 35,115
- repeated records with changed semantic hash: 306

Example unchanged snapshot:
`horse_id=20104778`, data dates 2025-01-05 -> 2025-01-11, semantic hash unchanged.

Example semantic change:
`horse_id=21105399`, 2025-01-19 -> 2025-03-23, owner / owner-group changed; semantic hash changed as intended.
