# JPDB P0 — accepted BAC × Course Master temporal join audit (2026-11-18)

**Result: P0 Course Master flat-course identity and physical-epoch join PASS for 2023–2025; complete physical history and pre-race as-of evidence remain REVIEW_REQUIRED.**

## Scope and provenance

- Accepted JRDB Warehouse: `jrdb_normalized_warehouse_v1_2010_2025_g20261118_bacfix`.
- Independent BAC/KYI/SED input: exact nine SHA-pinned assets in `config/public_drive/jpdb_p0_current_2023_2025_readonly_v0_1.json`; the 2025 BAC includes the repaired Dec 13/14 rows.
- Phase 3 Course Master source: **existing accepted RRDB Horse Course Fit** [Actions run 38370479179](https://github.com/yukki0113/GPT/actions/runs/38370479179), artifact `rrdb-course-fit-v0-1-38370479179`, ID `11799761734`; original `course_master/course_master_seed_v0_1.jsonl` (177 rows), `course_jrdb_mapping_seed_v0_1.jsonl` (433), `course_geometry_configuration_v0_1.jsonl` (57).
- Read-only DuckDB auditor: `horse-racing/jrdb/tools/jpdb_p0_course_temporal_audit.py`. Uses canonical accepted Parquet, original Phase 3 seed rows and version bounds; no Raw or Warehouse mutation and no parser duplication.
- Successful [Issue #2648](https://github.com/yukki0113/GPT/issues/2648) / [Actions run 44268950772](https://github.com/yukki0113/GPT/actions/runs/44268950772) / [artifact 14411373241](https://github.com/yukki0113/GPT/actions/runs/44268950772/artifacts/14411373241).
- Source commit pinned by runner: `00738c49e406bb8d6215ef2a2487a6917cd42243`.
- Audit JSON inside output artifact: `output/jpdb_p0_course_temporal_2023_2025.json`, byte SHA-256 `1a2ae4820a6497f865607cfafe955fc268f222bd3c2c333419349ec691d5d9c8`. Fallback audit status PASS; 9/9 immutable public Drive fetch receipts validated.
- First [Issue #2647](https://github.com/yukki0113/GPT/issues/2647) / [run 44268542375](https://github.com/yukki0113/GPT/actions/runs/44268542375) returned REVIEW_REQUIRED due to an **audit-join normalization defect**, not missing data: the stored BAC `course_code` empty string for dirt was compared to Phase3 mapping `NULL`. Fixed with `NULLIF(TRIM(b.course_code),'') IS NOT DISTINCT FROM m.course_code`; rerun PASS. No raw records were edited.

## 1. Actual 2023–2025 relation counts

| Year | All BAC races | Flat turf/dirt | Flat Course mapping CONFIRMED | Flat missing course_key | Flat missing geometry_key | Obstacle races |
|---|---:|---:|---:|---:|---:|---:|
| 2023 | 3,456 | 3,329 | 3,329 | 0 | 0 | 127 |
| 2024 | 3,454 | 3,327 | 3,327 | 0 | 0 | 127 |
| 2025 | **3,455** | **3,335** | **3,335** | 0 | 0 | 120 |
| **Total** | **10,365** | **9,991** | **9,991** | **0** | **0** | **374** |

- The row join is **1:1**: 3,456/3,454/3,455 BAC rows before and after mapping in each year, no mapping/geometry fanout.
- Geometry `physical_version_id` vs master `physical_version_id` mismatch = **0** for all 9,991 flat races.
- The 2025 repaired increase includes 51 flat races relative to old BAC flat population; actual full 2025 flat = 3,335. The other 2 of the originally absent 53 races are obstacle races (identified by source surface classification).
- These are actual rows from accepted Parquet, joined against the **same Phase3 seed artifact used by the earlier RRDB study**, not counts inferred from a manifest or from post-race synthetic BAC.

## 2. Obstacle coverage is not a flat gate

| Year | PROVISIONAL obstacle mappings | UNRESOLVED obstacle mappings |
|---|---:|---:|
| 2023 | 125 | 2 |
| 2024 | 122 | 5 |
| 2025 | 115 | 5 |
| **Total** | **362** | **12** |

JPDB's initial flat-only performance analysis does not absorb these 374 obstacle races. Their provisional/unresolved mapping must not be silently converted to CONFIRMED by the stable course-key function.

## 3. Physical epoch and attribute coverage

The Phase3 seed uses `physical_valid_from=2023-01-01` and `physical_valid_to_exclusive=null` for current verified flat geometry. Across the **9,991 flat races**, both the master and geometry physical epoch conditions pass, and the associated physical version identifiers agree.

| Field/category in Phase3 seed | Actual 2023–2025 flat races |
|---|---:|
| Stable course_key resolved | **9,991 / 9,991** |
| Geometry_key resolved | **9,991 / 9,991** |
| Master physical epoch eligible | **9,991 / 9,991** |
| Geometry physical epoch eligible | **9,991 / 9,991** |
| Master final-straight uphill flag non-null | **9,991 / 9,991** |
| Master course-size class non-null | **9,587 / 9,991** |
| Master final-straight length non-null | **7,754 / 9,991** |
| Master `physical_data_status=PARTIAL` | **9,991 / 9,991** |
| Physical version identity conflicts | **0** |

Physical epoch eligibility **does not mean all course attributes are fully known**: master final-straight length remains null for 2,237 flat races, and course size remains null for 404. The exact geometry-specific field may be separately available, but that is **not** a warrant to silently fill master nulls; consumers must define whether to use a geometry-specific field, its validity and its corresponding version.

**Critical schema distinction:** the accepted Phase3 JSONL has `physical_version_id` on the verified geometry seed, but does **not** provide a complete temporal `course_version_id` history as envisaged by `schema/jra_course_profile_master_schema_v0_2.sql`. The 2023+ physical validity epoch is conservative research evidence, not a complete historical course renovation registry. No such ID was fabricated by this audit.

## 4. Rider and as-of cross-check

The course audit read the same KYI/SED partitions and reconfirmed planned-vs-actual jockey-code differences:

| Year | Differences | By SED abnormal code |
|---|---:|---|
| 2023 | 132 | 0:132 |
| 2024 | 280 | 0:278, 2:1, 3:1 |
| 2025 | 319 | 0:318, 3:1 |
| **Total** | **731** | **0:728, 2:1, 3:2** |

This classifies **observed archive differences**, not 731 official rider substitutions. Original last-pre-race PACI/KYI versions and official substitution publication timestamps were not resolved. Formal as-of fail-closed contract: `docs/JPDB_P0_ASOF_RIDER_SOURCE_CONTRACT_20261118.md`.

## 5. P0 gates after this run

- **PASS:** 2023–2025 repaired BAC ↔ KYI ↔ SED structural row join (previous audit).
- **PASS:** 2023–2025 flat BAC ↔ Course Master logical identity, geometry identity and conservative 2023+ physical epoch validity, with no many-to-many join or version conflict.
- **PARTIAL:** Physical attributes are explicitly PARTIAL even where the 2023+ epoch is valid, and complete historical `course_version_id` evidence is absent.
- **OPEN:** Original pre-race KYI/PACI as-of source snapshots, historical availability/late SED revision timeline, official jockey-change event classification, P1 population-filter denominator freeze, and 2026 YTD source coverage.
- **NOT AUTHORIZED:** P1 production implementation, P2 metrics publication and P4 RaceNote integration.

**Overall P0 = REVIEW_REQUIRED.** The full 2023–2025 flat-course identity and 2023+ verified physical epoch joins are accepted as a specific P0 audit gate; they do not release retrospective outcome data for unauthorized use as target-race pre-race features.
