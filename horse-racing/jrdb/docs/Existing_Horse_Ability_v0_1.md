# Existing-Horse Ability v0.1

## Status

**PRODUCTION CANDIDATE — PROMOTED AFTER PASS_STRONG TEMPORAL CONFIRMATION**

This document is the publication/materialization record for the existing-horse Ability model selected on 2013-2023 development and confirmed on 2024-2025 under the frozen protocols.

This is **not** the all-runner Ability model. Debut horses remain outside this model until the dedicated Debut Ability workstream is completed.

## 1. Definition

Existing-Horse Ability v0.1 estimates expected official RunPerf v0.1 for a horse with at least one prior scored official RunPerf observation, using only information available before the target race.

```text
Ability_existing(target race, horse)
  = E[official RunPerf v0.1 | frozen pre-race feature set]
```

Official target:

```text
RunPerf v0.1 = T1|EXPANDING|RAW
```

## 2. Frozen model

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

Feature template is exactly the A1 template from `Ability_Model_Comparison_Protocol_v0_1.md`:

- `recent_perf_d070`
- `peak_best1_last5`
- `peak_best2_mean_last5`
- `peak_gap = peak_best2_mean_last5 - recent_perf_d070`
- `performance_mad_last5`
- `surface_fit_delta_raw` with aptitude k=0
- `distance_d200_delta_raw` with aptitude k=0
- `course_exact_delta_raw` with aptitude k=0
- `jockey_residual_mean_raw` with jockey k=0
- `weight_relative`
- `log1p(career_scored_run_count)`
- the corresponding explicit missing flags

Not used:

- `rest_days`
- going fit
- odds/popularity/market data
- target result fields
- target SED final going
- same-day results

## 3. Preprocessing

For target model year Y, fit preprocessing on labeled training rows with target year `< Y` only.

1. retain explicit missing flags;
2. median-impute numeric missing values using training rows only;
3. standardize using training-fold mean/std only;
4. zero-variance columns use safe scale 1.0 while their value remains constant;
5. apply the frozen preprocessing unchanged to target-year rows.

No future-year statistics may enter the model snapshot.

## 4. Annual model snapshot chronology

For each target year Y:

```text
training labels: target year < Y
scored targets:  target year = Y
```

Examples:

```text
2024 model: training labels through 2023
2025 model: training labels through 2024
2026 model: training labels through 2025
```

Historical model snapshots are immutable once published. A later-year refit does not rewrite a prior year's Ability score.

## 5. Eligible target rows

A target row is scoreable only when:

- `race_context_availability='PRE_RACE'`,
- `career_scored_run_count >= 1`,
- target year is at least 2013,
- frozen feature preprocessing produces a finite prediction.

The target race result is not required to exist at scoring time.

Rows must be retained but unscored when:

- debut horse: `DEBUT_MODEL_PENDING`,
- target context is not valid PRE_RACE: `PRE_RACE_CONTEXT_UNAVAILABLE`,
- target year is before first official Ability model year: `PRE_MODEL_WARMUP`,
- a technical scoring/model snapshot failure occurs: fail closed rather than emit a numeric score.

## 6. Development evidence

2013-2023 equal-year primary:

```text
A0_D070:     0.473766
best Ridge:  0.48423 approximately
Elastic Net: 0.490990
```

Frozen Elastic Net exceeded the best A0 primary in all 11 development years.

Development selection was completed before 2024-2025 Ability predictive metrics were opened.

## 7. 2024-2025 temporal confirmation

Canonical confirmation:

```text
Issue:     #320
Actions:   33720247812
Head SHA:  7cb5ec0f8b34b45f9ebfc5b115e61e8cb0040ecc
Artifact:  9880403171
Digest:    sha256:0ed57442eacbabffe4f6ba89bfb0ef5bf528792b7c0efc2bb7e01a2fd67dafb7
Result:    PASS_STRONG
```

Primary results:

```text
2024 A1: 0.4832646155956626
2024 A0: 0.46571424934037564
2024 delta: +0.017550366255286942

2025 A1: 0.4887870366473240
2025 A0: 0.4710172854175092
2025 delta: +0.017769751229814780

mean delta: +0.01766005874255086
```

A1 prediction coverage and paired coverage were both 1.0 in both years. All technical gates passed.

The classification follows `Ability_Holdout_Protocol_v0_1.md` exactly and was not changed after results were observed.

## 8. Materialization contract

Official existing-horse Ability materialization must persist:

- target identity and race date,
- raw Ability prediction,
- target-year model snapshot ID,
- training-through year,
- training row count,
- preprocessing parameters,
- model intercept and coefficients,
- frozen hyperparameters,
- score status and provenance,
- builder/schema/model versions.

All source target rows should remain materialized, including debut/unavailable rows, with explicit unscored status.

## 9. Boundaries

This production-candidate promotion does not authorize:

- applying this model to debut horses and calling it complete Ability,
- retuning on 2024-2025,
- adding A2/nonlinear models to recover or improve confirmation results,
- adding odds/popularity to Ability,
- moving Edge/state-change features into Ability without a new incremental protocol.

2024-2025 Ability predictive evidence is now consumed and must never again be described as untouched.

## 10. Next work

1. materialize/audit Existing-Horse Ability v0.1 with annual model snapshots;
2. build dedicated Debut Ability priors using time-aware pedigree/training/jockey/trainer evidence;
3. join existing-horse and debut paths into the all-runner Ability publication layer;
4. only then proceed to Edge development on top of the published Ability baseline.
