# EdgeDB v0.4 R1 DuckDB Equivalence / R3 Branch Decision — Instruction

Status: TODO  
Date: 2026-10-05  
Research decision owner: ChatGPT  
Execution worker: Codex  
Production impact: NONE

## Objective

Before advancing EdgeDB v0.4 beyond the R1 Wave A 3y result in PR #1800, validate that the temporary PyArrow reproduction of C2A is exactly equivalent to the repository's canonical DuckDB C2A implementation.

If equivalence passes, use the validated R1 evidence to produce the R3 branch decision package: which families should remain 3y, which deserve a frozen 5y extension, which may justify controlled depth-4 expansion, and which should stop.

Do not start the 5y or depth-4 execution in this task.

## Mandatory repository data-storage preflight

This repository already has a shared Parquet / DuckDB utility layer:

`tools/data-storage/`

Canonical guide:

`tools/data-storage/README.md`

For **every Parquet / DuckDB task in this repository**, do not conclude that DuckDB/Parquet is unavailable merely because the current Python interpreter cannot import it.

Required preflight:

1. inspect `tools/data-storage/README.md`;
2. check for the dedicated `.venv-data-storage`;
3. run the repository dependency check;
4. if missing/broken, bootstrap or repair from `tools/data-storage/requirements.txt`;
5. rerun `check-deps`;
6. use the shared environment / CLI for Parquet and DuckDB work whenever applicable.

Canonical commands from repository root:

```bash
if [ ! -x .venv-data-storage/bin/python ]; then
  python -m venv .venv-data-storage
  .venv-data-storage/bin/python -m pip install -r tools/data-storage/requirements.txt
fi

PYTHONPATH=tools/data-storage \
  .venv-data-storage/bin/python -m data_storage check-deps
```

If the environment exists but dependency check fails:

```bash
.venv-data-storage/bin/python -m pip install -r tools/data-storage/requirements.txt
PYTHONPATH=tools/data-storage \
  .venv-data-storage/bin/python -m data_storage check-deps
```

DuckDB is pinned by the repository to version `1.1.3`.

Only report DuckDB as unavailable if this repository-standard bootstrap/check path itself genuinely fails or is prohibited.

Do not implement another project-local Parquet/DuckDB dependency path unless there is a concrete gap in `tools/data-storage/`.

## PR #1800 status

PR:

`#1800 research(jrdb): record EdgeDB v0.4 R1 Wave A 3y results`

Observed R1 facts:

- 1,106 templates / 6 shards;
- C1 merge: 68,685 candidates;
- C2A reproduced via PyArrow because the executor incorrectly treated DuckDB as unavailable;
- PyArrow-reproduced C2A: 17,807 shortlist;
- C2B: 30,733 / 30,733 exact metric requests/results;
- incrementality labels:
  - INCREMENTAL_CANDIDATE: 367
  - JACKPOT_DEPENDENT: 17,350
  - MIXED_PARENT_INCREMENTALITY: 90
- production impact: NONE.

The scientific thresholds were not intentionally changed, but the canonical DuckDB C2A path was not executed.

## Preconditions

Prefer to run this task after PR #1800 is merged into main.

If PR #1800 is still open:

- inspect its current state;
- do not silently assume its result files are on main;
- either work from the exact PR head commit with explicit provenance, or stop with a clear instruction that merge is required first.

Do not recreate the R1 result from chat text.

## Phase A — Canonical DuckDB C2A equivalence validation

Using the same merged C1 research candidate artifact / frozen inputs used by R1:

- run the canonical:
  `horse-racing/jrdb/src/prepare_jrdb_edge_v04_stage_c2.py`
- run it with the repository-standard DuckDB environment from `tools/data-storage/`;
- do not modify C2A SQL predicates or thresholds.

Compare the canonical DuckDB outputs against the PyArrow fallback outputs used for PR #1800.

At minimum compare exact identity/counts for:

1. C2 shortlist candidate IDs;
2. `c2_entry_route`;
3. child metric request IDs;
4. child-parent map rows;
5. parent metric request IDs;
6. complete metric request catalog IDs;
7. route/depth/lane counts.

Required outcome:

### EQUIVALENT

All identity sets and relevant classifications are identical.

If ordering differs only, normalize and compare as sets/sorted records.

### NOT_EQUIVALENT

Any candidate/request/parent membership differs, even if aggregate counts match.

If NOT_EQUIVALENT:

- do not proceed to R3 branch decision;
- identify the exact predicate/typing/null/ordering semantic difference;
- produce a correction plan;
- do not tune thresholds.

## Phase B — Determine whether C2B rerun is required

If canonical DuckDB C2A is exactly equivalent at the metric-request catalog level, the existing C2B exact metrics may be reused because the input request IDs are identical and C2B itself ran the canonical evaluator unchanged.

In that case:

- verify the C2B request catalog hash / ID set corresponds exactly to the DuckDB C2A request set;
- no C2B rerun is required solely for tool-path purity.

If the metric request set differs:

- invalidate the affected C2B result;
- do not make R3 decisions from mismatched exact metrics.

## Phase C — PR #1800 acceptance audit

If equivalence passes, mark the R1 result scientifically accepted with the following caveat resolved:

> C2A PyArrow fallback was independently verified against canonical DuckDB C2A and produced identical candidate/request identity.

Check also:

- PR #1800 changed only intended research result assets;
- production serving remains unchanged;
- no threshold tuning occurred;
- no full candidate Parquet / raw Feature Mart was committed;
- bounded shortlist remains <=100 rows;
- hashes/provenance remain internally consistent.

Do not merge PR #1800 automatically unless explicitly required by the current repository workflow / user instruction. If already merged, report merge SHA.

## Phase D — R3 branch decision package

Using only validated R1 evidence, classify research families separately.

Families currently observed:

- `PEDIGREE_CROSS`
- `PEDIGREE_TRANSITION_CROSS`
- `TRANSITION_CROSS`

For each family, summarize:

- C1 candidate count;
- C2 shortlist count;
- INCREMENTAL_CANDIDATE count and rate;
- MIXED_PARENT_INCREMENTALITY count/rate;
- JACKPOT_DEPENDENT count/rate;
- top3-exclusion failures;
- 730d/full-3y directional contradictions;
- single-year confinement;
- no-365d-support cases;
- depth-2 vs depth-3 contribution;
- support distribution of incremental candidates;
- minimum/median parent ROI deltas where available;
- recent 365/730 support and direction for incremental candidates.

Do not introduce a composite score.

### Allowed R3 family decisions

For each family choose exactly one:

- `KEEP_3Y_AND_ALLOW_DEPTH4_DESIGN`
- `EXTEND_FROZEN_FAMILY_TO_5Y`
- `KEEP_3Y_OBSERVE_ONLY`
- `STOP_FAMILY_EXPANSION`

Decision guidance:

#### KEEP_3Y_AND_ALLOW_DEPTH4_DESIGN

Use only when 3y already has a coherent subset with:

- multiple non-jackpot incremental candidates;
- reasonable temporal dispersion;
- evidence that added dimensions matter beyond parents;
- enough support that 5y is not required merely to establish existence.

This does **not** authorize a depth-4 run yet. It only authorizes designing a prefix/parent-controlled depth-4 expansion.

#### EXTEND_FROZEN_FAMILY_TO_5Y

Use when:

- 3y has plausible incremental patterns;
- but support / temporal dispersion is too thin to distinguish signal from recent noise;
- candidate definitions and thresholds can be frozen before extension.

The 5y run must reuse the same as-of date `2025-12-28` and must not retune thresholds.

#### KEEP_3Y_OBSERVE_ONLY

Use when useful evidence exists but is not strong enough to justify compute expansion yet.

#### STOP_FAMILY_EXPANSION

Use when evidence is overwhelmingly jackpot-dependent, parent-redundant, temporally unstable, or too weak to justify further search.

## Phase E — Candidate-family examples

For each family, provide a bounded set of representative examples:

- 5–10 strongest non-jackpot incremental examples;
- 3–5 examples rejected for jackpot dependence or temporal instability;
- readable conditions;
- child metrics;
- immediate-parent comparisons;
- temporal diagnostics.

Do not present these examples as betting recommendations.

## Required result

Write:

`horse-racing/jrdb/docs/edgedb/v0_4/collab/results/20261005_004_r1-duckdb-equivalence-and-r3-branch-decision_result.md`

Required fields:

- Status: DONE / BLOCKED / NOT_EQUIVALENT;
- repository main/head used;
- PR #1800 state and merge SHA if applicable;
- `tools/data-storage` preflight result;
- Python executable/environment used;
- DuckDB version;
- canonical C2A command;
- exact equivalence comparison result;
- set/count/hash comparisons;
- whether C2B reuse is valid;
- R1 acceptance decision;
- per-family R3 decision;
- supporting metrics;
- representative examples;
- recommended next task;
- production impact = NONE.

## If equivalence passes: prepare the next execution instruction

Also create the **next instruction document** in:

`horse-racing/jrdb/docs/edgedb/v0_4/collab/instructions/`

The next instruction must be derived from the R3 family decisions.

It may contain:

- frozen selected-family 5y extension;
- controlled depth-4 design/preflight;
- both, if different families require different paths.

It must again explicitly state the mandatory `tools/data-storage/` Parquet/DuckDB preflight.

Do not execute that next instruction in this task.

## Non-goals

- no actual 5y family execution;
- no actual depth-4 expansion;
- no threshold tuning;
- no market/popularity-conditioned generation;
- no SHADOW publication;
- no RaceNote/PWA integration;
- no v0.2/v0.3 production serving changes.
