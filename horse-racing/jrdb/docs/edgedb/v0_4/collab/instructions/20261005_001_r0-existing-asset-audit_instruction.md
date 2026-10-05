# EdgeDB v0.4 R0 Existing-Asset Audit — Instruction

Status: TODO  
Date: 2026-10-05  
Owner for research decision: ChatGPT  
Execution worker: Codex  
Production impact: NONE

## Objective

Audit the current EdgeDB v0.4 implementation and determine the minimum changes required to restart research under the new staged execution plan.

Canonical redesign:

`horse-racing/jrdb/docs/edgedb/v0_4/EdgeDB_v0_4_Research_Execution_Redesign_20261005.md`

Original design reference:

`horse-racing/jrdb/docs/EdgeDB_v0_4_HighOrder_Transition_Value_Discovery_Design_20260926.md`

Parent issue:

`#1536 [JRDB_EDGE_V04] high-order-transition-value-prototype`

## Known historical facts

- Stage B produced 47,371 templates.
- Stage C1 r2 completed 104 shards and merged 4,639,841 research candidates.
- full-history r2 PASS: run 36697607028.
- trailing-5y r3 failed during shard evaluation: run 36803275900.
- Production v0.2 / v0.3 serving was not changed.

## Required audit

### 1. Current implementation inventory

Inspect at least:

- Stage A / B implementation and outputs/contracts;
- `plan_jrdb_edge_v04_stage_c1_shards.py`;
- `evaluate_jrdb_edge_v04_stage_c1_shard.py`;
- `merge_jrdb_edge_v04_stage_c1_shards.py`;
- related configs / tests / workflows / docs;
- any current Stage C2 or downstream prototype code.

Report what is reusable as-is.

### 2. Window support

Determine whether the current evaluator correctly supports an arbitrary trailing discovery window such as 3 years.

Check:

- as-of derivation;
- inclusive / exclusive date boundaries;
- date filtering location;
- parent metrics under the same window;
- recent-window metrics;
- whether filtering occurs before grouping;
- whether any full-history statistic leaks into a 3y candidate decision.

Do not run a large aggregation yet.

### 3. Lane / depth restriction

Determine the smallest change required to run only:

- depth 2-3;
- TRANSITION_PRIORITY;
- PEDIGREE_INTERACTION / pedigree-transition equivalent lanes;
- baseline parents needed for incrementality.

Identify whether planner filtering, template filtering, or evaluator filtering is safest.

### 4. Progressive expansion feasibility

Assess whether the existing template catalog can support:

- Wave A depth 2-3;
- later depth 4 expansion only for approved parent/prefix families;
- optional depth 5-6 exceptional expansion.

If current Stage B catalog structure makes prefix-directed expansion difficult, propose the minimum compatible addition rather than rebuilding Stage B from scratch.

### 5. Failure audit for trailing-5y r3

Inspect available source/workflow/run evidence and identify the actual failure mode of run 36803275900.

Classify it as one or more of:

- code defect;
- data / date-window defect;
- memory;
- timeout;
- artifact size;
- shard imbalance;
- runner/environment;
- unknown.

If exact diagnosis is not possible from retained evidence, state what evidence is missing.

### 6. Execution routing

Recommend which R1/R2 work should run via:

- Codex/local deterministic execution;
- GitHub Actions.

Actions must not remain the default merely because the current implementation already uses them.

Consider:

- memory footprint;
- runtime;
- artifact size;
- repeatability;
- need for secrets;
- need for formal immutable audit.

### 7. Compact output contract

Propose a compact R1 summary artifact / report schema sufficient for ChatGPT to decide:

- candidate count by lane/depth;
- support distribution;
- ROI/rate distribution;
- jackpot dependency;
- temporal dispersion;
- parent incrementality;
- shortlist / near-shortlist;
- top rejection reasons.

Do not propose committing millions of candidate rows to Git.

## Required code changes

R0 is audit-first.

You may make small focused changes only when they are necessary to:

- fix an obvious correctness bug;
- expose deterministic window/lane/depth parameters;
- add focused tests required to establish feasibility.

Do not launch the full R1 aggregation in this task.

Do not change production serving.

## Required result

Write:

`horse-racing/jrdb/docs/edgedb/v0_4/collab/results/20261005_001_r0-existing-asset-audit_result.md`

The result must include:

- Status: DONE or BLOCKED;
- files inspected;
- reusable assets;
- defects / risks found;
- exact 5y-r3 failure diagnosis if available;
- required minimal code changes;
- proposed R1 execution command / entrypoint;
- proposed compact output schema;
- tests run;
- commits made;
- unresolved questions;
- recommended next action.

## Acceptance criteria

R0 is complete when ChatGPT can answer, from the result alone:

1. Can the current code safely run trailing 3y?
2. Can it restrict to Wave A without rebuilding everything?
3. What caused the failed 5y run?
4. Which execution route should R1 use?
5. What exact code changes are needed before R1?
6. What compact outputs will R1 return?

## Non-goals

- no full 3y aggregation;
- no full 5y aggregation;
- no depth 4-6 expansion;
- no candidate promotion;
- no SHADOW publication;
- no production modification;
- no threshold optimization against observed ROI.
