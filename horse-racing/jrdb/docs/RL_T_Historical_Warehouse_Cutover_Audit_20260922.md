# RL-T / RaceLift Historical Warehouse Cutover Audit — updated 2026-09-25

## Decision

2010–2025 JRDB Historical の正式標準入力方針は JRDB Normalized Warehouse v1。

accepted generation は `jrdb_normalized_warehouse_v1_2010_2025_g20260921` のまま変更しない。

2026 日次 PACI / SED / Raw direct、既存 Index Base schema、RunPerf / Official RunPerf、
Training Edge v0.2 / RL-T scientific semantics、calibration、runtime fingerprint、
HOLDOUT 境界は変更しない。

production workflow の Historical 入力切替は、2010–2025 全期間 Index Base dual-read
および downstream non-regression が PASS した後にのみ行う。

## Confirmed Warehouse state

- generation_id: `jrdb_normalized_warehouse_v1_2010_2025_g20260921`
- coverage: 2010–2025
- families: BAC/KYI/CHA/CYB/SED/SKB/ZED/ZKB/HJC/UKC
- asset_count: 192
- final audit: PASS
- duplicate_object_count: 0

Formal retry r5/r6 では、JRDB upstream から原本 Raw を再取得し、
各 family を original source commit / created_at で再生成した結果、
accepted manifest に対して SHA-256 / size / row_count / schema_hash /
canonical_key / relative_path が byte-identical であることを確認した。

したがって accepted Warehouse 自体の欠損・破損・重複は原因ではない。

## Historical Index Base path

Legacy route:

```text
annual Raw
  -> build_jrdb_index_base_from_raw.py
  -> Index Base v0.1
  -> RunPerf
  -> Official RunPerf
  -> Training Research / RL-T
```

Warehouse route:

```text
accepted Historical Warehouse
  -> jrdb_index_base_warehouse_adapter.py
  -> unchanged Index Base v0.1
  -> unchanged downstream scientific chain
```

Raw route は cutover 後も rollback / audit 用として保持する。

## Formal mismatch diagnosis

Initial full dual-read audit returned FAIL for six tables:

- race_context
- runner_pre
- runner_result
- workout_main
- training_analysis
- horse_profile_observation

The following two tables already passed:

- race_result_context
- runner_previous_link

Column-level diagnostics proved that, for every failing table:

- primary/canonical keys matched
- row counts matched
- schema matched
- NULL/blank semantics matched
- representative aggregates matched
- all logical columns matched
- the only differing column was `record_hash`

### Root cause

Legacy Raw Index Base uses:

```python
zf.read(member).splitlines()
sha256(record_body)
```

Therefore CR/LF is removed before the legacy `record_hash` is calculated.

Normalized Warehouse uses Common Raw Reader fixed blocks and records
`source_record_sha256` for the record exactly as ingested. When the published
fixed length includes CR/LF, that hash includes those bytes.

Thus the mismatch was provenance representation only, not a logical-data mismatch.

## Compatibility implementation

A generation-bound compatibility sidecar was added:

`src/build_jrdb_index_base_record_hash_compat.py`

It stores:

- year
- source_member
- source_record_ordinal
- legacy_record_hash = SHA-256(record body after splitlines)

Warehouse adapter accepts the sidecar and uses `legacy_record_hash` only when
projecting the unchanged Index Base `record_hash` field.

The normalized Warehouse Parquet itself is not modified.

Relevant implementation:

- `src/jrdb_index_base_warehouse_adapter.py`
- `src/build_jrdb_index_base_from_warehouse.py`
- `src/audit_jrdb_index_base_raw_vs_warehouse.py`
- `src/build_jrdb_index_base_record_hash_compat.py`

The auditor also emits column-level mismatch counts and samples.

## Representative real-data PASS

Issue #1270 / Actions run `35956420745`:

- years: 2010 / 2018 / 2025
- Warehouse rebuild equivalence: PASS
- Raw vs Warehouse Index Base: PASS
- SQLite integrity: PASS
- repeat Warehouse build idempotence: PASS
- audit exit code: 0

All eight Index Base tables passed.

Representative row counts:

- race_context: 10,363
- race_result_context: 10,363
- runner_pre: 146,607
- runner_previous_link: 733,035
- runner_result: 146,607
- workout_main: 146,607
- training_analysis: 146,607
- horse_profile_observation: 145,942

## Full 2010–2025 gate

Formal full-period audit is running under:

- Issue #1280
- workflow: `rlt_historical_warehouse_audit_issue.yml`
- run: `36042308232`

The workflow:

1. validates accepted final manifest/audit
2. refetches original annual JRDB Raw
3. builds legacy record-hash compatibility sidecar
4. rebuilds Warehouse using frozen original semantics
5. verifies rebuilt Warehouse is byte-identical to accepted assets
6. runs full 2010–2025 Raw vs Warehouse Index Base dual-read

No production cutover is authorized until this run returns PASS.

## Downstream non-regression gate

The downstream comparison path has been implemented in advance:

- `src/run_rl_t_warehouse_downstream_nonregression.py`
- `src/audit_rl_t_warehouse_downstream_nonregression.py`
- `.github/workflows/rlt_historical_warehouse_downstream_issue.yml`

It independently builds Raw-route and Warehouse-route:

1. Index Base 2010–2025
2. RunPerf EXPANDING
3. Official RunPerf
4. Training Research
5. Training Stage1b
6. Training Edge v0.2 frozen runtime fingerprint

Then it compares scientific relations and frozen fingerprint fields.

`Training Research.source_archive` is intentionally excluded from scientific
equality because Raw and Warehouse are different provenance media by design.
`training_runner`, including its combined source record hash, remains part of
the strict non-regression comparison.

The Warehouse fingerprint is also validated against the frozen expected
`training_edge_v0_2_runtime_fingerprint.json`.

## Current formal gate

```text
HISTORICAL_POLICY                     = WAREHOUSE_STANDARD
WAREHOUSE_GENERATION                  = ACCEPTED_PASS
WAREHOUSE_REBUILD_EQUIVALENCE         = PASS
WAREHOUSE_TO_INDEX_BASE_ADAPTER       = IMPLEMENTED
LEGACY_RECORD_HASH_COMPATIBILITY      = IMPLEMENTED
REPRESENTATIVE_INDEX_BASE_EQUIVALENCE = PASS
FULL_2010_2025_INDEX_BASE_EQUIVALENCE = RUNNING
DOWNSTREAM_NONREGRESSION              = READY_NOT_RUN
RL_T_PRODUCTION_CUTOVER               = NOT_PERFORMED
TRAINING_RESEARCH_UPSTREAM_CUTOVER    = NOT_PERFORMED
2026_DAILY_ROUTE                      = UNCHANGED
RAW_HISTORICAL_ROUTE                  = ROLLBACK_AUDIT_ONLY_AFTER_CUTOVER
```

## Cutover rule

On full Index Base PASS:

- run downstream non-regression
- require unchanged eligible fit population
- require unchanged Training Research semantics
- require unchanged Stage1b outputs
- require unchanged frozen C / CAB prediction fingerprints
- retain 2024–2025 HOLDOUT exclusion and all market-field exclusions

Only after all of those gates PASS:

- 2010–2025 Historical -> Warehouse -> unchanged Index Base schema
- 2026 -> PACI / SED / Raw direct unchanged
- Historical Raw -> rollback/audit only

On any mismatch:

- no cutover
- preserve Raw route
- record affected table/key/column
- resolve and rerun the failed gate

No RL-T scientific semantics or 2026 daily semantics are changed by this migration.
