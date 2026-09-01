# Ability model comparison protocol v0.1

## Status

**FROZEN BEFORE EXISTING-HORSE ABILITY MODEL COMPARISON**

This protocol governs the first predictive comparison for existing-horse Ability using the accepted pre-race Ability snapshot and official RunPerf v0.1.

It must be committed before any 2024-2025 Ability predictive metric is inspected.

## 1. Scope

This protocol covers **existing horses only**:

```text
career_scored_run_count >= 1
```

Debut horses remain in the production snapshot, but their dedicated pedigree/workout/trainer prior model is a later work package. Do not score or judge debut Ability quality from the existing-horse model in this comparison.

Official target:

```text
official RunPerf v0.1 = T1|EXPANDING|RAW
```

RunPerf must not be redesigned.

## 2. Periods and chronology

- 2010-2012: warm-up / training history only
- 2013-2023: development walk-forward
- 2024-2025: **not read for Ability predictive performance in this package**
- 2026 onward: preferred prospective published-pipeline evaluation

For development test year Y:

```text
train rows: target year < Y
test rows:  target year = Y
```

All pre-race features were themselves built with `history_date < target_date`. Training preprocessing must also be fit only on the training rows for each fold.

## 3. Eligible development rows

A row is eligible for predictive comparison only when:

- target race context is valid PRE_RACE, not `CURRENT_RESULT_FALLBACK`,
- horse is existing (`career_scored_run_count >= 1`),
- target official RunPerf has scored status `OK`,
- the model-specific required inputs can be transformed under the missing-data contract below.

Do not use odds, popularity, market features, target finish, target SED going, or any current-result input other than the separate official RunPerf evaluation label.

## 4. A0 family — transparent recent-performance baseline

A0 has no fitted coefficients. Compare exactly four candidates:

```text
A0_D070 = recent_perf_d070
A0_D080 = recent_perf_d080
A0_D090 = recent_perf_d090
A0_D100 = recent_perf_d100
```

These establish how much value is available from simple recent demonstrated performance before aptitude/jockey/weight modeling.

No A0 decay is adopted automatically in the Work package. Report all four candidates and annual paired differences.

## 5. A1 family — regularized linear Ability model

A1 predicts target official RunPerf on its raw scale.

### 5.1 Core feature template

For each candidate configuration use:

- one selected recent candidate from `{D070,D080,D090,D100}`,
- `peak_best1_last5`,
- `peak_best2_mean_last5`,
- `peak_gap = peak_best2_mean_last5 - recent`,
- `performance_mad_last5`,
- shrunk `surface_fit_delta_raw`,
- shrunk distance-fit delta for one bandwidth from `{200,400,600,800}`,
- shrunk `course_exact_delta_raw`,
- shrunk `jockey_residual_mean_raw`,
- `weight_relative`,
- `log1p(career_scored_run_count)`,
- corresponding explicit missing flags.

Do not include `rest_days` in Ability v0 A1; rest is reserved for Edge/state-change work.

Do not include going-fit because verified historical target PRE_RACE going availability is zero.

### 5.2 Evidence shrinkage candidates

Aptitude shrinkage for surface/distance/course uses:

```text
shrunk_delta = raw_delta * neff / (neff + k)
```

Candidate `k` values:

```text
0, 4, 12
```

`k=0` means no shrinkage when evidence exists.

Jockey shrinkage uses:

```text
shrunk_jockey = raw_jockey_residual * n / (n + k_jockey)
```

Candidate `k_jockey` values:

```text
0, 20, 100
```

Missing raw evidence remains missing and is handled by the model preprocessing contract; it is not converted to evidence=0 before the missing flag is retained.

### 5.3 Distance candidates

Exactly one bandwidth is used per A1 configuration:

```text
200, 400, 600, 800m
```

No bandwidth is preselected.

### 5.4 Ridge candidates

For every feature configuration compare Ridge alphas:

```text
0.01, 0.1, 1, 10, 100
```

### 5.5 Elastic Net challenger

After the full Ridge grid is evaluated on 2013-2023 development, take the **10 highest mean-primary Ridge feature configurations ignoring alpha duplicates** and evaluate Elastic Net on those transforms only.

Elastic Net grid:

```text
alpha:    0.001, 0.01, 0.1
l1_ratio: 0.1, 0.5
```

This is still development search, not holdout validation. The top-10 procedural filter is frozen here before results.

A2/nonlinear models are out of scope.

## 6. Fold-local preprocessing

For every test year Y, preprocessing is fitted from training rows only.

Numeric missing values:

1. retain an explicit missing flag;
2. impute the numeric value with the training-fold median;
3. standardize using training-fold mean/std after imputation;
4. apply those training parameters unchanged to test Y.

Zero-variance training features are dropped for that fold and reported.

The target is never standardized globally across future years. A model may fit an intercept on the raw official RunPerf scale.

## 7. Metrics

Report metrics separately for each development year 2013-2023 and aggregate by equal-year mean.

### 7.1 Primary metric

For each year:

```text
primary_year = mean(
    spearman_all_rows(predicted_ability, target_runperf),
    mean_within_race_spearman(predicted_ability, target_runperf)
)
```

Within-race Spearman uses races with at least 3 eligible scored runners.

Overall candidate primary score is the equal-year mean of `primary_year`.

### 7.2 Required secondary metrics

- Pearson correlation with target official RunPerf
- MAE on RunPerf raw scale
- RMSE on RunPerf raw scale
- mean within-race Spearman
- top-predicted horse's target-RunPerf-rank percentile diagnostic
- coverage / eligible row count
- annual standard deviation of primary score

### 7.3 Required strata

Report at minimum:

```text
career_count = 1
career_count = 2
career_count = 3-5
career_count >= 6
same target surface as at least one history / untried surface
exact target distance history present / absent
course exact evidence present / absent
```

Do not report debut predictive performance in this package.

## 8. Comparison output

The development report must include:

- all four A0 candidates,
- full Ridge grid summary,
- Elastic Net challenger summary,
- top candidates overall,
- best-by-family,
- annual metrics for top candidates,
- paired annual differences versus the best A0 candidate,
- coefficient histories for top regularized models,
- feature-transform configuration for every reported candidate,
- training/test counts by fold,
- coverage and strata diagnostics.

No candidate is promoted to official Ability automatically by the Work package.

## 9. Controller decision rule

Work returns evidence only. Controller will select/freeze:

- recent decay,
- distance bandwidth,
- aptitude shrinkage k,
- jockey shrinkage k,
- A0 vs A1 family,
- regularization settings.

The decision will consider mean primary score, paired annual consistency, raw-scale error, coverage, career-strata behavior, coefficient stability, and complexity.

Small or unstable gains favor the simpler configuration.

## 10. Holdout boundary

This package must not query, calculate, print, store in the comparison report, or use for ranking any 2024-2025 Ability predictive metric.

Structural row counts from the already accepted snapshot are allowed, but target RunPerf/prediction comparisons for 2024-2025 are forbidden until a later Controller decision record freezes the Ability specification.

If code accidentally reads 2024-2025 labels during comparison, the comparison run is invalid and must fail closed.

## 11. Debut boundary

Debut horses require a separate Ability model using time-aware pedigree, workout/training, jockey-debut, and trainer-debut priors.

Do not force the existing-horse A1 model onto `career_scored_run_count = 0` and call that the project Ability model.

## 12. Acceptance of this work package

The model-comparison infrastructure is accepted when:

- all structural snapshot/upstream gates remain PASS,
- development comparator reads target years only through 2023,
- no market/current-result feature leakage exists,
- all annual folds respect training year < test year,
- fold-local preprocessing leakage checks pass,
- A0/Ridge/Elastic Net specified candidates execute,
- report contains all required annual/paired/strata diagnostics,
- no 2024-2025 predictive metric is inspected,
- no official Ability model is silently promoted.
