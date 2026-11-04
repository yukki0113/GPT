# BRDB P0-2 / P1-1 — Formal Research Acceptance (2026-11-04)

## Decision

**PASS — research code + 2016–2025 historical descriptive output, only.**

This PASS authorizes PR #2340 then PR #2342 to merge into GitHub `main` strictly as **research-only** source and audit assets. It does **not** approve predictions, as-of attribution, BRDB CURRENT promotion, RaceNote/PWA changes, automated publication or operational use.

Formal replay used exact GitHub-committed Python sources from stacked head `9b62dec0de2a6f3df1eb8b1db6d90d7970f81807`, including P0-2 head `11188a63aed47c29d0199076101bdd0d6e406d0e`. The source bundle was transferred by [Actions run 41748636544](https://github.com/yukki0113/GPT/actions/runs/41748636544); Git blob hashes were verified byte-for-byte:

- `build_brdb_result_mart.py` Git blob `970d3b29925db562e4f6c8c7375ee2438b324390`.
- `build_lineage_condition_report.py` Git blob `43516361a0020ab6eebb09d291d7ca6c95115b25`.
- P0-2 synthetic test Git blob `9fce6904ba5c9b91ef1d407925d3711f6a34552d`.
- P1-1 synthetic test Git blob `bbe4becee8143ac07955fba3e68bdb2b5329a6ac`.

## Reproducible environment

- Local CPython 3.13, **DuckDB 1.1.3**; exact official manylinux CPython 3.13 wheel SHA-256 `d5724fd8a49e24d730be34846b814b98ba7c304ca904fbdc98b47fa95c0b0cee`.
- The pinned wheel was safely fetched through a *temporary, unmerged* branch and [Actions run 41748491405](https://github.com/yukki0113/GPT/actions/runs/41748491405), then locally installed offline. No licensed JRDB rows were transmitted to GitHub.
- Exact Github-committed source: **8/8 local synthetic unit tests PASS**, including positive 481,627-row generated fixture, tamper and official SED abnormal status checks.
- Independently, [Actions run 41747425194](https://github.com/yukki0113/GPT/actions/runs/41747425194) confirms all P0-2 / P1-1 regressions PASS on the same pinned source revision, DuckDB 1.1.3 / PyArrow 25.0.1.
- Real historical assets were fetched through **connected Google Drive into the private runtime**, not GitHub Actions or public artifacts. SHA-256 verified for 30 individual immutable annual Parquet objects: KYI 10, SED 10, BAC 10, covering 2016–2025; BRDB pedigree generation `5279af0bd8226cde` fact and manifest verified.

## P0-2: Full cohort committed-code replay and exact row equivalence

| Check | Result |
|---|---|
| Historical cohort | **481,627 records** |
| Validating JOIN `(race_key,horse_no)` unique rows | **481,627** |
| Normal finishers | **477,650** |
| Static pedigree joined | **481,623** |
| BAC verified records | **480,892** |
| SED fallback | **735** |
| Original vs rerun schema | Identical 22 columns/types |
| New `EXCEPT ALL` archive (full row, all columns) | **0 rows** |
| Archive `EXCEPT ALL` new | **0 rows** |
| Annual audit | Identical across 10 years |
| Aggregated JSON SHA | Identical: `1e142d21d4d30c0940c1306cd66efe9a876d845e273cb552d70beecaa52d4e01` |

Archived P0-2 mart Parquet SHA-256 `0de9a6f25fd9a6295b3133c64cb276f442cfd6cc797ca6477bc7b273f0a5172c`; committed-source replay Parquet SHA-256 `8b41f4b7132bc268428133535cce9c4aff79ac5b7b4c0dca5a5cdd5c1df13b63`.

**These file-level SHA values differ, but the complete 481,627-row 22-column logical multiset is byte-for-byte field equivalent in both directions.** Parquet serialization/layout bytes are *not* an acceptance gate when validated logical rows and all typed columns match.

SED official abnormal codes in this cohort: `0=477650; 1=748; 2=1000; 3=2208; 4=1; 5=20; 6=0`, with 0 unknown/null. Actual starters are **not** equated to normal finishers.

## P1-1: Full cohort committed-code replay and exact output bytes

Newly generated P0-2 mart was SHA-pinned and used as P1-1 input. Both original and rerun audits report:

- `total_entries=481627`; `normal_finishers=477650`.
- `groups_all=18367`; `groups_eligible=1935`; SIRE eligible 948, BMS eligible 987.
- **All 3 generated P1-1 files exactly match the attached archive byte-for-byte, with identical SHA-256:**
  - `lineage_conditions_all.csv` `707c43343cadd9578dbee8f5e16d8bbf0b421d9ef69b26ef76be00dcac6c1bad`.
  - `lineage_conditions_eligible.csv` `331f873075fc11c63cb4818e3ef7d7d1fc3fa553e7d34c3fd60e3d8ffa2d7af7`.
  - `baseline_surface_distance.json` `81419a93ae02de85d5a3de2a54e9d76cb9ed411fb191f7ac6c9f3d1bb102f822`.
- All P1-1 audit semantic fields match the original, except the expected P0-2 input **Parquet physical file SHA**, which differs although the logical input rows are identical.
- Earlier independent CSV arithmetic verified 202,037 derived values without discrepancies.

## Input provenance exception (explicit, accepted for the 2016–2025 subset only)

The current KYI **manifest file itself** has SHA-256 `9a089ffe2e9edefc14d8597592b469cde00f72b54fac77c651ac230fec21fb6f`, while original archived audit recorded `f6464b03fc6eafcaf696eb87ee86ebb4833b17261fcf88e7796efaff8c47ca74`.

The *underlying selected 2016–2025 inputs* are nevertheless identical: same generation ID `historical-warehouse-staging-kyi-35443130585`, all **10 annual object SHA-256** match the archived audit object names exactly, and every P0-2 joined row matches the original archive in both directions. SED and BAC manifest file hashes also match the original. The differing KYI manifest **byte identity is not represented as equal**. This exception is accepted solely for the verified 10-year descriptive dataset and does **not** authorize silently accepting mismatched manifests in future updates.

## Acceptance boundary

- **Research-only:** `prediction_safe=false`, `pedigree_temporal_status=STATIC_LATER_SELECTED_SNAPSHOT_NOT_ASOF_VERIFIED`.
- No as-of proof, no pre-race use, no starter-denominator inference, no betting ranking or automated selection.
- Repeated-horse dependence, multiple testing, temporal stability and actual starter semantics remain separate research work.
- No changes to BRDB CURRENT generation `eeca93556584a5b8`, RaceNote, PWA, or publication workflows.
- Keep actual licensed JRDB records and generated row-level Parquet off public GitHub; this document contains aggregate-only evidence.

**Formal research PR acceptance: PASS, sequential merges permitted: #2340 then #2342.**
