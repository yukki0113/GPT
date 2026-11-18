# JPDB P0 — accepted CURRENT reconciliation and abnormal-code definition review (2026-11-18)

- Scope: **P0 read/audit only**; no JPDB production implementation, no historical source mutation, no RaceNote connection.
- Repository: `yukki0113/GPT` `main` inspected at `97e2b754f5662ab3ae1dc34665879ed8795584ae`.
- User-approved JPDB history start: **2023-01-01**; 2021–2022 comparison in the previous report is historical evidence, not the operational JPDB window.
- Audit scope this turn: live canonical Drive CURRENT/manifest/audit, **manifest metadata only** for 2023–2025 BAC/KYI/SED, and the repository official master-code transcription. **No new row-level Parquet joins were executed**; row counts below are *declared manifest row counts*, not independently re-counted data rows. In a separate byte-integrity check, the accepted 2025 BAC Parquet object was downloaded from its canonical Drive ID and SHA-verified.

## 1. Live canonical identity / integrity checks

Read via the connected Google Drive connector (no service account), then verified local JSON bytes and canonical-semantic SHA-256:

| Canonical object | Drive file ID | Verification |
|---|---|---|
| `GPT/horse-racing/10_warehouse/jrdb/v1/current.json` | `1uB0IQecWNKNn_ASZx4_0MhlWNXUmFrYA` | 627 bytes; raw SHA-256 `12dc312ce0f5ecb2aabfdda3abe77793941e430ad308f4aecaedaa3e7a816a35`; `status=accepted` |
| New generation `manifest.json` | `1dAqJf4qie3y3LEX_cfU8uxOzI7kj2AXq` | canonical JSON semantic SHA-256 `174eaf459f56eb1afe55bc157a2dcf0226a212bf6c00ba062ce5a3e641b2a269`; matches CURRENT |
| New generation `audit.json` | `1P1AteKFYE5N2ykrESHMb4Jm9M6ESBNsw` | canonical JSON semantic SHA-256 `a94d0a4ab45b2b861c0de47c624ff7cb773b0ef354db933688960d0cee4282c9`; matches CURRENT |

The canonical semantic hash is `SHA256(UTF8(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(',', ':'))))` (not the formatted JSON file's raw byte SHA). Both documents consistently bind `generation_id=jrdb_normalized_warehouse_v1_2010_2025_g20261118_bacfix`. Accepted audit declares 10 families, 192 assets, 0 duplicate objects and successor patch PASS. The predecessor generation is retained, **not** the current data source.

## 2. Declared 2023–2025 source partitions

These values come from the *live accepted manifest*, not from the older annual Raw audit or a fresh Parquet scan.

| Family | 2023 | 2024 | 2025 | Sum |
|---|---:|---:|---:|---:|
| BAC race rows | 3,456 | 3,454 | **3,455** | **10,365** |
| KYI entry rows | 47,672 | 47,181 | 47,884 | **142,737** |
| SED result rows | 47,672 | 47,181 | 47,884 | **142,737** |

- Each of the three 2023–2025 cohorts has a stable family-specific schema hash. BAC: `4adf70bd4114bfaace40872fc46704c5fa9f6f259dd943ce3dcf98a66e44ff90`; KYI: `3078ad6a032ffad839bfb6aa9763f589b4f626ac2d11d054699fa87b35d9c89a`; SED: `17e775fb8ae8387725d8d57ac645502a35500c4d52b8cd064002057282e948c2`.
- The 2025 BAC object was **independently downloaded from Drive file ID `1nvDnqBnv69KdMgH200lqOEg6E2VTNtpX`**: 171,165 bytes, `PAR1` magic at header/trailer, byte SHA-256 **`b26a364978143fbd6e9d30289db0eb85e9b33e9fe612759b23a85ffbb78a3bb9` = manifest**. This validates transport/immutable object bytes, **not** 3,455 independently queried rows, and is not the predecessor's 3,402-row object.
- The existing recent-window Raw audit found KYI↔SED identity integrity across 2021–2025, but the **new 2025 BAC Parquet ↔ KYI/SED ↔ Course mapping complete row-level join is not yet repeated here**. Do not interpret matching total counts as proof of complete key equality.
- 2026 year-to-date is not part of the 2010–2025 Historical Warehouse. JPDB's 2023+ scope must explicitly bind 2026 PACI/SED snapshots through the existing current-year route; 2023–2025 manifest-only checks do not establish 2026 completeness or historical pre-race availability.

## 3. Source-contract conflict discovered: SED abnormal code `5`

The previous audit `JPDB_P0_RECENT_WINDOW_VERIFICATION_20261118.md` calls observed `5` (2 rows in 2021–2025) undefined in the examined `Sed__sedsiyo_doc` reference. However the repository's sourced official master-code transcription `horse-racing/jrdb/docs/reference/JRDB_Master_Code_Definition.md`, section `□異常区分`, **explicitly defines `5=降着` and `6=再騎乗`** (also `0=異常なし,1=取消,2=除外,3=中止,4=失格`).

Disposition:
- **Code label resolution = FOUND IN THE MASTER CODE REFERENCE**, not a novel or unknown code. This supersedes the previous claim of *no known master-code definition*, but does **not** retroactively alter that source document's narrower observed table.
- **Field-applicability and denominator semantics = REVIEW_REQUIRED**: corroborate that the relevant SED field uses the same master-code version and inspect the two records (year, key, finish/order and any revised result). Do not automatically classify them as normal finishes or remove them from statistical denominators.
- Working audit statuses: `0=NORMAL_FINISH`; `1/2=NON_START`; `3=STARTED_NOT_FINISHED`; `4/5/6=SPECIAL_REVIEW`. **These are tentative P0 audit categories, not frozen P1/P2 population filters.** Preserve raw `abnormal_code` and distinguish participation, win and place-rate eligibility before P1.
- If final code interpretation changes the statistical base, version a `population_filter_id` and rerun affected cohort metrics; do not overwrite earlier accepted source data.

## 4. Remaining P0 acceptance gates and concrete execution checks

| Gate | Status after this check | Required evidence |
|---|---|---|
| Canonical Warehouse CURRENT source binding / JSON hashes | **PASS** | Live Drive fetch, semantic SHA, generation and file IDs above |
| 2023–2025 cohort presence and manifest row/schema totals | **PASS (metadata only)** | Entries above; independent Parquet record scan still open |
| BAC repair distribution to CURRENT | **PASS (manifest + physical object byte SHA)** | 2025 BAC Parquet downloaded and exact SHA-verified; relation-key/row-level query still open |
| SED abnormal code `5` label | **FOUND (master-code reference)** | Confirm field/version applicability and inspect both affected record keys |
| KYI scheduled rider vs SED actual rider | **PARTIAL** | Classify 2023+ mismatches; verify historical last-pre-race source/late rider changes rather than equating all differences to substitutions |
| Previous-race historical resolution | **PARTIAL** | Distinguish OUTSIDE_WINDOW, NON_JRA, NO_LINK, NOT_YET_AVAILABLE, BROKEN_LINK and preserve as-of exclusivity |
| 2023+ Course mapping and physical version | **PARTIAL** | New repaired BAC race-key join by date; report CONFIRMED/PROVISIONAL/UNRESOLVED; exclude PARTIAL geometry from unqualified physical-performance claims |
| As-of pre-race snapshot and late finalized SED | **OPEN** | Record event time, acquisition/knowledge time, snapshot version, eligible-before-target predicate and late-correction watermark |
| 2026 YTD | **OPEN** | Approved 2026 PACI/SED canonical sources, date coverage, version/availability checks |
| P1 schema, P2 statistics, P4 RaceNote production connection | **NOT AUTHORIZED / NOT STARTED** | P0 gate decision and subsequent approval |

Next execution should reuse `tools/data-storage/` DuckDB/Parquet Reader and Warehouse manifest materialization, not a new parser or bespoke data engine. At minimum independently verify the 2023–2025 `bac/kyi/sed` accepted-object SHA, race key sets, `(race_key_raw,horse_no)` uniqueness, differences in scheduled-vs-actual rider codes, raw abnormal-code distribution, Course Master time-effective joins, and missing/NULL rates. Capture query text, exact population predicates and file SHAs; any unresolved joins must fail closed.

**P0 overall: REVIEW_REQUIRED.** This document records a narrower *successful source binding check* and a newly identified definition discrepancy. It does not represent row-level re-audit, retrospective availability proof, P1 launch, or RaceNote acceptance.
