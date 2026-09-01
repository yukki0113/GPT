# JRDB Work INBOX 20260901-005

request_id: JRDB-WORK-20260901-005
issued_at: 2026-09-01 JST
supersedes: JRDB-WORK-20260901-004
required_outbox_filename: JRDB_Work_OUTBOX_20260901_005.md

## 1. Objective

Complete the existing-horse Ability development comparison by correcting the runtime implementation only.

The first real-history run `33464016734` is now classified by Controller as `SUPERSEDED_RUNTIME` because the comparison implementation repeated expensive work and the workflow hid all build/comparison subphases inside one step.

Do not change any model-selection semantics from `Ability_Model_Comparison_Protocol_v0_1.md`.

## 2. Read first

File Library:
- `JRDB_Work_OUTBOX_20260901_004.md`
- `JRDB_Work_Library_Exchange_Protocol_v0_1.md`

GitHub latest main:
- `horse-racing/jrdb/docs/Ability_Model_Comparison_Protocol_v0_1.md`
- `horse-racing/jrdb/docs/Ability_Comparison_Runtime_Correction_v0_1.md`
- `horse-racing/jrdb/docs/Ability_Development_Protocol_v0_1.md`
- `horse-racing/jrdb/docs/JRDB_Work_INBOX_20260901_004.md`
- current `compare_jrdb_ability_models.py`
- current `.github/workflows/jrdb_ability_compare_issue.yml`
- related tests

The runtime-correction document is authoritative for technical treatment of the old run and optimization boundaries.

## 3. Old run disposition

Old run:

```text
Issue #292
Run 33464016734
Head SHA 2662bc910a442c992f659b310fc08d8167348f07
```

Treatment:

1. If an authorized cancellation route is available, cancel it.
2. If cancellation is unavailable, do not wait for it; mark it `SUPERSEDED_RUNTIME` and proceed.
3. If it finishes successfully while 005 is in progress, save its artifact/result for equivalence comparison only.
4. A timeout/failure of the old run is a technical runtime failure, not model evidence.
5. The optimized rerun is the canonical run for Controller selection.

Record final old-run disposition in OUTBOX.

## 4. Frozen semantics

Do not change:

- development years 2013-2023
- clean source data only through 2023
- existing horses only
- A0 D070/D080/D090/D100
- all 144 feature transforms
- Ridge alpha grid 0.01/0.1/1/10/100
- Elastic Net top-10 transform procedure
- Elastic Net alpha/l1 grid
- aptitude/jockey shrink formulas
- fold-local preprocessing
- primary/secondary metrics
- strata
- holdout boundary
- no model promotion

2024-2025 Ability predictive data remain unopened.

## 5. Comparator optimization

Implement behavior-preserving optimization following `Ability_Comparison_Runtime_Correction_v0_1.md`.

Minimum requirements:

### 5.1 Load once / columnar cache

Load eligible rows once and prepare NumPy/columnar arrays for features, labels, years, race groups, and strata.

Avoid reconstructing full feature vectors from row dictionaries for every alpha.

### 5.2 Fold cache

Precompute train/test indices per test year once.

### 5.3 Race metric cache

Precompute race group indices/slices per test year and target-dependent ranks/percentiles once.

Do not use repeated full-array boolean scans `races == race` inside every candidate evaluation.

### 5.4 Transform/fold reuse

For each transform and test year:
- construct X train/test once
- fit fold-local median/scaling once
- reuse across all Ridge alphas

### 5.5 Ridge path

Share decomposition / sufficient statistics across five alphas when practical.

Closed-form/decomposition implementation is allowed only when equivalent to the frozen Ridge objective and intercept handling.

### 5.6 Elastic Net reuse

For the selected top-10 transforms, reuse fold-local transformed X across all six Elastic Net parameter pairs.

Precomputed Gram / warm starts / path solvers are allowed if objective and deterministic behavior remain equivalent.

### 5.7 Progress output

Comparator should emit progress at meaningful phase/fold boundaries so a long CI run is diagnosable.

## 6. Equivalence tests

Before full real-history rerun, compare optimized behavior against the current reference implementation on deterministic fixture(s) and a restricted real-history/dev subset where practical.

Required checks:
- candidate counts equal
- folds equal
- A0 metrics equal
- Ridge predictions/metrics within documented tight tolerance
- Elastic Net predictions/metrics within documented solver tolerance
- same top-10 Ridge transforms except documented numerical ties
- same primary/secondary metric definitions
- same strata definitions
- no 2024-2025 reads

If ranking changes materially beyond numerical tolerance, stop and return `BLOCKED`; do not silently accept the faster implementation.

## 7. Workflow observability

Refactor `.github/workflows/jrdb_ability_compare_issue.yml` so the previously combined step is split into visible steps at least:

```text
Fetch Raw
Build Index Base
Audit Index Base
Build RunPerf
Audit RunPerf
Build Official RunPerf
Audit Official RunPerf
Build Ability Snapshot
Audit Ability Snapshot
Compare Ability models
Build result
Upload artifact
Comment result
```

The workflow still uses clean 2010-2023 data.

## 8. Regression gates

Run existing 004/003/upstream relevant tests plus new runtime-equivalence tests.

No regression may relax chronology/leakage/model-boundary tests.

## 9. Canonical real-history rerun

After optimized implementation is merged to main, create a new Issue, suggested:

```text
[JRDB_ABILITY_COMPARE] 20260901-005-optimized
```

Execute the same frozen 2010-2023 build and 2013-2023 comparison.

The new run must generate:
- artifact
- machine-readable comparison
- lightweight Issue result
- development_end=2023
- holdout_touched=false
- 2024_2025_predictive_metrics_inspected=false
- model_promoted=false

## 10. Required comparison evidence

Return the same evidence originally requested in 004:
- best A0
- best Ridge
- best Elastic Net
- top 20 candidates
- all four A0 aggregate/annual results
- Ridge/Elastic Net compact grids
- paired annual deltas vs best A0
- coefficient histories for top regularized models
- career/surface/distance/course strata diagnostics
- fold train/test counts
- preprocessing leakage checks
- all violation counts

Work must not select/promote the official Ability model.

## 11. Runtime evidence

OUTBOX must also include:
- old_run_disposition
- old_run_final_status if known
- optimized comparator commit/PR
- equivalence test result/tolerances
- workflow step observability result
- optimized run ID
- optimized compare-step status
- total Actions run status
- any measured runtime/profile information available from completed CI metadata/logs

Do not invent timings that are not observed.

## 12. Acceptance

005 is `COMPLETE` only when:
- optimized code is merged to main
- equivalence gates PASS
- new real-history run completes
- all upstream audits PASS
- comparator status PASS
- full frozen grid executed
- development_end=2023
- holdout_touched=false
- 2024-2025 predictive metrics remain uninspected
- required annual/paired/strata evidence exists
- model_promoted=false

Weak model results are acceptable. Runtime or predictive weakness must not trigger methodological changes.

## 13. OUTBOX

Create and place in File Library:

`JRDB_Work_OUTBOX_20260901_005.md`

Status enum:
- COMPLETE
- PARTIAL
- BLOCKED
- FAILED

Mandatory fields in addition to Exchange Protocol:

```text
supersedes: JRDB-WORK-20260901-004
old_run_id: 33464016734
old_run_disposition
old_run_final_status
main_start_sha
main_finish_sha
optimization_pr_or_commits
equivalence_status
equivalence_tolerances
canonical_issue
canonical_run_id
artifact_id
comparison_status
development_years
holdout_touched
best_a0
best_ridge
best_elastic_net
top_candidates
paired_vs_best_a0
career_strata_summary
preprocessing_leakage_violations
all_violation_counts
2024_2025_predictive_metrics_inspected: false
model_promoted: false
ready_for_controller_model_decision: true/false
controller_decisions_requested
```
