# Ability comparison runtime correction v0.1

## Status

**TECHNICAL CORRECTION ONLY — MODEL SEMANTICS FROZEN**

This record governs the runtime correction for the existing-horse Ability comparison after the first real-history run showed excessive runtime.

The frozen methodological specification in `Ability_Model_Comparison_Protocol_v0_1.md` is unchanged.

## Superseded execution

Original real-history run:

```text
Issue  #292
Run    33464016734
SHA    2662bc910a442c992f659b310fc08d8167348f07
Started 2026-09-01 11:50:10 JST
```

At the Controller review around 13:40 JST, the run was still inside the single workflow step:

```text
Clean 2010-2023 build and comparison
```

Regression tests had passed. No predictive result had been produced.

The run is classified as:

```text
SUPERSEDED_RUNTIME
```

This is a technical/runtime classification, not a model failure.

## Why the implementation is superseded

The first comparator repeated work at several levels:

- 144 feature transforms
- 5 Ridge alphas
- 11 annual folds
- 7,920 Ridge fits
- another 660 Elastic Net fits after the top-10 transform filter
- feature vectors reconstructed from Python dictionaries for every alpha/fold
- fold preprocessing repeated even when only alpha changed
- race-level metrics repeatedly built with full-row boolean masks for every race and candidate

The workflow also placed Raw fetch, all upstream builds/audits, snapshot build/audit, and comparison into one Actions step, making progress opaque.

## Treatment of the old run

1. Cancel run `33464016734` if an authorized cancellation path is available.
2. If cancellation is unavailable, allow it to finish or timeout, but mark it superseded.
3. If it successfully completes before the optimized run, preserve its report as comparison evidence.
4. Do not use it as the sole canonical 004 model-comparison evidence.
5. The optimized implementation must still run and must agree with the reference behavior within the equivalence tolerances below.

## Frozen semantics that must not change

Do not change:

- 2013-2023 development folds
- absence of 2024-2025 predictive labels/metrics
- existing-horse-only scope
- A0 candidates D070/D080/D090/D100
- full Ridge transform grid
- Ridge alphas `0.01,0.1,1,10,100`
- Elastic Net top-10-transform procedure
- Elastic Net alpha/l1 grid
- fold-local training-only imputation/scaling
- primary metric definition
- secondary metrics
- required strata
- missingness/shrink formulas
- no going/rest/market/current-result feature input
- no model promotion by Work

Optimization must be behavior-preserving.

## Required optimization direction

### 1. Columnar load

Load eligible rows once into NumPy/columnar arrays. Do not repeatedly reconstruct whole-dataset feature vectors from Python row dictionaries for every alpha.

Precompute:

- target
- year
- race id/group
- career stratum data
- raw recent candidates
- peak/stability inputs
- raw aptitude values/neff
- raw jockey value/n
- weight
- missing masks

### 2. Fold and race grouping cache

Precompute train/test row indices for every annual fold.

For each test year, precompute contiguous or indexed race groups once. Metric calculation must not repeatedly execute a whole-array `races == race` scan for each race.

Target within-race ranks/percentiles that do not depend on prediction should be cached once.

### 3. Transform-level matrix reuse

For one `(recent, bandwidth, aptitude_k, jockey_k, year)` transform/fold:

- create train/test X once
- fit train-only median/scaling once
- reuse the transformed matrices for every Ridge alpha

Do not re-run preprocessing merely because alpha changed.

### 4. Ridge multi-alpha computation

Because the feature dimension is small, Work may use an exact/equivalent closed-form or decomposition-based Ridge path so `X'X` / decomposition work is shared across the five alphas.

The objective and intercept behavior must remain equivalent to the frozen scikit-learn Ridge definition.

### 5. Elastic Net reuse

For the frozen top-10 transforms only, reuse fold-local transformed matrices across the six Elastic Net parameter pairs.

A precomputed Gram matrix, warm-start path, or equivalent deterministic solver optimization is allowed if the same Elastic Net objective is preserved.

### 6. Metric implementation

Keep the same metric definitions.

Optimize by:

- cached race slices/index lists
- vectorized global metrics
- cached target race ranks
- avoiding repeated whole-array boolean masks

Do not drop required metrics from the full candidate grid merely to gain speed unless the frozen comparison protocol is formally revised by Controller.

### 7. Workflow observability

Split the workflow into visible steps at least at:

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

This change is operational only.

## Equivalence gates before full rerun

The optimized comparator must be checked against the existing reference implementation on deterministic small fixtures / restricted years before the old implementation is retired.

Required:

- identical candidate grids/counts
- identical fold membership
- identical A0 outputs
- Ridge predictions/metrics agree within a tight numerical tolerance suitable for the equivalent solver
- Elastic Net predictions/metrics agree within a documented solver tolerance
- identical top-10 Ridge transform selection when differences are outside numerical ties
- same primary/secondary metric definitions
- same strata definitions
- no 2024-2025 reads

If optimization changes candidate ranking beyond numerical tie tolerance, treat that as a semantic discrepancy and stop before the full real-history run.

## Canonical rerun

After equivalence tests pass, run a new clean 2010-2023 Actions comparison from main.

The new run becomes the canonical evidence source for Controller model selection.

The old run remains recorded as `SUPERSEDED_RUNTIME` regardless of whether it later finishes.
