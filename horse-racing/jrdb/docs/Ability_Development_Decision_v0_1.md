# Ability development decision v0.1

## Status

**FROZEN FOR 2024-2025 TEMPORAL CONFIRMATION — NOT YET PRODUCTION-OFFICIAL**

Decision date: 2026-09-03 JST

This record freezes the existing-horse Ability v0.1 candidate after the predeclared 2013-2023 development comparison and before any 2024-2025 Ability predictive metric is inspected.

It is a Controller decision under `Ability_Model_Comparison_Protocol_v0_1.md` and does not change official RunPerf v0.1.

## 1. Canonical development evidence

Canonical optimized run:

```text
Issue:       #299 [JRDB_ABILITY_COMPARE] 20260901-005-optimized-v3
Actions run: 33472985499
Head SHA:    47017d635711385c72528312f6f97455dd3090df
Artifact ID: 9793261977
Artifact:    jrdb-ability-compare-2010-2023-33472985499
Digest:      sha256:a801d40d8709c0af78562216bb7d85638bd809dfe839238f87701c9806ae4788
```

The Actions run is displayed as `failure` only because the final Issue-comment step attempted to post the full multi-megabyte JSON and GitHub rejected the comment as too long. All upstream build/audit steps, the Ability comparison, lightweight-result generation, and artifact upload completed successfully.

Frozen boundaries confirmed by the comparison report:

```text
development_years: 2013-2023
source history:     2010-2023 only
holdout_touched:    false
2024_2025_predictive_metrics_inspected: false
debut_rows_used:    0
source_eligible_rows: 584467
preprocessing_leakage_violations: 0
model_promoted:     false
```

## 2. Technical result finalization

The canonical report contains 10 Elastic Net candidates with at least one non-finite annual primary metric caused by effectively constant predictions in an annual fold.

This is handled fail-closed after the run:

```text
A0:          4 total / 4 valid / 0 invalid
Ridge:     720 total / 720 valid / 0 invalid
ElasticNet: 60 total / 50 valid / 10 invalid
```

A candidate with any missing/non-finite required annual primary is ineligible for selection. Non-finite diagnostic values are serialized as explicit `null`; they are not replaced with favorable zero scores.

This result-finalization rule does not change the candidate grid, folds, fitted predictions, metric definition, or any finite candidate score. The winning candidate is unchanged.

## 3. Best-by-family development results

Equal-year mean primary over 2013-2023:

| Family | Candidate | Mean primary | Primary SD |
|---|---|---:|---:|
| A0 | `A0_D070` | 0.4737656270 | 0.0126634313 |
| Ridge | `Ridge:R:070:200:0:0:10.0:` | 0.4842332972 | 0.0134380742 |
| Elastic Net | `ElasticNet:R:070:200:0:0:0.01:0.5` | **0.4909903692** | 0.0131614100 |

Equal-year secondary means:

| Metric | A0 D070 | Best Ridge | Best Elastic Net |
|---|---:|---:|---:|
| Spearman all rows | 0.4986346608 | 0.5113415524 | **0.5155131822** |
| Mean within-race Spearman | 0.4488965933 | 0.4571250420 | **0.4664675562** |
| Pearson | 0.4629220980 | **0.4901970143** | 0.4841837870 |
| MAE | 0.0658274125 | **0.0623512293** | 0.0631436726 |
| RMSE | 0.1016031444 | **0.0941317038** | 0.0948678082 |
| Top-predicted target-rank percentile | 0.7444482325 | 0.7473856150 | **0.7530481983** |

Elastic Net therefore has the strongest predeclared primary/race-ranking evidence. Ridge is slightly better on raw-scale MAE/RMSE, but its primary score is lower.

## 4. Paired annual consistency

Elastic Net minus best A0 primary by development year:

```text
2013 +0.0219787344
2014 +0.0194689223
2015 +0.0164719036
2016 +0.0171664253
2017 +0.0150801651
2018 +0.0185100667
2019 +0.0161428458
2020 +0.0141865779
2021 +0.0182305701
2022 +0.0152209048
2023 +0.0170150479
```

The delta is positive in **11/11 years**.

Approximate equal-year mean delta:

```text
+0.0172247
```

Elastic Net also exceeds the best Ridge primary in 11/11 years.

The gain is therefore not driven by one or two development years.

## 5. Selected existing-horse Ability candidate

Freeze the following candidate exactly for temporal confirmation:

```text
family:              ElasticNet
recent_decay:        D070
recent_feature:      recent_perf_d070
distance_bandwidth:  200m
aptitude_shrink_k:   0
jockey_shrink_k:     0
alpha:               0.01
l1_ratio:            0.5
fit_intercept:       true
max_iter:            10000
tol:                 1e-6
random_state:        0
```

Feature template and fold-local preprocessing remain exactly those frozen in `Ability_Model_Comparison_Protocol_v0_1.md`.

No feature may be added or removed for the 2024-2025 confirmation run.

## 6. Tie handling for distance/jockey settings

At the selected Elastic Net regularization, multiple D070 / aptitude-k=0 candidates are exactly tied in development primary across different distance bandwidth and jockey-k settings.

Inspection of the selected candidate's annual fitted coefficient histories shows that the distance-delta and jockey-residual coefficients are zero in every 2013-2023 fold. Therefore those transform choices do not alter the observed development predictions at this selected regularization.

The Controller freezes:

```text
distance bandwidth = 200m
jockey k          = 0
```

as the deterministic first/least-expanded options in the predeclared grids.

This is a tie-resolution convention, not evidence that 200m is predictively superior to 400/600/800m or that jockey k=0 is superior once the corresponding coefficient becomes nonzero in future refits. The choices are frozen now specifically so 2024-2025 cannot be used to resolve the tie post hoc.

## 7. Coefficient-stability evidence

For the selected Elastic Net candidate, annual development fits use 22 numeric columns including explicit missing indicators / the reserved zero column.

Nonzero features are sparse and stable. Across the 2013-2023 folds:

```text
recent_perf_d070:        positive every year, about 0.03538 to 0.03905
peak_best2_mean_last5:   positive every year, about 0.00414 to 0.00568
surface_delta:           positive every year, about 0.00503 to 0.00572
weight_relative:         positive every year, about 0.00050 to 0.00176
surface_missing flag:    negative every year, about -0.00718 to -0.00582
course_missing flag:     small/nonzero in part of the period
```

The selected model has 6 nonzero coefficients in folds 2013-2020 and 5 in folds 2021-2023. Distance raw delta and jockey residual are zeroed throughout the selected candidate's development coefficient history.

This supports keeping the regularized linear family rather than escalating to an A2 nonlinear challenger before temporal confirmation.

## 8. Why A1 Elastic Net is selected over A0/Ridge

The Controller decision rule considers primary score, paired annual consistency, raw-scale error, coverage, coefficient stability, and complexity.

Decision:

1. **A0 is not selected** because both regularized families improve the primary metric in all 11 development years.
2. **Elastic Net is selected over Ridge** because its primary improvement is materially larger and is positive versus Ridge in all 11 years.
3. Ridge's modest MAE/RMSE advantage is retained as a diagnostic, but the predeclared primary metric prioritizes race-relative Ability ordering as well as global rank correlation.
4. Elastic Net's sparsity substantially limits effective model complexity; the selected fit uses only 5-6 nonzero coefficients in the annual development folds.
5. No A2/nonlinear model is opened before temporal confirmation.

## 9. Frozen confirmation baselines

Primary baseline:

```text
A0_D070
```

Secondary diagnostic:

```text
Ridge:R:070:200:0:0:10.0:
```

Neither baseline may be retuned using 2024-2025.

## 10. Temporal refit rule

For target confirmation year Y, use the same frozen transform, preprocessing contract, and Elastic Net hyperparameters, but refit from chronologically available labeled rows only:

```text
2024 prediction model:
  train target years <= 2023
  test target year = 2024

2025 prediction model:
  train target years <= 2024
  test target year = 2025
```

Fold preprocessing is recomputed from that training set only. No 2025 row may affect the 2024 model, and no target-year preprocessing statistic may enter its own prediction fold.

Historical official RunPerf rows retain their original annual as-of RunPerf coefficient provenance.

## 11. What remains unfrozen

This decision is for **existing horses only**.

Still separate:

- debut-horse Ability prior/model,
- Edge model,
- Value/odds layer,
- final production composite and prospective 2026+ evaluation.

Do not force this existing-horse model onto debut horses and call it complete project Ability.

## 12. Next gate

The next step is the one-time 2024-2025 **post-freeze temporal confirmation** governed by `Ability_Holdout_Protocol_v0_1.md`.

2024-2025 are not described as a pristine project-level holdout because RunPerf development has already used them for RunPerf validation. For Ability model selection, however, no Ability predictive metric from those years was inspected before this decision record was frozen.
