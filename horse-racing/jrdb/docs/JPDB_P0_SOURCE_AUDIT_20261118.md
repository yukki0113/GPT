# JockeyProfileDB (JPDB) — P0 Source / Data Audit

- Audit date: 2026-11-18 (JST)
- Initial concept: Library `/🏇/JPDB_INITIAL_CONCEPT_20261118.md`
- Repository: `yukki0113/GPT`, branch `main`
- Inspected baseline commit: `cb3b1ad9add52c8fcbbf0826194a351223b9458a`
- Status: **P0 PARTIAL / REVIEW_REQUIRED** (sample evidence PASS; rolling 3–5-year identity and course-version acceptance NOT YET verified)
- Scope: Read-only source/data inspection; no JPDB implementation, no RaceNote change, no new prediction/consumer approval.

## 確定事項・復旧状況（2026-11-18 最新追記）

- **JPDB対象開始日を2023-01-01に確定**。以下に記録された「過去3〜5年」「3年と5年の比較」「期間未定」は**旧検討段階**の証跡であり、採用方針ではない。2021〜2022年のJPDB常用データ収集・統計集計は行わない。2023以降でもphysical Courseの一部PARTIALは別途管理。
- 2025-12-13/14のBAC欠損53RについてJRDB正規workflowで2日分を再取得し、全72Rを取得できた。2025年間BACの**修復候補**でBAC/KYI/SEDのrace-key 3,455/3,455一致を確認。ただし元19RのRawバイトが改版されており、既存annual Raw、accepted Warehouse、CURRENTは未改変。
- [JPDB_P0_BAC_2025_RECOVERY_20261118.md](JPDB_P0_BAC_2025_RECOVERY_20261118.md) が詳細監査・Source SHA／Run／復旧境界の最新版。**データ復旧候補PASS／正本世代の切替OPEN**。
- JPDB更新頻度は未決定。P1、本番RaceNote連携は未承認。

## P0追加検証への参照（2026-11-18）

本ファイルの実査・OPENゲートは**初回監査時点**の記録です。その後、同日に2021〜2025年のBAC/KYI/SED annual Raw（計15ZIP）と既存Course Profileの実データ照合を実施し、結果を次の文書へ独立して保存しました。

- [JPDB_P0_RECENT_WINDOW_VERIFICATION_20261118.md](JPDB_P0_RECENT_WINDOW_VERIFICATION_20261118.md)
- KYI/SEDの出走キー237,778/237,778整合、騎手コード差異1,062件。
- 3完全年（2023〜2025）と5完全年（2021〜2025）を比較。2025年BACの53レース／735頭欠損、2021〜2022の物理属性のepoch非適合を確認。
- 前走リンクの未解決は主にJRA年間SED外の場コード。履歴窓の端で別途coverageを示す。
- **新しい総合判定：P0現物調査は大幅に前進したが、pre-race provenance・2025 BAC欠損・物理versionと異常コード5が残り、本番受入は未完了。**
- 更新頻度、3年／5年の採用、JPDB本番実装、RaceNote接続は未決定／未承認のまま。

## 0. Scope decision — 2026-11-18 (supersedes broad historical JPDB ingestion assumptions)

**User decision:** JPDB's initial historical data collection/retention scope is limited to roughly **the past 3–5 years**, rather than consuming all 2010–2025 accepted Warehouse history. The rationale is to limit unnecessary accumulation of retired jockey data and prioritize recent, potentially changing riding tendencies. The exact lookback span, calendar-year vs rolling-date cutoff, and statistical windows remain **TBD** pending P0 data/sample-size review. This decision governs JPDB's operational dataset; it does not delete or modify upstream JRDB Raw/Historical Warehouse assets.

- **Historical storage vs target-race eligibility:** Do not keep an unlimited JPDB-wide historical rider fact copy. The prediction target's jockey must be identified from its pre-race entry; inactive/retired riders are not actively ranked when they are not in the target entry set. **Do not purge historical rides solely because the rider subsequently retired**, since that can distort comparison-group denominators, historical as-of replay, or reactivation handling. Define the precise activity/retirement criteria separately, distinguishing missing current rides from formally confirmed retirement.
- **Trends:** A 3-year vs 5-year comparison, temporal decay and shorter-term change indicators are **research candidates**, not fixed modeling assumptions. Show sample counts / uncertainty; do not infer skill from small conditional subgroups.
- **Temporal safety:** For a target race at time T, only use history available before T, then intersect it with the adopted lookback window. The use of current retirement status, later races or future corrected data in past replay is prohibited unless the historical snapshot and knowledge time are independently verified.
- **Refresh frequency = undecided:** Two alternatives remain open: (A) hook an idempotent JPDB update into the existing pre-race Raw acquisition scheduled processing, or (B) run a lower-frequency independent refresh. Distinguish **Raw acquisition cadence** from **JPDB derived-statistics/publication cadence**. No daily/weekly/monthly frequency, workflow coupling, automation or production update is approved here.
- **P0 gate change:** Assess rider IDs, previous rides, sample sufficiency and course joins across the **chosen recent-window cohorts and its moving boundary**, not as an exhaustive 2010–2025 retention requirement. Historical Warehouse remains a reproducible upstream reference for controlled sampling only.

## 1. Existing source contracts checked

1. `.gpt/GITHUB_OPERATION_POLICY.md`, `horse-racing/jrdb/README.md`, `horse-racing/jrdb/.gpt/{CONTEXT,WORKFLOW}.md`: source-of-truth, A read/audit routing, original fixed-length parser ownership, historical as-of separation.
2. `horse-racing/jrdb/src/jrdb_raw.py`: authoritative neutral Reader with 1-based fixed-width fields. Do not reimplement byte offsets inside JPDB.
3. `horse-racing/jrdb/schema/jrdb_canonical_schema_v0_1.sql`: `kyi_entry`, `kyi_previous_link`, `bac_race`, `sed_result`, relevant indexes and `v_pre_race_entry`.
4. `horse-racing/jrdb/src/jrdb_warehouse_normalize.py`, `build_jrdb_normalized_warehouse.py`, `jrdb_racenote_warehouse_reader.py`: historical warehouse flattening, SED↔KYI `(race_key_raw,horse_no)` and previous-result retrieval.
5. `horse-racing/jrdb/schema/jra_course_profile_master_schema_v0_2.sql`, `src/jrdb_course_profile_identity.py`, `docs/JRA_Course_Profile_{Master_Schema,Master_Phase3_Initial_Build,CourseStats}_v0_1.md`: physical course identity, version history, geometry, period-constrained statistics.
6. `horse-racing/brdb/docs/BRDB_CURRENT_READER_CONTRACT_v0_1.md`: immutable generation / manifest / read-only Reader / fail-closed reference pattern, **not** an approved JPDB dependency.
7. `tools/data-storage/README.md`: Parquet/DuckDB query/validation shared tool; no JPDB-specific storage implementation started.

### Field-level contract candidates (observed in main)

| Family | Field(s) | P0 role |
|---|---|---|
| BAC | `race_key_raw`, date, venue, `surface_code`, `turn_code`, `layout_code`, `distance_m`, type/class/grade, `course_code` | Race and physical-course observation |
| KYI | `race_key_raw`, `horse_no`, `blood_registration_no`, `jockey_code`, `trainer_code`, previous result/race links (up to 5), pre-race indexes | **Pre-race entry/rider** and previous-run locator |
| SED/ZED | `race_key_raw`, `horse_no`, `blood_registration_no`, `race_date`, `jockey_code`, `trainer_code`, `finish`, `abnormal_code`, post-race style, final odds/popularity | **Historical race outcomes** only, subject to as-of |
| Course Master | `course_key`, `course_version_id`, temporal `course_jrdb_mapping`, geometry | Physical condition joins, not automatically confirmed by `course_key_from_observation` alone |

`reference_jockey_code` in KYI is **the reference previous jockey** and must not be silently substituted for the most recent actual rider. Use actual previous-result locator + historical SED/ZED `jockey_code` when the link is verified. `SED.race_running_style_code` is post-race and must never become a current-race pre-race feature.

## 2. Live Google Drive evidence

Canonical 2026 folders verified by direct listing:
- PACI folder `1zFajenPU5jxInZCcmqZzkgiaYil3MD8r`.
- SED folder `1mm6sU8-skS7K2XYHm2citcorUVyMyL58`.

Downloaded exact sample:
- `PACI261115.zip`, Drive ID `1wVcoTvNw38nFaPcDWJme-zMsl6MobR3l`, 565,352 bytes, SHA-256 `3c80e70a74a13874a82b7f7cf4c5f9415d6abbf186ec0ccfa1d2842e51a7b050`. Source created 2026-11-14.
- `SED261115.zip`, Drive ID `1gjj4vI8k4qrRozjuvZiHGnfeokomSouA`, 34,232 bytes, SHA-256 `6d32427b5f72689b0c134d826e9de08aaed43267fb1a19bcf0c88365692a54c7`. Source created 2026-11-16.

An audit-only, read-only extraction of current `jrdb_raw.py` field positions was used for the following independent cross-check; **this is not a new JPDB parser**. Scope is **one day only**, not historical population.

### 2026-11-15 sample results

| Check | Observed | Result |
|---|---:|---|
| BAC races | 36 | PASS |
| KYI / SED horse rows | 505 / 505 | PASS |
| Unique race/horse keys (KYI; SED) | 505; 505 | PASS |
| KYI↔SED key matches | 505/505 | PASS |
| Horse IDs match in joined records | 505/505 | PASS |
| Jockey codes match KYI vs SED | 505/505 | PASS |
| Trainer codes match KYI vs SED | 505/505 | PASS |
| Blank/00000 jockey codes | 0/0 | PASS |
| Distinct jockey codes | 108 | Observed; not a longitudinal master |
| KYI↔BAC race join | 505/505 | PASS |
| SED abnormal code | `0`: 504, `1`: 1 | Requires explicit outcome denominator policy |
| Flat / obstacle split | 34 races / 2 races; 484 / 21 horses | JPDB initial scope should exclude obstacles from flat metrics |
| ZED historical rows in pre-race PACI | 1,984 | Available at pre-race source timestamp |
| KYI first-previous result keys populated | 437/505 | Remaining 68 not classified as debut without additional checks |
| First-previous ZED result-key matches | 437/437 | PASS for sample |
| Previous-result horse ID matches | 437/437 | PASS |
| Previous-result date before 2026-11-15 | 437/437 | PASS; dates 2025-12-27 to 2026-11-10 |
| Rider code same / different vs previous ZED | 138 / 299 | **Candidate continuity/change**, not final official rider-change labels |

`kyi_previous_link` + ZED is a plausible existing path for a pre-race riding continuity feature. Actual `reference_jockey_code`, mid-history corrections, multi-start/owner selection and disqualification semantics still require policy review.

### Historical Warehouse (2010–2025)

- `docs/JRDB_Normalized_Warehouse_Operation_v1.md` records accepted generation `jrdb_normalized_warehouse_v1_2010_2025_g20260921`, status PASS, 10 families, 192 referenced assets.
- 2025 BAC/KYI/SED immutable objects were resolved via `config/warehouse_drive_index_{bac,kyi,sed_a}_v1.json` and downloaded from canonical Drive locations. Drive object sizes match indexed metadata (169,370; 5,914,994; 3,612,532 bytes). All three have `PAR1` header/trailer.
- **Not independently row-queried:** local runtime lacks DuckDB and PyArrow, and one dependency-repair attempt failed due to network resolution. `tools/data-storage/` is the required execution path; do not substitute an ad hoc Parquet engine.
- The 2010–2025 Warehouse remains an upstream source and optional reference; JPDB initial ingestion is **not** a full-period copy. Jockey-code stability, missingness, pre-race/result agreement, duplicate rates, and course joins in JPDB's chosen rolling window are **NOT measured by this audit**. An earlier accepted warehouse status does not itself prove those JPDB-specific contracts.

## 3. Course Profile limits

- Design uses `course_key = venue_code × surface_code × distance_m × layout_variant`; historical changes are separately `course_version_id` and `valid_from <= race_date < valid_to_exclusive`.
- Phase 3 documents provisional/unresolved geometry and pre-renovation limits; `course_code` A/B/C/D is not a stable physical identity component.
- Existing RRDB Horse Course Fit 2026-10-13 report bundle was examined as **separate downstream evidence**, not a JPDB acceptance test: `course_master_validation.json` shows 177 master rows, 57 geometry rows, PASS and physical valid-from values of 2023-01-01. Its ledger `audit.json` reports `flat_unresolved=0` in its own processed cohort.
- No join against a JPDB candidate `course_master` generation was executed for the 2026-11-15 entries; **JPDB course_key/version/geometry join rates remain UNKNOWN**. Do not assert 2010–2022 physical-version coverage from a current-course snapshot.

## 4. Time safety and statistics risks

- Current-race features: only pre-race KYI/BAC/PACI and eligible historical records available before the target timestamp. Never include target SED finishing, final odds, payouts, post-race running style or later current-period aggregates.
- Prior-start `ZED` in the sampled PACI was demonstrably older than the target race date, but historical reconstruction also requires dataset delivery-time/version provenance and explicit `as_of_exclusive`.
- Rider identity: source five-character `jockey_code` is the leading candidate; name text is never an identity join. Renaming, historical aliases, retirement/reassignment and code reuse have not been audited.
- Simple rider win rate is confounded by horse quality, trainer, grade, track, and selection of mounts. Difference from a pre-race expectation and time-block holdout belong to P3, not a premature P0 score.
- Final odds/popularity from a historical SED may describe a **past completed** race, but never the target or a later race. The expectation model itself may already contain jockey effects.

## 5. P0 acceptance gates

| Gate | Status | Remaining work |
|---|---|---|
| Existing contracts located and scoped | PASS | Use latest main before P1 |
| Real 2026 PACI/SED source reachable | PASS | Preserve downloaded source SHA/identity |
| One-day entry/result rider and race identity | PASS (2026-11-15 only) | Replicate across seasons, venues, anomaly dates |
| One-day first-previous rider resolution | PASS (437/437) | Formalize NULL/debut/continuity semantics |
| Stable jockey identity across the selected recent window | **OPEN** | Check 3–5-year KYI/SED cohorts for code/name changes/reuse, including moving-window boundaries |
| Cancellation/abnormal event denominator | **OPEN** | Official code book + representative abnormal cohorts |
| Historical rider+horse+course join rate | **OPEN** | Validate non-missing/version-aligned mappings per time band |
| As-of snapshot/version provenance | **OPEN** | Confirm pre-day storage history and replay boundaries |
| JPDB statistics/API/storage schema | **NOT FROZEN** | Only after remaining P0 evidence |
| RaceNote/BRDB integration | **NOT AUTHORIZED** | P4 research only |

**P0 disposition:** Evidence supports feasibility and reuse, but **P0 is not fully accepted**. P1 implementation is on hold pending the OPEN gates. No JPDB code was authored.

## 6. Next strictly scoped P0 completion work

1. Run approved `tools/data-storage/` DuckDB checks over accepted BAC/KYI/SED **within the provisional rolling 3–5-year scope**, with reproducible recent-year and boundary cohorts (e.g., 2022–2026 where covered), plus code NULL/zero/alias drift, key uniqueness, KYI↔SED rider mismatches and previous-result coverage. Do not impose a full 2010–2025 JPDB load. Ensure data transport matches repository policy.
2. Reuse existing Course Profile Master and mapping assets; test `course_key` and **version-valid** joins by time period **inside the selected recent window**, including any pre-2023/renovation records actually included. Report denominator/exclusions; older history outside scope is not a P0 completion requirement.
3. Read official JRDB abnormal/cancel code definitions; decide which races/entries contribute to starts vs result rates, without changing source records.
4. Freeze a P0 evidence manifest with exact `main` commit, source manifests/generations, downloaded SHA, date/window, predicate definitions and query versions; decide P0 pass/review only from those tests.
5. Only after P0 acceptance: propose P1 storage schema and Reader API. Avoid creating production `horse-racing/jpdb/` code until contract and location are approved.

## 7. Guardrails

- No new persistent SQLite/DuckDB store; use common data-storage tooling.
- No custom fixed-width parser, no name-based jockey fallback, no service-account or authenticated Drive Actions transport.
- No implied causal rider skill from raw win rates.
- No changes to RaceNote marks, Confidence, T1–T7, newspaper or production consumer.
