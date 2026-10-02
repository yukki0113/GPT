# RL Retirement T2 — Active Workflow Retirement Report

Date: 2026-10-02
Contract: `RL_Retirement_Contract_20261002.md`

## 1. Result

RL / RaceLift研究を再開・日次算出・再学習・再検証できるGitHub Actions entrypointをactive workflow領域から退役した。

```text
ACTIVE_RL_MODEL_WORKFLOW_COUNT      = 0
ACTIVE_RL_DAILY_WORKFLOW_COUNT      = 0
ACTIVE_RL_RESEARCH_WORKFLOW_COUNT   = 0
OPEN_RL_RESEARCH_ISSUE_COUNT        = 0

RETIRED_RL_WORKFLOW_ARCHIVE_COUNT   = 8
SHARED_INFRA_RL_NAMED_WORKFLOW_COUNT = 5
```

## 2. Retired from .github/workflows

The following workflows were copied to
`.gpt/legacy_workflows/retired_rl/` and removed from
`.github/workflows/`.

- `jrdb_training_edge_holdout_issue.yml`
- `jrdb_training_edge_v02_daily_tests_issue.yml`
- `jrdb_training_edge_v02_runtime_freeze_issue.yml`
- `jrdb_training_edge_v02_verify_issue.yml`
- `jrdb_training_research_issue.yml`
- `jrdb_rl_t_parquet_cutover_audit_issue.yml`
- `jrdb_rl_t_production_cutover_audit_issue.yml`
- `rlt_historical_warehouse_downstream_issue.yml`

The archived copies contain a retirement header and are outside
`.github/workflows/`, so GitHub Actions cannot trigger them.

## 3. Already inactive daily/replay workflows

The former Training Edge daily/replay entrypoints were already outside the
active workflow directory before T2:

- `.gpt/legacy_workflows/drive_direct/jrdb_training_edge_v02_daily_issue.yml`
- `.gpt/legacy_workflows/drive_direct/jrdb_training_edge_v02_replay_issue.yml`

They remain historical reproduction assets and are not active Actions workflows.

## 4. Active workflows intentionally retained

The following `rlt_*` workflows remain active because their functional role
is shared JRDB Historical Warehouse / Index Base infrastructure, not RL model
development or RL index generation.

- `.github/workflows/rlt_historical_warehouse_audit_issue.yml`
  - full Raw-vs-Warehouse / Index Base equivalence audit
- `.github/workflows/rlt_record_hash_compat_direct_smoke_issue.yml`
  - canonical record-hash compatibility package smoke
- `.github/workflows/rlt_record_hash_compat_export_issue.yml`
  - explicit compatibility export / reproduction route
- `.github/workflows/rlt_record_hash_compat_split_issue.yml`
  - compatibility package transport/split reproduction
- `.github/workflows/rlt_warehouse_direct_materialize_issue.yml`
  - accepted Warehouse direct materialization smoke

These workflows must not be interpreted as evidence that RL research remains
active. Their `rlt_` naming is historical naming debt. Generic JRDB naming
may be considered in T5.

## 5. Historical Raw rule

Some retained shared-infrastructure audit/export workflows may explicitly read
Historical Raw.

This is permitted only as:

```text
AUDIT
ROLLBACK
REPRODUCTION
COMPATIBILITY EXPORT
```

It is not an RL production fallback and does not violate the retirement
contract.

## 6. Open issue cleanup

Issue #1521:

`RL-T current-forward runtime fingerprint drift after 2026-09-20`

was closed as:

```text
state_reason = not_planned
reason       = RL research retired
```

Search of active issues found no remaining open:

- `JRDB_TRAINING_EDGE`
- `JRDB_TRAINING_V02`
- `JRDB_TRAINING_RESEARCH`
- `RL_T_HISTORICAL_WAREHOUSE_DOWNSTREAM`
- RL-T research issue

## 7. What T2 does not do

T2 does not yet:

- remove historical RL source/config/docs;
- remove Newspaper `my_index` compatibility;
- rename shared `rlt_*` infrastructure;
- change RaceNote anti-RL firewalls;
- delete Training Research Parquet/evidence.

Those belong to T3–T5.

## 8. Gate

```text
ACTIVE_RL_MODEL_WORKFLOW_COUNT     = 0
ACTIVE_RL_DAILY_WORKFLOW_COUNT     = 0
ACTIVE_RL_RESEARCH_WORKFLOW_COUNT  = 0
OPEN_RL_RESEARCH_ISSUE_COUNT       = 0

T2_WORKFLOW_RETIREMENT             = PASS
```
