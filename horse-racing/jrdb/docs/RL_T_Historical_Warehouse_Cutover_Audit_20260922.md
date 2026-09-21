# RL-T / RaceLift Historical Warehouse Cutover Audit — 2026-09-22

## Decision

2010–2025 JRDB Historical の正式標準入力方針は JRDB Normalized Warehouse v1。

ただし本監査時点では、Index Base の Raw-direct vs Warehouse 実データ完全同値ゲートをまだ PASS として確定していないため、production workflow の切替は行わない。

2026 日次 PACI / SED / Raw direct、既存 Index Base schema、RunPerf / Official RunPerf、Training Edge v0.2 / RL-T scientific semantics、calibration、runtime fingerprint、HOLDOUT境界は変更していない。

## Confirmed source state

Accepted Warehouse:
- generation_id: jrdb_normalized_warehouse_v1_2010_2025_g20260921
- coverage: 2010–2025
- families: BAC/KYI/CHA/CYB/SED/SKB/ZED/ZKB/HJC/UKC
- asset_count: 192
- final audit: PASS
- duplicate_object_count: 0

The generation references immutable staging Parquet objects. The corresponding family staging also retains Raw receipts with annual source Drive IDs / sizes / SHA-256, so a same-origin Raw-vs-Warehouse audit is possible without refetching JRDB upstream.

## Historical path audit

RL-T / Training Research historically rebuilds the Index Base through:
annual Raw -> build_jrdb_index_base_from_raw.py -> Index Base v0.1 -> RunPerf -> Official RunPerf -> Training Research / RL-T.

This route still exists and must not remain the normal 2010–2025 input after cutover.

The Raw builder has consumer-specific selection semantics that must be reproduced:
- BAC later-date correction selection
- CHA/CYB canonical race-date snapshot selection
- non-identical duplicate rejection
- SED fallback race context
- UKC snapshot/as-of observations
- record_hash = SHA-256 of the original Raw record

Therefore direct file-path substitution is not sufficient.

## Implementation added

1. src/jrdb_index_base_warehouse_adapter.py
   - no fixed-width offsets
   - maps normalized Warehouse columns into unchanged Index Base v0.1 rows
   - source_record_sha256 -> existing record_hash
   - reproduces BAC / CHA / CYB correction selection
   - rejects years outside 2010–2025
   - reads immutable Parquet with DuckDB

2. src/build_jrdb_index_base_from_warehouse.py
   - builds the existing jrdb_index_base_schema_v0_1.sql shape
   - records Warehouse generation / asset SHA evidence in metadata
   - Historical-only coverage guard

3. src/audit_jrdb_index_base_raw_vs_warehouse.py
   - builds Raw and Warehouse Index Base independently
   - compares all eight logical tables:
     race_context
     race_result_context
     runner_pre
     runner_previous_link
     runner_result
     workout_main
     training_analysis
     horse_profile_observation
   - checks schema/order, row counts, logical values via deterministic canonical hash,
     NULL/blank semantics, record_hash profile, representative aggregates,
     SQLite integrity and repeated Warehouse-build idempotence
   - FAIL exits non-zero

Implementation commits:
- 0533311a02cc1692bad995ab5b4ed038111f97a5
- 3d36e45528919a9a3203a84513290f9b34ce8a71
- 52d69dafbb1a7878d4da478956569fdab46ff375

## Existing evidence reused

The Analysis subsystem has already completed a separate Raw-vs-Warehouse dual-read PASS for representative 2010/2018/2025 deliveries and is Warehouse-standard for Historical Analysis. That confirms the accepted Warehouse is operationally consumable, but it is not sufficient to waive the Index Base-specific gate because Index Base carries additional fields and correction semantics.

## Current formal gate

HISTORICAL_POLICY = WAREHOUSE_STANDARD
WAREHOUSE_GENERATION = ACCEPTED_PASS
WAREHOUSE_TO_INDEX_BASE_ADAPTER = IMPLEMENTED
INDEX_BASE_DUAL_READ_AUDITOR = IMPLEMENTED
INDEX_BASE_REAL_DATA_EQUIVALENCE = NOT_YET_FORMALLY_PASSED
RL_T_PRODUCTION_CUTOVER = NOT_PERFORMED
TRAINING_RESEARCH_UPSTREAM_CUTOVER = NOT_PERFORMED
2026_DAILY_ROUTE = UNCHANGED
RAW_HISTORICAL_ROUTE = RETAINED_FOR_ROLLBACK_AND_AUDIT

Reason:
The current Chat runtime does not provide a DuckDB/Parquet execution dependency, so the newly implemented formal auditor could not be executed here against the complete 2010–2025 asset set. The accepted Warehouse Parquet and matching Raw receipts were inspected through Drive, and representative object/source identities were confirmed, but that is not treated as equivalent to a full Index Base table-level PASS.

## Cutover rule

Do not switch the current daily/replay/research workflows until the auditor returns PASS on the agreed real-data gate.

On PASS:
- 2010–2025 Historical -> Warehouse -> unchanged Index Base schema
- 2026 -> PACI / SED / Raw direct unchanged
- Raw Historical remains explicit rollback/audit only
- downstream RunPerf / Official RunPerf / Training Research / frozen RL-T fingerprint non-regression must then be checked before final production promotion

On any mismatch:
- no cutover
- preserve Raw route
- record affected table/key/column and resolve before retry

No scientific semantics or 2026 daily semantics were changed by this work.
