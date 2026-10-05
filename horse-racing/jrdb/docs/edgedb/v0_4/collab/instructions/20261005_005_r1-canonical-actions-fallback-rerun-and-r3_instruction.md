# EdgeDB v0.4 R1 Canonical Actions-Fallback Rerun / R3 Decision — Instruction

Status: TODO  
Date: 2026-10-05  
Research decision owner: ChatGPT  
Execution worker: Codex  
Production impact: NONE

## Objective

Supersede the environment-limited R1 execution path from PR #1800 by rerunning the frozen R1 Wave A pipeline through the repository-standard Data Storage Actions fallback, using canonical DuckDB/PyArrow dependencies.

This task must:

1. use the new local-first -> Actions fallback contract;
2. rerun the frozen 3y Wave A C1 pipeline from pinned canonical inputs;
3. run the canonical DuckDB C2A implementation;
4. run canonical C2B exact metrics;
5. rebuild compact R1 evidence;
6. compare aggregate results against PR #1800 as a sanity check;
7. treat the new canonical fallback run as the authoritative R1 result if all integrity checks pass;
8. make R3 family decisions;
9. prepare the next instruction document, but do not execute 5y/depth-4 work yet.

Do not spend this task trying to reconstruct the temporary PyArrow fallback implementation from PR #1800. The full prior fallback identity set was not retained in Git, so exact set-equivalence cannot now be independently proven. Canonical rerun is the replacement strategy.

## Mandatory Data Storage routing

Read and follow:

- `tools/data-storage/README.md`
- `tools/data-storage/docs/CODEX_LOCAL_FIRST_ACTIONS_FALLBACK.md`
- `.gpt/GITHUB_OPERATION_POLICY.md`

New fallback components already smoke-tested:

- `tools/data-storage/scripts/data_storage_fallback_runner.py`
- `.github/workflows/data_storage_fallback_issue.yml`

Smoke evidence:

- Issue #1802
- run `37317982545`
- status PASS
- DuckDB `1.1.3`
- PyArrow `25.0.1`
- artifact `data-storage-fallback-37317982545`

### Required routing behavior

First perform the documented local check:

```text
.venv-data-storage
-> check-deps
-> one normal repair attempt
```

If the managed Codex runtime remains blocked by proxy/network policy, **do not stop** and do not substitute another engine.

Create a validated `[DATA_STORAGE_FALLBACK]` Issue and run the canonical repository code in Actions.

## PR #1800 / #1801 treatment

### PR #1800

PR #1800 contains useful compact R1 evidence but C2A was executed through a temporary PyArrow reproduction because the local executor lacked DuckDB.

Treat it as:

`PROVISIONAL_R1_REFERENCE`

Do not use it as the final authoritative R1 evidence after this canonical rerun succeeds.

Its aggregate facts may be used only as a sanity comparison.

### PR #1801

PR #1801 records the blocked local DuckDB preflight before the fallback infrastructure existed.

Treat it as:

`SUPERSEDED_BY_DATA_STORAGE_FALLBACK`

Do not repeat the same blocked installation loop beyond the one required local-first check.

Do not merge blocked-only documentation as though it were a successful research result.

When the canonical rerun succeeds, recommend appropriate close/supersede handling for #1800/#1801 according to repository GitHub policy.

## Source ref for fallback

Use a source ref/commit that contains all of the following:

- R1 preflight planner/window implementation;
- current canonical C1 planner/evaluator/merge;
- canonical `prepare_jrdb_edge_v04_stage_c2.py`;
- canonical C2B evaluator;
- Data Storage fallback runner/workflow.

Pin and record the exact source commit before execution.

Do not execute from an ambiguous dirty working tree.

## Frozen research inputs

### Feature Mart

- run: `36116777782`
- artifact: `jrdb-edge-feature-mart-parquet-36116777782`
- expected `edge_runner_fact.parquet` SHA-256:
  `82e6550639210eea6cf1fc1ac374ee8b6fc07115214fe75ea6e1bb704d3751f6`
- rows: `781161`

### Stage B catalog

- run: `36262821119`
- artifact: `jrdb-edge-v04-stage-b-36262821119`
- expected catalog SHA-256:
  `cf70098156283e42df49cc61d4988f1d2b578a4dbf4135c8121eb81262d5d2ba`
- templates: `47371`

The fallback request must declare these as upstream Actions artifacts.

Verify extracted content hashes inside the execution steps before research results are accepted.

## Frozen R1 request

Window:

- discovery years: `3`
- as-of: `2025-12-28`
- inclusive window: `2022-12-28 .. 2025-12-28`

Wave A lanes:

- `TRANSITION_PRIORITY`
- `PEDIGREE_INTERACTION`
- `PEDIGREE_BASELINE`

Depth:

- min 2
- max 3

C1 thresholds:

- min win ROI: 110
- min place ROI: 105
- max per template: 100
- existing support floors unchanged

Expected planner identity from preflight:

- 1,106 templates
- 6 shards
- depth 2: 123
- depth 3: 983
- TRANSITION_PRIORITY: 586
- PEDIGREE_INTERACTION: 64
- PEDIGREE_BASELINE: 456
- prior plan SHA-256:
  `de823224c0f10690232835b35557517c474377734b2df347ca3a9a08daa3ded8`

If the canonical rerun produces a different selected template set or materially different shard plan from the same source/catalog/options, fail closed and explain.

## Required Actions-fallback execution

Prefer one `[DATA_STORAGE_FALLBACK]` request with sequential repository Python steps, or a small number of fallback requests if output handoff between stages requires it.

Do not create six independent unrelated Issues unless technically necessary.

The fallback request must use repository entrypoints, not inline scientific reimplementations.

### Stage 1 — input verification / planning

Use repository code to:

- verify Feature Mart hash;
- verify Stage B catalog hash;
- generate Wave A shard plan;
- assert expected template/shard identity.

A small dedicated verification/orchestration Python script may be added to the repository if needed, but it must only orchestrate canonical modules and verify provenance. It must not duplicate C1/C2 scientific logic.

### Stage 2 — C1 six-shard sequential execution

Run all six planned shards sequentially with:

- same frozen Feature Mart;
- same catalog;
- same plan;
- `--discovery-years 3`;
- `--as-of-date 2025-12-28`;
- frozen ROI thresholds;
- frozen max-per-template.

Then run canonical C1 merge.

Required integrity:

- all 6 shard audits PASS;
- same Feature Mart hash across shards;
- same catalog/plan provenance;
- no missing shard;
- no duplicate candidate ID;
- merge PASS.

### Stage 3 — canonical DuckDB C2A

Run exactly:

`horse-racing/jrdb/src/prepare_jrdb_edge_v04_stage_c2.py`

through the fallback environment where DuckDB 1.1.3 is available.

Do not mirror its SQL in another engine.

Record:

- C1 candidate count;
- C2 shortlist count;
- route counts;
- child-parent map count;
- unique parent request count;
- unique metric request count.

### Stage 4 — canonical C2B

Run canonical:

`horse-racing/jrdb/src/evaluate_jrdb_edge_v04_stage_c2b_shard.py`

using the same:

- Feature Mart hash;
- discovery years 3;
- as-of 2025-12-28.

Use deterministic sequential sharding appropriate to request count.

If no canonical merger exists, add a small deterministic merge/audit utility that:

- concatenates C2B outputs;
- validates one result per metric_request_id;
- rejects duplicate/missing/extra IDs;
- validates common window/hash provenance.

This merger may use DuckDB/Parquet tooling but must not reinterpret metrics.

## Canonical compact reporter

Rebuild the R1 compact outputs from the canonical C1/C2 results.

Allowed to add a deterministic report builder if needed.

Produce:

- `r1_summary.json`
- `r1_report.md`
- `shortlist.csv` <=100 rows

Do not commit:

- full C1 candidate Parquet;
- full C2B metric table;
- raw Feature Mart;
- large temporary shard outputs.

The fallback artifact may retain broader outputs for audit.

## Sanity comparison to PR #1800

Compare canonical rerun aggregate facts against PR #1800.

PR #1800 provisional aggregate reference:

- C1 merged candidates: `68685`
- C2A shortlist: `17807`
- child-parent links: `52171`
- unique parent metric requests: `14129`
- total exact requests: `30733`
- provisional labels:
  - INCREMENTAL_CANDIDATE: 367
  - JACKPOT_DEPENDENT: 17350
  - MIXED_PARENT_INCREMENTALITY: 90

Interpretation:

- exact equality is reassuring;
- a difference is not automatically an error, because canonical DuckDB C2A is replacing an unverified PyArrow reproduction;
- any difference must be explained before R3 decisions;
- C1 should normally match exactly if source/input/request are truly frozen.

If C1 differs, fail closed.

If only C2A/downstream differs, identify the exact canonical change in membership/count caused by DuckDB semantics.

## R1 authoritative acceptance rule

Mark the new result:

`CANONICAL_R1_ACCEPTED`

only if:

- fallback audit PASS;
- DuckDB version is 1.1.3;
- pinned input hashes match;
- planner identity is valid;
- all C1 shards + merge pass;
- canonical DuckDB C2A passes;
- C2B request/result integrity is exact;
- no threshold/request semantics changed;
- production remains unchanged.

Once accepted, use this canonical run instead of the provisional PR #1800 computation for R3.

## R3 family decision

Evaluate separately:

- `PEDIGREE_CROSS`
- `PEDIGREE_TRANSITION_CROSS`
- `TRANSITION_CROSS`

For each report:

- C1 candidate count;
- C2 shortlist count;
- incremental candidate count/rate;
- mixed-parent count/rate;
- jackpot-dependent count/rate;
- top3-exclusion failures;
- 730d/full-3y contradictions;
- single-year confinement;
- no-365d support;
- depth-2 vs depth-3 contribution;
- support distribution of incremental candidates;
- immediate-parent ROI/rate deltas;
- recent 365/730 support/direction.

Allowed family decisions:

- `KEEP_3Y_AND_ALLOW_DEPTH4_DESIGN`
- `EXTEND_FROZEN_FAMILY_TO_5Y`
- `KEEP_3Y_OBSERVE_ONLY`
- `STOP_FAMILY_EXPANSION`

Do not create a composite score.

Do not tune thresholds from observed results.

## Representative examples

For each family provide:

- 5–10 strong non-jackpot incremental examples;
- 3–5 rejected examples showing jackpot or temporal instability;
- readable conditions;
- child exact metrics;
- all immediate-parent comparisons;
- temporal evidence.

These are research examples, not betting recommendations.

## Required Git result

Write:

`horse-racing/jrdb/docs/edgedb/v0_4/collab/results/20261005_005_r1-canonical-actions-fallback-rerun-and-r3_result.md`

If compact canonical outputs are small, store them under:

`horse-racing/jrdb/docs/edgedb/v0_4/collab/results/r1_wave_a_3y_canonical/`

Allowed:

- `r1_summary.json`
- `r1_report.md`
- `shortlist.csv`

The result must include:

- Status;
- exact source commit;
- fallback Issue number;
- fallback run ID;
- fallback artifact name/digest if available;
- DuckDB/PyArrow versions;
- pinned input hashes;
- C1 planner/shard/merge integrity;
- canonical C2A counts;
- C2B integrity;
- comparison to PR #1800;
- authoritative R1 acceptance status;
- R3 family decisions;
- representative examples;
- PR #1800/#1801 disposition recommendation;
- production impact = NONE.

## Prepare next instruction

If `CANONICAL_R1_ACCEPTED`, also create the next collaboration instruction document.

It must be derived from the R3 family decisions and may contain:

- frozen selected-family 5y extension;
- controlled parent/prefix-directed depth-4 design/preflight;
- both on different families.

The next instruction must again contain the mandatory Data Storage local-first -> Actions fallback rule.

Do not execute that next instruction in this task.

## Git / PR hygiene

Do not create a new PR merely because Codex defaults to PR-based output if direct Git Change is available and safe.

If a PR is created:

- clearly identify it as the canonical replacement result;
- do not leave superseded #1800/#1801 ambiguous;
- recommend close/merge state for each according to actual content;
- never claim a provisional/blocked PR is authoritative.

## Non-goals

- no 5y execution;
- no depth-4 execution;
- no threshold tuning;
- no market/popularity-conditioned candidate generation;
- no SHADOW publication;
- no RaceNote/PWA integration;
- no v0.2/v0.3 production change.
