# BRDB P0-2 / P1-1 acceptance — supplied archive intake (2026-11-04)

Status: **HOLD (research-only)**. This record is an intake/integrity audit, **not** a rerun of the GitHub committed code or a publication approval.

## Supplied archive byte identities

- P0-2 ZIP SHA-256: `1939424ffa477f2e56702a2ef2a069c626a5fadf88c323aff16d833b76b37bef`
- P1-1 ZIP SHA-256: `ad5382b4171b13498786c98fb4f25a835ef9a9999618e0b9a333a4988c694d4c`

The ZIPs were provided as conversation attachments. They are **not** uploaded to this repository or its public Actions artifacts.

### P0-2 archived script identities

- `build_brdb_result_mart.py` SHA-256: `353f3ba8ab2ce31aa578a6086c97ab1a2c6d1b9cb3cc8d7e92e4e95fb7796bca`; Git blob: `39161db68c0e2002a30341f0631090ee67b0abfd`
- `test_build_brdb_result_mart.py` Git blob: `aa2472e91122768777262930ff2061c63c2801e3`

### P1-1 archived script identities

- `build_lineage_condition_report.py` SHA-256: `50f95aaa69df7c8e156c3d5f008179145db50bf0c549f253d9842f5abbc6e3eb`; Git blob: `0d882dcd1c62c8058ef750e4799aa6deee069bd0`
- `test_lineage_condition_report.py` Git blob: `7bdd265ec06f5e3cbecac16e14dc0c5fdf5139b6`

None of the four script Git blob IDs matches the previously committed PR source/test blob. Committed code has additional safety checks and must **not** be blindly overwritten with older archived sources.

## Archived result integrity and audit claims

From the archive audit records, with corresponding stored result file SHA-256 checked:

- P0-2: `total_entries=481627`; `brdb_result_mart.parquet` SHA-256 `0de9a6f25fd9a6295b3133c64cb276f442cfd6cc797ca6477bc7b273f0a5172c`; `brdb_sire_condition_counts.json` SHA-256 `1e142d21d4d30c0940c1306cd66efe9a876d845e273cb552d70beecaa52d4e01`.
- P1-1: `total_entries=481627`; `normal_finishers=477650`; `groups_all=18367`; `groups_eligible=1935`; source P0-2 SHA as above.
- P1-1 output SHA-256: `lineage_conditions_all.csv` `707c43343cadd9578dbee8f5e16d8bbf0b421d9ef69b26ef76be00dcac6c1bad`; `lineage_conditions_eligible.csv` `331f873075fc11c63cb4818e3ef7d7d1fc3fa553e7d34c3fd60e3d8ffa2d7af7`; `baseline_surface_distance.json` `81419a93ae02de85d5a3de2a54e9d76cb9ed411fb191f7ac6c9f3d1bb102f822`.

## Independent CSV structural checks (without DuckDB)

The archived P1-1 CSVs were parsed in their entirety with Python standard-library `csv`:

| File | Data rows | Key duplicates | Role split | `wins > n` |
|---|---:|---:|---|---:|
| `lineage_conditions_all.csv` | 18,367 | 0 | SIRE 6,616 / BMS 11,751 | 0 |
| `lineage_conditions_eligible.csv` | 1,935 | 0 | SIRE 948 / BMS 987 | 0 |

The group key used for this check is `(lineage_role,lineage_code,surface_code,distance_band,venue_code,race_class_code)`. These are **structural checks only**; they do not demonstrate scientific row-equivalence of a committed-code rerun.

## Actions fallback smoke requests

- P0-2 pinned source ref `59b742e743075a334277e730218b2caae28d1ea7`: [Issue #2351](https://github.com/yukki0113/GPT/issues/2351).
- P1-1 pinned source ref `bedd3219d1424198381020f77418b96b4ef0b18b`: [Issue #2353](https://github.com/yukki0113/GPT/issues/2353).

Both request Issues have now closed with **DATA_STORAGE_FALLBACK_RESULT status: PASS**, and each underlying GitHub Actions job completed successfully with a result artifact:

- P0-2: [run 41743585539](https://github.com/yukki0113/GPT/actions/runs/41743585539); `source_commit=59b742e743075a334277e730218b2caae28d1ea7`; `duckdb_version=1.1.3`; `pyarrow_version=25.0.1`; artifact `data-storage-fallback-41743585539`.
- P1-1: [run 41743678023](https://github.com/yukki0113/GPT/actions/runs/41743678023); `source_commit=bedd3219d1424198381020f77418b96b4ef0b18b`; `duckdb_version=1.1.3`; `pyarrow_version=25.0.1`; artifact `data-storage-fallback-41743678023`.

**These are synthetic regression PASS results only, NOT a real-data acceptance or a source-equivalence claim.**

## Current acceptance gates

1. Validate new source changes on **DuckDB 1.1.3**, using repository shared `tools/data-storage/` and its documented local-first / Actions fallback.
2. Compare exact committed source output to the archived full-cohort results at row/semantic level; Parquet byte SHA may differ with layout.
3. Securely reproduce JRDB KYI/SED/BAC 2016–2025 and BRDB pedigree generation from authorized immutable, SHA-verified inputs; **do not make licensed/private JRDB data public for fallback**.
4. Verify P1-1 aggregate rows and metrics, and record source commits, input generations and independent audit results.
5. Keep both PRs draft/HOLD until gates pass. Do not advance BRDB CURRENT, predictions, as-of backtests, or downstream publication.

This intake record preserves traceability, not a PASS/merge decision.
