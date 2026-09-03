# Debut Ability model comparison protocol v0.1

## Status

**FROZEN BEFORE DEBUT / NO-SCORED-HISTORY ABILITY PREDICTIVE COMPARISON**

This protocol governs the first predictive comparison for horses with no prior scored official RunPerf, using the accepted Debut Ability snapshot v0.1.1 and official RunPerf v0.1.

It is frozen after structural acceptance and before any 2024-2025 Debut Ability predictive metric is inspected.

## 1. Scope

Target population:

```text
career_scored_run_count = 0
```

This includes both:

- true first starts;
- prior-start runners whose earlier races produced no scored official RunPerf.

Official target:

```text
official RunPerf v0.1 = T1|EXPANDING|RAW
```

Existing-Horse Ability v0.1 must not be applied to these rows as a substitute.

## 2. Accepted snapshot and availability semantics

Canonical structural source is Debut Ability snapshot v0.1.1 accepted under Issue #334.

For target date D:

- UKC identity/pedigree observation may use latest verified PRE_RACE observation with `data_date <= D`;
- same-day UKC is allowed because Issue #332 verified the target-date archive is published before racing;
- exact selected profile date and same-day-selection provenance must remain persisted;
- historical result/debut-prior evidence remains strict `race_date < D`;
- current result and same-day race results are forbidden as feature history.

No future UKC profile is allowed.

## 3. Periods and walk-forward chronology

- 2010-2012: history formation / warm-up only;
- 2013-2023: development walk-forward;
- 2024-2025: unopened Debut Ability temporal confirmation;
- 2026 onward: prospective evaluation preferred.

For development test year Y:

```text
training labels/features: target year < Y
test rows:                target year = Y
```

All fold preprocessing, category vocabulary, imputation, scaling, and fitted coefficients must use training rows only.

Any accidental calculation or inspection of 2024-2025 Debut predictive performance invalidates the development run.

## 4. Eligible development rows

A row is eligible when:

- target race context is valid `PRE_RACE`;
- `career_scored_run_count = 0`;
- target official RunPerf has scored status `OK`;
- horse identity is valid;
- model-specific predictors can be represented under the missing-data contract.

`CURRENT_RESULT_FALLBACK` targets remain persisted for audit but are excluded from predictive comparison.

No odds, popularity, market field, target finish, target SED final going, target result, or same-day result may enter predictors.

## 5. Development sequence

Development is intentionally staged:

```text
D0 = pedigree-only baseline
D1 = D0 pedigree + target PRE_RACE training/basic fields
D2 = later residualized jockey/trainer effects after D1 is frozen
```

This protocol compares D0 and D1 only.

Raw jockey/trainer debut RunPerf averages are not final D1 predictors. They may be retained as structural diagnostics but D2 must be governed by a later protocol using past-only residual effects from a frozen horse/pedigree/training baseline.

## 6. D0 family — pedigree Ability baseline

### 6.1 Transparent baselines

Report these non-fitted references individually:

```text
D0_SIRE      = sire_debut_runperf_raw
D0_DAMSIRE   = broodmare_sire_debut_runperf_raw
D0_SIRE_LINE = sire_line_debut_runperf_raw
D0_DAMSIRE_LINE = broodmare_sire_line_debut_runperf_raw
```

Missing rows are excluded only from the corresponding transparent-baseline diagnostic; report coverage explicitly.

### 6.2 Regularized pedigree model

Core numeric pedigree template:

- `sire_debut_runperf_raw`;
- `broodmare_sire_debut_runperf_raw`;
- `sire_line_debut_runperf_raw`;
- `broodmare_sire_line_debut_runperf_raw`;
- `sire_surface_debut_runperf_raw`;
- `broodmare_sire_surface_debut_runperf_raw`;
- one sire distance kernel candidate;
- one broodmare-sire distance kernel candidate;
- `log1p(n)` for the corresponding evidence counts;
- `log1p(neff)` where distance neff exists;
- explicit missing flags.

Distance bandwidth is shared by sire and broodmare-sire in one configuration and must be one of:

```text
200, 400, 600, 800m
```

No bandwidth is preselected.

### 6.3 Pedigree evidence shrinkage

For raw overall/surface pedigree means compare empirical shrinkage toward the corresponding line-level mean when both are available:

```text
shrunk = line_mean + (raw_mean - line_mean) * n / (n + k)
```

Candidate k values:

```text
0, 8, 32
```

If line evidence is unavailable, retain raw evidence + missing flags; do not silently substitute zero.

Distance features are already weighted kernels and are compared by bandwidth without an additional shrinkage grid in D0 v0.1.

## 7. D1 family — pedigree + training/basic PRE_RACE information

D1 starts from one D0 pedigree transform and adds only target PRE_RACE information.

### 7.1 Continuous / ordinally meaningful numeric fields

Eligible numeric fields:

- `weight_relative`;
- `age_in_months`;
- CHA segment times when populated;
- CHA JRDB first/middle/final segment indices;
- CHA JRDB workout index;
- CYB JRDB workout index;
- CYB finish index;
- week-ago workout index;
- workout count;
- furlong count;
- explicit missing flags.

### 7.2 Categorical fields

Treat as categorical, never as continuous numbers merely because the raw code is numeric/alphanumeric:

- workout course;
- effort / chase-state / rider-type codes;
- pair result / pair effort / pair class;
- training type / training course type;
- used-slope / wood / dirt / turf / pool / jump / polytrack indicators;
- training distance code;
- training focus code;
- training volume code;
- finish change code;
- training evaluation code;
- week-ago course code;
- sex code.

Categorical vocabulary must be learned from training rows only for each fold. Unknown test categories map to an explicit unknown category; do not infer numeric ordering.

### 7.3 D1 ablation families

Compare the following predeclared additions so incremental value remains interpretable:

```text
D1_NUMERIC   = D0 + numeric training/basic fields
D1_FULL      = D1_NUMERIC + categorical training fields
```

No jockey/trainer effect is added in this protocol.

## 8. Model families and regularization grid

For each D0/D1 feature configuration compare Ridge:

```text
alpha = 0.01, 0.1, 1, 10, 100
```

After the complete Ridge grid is evaluated on 2013-2023 development, take the 10 highest mean-primary feature configurations ignoring alpha duplicates and evaluate Elastic Net challengers only on those transforms:

```text
alpha    = 0.001, 0.01, 0.1
l1_ratio = 0.1, 0.5
```

No tree/boosting/neural model is allowed in this first Debut comparison.

## 9. Fold-local preprocessing

For every test year Y:

Numeric features:

1. retain explicit missing flags;
2. impute from training-fold median only;
3. standardize from training-fold mean/std only;
4. apply unchanged to test Y;
5. drop zero-variance training columns and report them.

Categorical features:

1. learn categories from training rows only;
2. one-hot encode training categories;
3. map unseen test categories to explicit unknown;
4. do not create target/future-derived category levels.

The target remains on raw official RunPerf scale.

## 10. Metrics

Report each development year 2013-2023 separately and aggregate by equal-year mean.

Primary metric matches Existing-Horse Ability comparison:

```text
primary_year = mean(
    spearman_all_rows(predicted_ability, target_runperf),
    mean_within_race_spearman(predicted_ability, target_runperf)
)
```

Within-race Spearman uses races with at least 3 eligible scored runners.

Required secondary metrics:

- Pearson correlation with target official RunPerf;
- MAE;
- RMSE;
- mean within-race Spearman;
- top-predicted runner target-RunPerf-rank percentile diagnostic;
- coverage / eligible row count;
- annual standard deviation of primary score.

## 11. Required strata

Report at minimum:

- true first start vs prior-start/no-scored-history;
- sire prior present / missing;
- broodmare-sire prior present / missing;
- low sire evidence `n < 8` / medium `8-31` / established `>=32`;
- low damsire evidence `n < 8` / medium `8-31` / established `>=32`;
- CHA core index present / missing;
- CYB core index present / missing;
- week-ago workout index present / missing;
- surface-conditioned sire evidence present / absent.

## 12. Comparison output

The report must include:

- all transparent D0 references;
- full D0 Ridge summary;
- D1_NUMERIC and D1_FULL Ridge summaries;
- Elastic Net challenger summary;
- top candidates overall and best-by-family;
- annual metrics for top candidates;
- paired annual differences versus the best transparent D0 reference and best D0 regularized model;
- coefficient histories / selected-category dimensions for top regularized candidates;
- training/test counts by fold;
- coverage and required strata diagnostics;
- exact transform/configuration for every reported candidate.

Work returns evidence only and must not auto-promote a Debut Ability model.

## 13. Controller decision rule

Controller will select/freeze after development based on:

- equal-year mean primary;
- paired annual consistency;
- raw-scale error;
- true-first-start behavior;
- low-evidence pedigree behavior;
- coefficient stability;
- coverage;
- complexity.

Small or unstable gains favor the simpler D0/D1 configuration.

D2 residualized jockey/trainer work starts only after a D1 horse/pedigree/training baseline is frozen.

## 14. Holdout boundary

This package must not query, calculate, print, store, or rank any 2024-2025 Debut Ability predictive metric.

Structural counts already accepted from snapshot audits are allowed. Predictive labels/predictions for 2024-2025 are forbidden until Controller freezes the development winner and separately authorizes temporal confirmation.

## 15. Acceptance gates

Comparison infrastructure is accepted when:

- upstream RunPerf / snapshot gates remain PASS;
- comparator reads predictive target years only through 2023;
- all folds use training target year < test year;
- fold-local numeric/categorical preprocessing leakage tests pass;
- no market/current-result/same-day-result leakage exists;
- all specified D0/D1 Ridge candidates execute;
- Elastic Net challenger procedure follows the frozen top-10 rule;
- annual/paired/strata diagnostics are produced;
- 2024-2025 predictive metrics remain unopened;
- no Debut Ability model is silently promoted.
