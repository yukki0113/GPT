# EdgeDB v0.4 R1 Preflight / Wave-A Enablement — Instruction

Status: TODO  
Date: 2026-10-05  
Owner for research decision: ChatGPT  
Execution worker: Codex  
Production impact: NONE

## Objective

Implement the minimum safe changes identified by R0 so that EdgeDB v0.4 can run a reproducible trailing-3y Wave A screen, then validate the execution path with focused tests and one representative shard resource preflight.

This task does **not** run the full R1 aggregation.

## Canonical references

Research redesign:

`horse-racing/jrdb/docs/edgedb/v0_4/EdgeDB_v0_4_Research_Execution_Redesign_20261005.md`

R0 result:

`horse-racing/jrdb/docs/edgedb/v0_4/collab/results/20261005_001_r0-existing-asset-audit_result.md`

Original v0.4 design:

`horse-racing/jrdb/docs/EdgeDB_v0_4_HighOrder_Transition_Value_Discovery_Design_20260926.md`

## R0 acceptance

Treat R0 as accepted.

Important findings to preserve:

- the 5y r3 failure was an undefined-`max_date` code defect, not evidence that 5y itself is computationally infeasible;
- current Stage B catalog is reusable;
- Wave A should be selected in the planner, not by mutating the canonical catalog and not by evaluator-side hidden filtering;
- 3y support is currently code-inspected but not regression-tested;
- full R1 must remain gated until this task passes.

## Required changes

### 1. Planner lane/depth selection

Update:

`horse-racing/jrdb/src/plan_jrdb_edge_v04_stage_c1_shards.py`

Add:

- repeatable `--search-lane`;
- `--min-depth`;
- `--max-depth`.

Required behavior:

- filter the in-memory Stage B catalog before grouping / shard assignment;
- never rewrite the source catalog;
- empty selection must fail closed;
- every selected template must be assigned exactly once;
- unselected templates must not appear in the plan;
- the plan must preserve the source catalog SHA-256;
- the plan must record requested lanes/depth range and actual selected lane/depth counts;
- shard partitioning must remain result/ROI/odds/popularity blind.

Wave A canonical request:

- `TRANSITION_PRIORITY`
- `PEDIGREE_INTERACTION`
- `PEDIGREE_BASELINE`
- depth 2–3

Do not add STATIC_CROSS as a broad default Wave A lane merely to increase coverage.

### 2. Explicit reproducible as-of date

R0 noted that C1/C2B derive the endpoint from the maximum date in the supplied artifact. For research comparison, make the endpoint explicit and reproducible.

Update both:

- `evaluate_jrdb_edge_v04_stage_c1_shard.py`
- `evaluate_jrdb_edge_v04_stage_c2b_shard.py`

Add optional:

`--as-of-date YYYY-MM-DD`

Required semantics:

- if omitted, retain current behavior: derive from maximum valid `race_date`;
- if supplied, validate ISO date;
- supplied as-of must not exceed the maximum valid date in the source artifact;
- filter upper bound must be `race_date <= as_of_date`;
- lower bound is calendar `as_of_date - discovery_years`;
- window endpoints are inclusive;
- rows later than an explicit as-of must not influence support, ROI, recent metrics, or any candidate/parent metric;
- record requested/resolved as-of in audit output;
- C1 and C2B must use the same semantics.

Reason:

The later 3y -> 5y comparison must be able to freeze the same endpoint even if a newer Feature Mart becomes available.

### 3. Discovery-years validation

In C1 and C2B:

- reject `discovery_years <= 0`;
- reject missing/all-null/malformed date domains cleanly;
- do not silently use sentinel dates to form a research window.

Do not change the scientific support floors or ROI screening thresholds in this task.

### 4. Focused regression tests

Add a dedicated EdgeDB v0.4 test module or modules covering at least:

#### Planner

- lane filter selects only requested lanes;
- depth 2–3 selects only those depths;
- every selected template is assigned exactly once;
- unselected template IDs are absent;
- empty selection fails;
- source catalog digest/provenance is recorded;
- same input/options produce deterministic plan/shard assignment.

#### C1 date/window

Use a very small synthetic Parquet fixture.

Verify:

- explicit as-of upper bound excludes later rows;
- trailing 3 calendar years lower boundary is inclusive;
- Feb. 29 fallback behavior is deterministic;
- rows before the 3y window cannot affect support / ROI admission;
- 365/730/1095 metrics are evaluated relative to resolved as-of, not source max when explicit as-of is supplied;
- nonpositive discovery years fail;
- malformed/all-null dates fail.

#### C2B parity

Verify:

- C2B resolves the same start/end window as C1 for the same input, discovery years, and explicit as-of;
- rows outside the window cannot alter exact parent/child metrics.

Tests may refactor small date-window helpers into shared reusable code if doing so clearly reduces semantic drift, but do not perform a broad architecture rewrite.

## Representative resource preflight

After code/tests pass, execute **one representative Wave A shard only** if the pinned Feature Mart and Stage B artifacts can be resolved without inventing a new data route.

Preferred choice:

- depth 3;
- `TRANSITION_PRIORITY` or `PEDIGREE_INTERACTION`;
- choose a shard with estimated cost near the upper-middle / high end of Wave A, not the easiest shard.

Run with:

- `--discovery-years 3`;
- an explicit frozen `--as-of-date` equal to the chosen research endpoint;
- existing frozen C1 ROI thresholds;
- existing max-per-template policy.

Record:

- exact Feature Mart artifact/generation/hash;
- exact Stage B catalog artifact/hash;
- source commit;
- shard ID;
- selected template count;
- estimated cost;
- all-history row count;
- 3y row count;
- elapsed wall time;
- peak RSS / memory if measurable;
- output candidate count;
- output file size;
- audit status;
- whether local/Codex execution is practical for the full Wave A.

### Input resolution rule

Do not rebuild historical input merely because a prior Actions artifact expired.

Use existing canonical/current Edge Feature Mart / Stage B assets if repository/Drive/current artifact contracts identify them.

If the exact accepted Stage B catalog or Feature Mart cannot be resolved safely:

- complete the code + tests;
- mark only the resource-preflight subsection BLOCKED;
- state the exact missing asset and canonical resolution path needed;
- do not launch a broad rebuild in this task.

## Execution route decision

At the end, make one of these recommendations for full R1 Wave A:

- `LOCAL_SEQUENTIAL`
- `LOCAL_BOUNDED_PARALLEL`
- `ACTIONS_SHARDED`
- `BLOCKED_INPUT_RESOLUTION`

Base the recommendation on measured preflight evidence, not preference.

If local is viable, recommend a conservative parallelism value. Do not assume 12-way concurrency.

## Compact R1 report preparation

Do not build the full report pipeline yet unless trivial, but define/implement enough scaffolding that the next task can produce:

- `r1_summary.json`
- `r1_report.md`
- bounded `shortlist.csv`

The broad candidate parquet remains outside Git.

No shortlist thresholds may be retuned based on this one preflight shard.

## Required result

Write:

`horse-racing/jrdb/docs/edgedb/v0_4/collab/results/20261005_002_r1-preflight-and-wave-a-enable_result.md`

Include:

- Status: DONE or BLOCKED;
- files changed;
- planner filter semantics;
- as-of/window semantics;
- tests added and exact test results;
- representative preflight details and measurements, or exact blocker;
- chosen full-R1 execution route;
- expected Wave A template/shard counts from the filtered planner if inputs are available;
- commits made;
- remaining risks;
- exact recommended next command/task for R1.

## Acceptance criteria

This task is accepted only if ChatGPT can answer:

1. Is Wave A planning now market-blind, deterministic, and limited to the intended lanes/depth?
2. Is trailing 3y empirically protected by focused tests?
3. Can C1 and C2B freeze the same explicit as-of endpoint?
4. What does one realistic shard cost in time/memory/output?
5. Which route should full R1 use?
6. Are the exact canonical inputs pinned?

If code/tests pass but preflight input resolution is blocked, report partial completion clearly; do not call the resource preflight PASS.

## Non-goals

- no full R1 Wave A aggregation;
- no 5y run;
- no depth 4–6 run;
- no approved-prefix/value-pruning implementation yet;
- no threshold tuning;
- no candidate promotion;
- no v0.4 SHADOW publication;
- no v0.2/v0.3 production change.
