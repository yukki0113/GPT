# JPDB P0 — accepted CURRENT 2023–2025 row-level BAC/KYI/SED audit (2026-11-18)

## Outcome and scope

**Row-level structural join audit PASS**, for the 9 immutable Parquet objects in accepted Warehouse generation `jrdb_normalized_warehouse_v1_2010_2025_g20261118_bacfix`, years **2023–2025 only**. This result is a **P0 partial gate PASS**, not P0 overall acceptance. It does not establish pre-race historical as-of availability, 2026 YTD completeness, Course Profile geometry applicability, or final rider-change semantics.

- Approved input manifest: `horse-racing/jrdb/config/public_drive/jpdb_p0_current_2023_2025_readonly_v0_1.json`; exactly 9 immutable assets with Drive ID, exact expected filename, byte size and SHA-256.
- Read-only auditor: `horse-racing/jrdb/tools/jpdb_p0_current_join_audit.py`. Uses **DuckDB** (no second Parquet engine or custom JRDB parser); checks 3 annual BAC/KYI/SED partitions from the **accepted 2026-11-18 CURRENT**. The 2025 BAC is the repaired **3,455-row** object `b26a364978143fbd6e9d30289db0eb85e9b33e9fe612759b23a85ffbb78a3bb9`, *not* the retired 3,402-row object.
- Successful [Issue #2646](https://github.com/yukki0113/GPT/issues/2646) / [Actions run 44266451396](https://github.com/yukki0113/GPT/actions/runs/44266451396) / [result artifact 14410462135](https://github.com/yukki0113/GPT/actions/runs/44266451396/artifacts/14410462135).
- Repro source commit: `e53eda985385acb0a2142a26c0718ec929ef6d95`. Runner outcome **PASS**; DuckDB `1.1.3`, PyArrow `25.0.1`; **9/9** public Drive integrity receipts verified.
- Durable output filename within artifact: `output/jpdb_p0_current_join_2023_2025.json`; JSON byte SHA-256: `5117ed27eb3fb8e696896b2df90874f20006d5847a2cbe831bb0f1fa9f57a5d2` (14,707 bytes).
- Initial [Issue #2645](https://github.com/yukki0113/GPT/issues/2645) / [run 44266196725](https://github.com/yukki0113/GPT/actions/runs/44266196725) **failed before download** because manifest destinations did not retain the Drive object filename; issue closed. The manifest's destinations and auditor's local paths were fixed and verified in #2646. Failed first run is not source-data failure.

## 1. Independently queried rows

| Year | BAC races | KYI entries | SED results | KYI–SED left / right missing | KYI/SED race absent in BAC | BAC race absent in KYI |
|---|---:|---:|---:|---:|---:|---:|
| 2023 | 3,456 | 47,672 | 47,672 | 0 / 0 | 0 / 0 | 0 |
| 2024 | 3,454 | 47,181 | 47,181 | 0 / 0 | 0 / 0 | 0 |
| 2025 | **3,455** | 47,884 | 47,884 | 0 / 0 | 0 / 0 | 0 |
| **Total** | **10,365** | **142,737** | **142,737** | **0 / 0** | **0 / 0** | **0** |

- Unique key checks: **0 duplicate** BAC `race_key_raw`; **0 duplicate** KYI/SED `(race_key_raw,horse_no)` for each year. **0 NULL or blank canonical keys** in these three relations.
- Matched `blood_registration_no` mismatches: **0**. Blank/zero jockey codes in KYI/SED: **0**.
- 2025 repaired BAC day coverage: `2025-12-13` = **36R** and `2025-12-14` = **36R** (actual BAC `race_date` field).
- These are **real Parquet SQL counts**, not solely the manifest's declared row counts. Download/receipt SHA validation precedes SQL.

## 2. Planned vs actual jockey identity — differences are not automatically errors

| Year | KYI vs SED `jockey_code` mismatch | By SED `abnormal_code` |
|---|---:|---|
| 2023 | **132** | `0`: 132 |
| 2024 | **280** | `0`: 278, `2`: 1, `3`: 1 |
| 2025 | **319** | `0`: 318, `3`: 1 |
| **Total** | **731** | `0`: 728, `2`: 1, `3`: 2 |

The mismatch is *evidence of KYI pre-race planned vs SED post-race actual codes*, not a demonstrated integrity error. It cannot by itself establish the final pre-race rider, official substitution status, or time-available provenance. JPDB must retain **both codes** and use SED actual for retrospective completed-race rider facts, KYI snapshot code only for historical pre-race entries whose delivery timing is independently validated.

The full artifact contains up to 20 mismatch key/code samples per year for follow-up; do not replace these samples with guessed jockey names.

## 3. SED abnormal codes — observed physical records

| Code | 2023 | 2024 | 2025 | Total |
|---|---:|---:|---:|---:|
| `0` normal | 47,273 | 46,752 | 47,497 | **141,522** |
| `1` 取消 | 78 | 85 | 58 | **221** |
| `2` 除外 | 101 | 102 | 111 | **314** |
| `3` 中止 | 219 | 242 | 218 | **679** |
| `5` 降着 (JRDB master code table) | 1 | 0 | 0 | **1** |

Total = 142,737. Code 5 appears in **2023** in the JPDB-adopted cohort, rather than the previously broader 2021–2025 total of two occurrences. Code definitions are referenced from `docs/reference/JRDB_Master_Code_Definition.md` section `□異常区分`, while field-specific applicability and final percentage denominators remain open. Do not silently treat codes 3/5 as normal completed results.

## 4. Remaining P0 gates

- **Course Master:** No new version-effective mapping/geometry join performed by this auditor. Run time-valid `course_key`/`course_version_id` joins on repaired BAC 2023–2025 and report CONFIRMED/PROVISIONAL/UNRESOLVED by source year and physical-data status. Never infer geometry completeness from BAC→KYI coverage.
- **As-of correctness:** Annual Warehouse encodes historical finalized results, not proof of an original pre-race snapshot. Design/verify event time, availability time, historical PACI snapshots, and late-finalized SED watermarks, then reject future knowledge for historical target date T.
- **Rider changes:** Classify the 731 mismatches with official change evidence, last-available pre-race KYI version, cancelled/withdrawn entries, and missingness. Avoid name joins.
- **Previous rides and P1 denominators:** Distinguish outside-window/non-JRA/unavailable/broken previous result links; formalize `population_filter_id` and abnormal codes 3/4/5/6 before production.
- **2026 YTD:** This Warehouse CURRENT ends in 2025; integrate only via the existing PACI/SED canonical source with verified version/coverage.

**Disposition: JPDB P0 = REVIEW_REQUIRED**, with the repaired 2023–2025 core BAC/KYI/SED join integrity gate now **PASS**. P1 implementation and P4 RaceNote production connection remain on hold.
