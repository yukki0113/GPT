# EdgeDB v0.4 — Observe-Only Cohort Freeze / Prospective SHADOW Validation

Status: TODO  
Date: 2026-10-06  
Research decision owner: ChatGPT  
Execution worker: Codex  
Production impact: NONE

## Objective

Close historical search expansion for EdgeDB v0.4 and transition the surviving families into a frozen prospective SHADOW observation program.

Historical R3/R5 decisions are now:

- `PEDIGREE_CROSS` -> `PEDIGREE_CROSS_5Y_MIXED_OBSERVE_ONLY`
- `PEDIGREE_TRANSITION_CROSS` -> `KEEP_3Y_OBSERVE_ONLY`
- `TRANSITION_CROSS` -> `STOP_FAMILY_EXPANSION`

No family is authorized for depth-4+ search.

This task must create a reproducible observe-only cohort and the machinery/contract for prospective pre-race matching and post-result evaluation without reopening historical candidate discovery.

## Scientific boundary

This is no longer a discovery task.

Do not:

- add candidate dimensions;
- add depth;
- retune ROI/support thresholds;
- extend historical windows to improve fit;
- regenerate candidates from current/future outcomes;
- use current-race popularity/odds to decide cohort membership;
- promote any family to production;
- alter v0.2 STANDARD or v0.3 SHADOW serving.

The only allowed work is freezing the already observed candidate/cohort definitions and validating them prospectively.

## Canonical historical evidence

Read and treat as authoritative:

- 3y canonical result:
  `horse-racing/jrdb/docs/edgedb/v0_4/collab/results/20261005_005_r1-canonical-actions-fallback-rerun-and-r3_result.md`
- 5y PEDIGREE_CROSS result:
  `horse-racing/jrdb/docs/edgedb/v0_4/collab/results/20261006_007_resume-pedigree-cross-5y-after-family-planner-unblock_result.md`
- compact 3y outputs:
  `horse-racing/jrdb/docs/edgedb/v0_4/collab/results/r1_wave_a_3y_canonical/`
- compact 5y outputs:
  `horse-racing/jrdb/docs/edgedb/v0_4/collab/results/r1_wave_a_pedigree_cross_5y/`

Do not use PR #1800/#1801/#1809 as research truth.

## Families in observe-only program

### A. PEDIGREE_CROSS

Historical status:

`PEDIGREE_CROSS_5Y_MIXED_OBSERVE_ONLY`

Use only candidates that are already present in the accepted historical canonical evidence and satisfy the frozen observe-only selection contract defined below.

### B. PEDIGREE_TRANSITION_CROSS

Historical status:

`KEEP_3Y_OBSERVE_ONLY`

Use only candidates already present in the accepted 3y canonical evidence.

Do not extend this family to 5y in this task.

### C. TRANSITION_CROSS

Historical status:

`STOP_FAMILY_EXPANSION`

Do not include it in the prospective cohort.

## Observe-only cohort selection contract

The prospective cohort must be derived deterministically from accepted canonical candidate outputs, not by fresh historical search.

### PEDIGREE_CROSS source

Use the accepted 5y canonical compact/full artifact evidence where available.

Eligible historical label:

- `INCREMENTAL_CANDIDATE`

Exclude:

- `JACKPOT_DEPENDENT`
- `PARENT_REDUNDANT`
- `TEMPORALLY_THIN`
- any candidate whose exact definition/provenance cannot be reconstructed
- any candidate with semantic duplicate identity that cannot be disambiguated

### PEDIGREE_TRANSITION_CROSS source

Use accepted 3y canonical evidence.

Eligible historical label:

- `INCREMENTAL_CANDIDATE`

Apply the same exclusions above.

### No historical reranking

Do not invent a new score or cutoff.

If the eligible cohort is large, preserve all eligible unique candidate definitions and separate:

- canonical cohort membership;
- presentation priority.

Presentation priority may be deterministic for review convenience but must not affect membership.

## Semantic deduplication

Before freezing:

1. normalize each candidate to a canonical condition fingerprint;
2. preserve family, depth, lane, template/candidate ID, and all conditions;
3. detect exact duplicate condition fingerprints;
4. detect obvious semantic duplicates caused only by ordering/serialization differences;
5. do not merge non-equivalent candidates merely because they are correlated;
6. retain a duplicate map if multiple historical IDs resolve to one exact semantic condition.

The frozen cohort must have one canonical condition fingerprint per prospective matcher row.

Record:

- source candidate count;
- exact duplicate count;
- deduplicated cohort count;
- duplicate map count.

## Cohort freeze artifact

Create a versioned, immutable SHADOW research cohort.

Suggested path:

`horse-racing/jrdb/config/edgedb/v0_4/observe_only_cohort_v0_1.json`

or an equivalent repository-appropriate path if a better existing EdgeDB config location exists.

Required fields per row:

- `cohort_id`
- `family`
- `historical_source` (3y or 5y canonical)
- `candidate_id`
- `template_id` if available
- `search_lane`
- `depth`
- `conditions`
- `condition_fingerprint`
- `historical_label`
- historical support/ROI diagnostics needed only for audit
- parent incrementality summary needed only for audit
- `status = OBSERVE_ONLY`
- `production_eligible = false`

Top-level metadata:

- schema version;
- generated_at;
- source commits;
- source result file SHAs;
- source artifact/run IDs where relevant;
- family inclusion/exclusion policy;
- cohort row count;
- fingerprint-set SHA-256;
- `market_or_popularity_used_for_membership = false`;
- `production_impact = NONE`.

## Matching semantics

Implement or reuse a matcher that evaluates the frozen cohort against current/pre-race facts.

Preferred principle:

- reuse existing Edge v0.4 condition semantics;
- do not reimplement feature meaning in the matcher if a canonical evaluator/matcher already exists;
- matcher must be deterministic;
- matcher must use pre-race available values only.

Required output for a pre-race day/race:

- race identity;
- horse identity;
- cohort_id;
- family;
- candidate_id;
- matched conditions;
- match timestamp/as-of;
- source fact provenance;
- `result_opened = false`;
- `market_used_for_match = false`.

If multiple cohort rows match one horse, preserve all raw matches.

Do not collapse overlapping matches into a single score.

## Prospective freeze contract

For each prospective observation date:

1. materialize pre-race facts only;
2. run frozen cohort matcher;
3. write a match freeze;
4. hash the freeze;
5. validate that result/settlement fields are absent;
6. record freeze timestamp and source identities;
7. only after freeze PASS may result data be opened.

Suggested freeze path:

`horse-racing/jrdb/data/edgedb/v0_4/shadow_freezes/YYYYMMDD/`

If repository policy excludes generated day data from Git, store only the compact manifest/report in Git and keep full freeze in the approved artifact/data store.

Required freeze manifest:

- target date;
- as-of/freeze timestamp;
- cohort version + SHA;
- pre-race source identities/hashes;
- race/horse count;
- raw match count;
- unique matched horse count;
- family match counts;
- no-result-leakage validation;
- output SHA.

## Post-result evaluation

After a prospective freeze exists and passes validation:

1. obtain result data through the normal JRDB post-result route;
2. join by race/horse identity;
3. compute forward metrics without changing cohort membership;
4. preserve both raw match-level and unique-horse views.

Evaluate at minimum:

### Performance lane

- n;
- win/place hit count/rate;
- race-day dispersion;
- venue/class/surface/distance context counts.

### Value lane

Only after freeze:

- win/place ROI;
- top1 contribution;
- ex-top1 ROI;
- ex-top3 ROI;
- payout concentration;
- market/popularity diagnostics.

Do not use market diagnostics retroactively to alter frozen cohort membership.

## Prospective observation units

Report at least:

- by family;
- by cohort_id;
- by race day;
- aggregate all observed days.

Keep overlapping candidate matches explicit.

Do not add overlapping ROI as independent value.

## Minimum evidence before any later promotion discussion

This task does not promote anything.

Define a future review gate only.

Before any later SHADOW catalog/promotion discussion, require at minimum:

- multiple distinct race days;
- multiple independent hits where applicable;
- non-trivial support;
- no single-payout domination;
- parent/context logic still interpretable;
- prospective direction not materially contradicting historical claim.

Do not hard-code a numeric promotion threshold unless one already exists in canonical policy.

## Current-date handling

Do not backfill a "prospective" freeze using results already known to the execution process.

If no clean unseen date is available at execution time:

- create the cohort;
- create matcher/freeze/validator tooling;
- run only fixtures or explicitly historical reproduction tests;
- report `READY_FOR_NEXT_TRUE_FORWARD_DATE`.

Do not pretend historical replays are prospective evidence.

## Data Storage routing

For Parquet / DuckDB tasks follow:

- `tools/data-storage/README.md`
- `tools/data-storage/docs/CODEX_LOCAL_FIRST_ACTIONS_FALLBACK.md`

Local-first:

1. `.venv-data-storage`
2. `check-deps`
3. one normal repair attempt
4. if managed proxy/network blocks repair, use `[DATA_STORAGE_FALLBACK]`

Do not substitute another engine for canonical DuckDB logic solely because local dependencies are unavailable.

## Required implementation outputs

At minimum create/update:

1. frozen observe-only cohort artifact/config;
2. cohort builder/freezer script;
3. deterministic pre-race matcher or adapter;
4. freeze validator;
5. post-result evaluator;
6. focused tests for:
   - membership immutability;
   - exact fingerprint stability;
   - no-result leakage;
   - market/popularity not used for matching;
   - duplicate handling;
   - repeated run determinism.

Use existing canonical modules where possible. Avoid duplicate scientific semantics.

## Required research result

Write:

`horse-racing/jrdb/docs/edgedb/v0_4/collab/results/20261006_008_observe-only-cohort-freeze-and-prospective-shadow_result.md`

Required fields:

- Status;
- exact source commit;
- cohort source evidence;
- family inclusion/exclusion counts;
- duplicate/dedup counts;
- frozen cohort row count;
- cohort fingerprint-set SHA-256;
- matcher implementation path;
- validator path;
- post-result evaluator path;
- tests and results;
- whether a true-forward date was executed;
- if yes: target date, freeze artifact/manifest, pre-result validation, post-result summary;
- if no: `READY_FOR_NEXT_TRUE_FORWARD_DATE`;
- production impact = NONE.

## Decision outputs allowed

This task may end in one of:

- `READY_FOR_NEXT_TRUE_FORWARD_DATE`
- `TRUE_FORWARD_FREEZE_COMPLETED_AWAITING_RESULTS`
- `TRUE_FORWARD_OBSERVATION_RECORDED`
- `BLOCKED`

Do not output a production promotion decision.

## Non-goals

- no historical candidate discovery;
- no depth-4+ search;
- no 5y extension for PEDIGREE_TRANSITION_CROSS;
- no TRANSITION_CROSS resurrection;
- no threshold retuning;
- no market-conditioned membership;
- no production Edge Registry publication;
- no RaceNote/PWA mark logic change;
- no v0.2/v0.3 serving change.
