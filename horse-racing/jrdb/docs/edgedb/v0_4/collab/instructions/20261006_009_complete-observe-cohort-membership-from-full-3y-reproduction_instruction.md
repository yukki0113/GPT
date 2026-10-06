# EdgeDB v0.4 — Complete Observe-Only Cohort Membership from Full 3y Reproduction

Status: TODO  
Date: 2026-10-06  
Research decision owner: ChatGPT  
Execution worker: Codex  
Production impact: NONE

## Objective

Correct the observe-only cohort membership proposed in PR #1818 before merge.

The prospective SHADOW tooling is conceptually accepted, but the current cohort includes only 10 retained PEDIGREE_TRANSITION_CROSS presentation examples out of 81 accepted 3y INCREMENTAL_CANDIDATE rows.

Those 10 examples must not define prospective membership.

Reconstruct the full accepted 3y canonical enriched population using the frozen canonical R1 pipeline, then rebuild the cohort from the complete eligible populations.

## Blocking issue in PR #1818

Current proposed cohort:

- PEDIGREE_CROSS 5y incremental: 266 / 266 included
- PEDIGREE_TRANSITION_CROSS 3y incremental: 10 / 81 included
- total before dedup: 276

The 10 retained PEDIGREE_TRANSITION_CROSS rows come from the historical `strong_incremental` presentation examples.

Instruction 008 explicitly requires presentation priority not to affect cohort membership.

Therefore PR #1818 must not be merged until full canonical 3y membership is reconstructed.

## Scientific rule

This is reconstruction of an already accepted canonical result, not new historical discovery.

Must not change:

- Feature Mart;
- Stage B catalog;
- Wave A lanes;
- depths;
- as-of;
- discovery window;
- thresholds;
- support floors;
- C1/C2A/C2B implementation semantics;
- label classifier;
- family decisions.

No candidate may be added because it looks good in a new rerun. The rerun is accepted only if it exactly reproduces the already accepted canonical aggregate identities/counts.

## Accepted 3y canonical pins

Use the same immutable inputs as canonical R1.

Feature Mart:

- run `36116777782`
- artifact `jrdb-edge-feature-mart-parquet-36116777782`
- SHA-256 `82e6550639210eea6cf1fc1ac374ee8b6fc07115214fe75ea6e1bb704d3751f6`

Stage B:

- run `36262821119`
- artifact `jrdb-edge-v04-stage-b-36262821119`
- catalog SHA-256 `cf70098156283e42df49cc61d4988f1d2b578a4dbf4135c8121eb81262d5d2ba`

3y request:

- as-of `2025-12-28`
- inclusive window `2022-12-28 .. 2025-12-28`
- lanes:
  - TRANSITION_PRIORITY
  - PEDIGREE_INTERACTION
  - PEDIGREE_BASELINE
- depths 2–3
- win ROI threshold 110
- place ROI threshold 105
- max per template 100
- frozen planner SHA `de823224c0f10690232835b35557517c474377734b2df347ca3a9a08daa3ded8`

Accepted aggregate reproduction guards:

- selected templates: 1,106
- C1 merged candidates: 68,685
- C2A shortlist: 17,807
- child-parent links: 52,171
- unique parent metric requests: 14,129
- exact metric requests/results: 30,733
- INCREMENTAL_CANDIDATE: 367
- MIXED_PARENT_INCREMENTALITY: 90
- JACKPOT_DEPENDENT: 17,350
- PEDIGREE_CROSS incremental: 266
- PEDIGREE_TRANSITION_CROSS incremental: 81
- TRANSITION_CROSS incremental: 20

If any guard differs, fail closed and do not rebuild cohort.

## Data Storage routing

Follow repository standard:

- `tools/data-storage/README.md`
- `tools/data-storage/docs/CODEX_LOCAL_FIRST_ACTIONS_FALLBACK.md`

Local-first, then one normal repair attempt, then Actions fallback if managed network policy blocks dependencies.

Do not replace canonical DuckDB logic with another engine.

## Full 3y enriched export

Use the canonical R1 classifier unchanged and export the full enriched 3y candidate rows after successful reproduction.

The export must include at minimum:

- candidate_id
- template_id
- family
- lane
- depth
- conditions_json
- label
- child metrics
- immediate-parent comparisons
- lane diagnostics
- temporal warnings
- support_for_review
- minimum_parent_roi_delta

Verify candidate/template identity using the canonical candidate-ID construction.

The export is an audit/reconstruction artifact, not a new research ranking.

Full enriched data should remain in Actions artifact/data store; do not commit the entire full table to Git.

## Cohort rebuild

Rebuild `observe_only_cohort_v0_1` from exactly:

### PEDIGREE_CROSS

Source: accepted 5y full enriched population.

Membership:

- family == PEDIGREE_CROSS
- label == INCREMENTAL_CANDIDATE
- expected count before semantic dedup = 266

### PEDIGREE_TRANSITION_CROSS

Source: reproduced accepted 3y full enriched population.

Membership:

- family == PEDIGREE_TRANSITION_CROSS
- label == INCREMENTAL_CANDIDATE
- expected count before semantic dedup = 81

### TRANSITION_CROSS

Exclude entire family.

Expected total source membership before semantic dedup:

- 347 rows

Do not apply ranking, top-N, strongest-example, support percentile, ROI sorting, or presentation selection to membership.

## Deduplication

Apply the same exact semantic fingerprint logic already introduced in PR #1818.

Record:

- source membership count = 347
- exact duplicate count
- semantic duplicate count
- deduplicated cohort count
- duplicate map
- family counts before/after dedup
- fingerprint-set SHA-256
- cohort file SHA-256

If duplicates cross families, do not silently discard family provenance. Preserve a duplicate/provenance mapping that shows every historical candidate represented by the canonical matcher row.

## Tooling

Keep and update the PR #1818 tooling where scientifically valid:

- cohort builder/freezer
- pre-race matcher
- freeze validator
- post-result evaluator
- full 5y export helper
- tests

Modify the cohort builder so PEDIGREE_TRANSITION_CROSS membership comes from the full reproduced 3y enriched population, not `examples.strong_incremental`.

The bounded 3y examples may remain in reporting only.

## Required tests

Tests must cover at minimum:

1. full 347 source rows are eligible before dedup;
2. no presentation/top-N list affects membership;
3. family counts are correct before dedup;
4. fingerprint determinism;
5. semantic duplicate handling;
6. cohort immutability;
7. result leakage rejection;
8. market/popularity independence;
9. repeated freeze determinism;
10. overlapping raw matches preserved;
11. post-result unique-horse view;
12. result-open timing guard.

Run the focused suite and report exact test count/PASS.

## Prospective status

Do not run a historical date and call it prospective.

If no true unseen date is available during this task, end with:

`READY_FOR_NEXT_TRUE_FORWARD_DATE`

No result data should be opened.

## Required PR update

Update PR #1818 rather than creating an unrelated replacement PR unless technically necessary.

Replace:

- the 276-row cohort;
- cohort source metadata;
- result document counts;
- fingerprint/file SHAs;
- tests expecting 276/10 membership.

Retain valid prospective matcher/freeze/evaluator code after correction.

## Required result

Update:

`horse-racing/jrdb/docs/edgedb/v0_4/collab/results/20261006_008_observe-only-cohort-freeze-and-prospective-shadow_result.md`

The result must clearly state:

- full 3y canonical reproduction run/Issue/artifact;
- exact aggregate reproduction guards;
- full PEDIGREE_TRANSITION_CROSS 81-row reconstruction;
- final cohort membership before/after dedup;
- new fingerprint-set SHA;
- tests;
- `READY_FOR_NEXT_TRUE_FORWARD_DATE`;
- production impact = NONE.

## Merge gate

PR #1818 is mergeable only if:

- accepted 3y aggregates reproduce exactly;
- all 81 PEDIGREE_TRANSITION_CROSS incremental definitions are reconstructed;
- membership uses all eligible rows, not the retained top examples;
- cohort/tooling tests pass;
- no true-forward result data was opened;
- production impact remains NONE.

## Non-goals

- no new historical search;
- no threshold tuning;
- no depth-4+ work;
- no PEDIGREE_TRANSITION 5y extension;
- no TRANSITION_CROSS resurrection;
- no production publication;
- no RaceNote/PWA serving change.
