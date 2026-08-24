# JRDB Core Builder v1.1.2

`build_jrdb_core.py` reads annual JRDB Raw ZIPs in CP932 fixed-width byte offsets and creates a provenance-preserving SQLite Core database. The source ZIPs are not modified.

## Scope

- Target types: `BAC / KYI / SED / SKB / CYB / CHA / UKC`
- Excluded: `KKA`
- Input layout: `<raw-root>/<TYPE>/<TYPE>_<YYYY>.zip`
- Required schema: `jrdb_core_schema_v1_1_2.sql`

## Run

```bash
python build_jrdb_core.py \
  --years 2010 2011 2012 2013 2014 2015 2016 2017 \
          2018 2019 2020 2021 2022 2023 2024 2025 \
  --raw-root ./00_raw_local \
  --db ./jrdb_history_2010_2025.sqlite \
  --schema ./jrdb_core_schema_v1_1_2.sql
```

## v1.1.2 behavior

- Only exact canonical members matching `TYPE+YYMMDD.txt` are normalized. Other same-prefix TXT members are kept in `meta_source_file` with `is_canonical=0` and `source_role=NON_CANONICAL`, but are excluded from Core tables.
- Duplicate raw records are never silently replaced by a generic completeness rule. Identical records are collapsed; conflicting records are retained in `meta_duplicate` and resolved only when date evidence is available.
- BAC race-date conflicts may be resolved through cross-type date support (`CROSS_TYPE_DATE_CONFIRMED`). CYB/CHA conflicts may be resolved only when the established BAC race date matches one of the candidate source dates (`RACE_DATE_ALIGNED_SELECTED`).
- SED payout fields use the fixed-width positions beginning at byte offsets 341 and 348 (0-based).
- BAC fallback races, orphan records, missing source dates, duplicate conflicts, and invalid filename dates are recorded in `meta_anomaly`.
- Every normalized row retains `source_file_id`, `source_record_no`, and record SHA-256 for raw provenance.

## Notes

Build into a new SQLite path. Do not append to an existing database. Run `PRAGMA integrity_check;` after the build and preserve the matching audit outputs with the DB.
