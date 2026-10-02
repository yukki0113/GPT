# RL Retirement Final Report

Date: 2026-10-02  
Repository: yukki0113/GPT  
Retirement contract: docs/RL_Retirement_Contract_20261002.md  
Asset inventory: docs/RL_Retired_Asset_Inventory_20261002.md

## Decision and rationale

RL / RaceLift research, new index development, daily scoring and production
dependency are retired. Newspaper already exposes workout-uptrend and EdgeDB
evidence, RaceNote composes source evidence without collapsing its meaning,
and EdgeDB remains an independent evidence channel. A single RL score is no
longer needed in production.

RL absence is now the normal state. No normal entrypoint runs a scorer, builds
Training Research, opens HOLDOUT/OOT/calibration, retunes the model or falls
back to Historical Raw because an RL value is missing.

## T1–T6 closure

| Turn | Result | Evidence |
|---|---|---|
| T1 Contract | PASS | docs/RL_Retirement_Contract_20261002.md |
| T2 Workflow retirement | PASS | docs/RL_Retirement_T2_Workflow_Audit_20261002.md |
| T3 Downstream independence | PASS | docs/RL_Retirement_T3_Downstream_Audit_20261002.md |
| T4 Frozen asset inventory | PASS | docs/RL_Retired_Asset_Inventory_20261002.md |
| T5 Shared infrastructure roles | PASS | docs/RL_Retirement_T5_Shared_Infrastructure_Audit_20261002.md |
| T6 Final repo-wide audit | PASS | run 36961003878 / artifact 11206784733 |

## Final audit evidence

Formal GitHub Actions run:

- Run: 36961003878 — success
- Audit source commit: 621ad3a961e050d3b12672add4aae3290bd33037
- Artifact: jrdb-rl-retirement-final-36961003878
- Artifact digest: sha256:437e34ecef5afedb9f1f51327a4ad190fad6e16f0ea1f578eacacfa251bf67cd
- Run URL: https://github.com/yukki0113/GPT/actions/runs/36961003878
- Active workflows scanned at audit time: 139, including the temporary audit
  workflow. That workflow was removed immediately after the successful run.
  The latest main has 139 workflows and does not contain the temporary audit
  workflow; a concurrent RaceNote finalize workflow accounts for the net count.

The permanent wrapper src/audit_rl_retirement_final.py reuses
src/audit_rl_retirement_downstream_dependencies.py. Audit result: PASS,
failure_count = 0.

```text
ACTIVE_RL_MODEL_WORKFLOW_COUNT = 0
ACTIVE_RL_DAILY_WORKFLOW_COUNT = 0
ACTIVE_RL_RESEARCH_WORKFLOW_COUNT = 0
OPEN_RL_RESEARCH_ISSUE_COUNT = 0

RACENOTE_RL_REQUIRED = FALSE
NEWSPAPER_RL_REQUIRED = FALSE
EDGEDB_RL_REQUIRED = FALSE
PWA_RL_REQUIRED = FALSE
ACTIVE_MY_INDEX_ARGUMENT_COUNT = 0
RL_ABSENCE_FAILURE_PATH_COUNT = 0

RL_SOURCE_ROLE = FROZEN_REPRO_ONLY
RL_CONFIG_ROLE = FROZEN_REPRO_ONLY
RL_TEST_ROLE = FROZEN_REPRO_ONLY
TRAINING_RESEARCH_ROLE = FROZEN_RESEARCH_ASSET

SHARED_WAREHOUSE_INFRA_ACTIVE = TRUE
SHARED_INDEX_BASE_ACTIVE = TRUE
RECORD_HASH_COMPAT_ACTIVE = TRUE
```

The three final-audit Issues were terminally handled: #1726 and #1727 closed as
duplicates of the successful retry; #1728 closed as completed. Open RL research
issue count is 0.

## Preserved assets and boundaries

- Frozen RL source/config/tests and Training Research schema/data remain in Git
  or their established immutable evidence locations.
- No accepted Training Research Parquet generation or evidence was deleted or
  rebuilt.
- Five active rlt_* workflows and the RL-T-named Warehouse input preparer
  remain enabled as JRDB shared infrastructure. Their names and issue routing
  were retained; headers clarify their Warehouse / Index Base / record-hash
  roles.
- JRDB Warehouse, Index Base, Warehouse adapters/materializers, record-hash
  compatibility, and shared DuckDB/Parquet tooling remain active.
- Newspaper may retain optional historical my_index compatibility. Normal
  production omits it and does not auto-generate RL.
- RaceNote anti-dependency firewalls remain: training_edge_visible=false,
  rl_index_visible=false, do_not_use_training_edge=true, and
  training_edge_status=NOT_CONSUMED.
- The temporary T6 workflow is deleted. The permanent static audit scripts and
  historical evidence remain readable.

## Remaining historical references

- Newspaper source/schema retain optional historical my_index /
  training_edge_index compatibility fields.
- Shared infrastructure workflow names continue to contain rlt/RL-T for issue
  routing compatibility; T5 documents their active functional role.
- Dated RL-T migration and Training Edge documents remain historical evidence.
- The runtime_freeze.pending.json file remains as stale pre-freeze evidence and
  is explicitly not a pending task.

These references are not production dependencies and do not authorize resuming
RL research or generation.

## Future reopening rule

Do not restore the frozen version to production by removing its retirement
markers. Any future research must begin as a new version under an explicit
decision that defines its objective, input contract, target, leakage boundary,
evaluation design, production role and downstream dependencies.

## Final target

RL_RESEARCH = RETIRED
RL_DAILY_GENERATION = RETIRED
RL_MODEL_DEVELOPMENT = RETIRED
RL_PRODUCTION_REQUIRED = FALSE
RL_DOWNSTREAM_HARD_DEPENDENCIES = 0
RL_FROZEN_ASSETS = PRESERVED
RL_REPRODUCIBILITY = PRESERVED
RACENOTE / NEWSPAPER / EDGEDB / PWA = ACTIVE AND RL-INDEPENDENT
JRDB_WAREHOUSE / INDEX_BASE / RECORD_HASH_COMPAT = ACTIVE
OPEN_RL_RESEARCH_ISSUES = 0
RL_RETIREMENT = COMPLETE
