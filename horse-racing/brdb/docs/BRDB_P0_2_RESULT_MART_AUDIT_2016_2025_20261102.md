# BRDB P0-2 — JRDB race-result × static pedigree descriptive research mart (2026-11-02)

**Status: Local full-data research audit PASS / GitHub implementation candidate.** No production approval, prediction, serving, or CURRENT change.

## Provenance

Source: JRDB Historical Warehouse immutable year-partitioned Parquet, 2016–2025:

| Family | Generation | Manifest SHA-256 |
| --- | --- | --- |
| KYI | `historical-warehouse-staging-kyi-35443130585` | `f6464b03fc6eafcaf696eb87ee86ebb4833b17261fcf88e7796efaff8c47ca74` |
| SED | `historical-warehouse-staging-sed-35443130585` | `ca922611b5bb2db73a0e1f5b1d5ba591b9b18e4eabf9ef109389c707341377ee` |
| BAC | `historical-warehouse-staging-bac-35443130585` | `5e186f2b4f609fc75e2f66fe26db485fcca90997cb47aef962152c10ac9a9072` |
| BRDB pedigree | `5279af0bd8226cde` | `7efb70ab370cafd18d39eb20ea4fc2bb32490653364a58b44b1382cf9fa5f16c` |

All year assets were local size- and SHA-validated against their manifests. No new external pedigree data were fetched.

## Exact keys and guardrails

- KYI ↔ SED: `(race_key_raw,horse_no)`, with `blood_registration_no` required to agree; no horse-name fallback.
- SED ↔ BAC: `race_key_raw`, with cross-source race-date, surface, and distance consistency checks. When BAC does not contain a race, use SED conditions and record `context_source=SED_FALLBACK`.
- KYI ↔ BRDB: `blood_registration_no=horse_id`, **static, later-selected profile**. If absent, keep row as `UNKNOWN_HORSE_ID`.
- Output `pedigree_temporal_status=STATIC_LATER_SELECTED_SNAPSHOT_NOT_ASOF_VERIFIED` for every row, including matched profiles. **Not pre-race safe.**
- `abnormal_code='0'` and `finish BETWEEN 1 AND 18` are **normal finishers**, not all confirmed actual starters. The other statuses are retained without guessing start/cancellation classifications.
- Non-normal records, missing BAC, and missing pedigree are not silently dropped. Fail closed on duplicate identity, conflicting horse ID, bad asset hash, changed row cardinality, or conflicting race metadata.
- No scores, no inference of pedigree condition fitness, no historical prediction claims.

## Full 2016–2025 executed result

| Year | KYI↔SED joined | Static BRDB matched | BAC matched | SED context fallback | Normal finishers |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2016 | 50,076 | 50,076 | 50,076 | 0 | 49,697 |
| 2017 | 49,299 | 49,299 | 49,299 | 0 | 48,922 |
| 2018 | 48,618 | 48,618 | 48,618 | 0 | 48,199 |
| 2019 | 47,574 | 47,574 | 47,574 | 0 | 47,118 |
| 2020 | 48,282 | 48,282 | 48,282 | 0 | 47,876 |
| 2021 | 47,821 | 47,821 | 47,821 | 0 | 47,476 |
| 2022 | 47,220 | 47,220 | 47,220 | 0 | 46,840 |
| 2023 | 47,672 | 47,672 | 47,672 | 0 | 47,273 |
| 2024 | 47,181 | 47,181 | 47,181 | 0 | 46,752 |
| 2025 | 47,884 | 47,880 | 47,149 | 735 | 47,497 |
| **Total** | **481,627** | **481,623** | **480,892** | **735** | **477,650** |

2025's **4** missing BRDB profiles are preserved; 2025 BAC coverage has **735** runner entries with SED-derived course-condition fallback. For 2016–2024 BAC joins fully cover the KYI cohort.

## Local research output

Builder: `horse-racing/brdb/src/build_brdb_result_mart.py`.

- `brdb_result_mart.parquet`: 481,627 rows, ZSTD Parquet, SHA-256 `0de9a6f25fd9a6295b3133c64cb276f442cfd6cc797ca6477bc7b273f0a5172c`.
- `brdb_sire_condition_counts.json`: father-lineage code × surface code × distance band × race year; normal finishers, winners, and top-three counts. SHA-256 `1e142d21d4d30c0940c1306cd66efe9a876d845e273cb552d70beecaa52d4e01`.
- `audit.json`: local manifest SHA bindings, annual row-level match counts, output hashes, limitations.
- Source record-level Parquet is proprietary, kept in the private GPT execution environment. **Do not commit it or raw IDs to GitHub** or publish it to a public URL.

The executed local build and three synthetic tests passed with DuckDB 1.2.2. Repository common data-storage currently pins DuckDB 1.1.3; this version difference requires CI/reproduction qualification before production use.

## Next acceptance gate

1. Verify this PR source and unit tests on an approved repo runtime (including pinned DuckDB 1.1.3); fix any version-specific issues.
2. Independently rerun all ten partitions from the approved manifests and compare exact aggregate and output hashes.
3. Complete stronger result classification / start-status semantics from the JRDB fixed-width master if analyzing true starters.
4. For predictive backtests, create a **separate** pre-race as-of verified lane. P0-1 date-only coverage was partial (54,929/481,627); descriptive static facts must not enter that lane.
5. P1 blood × condition statistics may use these **descriptive** counts, with sample-size and selection-bias annotations; no fitted scoring/release until validated.

**No BRDB CURRENT, PWA, RaceNote, Newspaper, frozen Blood Review v0.1 or production workflow was modified.**
