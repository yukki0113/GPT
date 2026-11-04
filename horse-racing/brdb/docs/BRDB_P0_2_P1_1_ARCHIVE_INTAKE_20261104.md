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

## Additional independent verification (2026-11-04)

With only the attached archives and the standalone SED canonical manifest, without a DuckDB engine:

- Independently recomputed **202,037** P1-1 formula values across all **18,367** groups: rates, lifts, Wilson intervals and sample eligibility; **zero differences**.
- Recomputed the eligible subset: **1,935** rows, exact row membership and full CSV content equality with the all-groups file; **zero differences**.
- Checked key uniqueness (18,367 unique keys), 365 consistent baseline race-condition strata and per-row arithmetic bounds; **zero differences**.
- SHA-256 of the supplied SED canonical manifest: `ca922611b5bb2db73a0e1f5b1d5ba591b9b18e4eabf9ef109389c707341377ee`, matching the archived P0-2 audit input record.
- For **every 2016–2025 year**, P0-2 audit `entries` exactly matched the corresponding accepted SED manifest object's `row_count`; sum **481,627**.
- Supplied BRDB research pedigree archive manifest SHA-256 `7efb70ab370cafd18d39eb20ea4fc2bb32490653364a58b44b1382cf9fa5f16c`; `pedigree_fact.parquet` SHA-256 `1e7574f78703d79d8d83797f9e350a8927b728fc68c659cf5d340ee0f79b3536`, both matching the P0-2 input audit.

**Input location / legal boundary:** Attached ZIPs contain the derived P0-2/P1-1 results and the BRDB pedigree generation, but not the full 2016–2025 KYI/SED/BAC annual Parquet objects. The official JRDB terms <https://jrdb.com/terms> Article 5 prohibit sharing/public disclosure of JRDB information, including unpaid third-party provision. Consequently, Google Drive `anyone:reader` metadata is **not** permission to create or use public GitHub Actions artifacts or public Drive fallback manifests containing proprietary JRDB rows. Do not bootstrap full-data Actions with these files without separate explicit licensing/security authorization. Prefer private authorized execution and keep the raw data off GitHub.

## P1-1 GitHub output-contract repair and pinned regression

Review found that the committed P1-1 builder omitted `baseline_entries` from the per-lineage CSV output (the archived, full-cohort-tested script included it) and omitted `identities` and `baseline_surface_distance` audit fields. This was a substantive output-contract difference, despite earlier negative-only tests PASSing.

Fixed on P1-1 branch:

- Builder commit `c535f45d0441c390eac30a280a812f205db1e0c0`: restored `baseline_entries` and original descriptive audit contract while retaining the committed input SHA, temporal, cohort and key guards.
- Test commit `9a4ba9930919246c6958e21e4aa4bbabd5e6a823`: added positive regression using **481,627 generated synthetic rows** without proprietary inputs, verifying 2 lineage roles, baseline entries/denominator, eligibility and audit fields.
- [Fallback Issue #2359](https://github.com/yukki0113/GPT/issues/2359) closed with `status: PASS`; [run 41746337349](https://github.com/yukki0113/GPT/actions/runs/41746337349) job `success`; artifact `data-storage-fallback-41746337349`; DuckDB `1.1.3`, PyArrow `25.0.1`, source commit `9a4ba9930919246c6958e21e4aa4bbabd5e6a823`.

This is still **not** a full proprietary-data replay or row-level identity validation against archived P1-1 CSVs. Keep the PRs HOLD pending legitimate complete-data access and actual committed-code equivalence.

## Stacked PR reconciliation and combined regression (2026-11-04)

- P1-1 branch synchronized with latest P0-2 using merge commit `2e62a4484e70d0b1ceee65985bcc664ca40f1310`, preserving both parents and all P1-1 files.
- GitHub comparison of current P0-2 base to P1-1 head: **ahead 7, behind 0**, PR #2342 reports `mergeable=true`.
- [DATA_STORAGE_FALLBACK Issue #2360](https://github.com/yukki0113/GPT/issues/2360) closed with `status=PASS`. The **same source commit** ran both `test_build_brdb_result_mart.py` and `test_build_lineage_condition_report.py`, including the 481,627-row **synthetic** positive fixture, on DuckDB `1.1.3`, PyArrow `25.0.1`.
- [Actions run 41747039718](https://github.com/yukki0113/GPT/actions/runs/41747039718): job completed `success`, artifact `data-storage-fallback-41747039718` present.

**Full cohort replay remains unverified for the GitHub source commits.** The archived source versions and later GitHub versions are distinct Git blobs; the synthetic regression, archived artifact hashes, independent CSV arithmetic, and 10 annual SED manifest row counts do **not** prove row-level equivalence of a full committed-code replay. The attached ZIP carries the finished P0-2 mart but **not** the 2016–2025 complete KYI/SED/BAC annual assets. The current managed Python runtime also lacks DuckDB and its package source is unavailable. Do not substitute a hand-written data parser or publish record-level data to Actions to manufacture a PASS.

## Current acceptance gates

1. Validate new source changes on **DuckDB 1.1.3**, using repository shared `tools/data-storage/` and its documented local-first / Actions fallback.
2. Compare exact committed source output to the archived full-cohort results at row/semantic level; Parquet byte SHA may differ with layout.
3. Securely reproduce JRDB KYI/SED/BAC 2016–2025 and BRDB pedigree generation from authorized immutable, SHA-verified inputs; **do not make licensed/private JRDB data public for fallback**.
4. Verify P1-1 aggregate rows and metrics, and record source commits, input generations and independent audit results.
5. Keep both PRs draft/HOLD until gates pass. Do not advance BRDB CURRENT, predictions, as-of backtests, or downstream publication.

This intake record preserves traceability, not a PASS/merge decision.
