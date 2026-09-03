# Ability temporal confirmation protocol v0.1

## Status

**FROZEN BEFORE 2024-2025 ABILITY PREDICTIVE METRICS ARE OPENED**

This protocol governs the one-time post-development temporal confirmation of the frozen existing-horse Ability v0.1 candidate selected in `Ability_Development_Decision_v0_1.md`.

It is not a new tuning phase.

## 1. Frozen candidate

Evaluate exactly:

```text
family:              ElasticNet
recent_decay:        D070
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

Use the exact A1 feature template and fold-local preprocessing contract from `Ability_Model_Comparison_Protocol_v0_1.md`.

Do not alter feature definitions, candidate settings, imputation, scaling, target, or metric definitions after 2024-2025 results are opened.

## 2. Scope

Existing horses only:

```text
career_scored_run_count >= 1
```

Target label:

```text
official RunPerf v0.1 = T1|EXPANDING|RAW
```

Debut horses are outside this protocol and remain a separate Ability-prior workstream.

No odds, popularity, or market information is allowed.

## 3. Period and chronology

Temporal confirmation years:

```text
2024
2025
```

Training rule:

```text
2024:
  train target year < 2024
  test target year = 2024

2025:
  train target year < 2025
  test target year = 2025
```

Thus the 2025 fit may use completed 2024 labeled rows, but the 2024 fit cannot use 2024/2025 labels and the 2025 fit cannot use 2025 labels.

Feature snapshots themselves must remain strict-as-of:

```text
history_date < target_date
```

Same-day result leakage remains forbidden.

## 4. Frozen comparators

Primary comparator:

```text
A0_D070
```

Secondary diagnostic only:

```text
Ridge:R:070:200:0:0:10.0:
```

The Ridge diagnostic is not an alternate candidate-selection opportunity. It must not replace Elastic Net based on 2024-2025 results without a new post-confirmation development protocol.

## 5. Evaluation cohort

A target row enters the temporal confirmation cohort only when:

- target race context is valid `PRE_RACE`,
- horse is existing (`career_scored_run_count >= 1`),
- target official RunPerf has `score_status='OK'`,
- frozen A1 preprocessing can produce a finite prediction from pre-race inputs under the existing missing-data contract.

The A1 model is expected to retain all otherwise eligible rows because missing numeric values are handled by explicit missing flags plus training-fold median imputation.

Report:

- total eligible existing-horse labeled rows,
- A1 predicted rows,
- A0 D070 evaluable rows,
- paired evaluation rows,
- coverage by year.

A1 prediction coverage below 100% of the structurally eligible cohort is a technical/data gate failure unless the exact excluded rows are explicitly accounted for by a pre-existing frozen exclusion rule.

## 6. Metrics

Use exactly the development definitions.

For each year:

```text
primary_year = mean(
    spearman_all_rows(predicted_ability, target_runperf),
    mean_within_race_spearman(predicted_ability, target_runperf)
)
```

Within-race Spearman uses races with at least 3 eligible scored runners.

Required secondary metrics:

- Pearson
- MAE
- RMSE
- mean within-race Spearman
- top-predicted horse's target-RunPerf-rank percentile
- row/race coverage

Report A1, A0 D070, and the frozen Ridge diagnostic separately.

## 7. Primary confirmation gate

Define annual paired primary deltas:

```text
delta_2024 = A1_primary_2024 - A0_D070_primary_2024
delta_2025 = A1_primary_2025 - A0_D070_primary_2025
mean_delta = mean(delta_2024, delta_2025)
```

Classification is frozen as follows.

### PASS_STRONG

All technical/chronology gates pass, and:

```text
delta_2024 > 0
delta_2025 > 0
mean_delta > 0
```

### PASS_MIXED

All technical/chronology gates pass, and:

```text
mean_delta > 0
```

but exactly one annual delta is `<= 0`.

### FAIL

Any of:

```text
mean_delta <= 0
non-finite required primary metric
technical/audit gate failure
preprocessing leakage
same-day/current-result leakage
market contamination
unexpected cohort loss
model/hyperparameter drift
```

Secondary metrics are mandatory diagnostics but do not override the predeclared primary classification after the fact.

## 8. Model/refit integrity gates

For each confirmation year:

- preprocessing medians/means/stds come only from training rows,
- model coefficients/intercept are finite,
- train maximum year is `< test year`,
- prediction count reconciles to the eligible cohort,
- candidate hyperparameters exactly match this protocol,
- no 2024-2025 row is used to reselect decay/bandwidth/shrinkage/regularization,
- no A2/nonlinear challenger is evaluated in this confirmation.

Record coefficient histories for 2024 and 2025 fits.

## 9. Upstream audit gates

Before predictive confirmation, the clean 2010-2025 pipeline must pass:

- Index Base audit,
- RunPerf feature audit,
- official RunPerf audit,
- Ability snapshot audit.

At minimum require zero:

```text
Index/RunPerf chronology violations
RunPerf arithmetic violations
official RunPerf arithmetic violations
official RunPerf future-coefficient backfill
Ability history_date >= target_date
Ability same-day result leakage
Ability target-result feature leakage
Ability target-SED-going leakage
Ability fallback PRE_RACE misuse
market contamination
```

Known historical structural missingness may remain explicit and audited; it must not be silently imputed outside the frozen contracts.

## 10. Result handling

The confirmation output must include:

- protocol version,
- source/head SHA,
- 2024 and 2025 train/test counts,
- A1 annual metrics,
- A0 annual metrics,
- Ridge diagnostic annual metrics,
- annual A1-A0 deltas,
- equal-year mean delta,
- coefficient/preprocessing evidence,
- all relevant violation counts,
- final classification `PASS_STRONG | PASS_MIXED | FAIL`,
- `model_promoted=false` during the workflow itself.

The workflow returns evidence. Controller performs any subsequent production promotion.

## 11. No post-hoc tuning

After 2024-2025 metrics are opened:

- do not change hyperparameters and call the same period untouched,
- do not add/drop features to recover a weak result,
- do not change the acceptance thresholds,
- do not swap Ridge/Elastic Net based on the confirmation and treat that as the same pre-frozen test.

A semantics-preserving technical bug may be fixed and the same confirmation rerun only when the first result is explicitly invalidated as a technical failure, with both runs recorded.

If the frozen model fails predictively, subsequent model changes belong to a new post-confirmation development protocol and 2024-2025 must be treated as consumed evidence.

## 12. Interpretation

2024-2025 are **post-freeze Ability temporal confirmation**, not a pristine project-level holdout, because the same calendar years were already used to validate the upstream RunPerf definition.

Nevertheless, Ability model selection did not inspect Ability predictive metrics from these years before `Ability_Development_Decision_v0_1.md` and this protocol were frozen.

## 13. Controller action after result

- `PASS_STRONG`: existing-horse Ability v0.1 may be promoted to the production-candidate layer, subject to a separate publication/materialization record.
- `PASS_MIXED`: Controller review required; do not auto-promote.
- `FAIL`: do not promote the frozen existing-horse model as official Ability v0.1.

Debut Ability remains separate regardless of the classification.
