# RL-T Production Workflow — Final Historical Warehouse Cutover Result

Date: 2026-09-26

## 1. Result

RL-T / Training Edge / Training Research の production Historical upstream を、
2010–2025 Raw normal fetch から accepted JRDB Historical Warehouse へ切り替えた。

Accepted Warehouse generation:

```text
jrdb_normalized_warehouse_v1_2010_2025_g20260921
```

Final storage/plumbing status:

```text
DAILY_HISTORICAL_SOURCE                = WAREHOUSE
REPLAY_HISTORICAL_SOURCE               = WAREHOUSE
TRAINING_RESEARCH_UPSTREAM_SOURCE      = WAREHOUSE

HISTORICAL_RAW_NORMAL_FETCH            = 0
HISTORICAL_RAW_FALLBACK                = DISABLED

WAREHOUSE_MATERIALIZATION              = PASS
INDEX_BASE_BUILD                       = PASS
RUNPERF                                = PASS
OFFICIAL_RUNPERF                       = PASS

2026_ROUTE                             = UNCHANGED
TARGET_RESULT_LEAKAGE_FIXED_SMOKE      = 0

TRAINING_RESEARCH_PARQUET_CANONICAL    = PASS
STAGE2B_PARQUET_ROUTE                  = PASS

RL_T_OLD_GPT_JRDB_ACTIVE_REFERENCE_COUNT = 0
RL_T_PRODUCTION_CUTOVER                = PASS
TRAINING_RESEARCH_UPSTREAM_CUTOVER     = PASS
RESEARCH_BLOCKER                       = NONE
```

A separate current-forward runtime fingerprint finding is recorded in Issue #1521.
It does not authorize changing frozen v0.2 science or restoring Historical Raw fallback.

## 2. main SHA

Before production plumbing cutover:

```text
c28e21fbe0296b994efb0088e00b366d439114b4
```

Production workflow implementation commits:

```text
1a90122e39f5308a7fd8999f072e899429a7453f
  daily Historical upstream -> Warehouse

36f3161fcb0b469fcea06287b3c91b87b4cb43f2
  replay Historical upstream -> Warehouse

2244bb44b42b3e6520f9a00a35066f93f480fb6b
  Training Research upstream -> Warehouse

530772306e9a1ef28d67b6515824e1b6781b4854
86330f5ad4e20a54c0019eebb3b20a32bc85ea61
833a235970a6daa8aeeb1ba04c3968702443477d
  shared data-storage runtime / PYTHONPATH corrections

35aeca2a37946e9e44ee495b0dd2e40128b638a5
3b8b55c2bfcff2fc88cd1be4aef86bc2c94a91e9
64e87883731740f5b9214bef8f6cd63c374f595c
  materialized Warehouse asset-root corrections

907e0b79feb4b180c3fea720971a5f8a2702b2e0
c946ced8df1a831d65f40d026ff29b4511d2a80d
  daily/replay data-storage runtime dependency installation
```

After status-document update:

```text
188181ac1ed879bdefcc2186254bb0f8d019a91a
```

The final report commit is recorded separately by Git after this file is added.

## 3. Daily workflow diff summary

Target:

```text
.github/workflows/jrdb_training_edge_v02_daily_issue.yml
```

Removed normal Historical operation:

```text
fetch_jrdb_history.py --from-year 2010 --to-year 2025
build_jrdb_index_base_from_raw.py --years 2010..2026
```

New normal route:

```text
prepare_rl_t_historical_warehouse_inputs.py
  -> accepted Warehouse 2010–2025
  -> canonical record-hash compatibility package

2026 PACI + settled SED / Raw
  -> unchanged

build_jrdb_index_base_hybrid.py
  -> unchanged Index Base v0.1
```

No automatic Historical Raw fallback was added.

The 2026 PACI / SED acquisition and target SED absence guard remain unchanged.

## 4. Replay workflow diff summary

Target:

```text
.github/workflows/jrdb_training_edge_v02_replay_issue.yml
```

Historical annual Raw fetch was removed from normal operation.

New route:

```text
2010–2025 accepted Warehouse
+ canonical record-hash compatibility
+ existing 2026 replay PACI / settled SED
-> build_jrdb_index_base_hybrid.py
-> RunPerf
-> Official RunPerf
-> Training Edge projection
-> frozen scorer
```

Replay semantics were not changed.

## 5. Training Research workflow diff summary

Target:

```text
.github/workflows/jrdb_training_research_issue.yml
```

Old normal route:

```text
fetch_jrdb_history.py
-> build_jrdb_index_base_from_raw.py
```

New normal route:

```text
prepare_rl_t_historical_warehouse_inputs.py
-> build_jrdb_index_base_from_warehouse.py
-> RunPerf
-> Official RunPerf
-> Training Research transient SQLite
-> Stage 1b
-> immutable Training Research Parquet generation
```

Training Research scientific semantics, HOLDOUT, Stage1b semantics, and Parquet migration logic were not changed.

## 6. Warehouse input preparation

Shared normal-operation entrypoint:

```text
horse-racing/jrdb/src/prepare_rl_t_historical_warehouse_inputs.py
```

It materializes:

- accepted Historical Warehouse assets for BAC/KYI/CHA/CYB/SED/UKC
- canonical legacy Index Base record-hash compatibility sidecars

Required result:

```text
historical_raw_required = false
```

This result was observed as PASS in the final replay and Training Research runs.

## 7. Record-hash compatibility

The Warehouse itself was not modified.

The existing canonical compatibility package is used to reproduce the legacy Index Base
`record_hash` representation while preserving the accepted Warehouse Parquet as immutable.

Production no longer needs Historical Raw merely to reconstruct legacy `record_hash`.

## 8. Fixed-date smoke

Formal fixed boundary:

```text
target          = 2026-09-20
settled through = 2026-09-19
```

Evidence:

```text
Issue #1517
Run   36240031550
Result SUCCESS
```

Observed gates:

```text
HISTORICAL_PREPARE = 0
DRIVE              = 0
BUNDLE             = 0
INDEX               = 0
RUNPERF             = 0
PROJECT             = 0
SCORE               = 0
VALIDATE            = 0
```

Five-column handoff:

- target runners: 334
- nonblank indices: 154
- blank indices: 180
- unique keys: 334
- duplicate output keys: 0
- decimal places: 1
- output SHA-256:
  `a84d7584ec27d09d23cacabf6e1f054275577f579c1a75075dde5c41dd3d461f`

Target-date SED was excluded by replay semantics.

This fixed-date run uses the same frozen Training Edge v0.2 scorer as daily production.

## 9. 2026 route unchanged evidence

Daily/replay continue to use:

```text
PACI_FOLDER_URL
SED_FOLDER_URL
download_public_drive_inventory.py
bundle_jrdb_paci_year.py
bundle_jrdb_daily_year.py
```

Historical data alone changed source:

```text
2010–2025 Raw normal fetch
-> accepted Historical Warehouse
```

The following remain unchanged:

- PACI semantics
- settled SED semantics
- target SED absence / replay exclusion guards
- Training Edge v0.2 core
- features
- target
- eligibility
- alpha
- preprocessing
- calibration
- frozen runtime fingerprint
- daily scorer
- OOT logic
- market-field exclusions

## 10. Training Research production smoke

Evidence:

```text
Issue #1518
Run   36240033827
Result SUCCESS
```

All exits were zero:

```text
HISTORICAL_PREPARE
INDEX_BUILD
INDEX_AUDIT
RUNPERF
TRAINING_BUILD
TRAINING_AUDIT
STAGE1B
TRANSPORT
```

Training Research audit:

- total rows: 781,161
- duplicate race_key + horse_no: 0
- missing horse_id: 0
- chronology violations: 0
- market columns: none
- source record hash invalid: 0

Split:

- WARMUP 2010–2012: 149,196
- DEVELOPMENT 2013–2023: 536,900
- HOLDOUT 2024–2025: 95,065

HOLDOUT guard:

```text
max_selected_year             = 2023
predictive_outcomes_selected  = false
opened                        = false
```

The immutable Training Research Parquet generation step completed successfully.

## 11. Stage 2b / Parquet state

The earlier Stage 2b migration remains valid and was not reimplemented.

Previously completed gates remain:

```text
TRAINING_RESEARCH_PARQUET_CANONICAL = PASS
STAGE2B_PARQUET_READER              = PASS
STAGE2B_PARQUET_WORKFLOW            = PASS
STAGE2B_HISTORICAL_REGRESSION       = PASS
STAGE2B_ACTIVE_LEGACY_DEPENDENCY    = 0
```

## 12. Legacy active-reference audit

Final production static audit:

```text
Issue #1520
Run   36242350903
Result PASS
```

Required result:

```text
RL_T_OLD_GPT_JRDB_ACTIVE_REFERENCE_COUNT = 0
```

The three production workflows contain no normal:

```text
fetch_jrdb_history.py --from-year 2010 --to-year 2025
```

Historical Raw remains allowed only for audit / rollback / reproduction workflows.

## 13. Remaining LEGACY_REPRO references

The following categories may remain outside current production paths:

- Historical Raw fetch used by equivalence/audit workflows
- Raw-vs-Warehouse dual-read evidence
- old frozen historical workflows
- rollback/reproduction tools
- legacy provenance references in audit documents

These are not production dependencies.

## 14. Old GPT/JRDB deletion-readiness contribution

This cutover removes RL-T production reliance on old Historical Raw/store routing for the
2010–2025 normal path.

Specifically:

- daily no longer normal-fetches Historical Raw
- replay no longer normal-fetches Historical Raw
- Training Research no longer normal-fetches Historical Raw
- accepted Warehouse and canonical compatibility package are sufficient for Historical normal operation
- active old GPT/JRDB production reference count for the audited RL-T path is zero

This increases deletion readiness for old GPT/JRDB Historical production dependencies.
It does not by itself authorize deleting rollback/audit/reproduction assets used by other subsystems.

## 15. Current-forward runtime guard note

A forward smoke for 2026-09-27 was executed after the storage cutover:

```text
Issue #1519
Run   36240137625
```

It passed:

```text
HISTORICAL_PREPARE
DRIVE
BUNDLE
INDEX
RUNPERF
OFFICIAL RUNPERF
PROJECT
```

Target SED was absent.

The frozen scorer then failed closed with:

```text
Training Edge v0.2 runtime fingerprint mismatch:
training_semantic_sha256,
c_training_prediction_sha256,
cab_training_prediction_sha256
```

No frozen scientific asset was modified and no Raw fallback was enabled.

The finding is tracked separately:

```text
Issue #1521
RL-T current-forward runtime fingerprint drift after 2026-09-20
```

This is an operational follow-up beyond the Historical storage/plumbing cutover.
The formal fixed-date cutover evidence remains 2026-09-20 / settled through 2026-09-19,
which completed successfully.

## 16. Migration status documents updated

Updated:

```text
horse-racing/jrdb/.gpt/MIGRATION_STATUS.md
horse-racing/jrdb/.gpt/CONTEXT.md
horse-racing/jrdb/.gpt/HANDOFF.md
horse-racing/jrdb/docs/RL_T_Historical_Warehouse_Cutover_Audit_20260922.md
```

## 17. Final decision

Historical production plumbing cutover is accepted.

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

The 2026-09-27 frozen runtime fingerprint drift remains a separate fail-closed operational
follow-up and must not be “fixed” by changing v0.2 scientific semantics or reverting the
Historical production source to Raw.
