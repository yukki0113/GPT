# EdgeDB v0.4 R3 — Frozen PEDIGREE_CROSS 5y Extension

Status: TODO  
Date: 2026-10-05  
Research decision owner: ChatGPT  
Execution worker: Codex  
Production impact: NONE

## Objective

Execute a frozen 5-year validation for the single family selected by canonical R1:

`PEDIGREE_CROSS` → `EXTEND_FROZEN_FAMILY_TO_5Y`

The 3-year canonical R1 is accepted under fallback run `37321021557`, source commit `9aba7103f944ea419189c104be4e48485b819d0d`. The 5-year run tests temporal stability for this already selected family; it must not change the family definition, candidate thresholds, or C1 support floors.

Do not execute depth-4 or higher candidates in this task. Do not expand any other family.

## Mandatory Data Storage local-first → Actions fallback

Read and follow these repository documents before running:

- `tools/data-storage/README.md`
- `tools/data-storage/docs/CODEX_LOCAL_FIRST_ACTIONS_FALLBACK.md`
- `.gpt/GITHUB_OPERATION_POLICY.md`

From the repository root:

1. check `.venv-data-storage` and run `PYTHONPATH=tools/data-storage .venv-data-storage/bin/python -m data_storage check-deps`;
2. if dependencies are missing, make one normal install attempt from `tools/data-storage/requirements.txt` and rerun `check-deps`;
3. if the managed runtime blocks installation, use a validated `[DATA_STORAGE_FALLBACK]` Issue with `.github/workflows/data_storage_fallback_issue.yml`;
4. do not substitute another engine for canonical DuckDB SQL or repeatedly retry a blocked install.

The Actions source ref must be pinned to the successful canonical source commit above, or to a later reviewed commit that contains all the same canonical modules, fallback runner/workflow, and shared NumPy dependency. Record the exact resolved source commit. Do not run from a dirty or ambiguous tree.

## Frozen research inputs

Use the original, immutable upstream Actions artifacts and verify extracted file hashes inside the run before any research step:

### Feature Mart

- run: `36116777782`
- artifact: `jrdb-edge-feature-mart-parquet-36116777782`
- expected `edge_runner_fact.parquet` SHA-256: `82e6550639210eea6cf1fc1ac374ee8b6fc07115214fe75ea6e1bb704d3751f6`
- expected rows: `781161`

### Stage B catalog

- run: `36262821119`
- artifact: `jrdb-edge-v04-stage-b-36262821119`
- expected `candidate_template_catalog.parquet` SHA-256: `cf70098156283e42df49cc61d4988f1d2b578a4dbf4135c8121eb81262d5d2ba`
- expected catalog rows: `47371`

Declare both as upstream Actions artifacts in the fallback request. No Google Drive transport is required.

## Frozen window and candidate definition

- discovery years: `5`
- as-of date: `2025-12-28`
- inclusive window: `2020-12-28 .. 2025-12-28`
- lanes: `TRANSITION_PRIORITY`, `PEDIGREE_INTERACTION`, `PEDIGREE_BASELINE`
- depth: min 2, max 3
- family: `PEDIGREE_CROSS` only
- min win ROI: 110
- min place ROI: 105
- max per template: 100
- existing lane/depth support floors unchanged

Before C1 execution, create a deterministic, auditable family template selection from the pinned Stage B catalog using the pre-existing `family == PEDIGREE_CROSS` label, limited to the three Wave A lanes and depths 2–3. Record selected template count, per-lane/depth counts, sorted template-ID-set SHA-256, and shard plan SHA-256. Do not select templates based on 5-year results, ROI, support, or candidate performance.

If the family label, selected template set, or source/catalog provenance cannot be resolved deterministically, fail closed before evaluation and report the discrepancy. Do not broaden to other families to make the run succeed.

## Required canonical run

Use repository entrypoints; do not reproduce scientific logic inline.

1. Verify both frozen input hashes and expected row counts.
2. Generate and audit the frozen PEDIGREE_CROSS template subset and deterministic C1 shard plan.
3. Run each planned C1 shard sequentially through `horse-racing/jrdb/src/evaluate_jrdb_edge_v04_stage_c1_shard.py` with the frozen 5-year window, thresholds, depth, lanes, and support floors.
4. Merge with `horse-racing/jrdb/src/merge_jrdb_edge_v04_stage_c1_shards.py`; require all shard audits PASS, common hashes/window/plan, no missing shard, no duplicate candidate ID, and merge PASS.
5. Run canonical DuckDB C2A via `horse-racing/jrdb/src/prepare_jrdb_edge_v04_stage_c2.py`; do not modify its SQL predicates.
6. Run canonical C2B via `horse-racing/jrdb/src/evaluate_jrdb_edge_v04_stage_c2b_shard.py` with `--discovery-years 5` and the same as-of date; deterministically shard the exact request catalog.
7. Merge C2B through `horse-racing/jrdb/src/merge_jrdb_edge_v04_stage_c2b.py`. Validate one exact result per request ID, no missing/extra/duplicate IDs, consistent input hashes/window, and no missing value branches.
8. Produce bounded 5-year R1-style summary, report, and shortlist (shortlist <=100 rows) plus a 3y-to-5y comparison for PEDIGREE_CROSS. Retain full candidate and exact metric artifacts only in the Actions artifact, not Git.

## Required 3y-to-5y analysis

Use the canonical 3-year PEDIGREE_CROSS baseline from run `37321021557` and compare it with the canonical 5-year result. Report separately:

- selected templates, lane/depth plan, C1 candidate counts, and C2 shortlist counts;
- C2 entry routes, child-parent links, unique parent requests, and total exact requests;
- 3y vs 5y incremental/mixed/jackpot-dependent counts and rates;
- top3-exclusion failures, directional contradictions, one-year confinement, and no-365d support;
- depth-2 and depth-3 contribution;
- incremental support distributions and immediate-parent ROI/rate deltas;
- recent 365d/730d support and direction;
- overlap and additions/removals in candidate IDs where a reproducible 3y and 5y family identity set is available.

Do not introduce a composite score and do not retune thresholds based on these results. Label examples as research evidence, not betting recommendations.

## Acceptance

Mark the 5-year run valid only if input hashes match, the selected family/template identity is frozen before evaluation, every C1/C2A/C2B audit passes, the C2B request/result ID sets match exactly, and there is no threshold or production change. Otherwise report BLOCKED or FAILED with the exact failed guard; do not make a family expansion recommendation from partial outputs.

## Required result and Git scope

Write:

`horse-racing/jrdb/docs/edgedb/v0_4/collab/results/20261005_006_pedigree-cross-frozen-5y-extension_result.md`

If bounded, also store `r1_summary.json`, `r1_report.md`, and `shortlist.csv` under:

`horse-racing/jrdb/docs/edgedb/v0_4/collab/results/r1_wave_a_pedigree_cross_5y/`

Record source commit, fallback Issue/run/artifact/digest, Python/DuckDB/PyArrow versions, input hashes, family/template-set and plan hashes, all stage audits/counts, 3y-to-5y comparisons, exact C2B request/result integrity, decision, PR status, and `production impact = NONE`.

Do not commit Feature Mart data, full C1/C2B tables, or large shard outputs. Do not merge any PR automatically.

## Non-goals

- no non-PEDIGREE_CROSS family execution;
- no depth-4 or higher execution;
- no threshold/support-floor changes;
- no market/popularity-conditioned candidate generation;
- no SHADOW publication;
- no RaceNote/PWA integration;
- no v0.2/v0.3 production-serving change.
