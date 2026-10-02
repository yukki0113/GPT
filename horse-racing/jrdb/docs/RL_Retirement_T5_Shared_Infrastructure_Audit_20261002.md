# RL Retirement T5 — Shared Infrastructure Disentanglement

Date: 2026-10-02  
Inventory: docs/RL_Retired_Asset_Inventory_20261002.md

## Decision

The active workflow and preparer names are retained. Renaming would alter
issue-title routing and create needless reference risk. Their functional role
is now explicit in-file as ACTIVE_SHARED_INFRA. None generates RL / Training
Edge scores or builds Training Research.

SHARED_WAREHOUSE_INFRA_ACTIVE = TRUE
SHARED_INDEX_BASE_ACTIVE = TRUE
RECORD_HASH_COMPAT_ACTIVE = TRUE
RL_ONLY_SHARED_INFRA_COUNT = 0
AMBIGUOUS_RLT_ACTIVE_ROLE_COUNT = 0
T5_SHARED_INFRA_DISENTANGLEMENT = PASS

## Active workflows reviewed

- .github/workflows/rlt_historical_warehouse_audit_issue.yml — accepted
  Historical Warehouse audit / Raw-versus-Warehouse verification and Index
  Base coverage. Retained as JRDB data infrastructure audit.
- .github/workflows/rlt_record_hash_compat_direct_smoke_issue.yml — direct
  smoke of the canonical record-hash compatibility sidecars.
- .github/workflows/rlt_record_hash_compat_export_issue.yml — explicit
  compatibility export/reproduction route for sidecars.
- .github/workflows/rlt_record_hash_compat_split_issue.yml — transport/split
  route for an already accepted compatibility package.
- .github/workflows/rlt_warehouse_direct_materialize_issue.yml — materializes
  accepted Warehouse assets and validates direct materialization.

The five workflows remain under .github/workflows and their issue prefixes,
request contracts, data behavior and outputs are unchanged. Comments now state
that the names are historical and the workflows are not RL production paths.

## Shared source and infrastructure preserved

horse-racing/jrdb/src/prepare_rl_t_historical_warehouse_inputs.py remains
because it prepares accepted Warehouse and record-hash compatibility inputs.
Its name is historical; its functional role is shared JRDB infrastructure.

Preserved active infrastructure includes:

- JRDB Historical Warehouse readers, adapters and materializers
- Index Base and Hybrid Index Base
- Warehouse-to-Index-Base adapter
- record-hash compatibility readers/materializers
- tools/data-storage DuckDB / Parquet tooling

No source, workflow or data path was removed or disabled.

## Historical RL-T utilities

These are not active production entrypoints and remain historical evidence or
compatibility/reproduction tools:

- src/run_rl_t_historical_warehouse_minimum_cutover.py
- src/run_rl_t_warehouse_downstream_nonregression.py
- src/audit_rl_t_production_warehouse_cutover.py
- src/audit_rl_t_warehouse_downstream_nonregression.py
- src/audit_rl_t_training_research_parquet_cutover.py

Their historical source references do not change the current role of the five
active shared-infrastructure workflows. Frozen Training Research/scoring
components remain governed by the T4 inventory.

## T5 gate

SHARED_WAREHOUSE_INFRA_ACTIVE = TRUE
SHARED_INDEX_BASE_ACTIVE = TRUE
RECORD_HASH_COMPAT_ACTIVE = TRUE
RL_ONLY_SHARED_INFRA_COUNT = 0
AMBIGUOUS_RLT_ACTIVE_ROLE_COUNT = 0
T5_SHARED_INFRA_DISENTANGLEMENT = PASS
