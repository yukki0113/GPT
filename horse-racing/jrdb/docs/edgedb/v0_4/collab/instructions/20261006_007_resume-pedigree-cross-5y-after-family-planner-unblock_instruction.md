# EdgeDB v0.4 R3 — Resume PEDIGREE_CROSS Frozen 5y After Family Planner Unblock

Status: TODO  
Date: 2026-10-06  
Research decision owner: ChatGPT  
Execution worker: Codex  
Production impact: NONE

## Objective

Resume the previously blocked 5-year validation for:

`PEDIGREE_CROSS` -> `EXTEND_FROZEN_FAMILY_TO_5Y`

The blocker recorded in PR #1809 has now been addressed on main by adding deterministic family-aware template selection to the canonical Stage C1 planner.

Do not treat PR #1809 as a terminal research result. It is a pre-evaluation blocker record only.

## Implemented unblock on main

The canonical preflight/planner now supports:

`--family PEDIGREE_CROSS`

and records:

- requested families;
- selected template counts by family;
- selected template counts by lane;
- selected template counts by depth;
- sorted selected-template-ID SHA-256;
- original full Stage B catalog SHA-256.

Relevant main changes:

- `horse-racing/jrdb/src/jrdb_edge_v04_preflight.py`
- `horse-racing/jrdb/src/plan_jrdb_edge_v04_stage_c1_shards.py`
- `horse-racing/jrdb/tests/test_jrdb_edge_v04_family_preflight.py`

Family selection is result-blind and is applied before partitioning. Shard assignment itself remains based only on lane, depth, template ID, and estimated cost.

## Mandatory preflight

Read:

- `tools/data-storage/README.md`
- `tools/data-storage/docs/CODEX_LOCAL_FIRST_ACTIONS_FALLBACK.md`
- `.gpt/GITHUB_OPERATION_POLICY.md`
- prior instruction:
  `horse-racing/jrdb/docs/edgedb/v0_4/collab/instructions/20261005_006_pedigree-cross-frozen-5y-extension_instruction.md`
- prior blocked result:
  `horse-racing/jrdb/docs/edgedb/v0_4/collab/results/20261005_006_pedigree-cross-frozen-5y-extension_result.md`
  if available on the PR branch.

Run the new focused test before evaluation:

```bash
python -m unittest horse-racing/jrdb/tests/test_jrdb_edge_v04_family_preflight.py
```

If the managed local environment lacks the required Data Storage dependencies:

1. perform the documented `check-deps`;
2. attempt one normal requirements repair;
3. if proxy/network policy blocks it, use `[DATA_STORAGE_FALLBACK]`;
4. do not stop again solely because local DuckDB/PyArrow installation is blocked.

## Source ref

Use current reviewed main containing:

- canonical R1 fallback infrastructure;
- NumPy Data Storage dependency;
- family-aware planner/preflight;
- family planner focused test.

Pin and report the exact resolved source commit.

Do not use the historical `9aba7103...` source because it predates the family-filter implementation.

## Frozen inputs

Keep exactly the same immutable inputs as instruction 006.

### Feature Mart

- run: `36116777782`
- artifact: `jrdb-edge-feature-mart-parquet-36116777782`
- expected extracted SHA-256:
  `82e6550639210eea6cf1fc1ac374ee8b6fc07115214fe75ea6e1bb704d3751f6`
- expected rows: `781161`

### Stage B catalog

- run: `36262821119`
- artifact: `jrdb-edge-v04-stage-b-36262821119`
- expected extracted catalog SHA-256:
  `cf70098156283e42df49cc61d4988f1d2b578a4dbf4135c8121eb81262d5d2ba`
- expected rows: `47371`

### Canonical 3y baseline

- fallback run: `37321021557`
- artifact: `data-storage-fallback-37321021557`

Use it for 3y-to-5y comparison only. Do not derive 5y template eligibility from 3y outcomes.

## Frozen selection request

Planner request must include:

- `--family PEDIGREE_CROSS`
- `--search-lane TRANSITION_PRIORITY`
- `--search-lane PEDIGREE_INTERACTION`
- `--search-lane PEDIGREE_BASELINE`
- `--min-depth 2`
- `--max-depth 3`

Before C1 evaluation, record and validate:

- source catalog SHA;
- source template count;
- requested family = exactly `PEDIGREE_CROSS`;
- selected family counts;
- lane/depth selected counts;
- selected template count;
- `selected_template_ids_sha256`;
- shard count;
- shard plan SHA-256.

Fail closed if any selected row is not `PEDIGREE_CROSS`.

Do not materialize a rewritten Stage B catalog as the new source of truth merely to filter the family. The full immutable catalog remains the provenance source; selection occurs in the planner.

## Frozen research window and thresholds

- discovery years: `5`
- as-of: `2025-12-28`
- inclusive window: `2020-12-28 .. 2025-12-28`
- family: `PEDIGREE_CROSS` only
- depths: 2–3 only
- min win ROI: 110
- min place ROI: 105
- max per template: 100
- existing lane/depth support floors unchanged
- no result/ROI/popularity/odds conditioned template selection

## Required canonical execution

Execute the same scientific stages defined in instruction 006, now using the valid family-filtered planner.

### 1. Verify inputs

Extract and hash-verify Feature Mart and full Stage B catalog before research execution.

### 2. Generate family-only plan

Use canonical:

`horse-racing/jrdb/src/plan_jrdb_edge_v04_stage_c1_shards.py`

with the frozen family/lane/depth selection above.

Audit exact family membership before continuing.

### 3. C1

Run each planned shard sequentially with:

`horse-racing/jrdb/src/evaluate_jrdb_edge_v04_stage_c1_shard.py`

using:

- discovery years 5;
- as-of 2025-12-28;
- unchanged thresholds;
- unchanged max-per-template.

Merge using canonical C1 merger.

Require all shard audits PASS and no duplicate candidate IDs.

### 4. C2A

Run canonical DuckDB:

`horse-racing/jrdb/src/prepare_jrdb_edge_v04_stage_c2.py`

No SQL/predicate reimplementation.

### 5. C2B

Run canonical C2B with discovery years 5 and same as-of.

Merge/audit exact metric request IDs and result IDs.

Require:

- no missing IDs;
- no extra IDs;
- no duplicates;
- common input hash/window;
- no missing value branches.

### 6. 3y-to-5y comparison

Compare only `PEDIGREE_CROSS` against canonical 3y baseline.

Report:

- selected template identity/count;
- C1 candidate count;
- C2 shortlist count;
- incremental/mixed/jackpot-dependent counts/rates;
- top3 exclusion failures;
- temporal contradictions;
- one-year confinement;
- recent 365/730 support;
- depth2/depth3 contribution;
- parent ROI/rate deltas;
- reproducible candidate-ID overlap/additions/removals where available.

Do not introduce a composite score.

## Decision after 5y

Choose one:

- `PEDIGREE_CROSS_5Y_STABLE_CONTINUE_DESIGN`
- `PEDIGREE_CROSS_5Y_MIXED_OBSERVE_ONLY`
- `PEDIGREE_CROSS_5Y_WEAK_STOP`
- `BLOCKED`

A continuation decision does not authorize depth-4 execution automatically. It only allows a subsequent controlled design instruction.

## Required result

Write:

`horse-racing/jrdb/docs/edgedb/v0_4/collab/results/20261006_007_resume-pedigree-cross-5y-after-family-planner-unblock_result.md`

If bounded outputs are useful, store them under:

`horse-racing/jrdb/docs/edgedb/v0_4/collab/results/r1_wave_a_pedigree_cross_5y/`

Allowed compact files:

- `r1_summary.json`
- `r1_report.md`
- `shortlist.csv`

The result must record:

- source commit;
- family planner test result;
- local preflight outcome;
- fallback Issue/run/artifact/digest if used;
- DuckDB/PyArrow versions;
- exact input hashes;
- family/template-set hash;
- plan hash;
- all C1/C2A/C2B integrity results;
- 3y-to-5y comparison;
- final family decision;
- production impact = NONE.

## PR #1809 disposition

If this resumed canonical run succeeds, PR #1809 is superseded by this result and should be closed/not merged unless there is an independent reason to preserve the blocker record in main.

## Non-goals

- no other family execution;
- no depth-4+ execution;
- no threshold/support-floor tuning;
- no market/popularity-conditioned generation;
- no SHADOW publication;
- no RaceNote/PWA integration;
- no v0.2/v0.3 production serving change.
