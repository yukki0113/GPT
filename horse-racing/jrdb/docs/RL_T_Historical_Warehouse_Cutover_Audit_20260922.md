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

Formal full-period audit completed PASS under:

- Issue #1280
- workflow: `rlt_historical_warehouse_audit_issue.yml`
- run: `36042308232`
- audit exit code: 0
- Warehouse rebuild equivalence: PASS
- Raw vs Warehouse Index Base: all 8 tables PASS
- SQLite integrity: raw / warehouse / warehouse_repeat all `ok`

Full-period row counts:

- race_context: 55,268
- race_result_context: 55,268
- runner_pre: 781,161
- runner_previous_link: 3,905,805
- runner_result: 781,161
- workout_main: 781,161
- training_analysis: 781,161
- horse_profile_observation: 780,835

This closes the Historical Index Base equivalence gate. Production cutover still waits for the downstream non-regression gate.

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
FULL_2010_2025_INDEX_BASE_EQUIVALENCE = PASS
DOWNSTREAM_NONREGRESSION              = RUNNING
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


## Downstream execution status — 2026-09-25

The formal downstream non-regression gate is now running:

- Issue #1294
- workflow: `rlt_historical_warehouse_downstream_issue.yml`
- run: `36046318450`

It will revalidate the accepted Warehouse and full Index Base equivalence before comparing
RunPerf / Official RunPerf / Training Research / Stage1b / frozen RL-T v0.2 fingerprint.

No production cutover has been performed yet.


## Direct Warehouse materialization — PASS

The production-oriented Historical materializer no longer depends on recursive
`gdown --folder`.

Implementation:

- `src/materialize_jrdb_warehouse_from_object_index.py`
- frozen per-family Drive object indexes under `horse-racing/jrdb/config/`
- accepted final manifest remains the authority for relative path / SHA-256 / size
- Drive object indexes only supply immutable candidate file IDs

Formal smoke:

- Issue #1301
- run `36086217055`
- generation: `jrdb_normalized_warehouse_v1_2010_2025_g20260921`
- selected families: BAC/KYI/CHA/CYB/SED/UKC
- expected assets: 96
- materialized assets: 96
- every object verified against accepted manifest SHA-256 and size
- result: PASS

This closes the recursive-folder transport blocker for normal Historical
Warehouse consumption.

## Remaining cutover gates — 2026-09-25

1. Downstream scientific non-regression
   - Issue #1297
   - run `36085137368`
   - status: RUNNING
   - compares RunPerf / Official RunPerf / Training Research / Stage1b /
     projected `training_edge_input` / frozen RL-T v0.2 fingerprint.

2. Legacy record-hash compatibility package persistence
   - Issue #1300
   - run `36086214247`
   - status: RUNNING
   - canonical Drive destination:
     `record_hash_compat_v1_2010_2025`
     under the accepted generation folder.
   - after persistence, normal operation must not refetch Historical Raw merely
     to reconstruct legacy `record_hash`.

3. Historical Warehouse + current 2026 Raw hybrid equivalence
   - Issue #1302
   - run `36086427809`
   - fixed replay boundary: target 2026-09-20, settled results through 2026-09-19
   - legacy side: Raw 2010-2026
   - candidate side: Warehouse 2010-2025 + unchanged Raw/PACI/SED 2026
   - all eight Index Base relations must match exactly.

Production workflow files remain unchanged until these gates pass.


## Canonical legacy record-hash compatibility persistence — PASS

The legacy Index Base `record_hash` compatibility layer is now persisted so
normal Historical operation does not need to refetch 2010–2025 Raw merely to
reconstruct provenance hashes.

Canonical export:
- Issue #1300
- run `36086214247`
- source Warehouse generation:
  `jrdb_normalized_warehouse_v1_2010_2025_g20260921`
- families: BAC/KYI/SED/UKC/CHA/CYB
- status: PASS

Frozen canonical manifest:
- `config/jrdb_index_base_record_hash_compat_v1.json`

Drive package set:
- folder ID: `1fQF6uyAhJ7TDNRwfhb54Kt--j0q_Qj40`
- `bac.parquet.zip`
- `kyi.parquet.zip`
- `sed.parquet.zip`
- `ukc.parquet.zip`
- `cha.parquet.zip`
- `cyb.parquet.zip`
- `manifest.json.zip`

The original combined GitHub artifact exceeded the Drive connector's 100 MiB
transfer boundary, so the already-verified artifact was split without
recomputing source data:
- Issue #1303
- run `36087009991`
- each family artifact was verified against the frozen canonical manifest
  before upload.

Frozen Drive package mapping:
- `config/jrdb_index_base_record_hash_compat_drive_set_v1.json`

Production materializer:
- `src/materialize_jrdb_index_base_record_hash_compat_set.py`

Direct Drive reconstruction smoke:
- Issue #1304
- run `36087310475`
- six family packages downloaded directly from Drive
- package SHA-256 verified
- extracted Parquet SHA-256 verified against canonical manifest
- six-family coverage verified
- result: PASS

Therefore normal operation can materialize both accepted Historical Warehouse
data and legacy Index Base hash compatibility without Historical Raw.

Shared normal-operation preparer:
- `src/prepare_rl_t_historical_warehouse_inputs.py`
- materializes accepted Warehouse plus canonical compatibility sidecars
- reports `historical_raw_required=false`
## Production workflow final cutover — 2026-09-26

The remaining production plumbing cutover has now been performed.

Changed workflows:
- `.github/workflows/jrdb_training_edge_v02_daily_issue.yml`
- `.github/workflows/jrdb_training_edge_v02_replay_issue.yml`
- `.github/workflows/jrdb_training_research_issue.yml`

Normal Historical source in all three is now the accepted Warehouse generation
`jrdb_normalized_warehouse_v1_2010_2025_g20260921` through
`prepare_rl_t_historical_warehouse_inputs.py`.

The old normal step
`fetch_jrdb_history.py --from-year 2010 --to-year 2025`
is absent from the three production workflows. There is no automatic Raw fallback.
Historical Raw remains rollback / audit / reproduction only.

Production implementation:
- daily/replay use `build_jrdb_index_base_hybrid.py`: Warehouse 2010–2025 + unchanged 2026 PACI/settled SED Raw
- Training Research uses `build_jrdb_index_base_from_warehouse.py`: Warehouse 2010–2025
- canonical record-hash compatibility package is materialized by the shared preparer
- Index Base schema and downstream science are unchanged

Final static audit:
- Issue #1520
- run `36242350903`
- result: PASS
- `RL_T_OLD_GPT_JRDB_ACTIVE_REFERENCE_COUNT = 0`

Fixed-date operational evidence:
- target: 2026-09-20
- settled through: 2026-09-19
- Issue #1517 / run `36240031550`
- Warehouse preparation: PASS
- 2026 Drive input: PASS
- bundle: PASS
- hybrid Index Base: PASS
- RunPerf / Official RunPerf: PASS
- Training Edge projection: PASS
- frozen scorer: PASS
- five-column validation: PASS
- 334 target runners / 154 nonblank indices / duplicate key 0

Training Research production evidence:
- Issue #1518 / run `36240033827`
- Warehouse preparation: PASS
- Index Base: PASS
- Index Base audit: PASS
- RunPerf / Official RunPerf: PASS
- Training Research build/audit: PASS
- Stage1b: PASS
- immutable Parquet canonical generation: PASS
- total rows: 781,161
- development 2013–2023: 536,900
- holdout 2024–2025: 95,065
- HOLDOUT opened: false

Final migration status:

```text
RL_T_PRODUCTION_CUTOVER               = PASS
TRAINING_RESEARCH_UPSTREAM_CUTOVER    = PASS
HISTORICAL_NORMAL_OPERATION           = WAREHOUSE
HISTORICAL_RAW_NORMAL_FETCH           = DISABLED
HISTORICAL_RAW_FALLBACK               = DISABLED
2026_DAILY_ROUTE                      = UNCHANGED
RL_T_OLD_GPT_JRDB_ACTIVE_REFERENCE_COUNT = 0
RESEARCH_BLOCKER                      = NONE
```

### Current-forward guard note

A separate 2026-09-27 forward smoke (Issue #1519 / run `36240137625`) passed Warehouse preparation, current 2026 Drive acquisition, bundling, hybrid Index Base, RunPerf, Official RunPerf, and projection, but the unchanged frozen Training Edge v0.2 runtime fingerprint rejected the current input with differences in `training_semantic_sha256` and C/CAB prediction hashes.

This finding is tracked separately in Issue #1521. It is not resolved by altering the frozen v0.2 science, changing the runtime fingerprint, or re-enabling Historical Raw fallback. The fixed migration boundary remains the formally validated 2026-09-20 / settled-through-2026-09-19 evidence above.

