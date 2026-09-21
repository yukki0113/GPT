# RL-T / Training Research Historical Warehouse Migration Work Request — 2026-09-21

## 0. Decision

2010–2025 JRDB Historical の正式標準入力は JRDB Normalized Warehouse v1 とする。

ただし RL-T / Training Research 系は現時点で Historical Raw-direct に依存しており、
Warehouse -> existing Index Base contract の同値 adapter がまだ存在しない。
したがって、Raw 経路を即時削除・置換してはならない。

2026 日次 PACI / SED / Raw direct は変更対象外。
既存 schema、RunPerf、Official RunPerf、Training Edge v0.2 scientific semantics、
calibration、runtime fingerprint、HOLDOUT境界は変更しない。

## 1. Already verified

Analysis historical path is already Warehouse-standard for 2010–2025.

Evidence:
- docs/JRDB_Analysis_Warehouse_Input_Contract_v1.md
- docs/JRDB_Analysis_Warehouse_Dual_Read_Audit_20260921.md
- src/jrdb_analysis_warehouse_adapter.py
- src/audit_jrdb_analysis_raw_vs_warehouse.py

Formal Analysis dual-read PASS dates include 2010, 2018 and 2025 representative dates.
2026 remains PACI + SED / Raw direct.

## 2. Current RL-T / Training Research findings

The following live/re-runnable paths still fetch annual Raw 2010–2025 directly:

- .github/workflows/jrdb_training_edge_v02_daily_issue.yml
- .github/workflows/jrdb_training_edge_v02_replay_issue.yml
- .github/workflows/jrdb_training_edge_v02_runtime_freeze_issue.yml
- .github/workflows/jrdb_training_edge_v02_2026_oot_issue.yml
- .github/workflows/jrdb_training_research_issue.yml

Typical current route:

annual Raw 2010-2025
 -> build_jrdb_index_base_from_raw.py
 -> Index Base SQLite
 -> RunPerf SQLite
 -> Official RunPerf SQLite
 -> Training Edge projection / Training Research

This is not compliant with the new Historical input policy.

Training Research analytical storage itself has already migrated to Parquet ZSTD.
That storage migration does not by itself change the upstream Historical source route.

## 3. Why direct cutover is not safe yet

JRDB Warehouse is lossless normalized parser output with provenance, but Index Base has
consumer-specific selection semantics.

Important cases:
- BAC can contain later correction snapshots.
- CHA and CYB can contain later pre-race correction snapshots.
- ZED/ZKB are rolling snapshots.
- UKC is snapshot/as-of data with duplicate lineage handling.
- Index Base currently applies explicit canonical-date/revision rules.

A Warehouse consumer must reproduce those exact rules before RunPerf or RL-T sees the data.
Changing only file paths is insufficient.

## 4. Required implementation

### 4.1 Add Warehouse -> Index Base compatibility adapter

Add a dedicated module, for example:

- src/jrdb_index_base_warehouse_adapter.py
- src/build_jrdb_index_base_from_warehouse.py

Requirements:

1. Resolve only the accepted dedicated JRDB Warehouse current pointer:
   GPT/horse-racing/10_warehouse/jrdb/v1/current.json
2. Read immutable Parquet with DuckDB.
3. Consume BAC/KYI/SED/UKC and optional CHA/CYB for 2010–2025.
4. Own no fixed-width offsets.
5. Map Warehouse normalized columns to the existing Index Base schema exactly.
6. Use Warehouse source_record_sha256 as the existing Index Base record_hash equivalent.
7. Reproduce Raw builder revision/as-of semantics exactly.
8. Produce the existing jrdb_index_base_schema_v0_1.sql shape unchanged.
9. Record source_generation_id, manifest refs and asset SHA evidence in build metadata.
10. Reject years outside accepted Warehouse coverage.

### 4.2 Preserve current 2026 route

For a 2026 daily run use a hybrid source boundary:

2010–2025:
Warehouse current -> DuckDB -> existing Index Base schema

2026:
PACI + settled SED / Raw direct -> existing Index Base schema

The combined Index Base must be logically identical to the current reference route.
Do not normalize 2026 PACI as part of this migration.

### 4.3 Dual-read equivalence audit

Before any production cutover, compare:

Raw annual 2010–2025 -> Index Base
vs
Warehouse 2010–2025 -> Index Base

Required checks per logical Index Base table:
- schema and column order
- row count
- canonical keys / duplicate count
- all logical values
- NULL / blank profile
- deterministic canonical row hash
- record_hash equivalence
- representative aggregates
- repeated Warehouse-read idempotence

Tables at minimum:
- race_context
- race_result_context
- runner_pre
- runner_previous_link
- runner_result
- workout_main
- training_analysis
- horse_profile_observation

Audit coverage must span multiple years and correction-sensitive dates.
Preferred formal gate is full 2010–2025 table-level equivalence.
If full comparison is operationally too large, first run representative multi-year audit,
then a full canonical hash/count audit before cutover.

Any mismatch -> status FAIL, no cutover.

### 4.4 Scientific non-regression

After Index Base dual-read PASS, execute downstream comparison without changing logic:

- RunPerf
- Official RunPerf
- Training Research
- Stage 1b development
- frozen RL-T runtime fingerprint

Required:
- 2013–2025 eligible fit rows = existing frozen count
- frozen semantic SHA unchanged
- frozen C prediction SHA unchanged
- frozen CAB prediction SHA unchanged
- 2010–2023 development/HOLDOUT boundary unchanged
- 2024–2025 HOLDOUT remains excluded from normal development research
- no market fields introduced

### 4.5 Production workflow cutover

Only after all gates PASS:

Update the current operational paths so their 2010–2025 segment uses Warehouse.

Primary current paths:
- jrdb_training_edge_v02_daily_issue.yml
- jrdb_training_edge_v02_replay_issue.yml
- jrdb_training_research_issue.yml

Historical evidence workflows may either:
- remain immutable as provenance-only archived routes, clearly marked historical, or
- receive plumbing-only Warehouse support if re-run is still operationally required.

Do not rewrite historical evidence claims.

Raw direct must remain available as explicit rollback/audit mode, not standard Historical input.

## 5. Tests

Add tests for:
- Warehouse row -> Index Base mapping
- BAC revision selection
- CHA/CYB canonical delivery selection
- UKC as-of/profile handling
- missing optional CHA/CYB
- Warehouse coverage guard
- 2026 rejection by Historical Warehouse reader
- hybrid 2010–2025 Warehouse + 2026 Raw boundary
- Raw/Warehouse canonical hash equality on fixtures

## 6. Documentation updates after PASS

Update:
- Training_Research_Base_v0_1.md
- Training_Research_Parquet_Operation_v0_1.md
- Training_Edge_v0_2_Daily_Forward_Contract_20260915.md
- Training_Edge_v0_2_Work_Handoff_20260915.md
- JRDB README / operational handoff as applicable

Target source description:

2010–2025:
JRDB Warehouse -> DuckDB reader -> existing Index Base schema -> downstream unchanged

2026:
PACI + SED / Raw direct -> existing Index Base schema -> downstream unchanged

## 7. Acceptance criteria

- [ ] Warehouse->Index Base adapter implemented.
- [ ] 2010–2025 Raw vs Warehouse Index Base equivalence PASS.
- [ ] downstream RunPerf / Official RunPerf non-regression PASS.
- [ ] Training Research development boundary unchanged.
- [ ] frozen RL-T runtime fingerprint unchanged.
- [ ] current daily/replay historical segment switched to Warehouse.
- [ ] 2026 PACI/Raw route unchanged.
- [ ] Raw historical route retained only for rollback/audit.
- [ ] docs updated.
- [ ] formal audit artifact/run/SHA retained.

## 8. Current status

As of 2026-09-21:

HISTORICAL_POLICY = WAREHOUSE_STANDARD
ANALYSIS_CUTOVER = PASS
RL_T_CUTOVER = BLOCKED_PENDING_INDEX_BASE_EQUIVALENCE
TRAINING_RESEARCH_UPSTREAM_CUTOVER = BLOCKED_PENDING_INDEX_BASE_EQUIVALENCE
2026_DAILY_ROUTE = UNCHANGED
RAW_HISTORICAL_ROUTE = RETAIN_FOR_ROLLBACK_AND_AUDIT

No scientific or 2026 daily semantics were changed by this audit.
