# RL / Training Edge Retired Asset Inventory

Date: 2026-10-02  
Repository: yukki0113/GPT  
Inventory basis: recursive Git tree at dca3b6a33acd9e95cb16fefaa661e27afafb0aa0 plus current file contents.

## Status

RL / RaceLift model research, daily scoring and production use are retired. The
assets below are retained for historical reproduction and audit only. This is
an inventory/freeze record; no historical files, generations, schemas or
artifacts are deleted.

RL_SOURCE_ROLE = FROZEN_REPRO_ONLY
RL_CONFIG_ROLE = FROZEN_REPRO_ONLY
RL_TEST_ROLE = FROZEN_REPRO_ONLY
RL_DOC_ROLE = HISTORICAL_EVIDENCE
TRAINING_RESEARCH_ROLE = FROZEN_RESEARCH_ASSET
RL_ASSET_INVENTORY = COMPLETE

Frozen means: preserve the existing version and evidence; do not extend it, use
it as a production entrypoint, or resume development. Reproduction/audit is
allowed only when explicitly requested. A new research decision must define a
new version and contract.

## Classification rules

- FROZEN_REPRO: RL scoring/evaluation/runtime code, its fixed configs, schema
  and focused tests. Kept for reproduction/audit only.
- FROZEN_RESEARCH: Training Research builder, audit, resolver and Parquet
  migration. Its data and Parquet generations remain preserved, but no normal
  production build or automatic rebuild is allowed.
- HISTORICAL_EVIDENCE: dated research, migration, cutover and workflow
  records. Read as evidence, not current instructions.
- COMPATIBILITY_ONLY: retained examples or old workflow definitions that
  describe migration/reproduction routes; not normal production entrypoints.
- SHARED_INFRA: JRDB Warehouse, Index Base, record-hash compatibility and
  common DuckDB/Parquet tooling. These remain active and are outside RL freeze.

## FROZEN_REPRO — source

- src/training_edge_v0_2_core.py
- src/evaluate_training_edge_v0_1_holdout.py
- src/evaluate_training_edge_v0_2_oot.py
- src/fingerprint_training_edge_v0_2_runtime.py
- src/project_training_edge_v0_2_input.py
- src/score_training_edge_v0_2_daily.py

These compute/evaluate frozen RL versions. The daily scorer is not an active
production command.

## FROZEN_RESEARCH — Training Research source and schema

- src/build_jrdb_training_research.py
- src/audit_jrdb_training_research.py
- src/jrdb_training_research_parquet.py
- src/migrate_jrdb_training_research_parquet.py
- schema/jrdb_training_research_schema_v0_1.sql

Keep accepted immutable Training Research Parquet generations and their
manifests/evidence. Do not rebuild them to provide RL output. Common storage
libraries under tools/data-storage/ are shared infrastructure and are not
frozen by this entry.

## FROZEN_REPRO — config and focused tests

Config:
- config/training_edge_v0_2_calibration.json
- config/training_edge_v0_2_runtime_fingerprint.json
- config/training_edge_v0_2_runtime_versions.json

Focused reproduction tests:
- tests/test_fingerprint_training_edge_v0_2_runtime.py
- tests/test_jrdb_training_research.py
- tests/test_jrdb_training_research_parquet_resolver.py
- tests/test_project_training_edge_v0_2_input.py
- tests/test_score_training_edge_v0_2_daily.py
- tests/test_training_edge_v0_2_core.py

The tests remain useful for explicitly requested historical reproduction. Their
presence does not authorize production scoring or research rebuilds.

## Historical and compatibility assets

- config/training_edge_v0_2_runtime_freeze.pending.json —
  HISTORICAL_EVIDENCE; stale pre-freeze marker retained for provenance, not an
  outstanding task.
- config/README_training_edge_v0_2_runtime.md —
  HISTORICAL_EVIDENCE; runtime fingerprint explanation.
- config/storage/training_research.example.yaml —
  COMPATIBILITY_ONLY; migration/build-time example, not normal reader config.
- .gpt/legacy_workflows/retired_rl/ — archived retired Actions workflows;
  reproduction evidence only, outside active workflow discovery.
- .gpt/legacy_workflows/drive_direct/jrdb_training_edge_v02_2026_oot_issue.yml,
  jrdb_training_edge_v02_daily_issue.yml,
  jrdb_training_edge_v02_replay_issue.yml —
  COMPATIBILITY_ONLY; inactive historical definitions.

Dated evidence retained as HISTORICAL_EVIDENCE:
- docs/RaceLift_RL_Research_Handoff_20260922.md
- docs/Training_Edge_v0_*.md
- docs/Training_Research_*.md
- docs/RL_T_*.md
- docs/RL_Retirement_Contract_20261002.md
- docs/RL_Retirement_T2_Workflow_Audit_20261002.md
- docs/RL_Retirement_T3_Downstream_Audit_20261002.md

The prior warehouse cutover documents are historical evidence of shared JRDB
infrastructure migration; their results do not make RL a current dependency.

## SHARED_INFRA — explicitly outside this freeze

The following remain active shared JRDB infrastructure:
- Historical Warehouse, Warehouse readers/materializers and adapters
- Index Base, Hybrid Index Base and Warehouse-to-Index-Base adapter
- record-hash compatibility and materialization
- common DuckDB / Parquet tooling under tools/data-storage/
- five active rlt_* workflows and the shared Warehouse input preparer; T5
  records their functional roles without removing them

See RL_Retirement_T5_Shared_Infrastructure_Audit_20261002.md for the
workflow/source-level role audit.

## T4 gate

RL_SOURCE_ROLE = FROZEN_REPRO_ONLY
RL_CONFIG_ROLE = FROZEN_REPRO_ONLY
RL_TEST_ROLE = FROZEN_REPRO_ONLY
RL_DOC_ROLE = HISTORICAL_EVIDENCE
TRAINING_RESEARCH_ROLE = FROZEN_RESEARCH_ASSET
RL_ASSET_INVENTORY = COMPLETE
T4_ASSET_FREEZE = PASS
