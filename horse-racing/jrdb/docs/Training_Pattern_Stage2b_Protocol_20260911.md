# Training Pattern Stage 2b — Pre-Analysis Protocol

Date: 2026-09-11
Status: **FROZEN FOR DEVELOPMENT-PERIOD VALIDATION**

## 1. Purpose

Theme B tests whether stable/rotation/training-process information adds predictive information beyond the already confirmed `Training Edge v0.1` baseline.

The baseline already contains:

- JRDB processed training information;
- fixed rest bucket from `days_since_last_run`;
- same-horse workout vertical feature `final_self_pct`.

Stage 2b therefore does not ask whether a trainer or training pattern is associated with performance in isolation. It asks whether a pre-race pattern adds incremental information after the confirmed baseline is present.

## 2. Data and temporal boundary

Input is the development-only Training Research Lite:

`jrdb_training_research_2010_2023_development_lite_v0_1.sqlite`

Temporal use is fixed:

- 2010-2012: history formation only;
- 2013-2017: earliest model/history formation;
- 2018-2023: annual walk-forward evaluation;
- 2024-2025: **not used for Stage 2b model selection or validation**.

The 2024-2025 package was already opened and consumed by Training Edge v0.1. It must not be represented as an unopened holdout for any Stage 2b hypothesis.

For each test year Y, every model fit and every trainer-pattern outcome encoding must use years strictly earlier than Y. Same-year target outcomes must never be used to construct a feature for that test year.

## 3. Outcome and eligibility

Reuse the frozen Training Edge v0.1 definitions without modification.

```text
performance_delta =
  current official_runperf_raw
  - median(strictly-prior official_runperf_raw for same horse)
```

Eligibility:

- at least 3 strictly-prior valid Official RunPerf rows for the horse;
- at least 3 strictly-prior comparable workouts for `final_self_pct`;
- current `performance_delta` and `final_self_pct` present.

Comparable workout definition remains:

```text
same horse_id
+ same CHA course_code
+ same furlong_count
+ strictly earlier race_date
```

No odds, popularity or payout may enter Stage 2b.

## 4. Baseline M0

M0 reproduces the confirmed Training Edge v0.1 development specification.

Numeric:

- `kyi_training_score`
- `finish_index`
- `jrdb_final_segment_index`
- `jrdb_workout_index_cha`
- `final_self_pct`

Categorical:

- `kyi_training_arrow_code`
- fixed current `rest_bucket`: `<=20`, `21-34`, `35-62`, `63-119`, `120+`, `missing`

Estimator and preprocessing:

- numeric median imputation with missing indicators;
- StandardScaler;
- categorical most-frequent imputation;
- one-hot encoding with unknown categories ignored;
- `Ridge(alpha=1.0)`.

## 5. Generic B features

M1 adds generic pre-race rotation/training-process variables available in Training Research Base. No post-race information is used.

Numeric / binary:

- `days_before_race`
- `workout_count`
- previous race gap (`previous_days_since_last_run`)
- log ratio/change between current and previous gap (`gap_log_change`)
- `return_after_63d_break`: current gap <=35 and previous gap >=63
- `return_after_120d_break`: current gap <=35 and previous gap >=120
- `pair_work_present`
- `used_slope`
- `used_wood`
- `used_dirt`
- `used_turf`
- `used_pool`
- `used_jump`
- `used_polytrack`

Categorical:

- `previous_rest_bucket`
- `course_code`
- `effort_code`
- `chase_state_code`
- `rider_type_code`
- `furlong_count` treated categorically for B context
- `pair_result_code`
- `pair_effort_code`
- `pair_class_code`
- `training_type_code`
- `training_course_type_code`
- `training_distance_code`
- `training_focus_code`
- `training_volume_code`
- `week_ago_course_code`
- `course_x_rest`
- `effort_x_rest`
- `training_type_x_rest`
- `weekago_to_final_course`

`week_ago_workout_index` is deliberately excluded from the primary B feature set because it is a JRDB processed numeric evaluation rather than a self-built pattern fact.

If a listed source column is absent, the analyzer must report it explicitly and continue only when the missing field is not required for M0 or chronology. It must not silently substitute a different field.

## 6. Trainer-specific historical pattern features

M2 adds strictly-prior, shrinkage-regularized stable-pattern effects. `trainer_code` itself is not one-hot encoded: the objective is preparation-pattern deviation, not trainer quality.

For each test year, each effect is estimated from years strictly before the target year.

Pattern families:

- trainer x `course_code`
- trainer x `effort_code`
- trainer x `training_type_code`
- trainer x `training_course_type_code`
- trainer x current `rest_bucket`
- trainer x `course_code` x `rest_bucket`
- trainer x `effort_code` x `rest_bucket`
- trainer x `training_type_code` x `rest_bucket`
- trainer x `training_volume_code`
- trainer x `weekago_to_final_course`

For a trainer-pattern group with count `n`, group mean delta `g`, and trainer mean delta `t`:

```text
raw_relative_effect = g - t
weight = n / (n + 50)
shrunk_effect = weight * raw_relative_effect
```

Primary shrinkage lambda is fixed at **50**. No lambda selection is permitted after seeing 2018-2023 results.

Unknown/unseen trainer-pattern combinations receive `0.0` relative effect.

To prevent target leakage inside model-training rows, trainer-pattern encodings for any row in year Y are computed only from years < Y, including rows used to train a later fold.

## 7. Model families

All families use Ridge(alpha=1.0) and the same target/eligibility.

- **M0**: confirmed Training Edge v0.1 baseline.
- **M1**: M0 + generic B features.
- **M2**: M0 + trainer-specific shrunk historical-pattern features.
- **M3**: M0 + generic B + trainer historical-pattern features.
- **M4**: M3 + predeclared A x B interactions.

M4 interactions:

- `final_self_pct * return_after_63d_break`
- `final_self_pct * return_after_120d_break`
- `final_self_pct * used_polytrack`
- `final_self_pct * used_slope`
- `final_self_pct * used_wood`
- `final_self_pct * each trainer-pattern effect`

No model family may be added after results are inspected and then treated as predeclared Stage 2b evidence.

## 8. Walk-forward evaluation

Test years are 2018, 2019, 2020, 2021, 2022 and 2023.

For each test year Y:

1. build all chronology-sensitive and trainer-pattern features without using year Y outcomes;
2. fit on eligible rows from 2013 through Y-1;
3. predict eligible year Y rows;
4. retain predictions for pooled out-of-time evaluation.

Report per year and pooled:

- eligible n;
- Spearman(prediction, `performance_delta`);
- RMSE;
- year-relative decile top-minus-bottom mean delta spread;
- median delta spread;
- `P(delta>0)` spread.

For M1-M4 also report:

- Spearman increment over M0 by year and pooled;
- number of test years with positive Spearman increment;
- RMSE change vs M0;
- top-bottom mean-spread change vs M0.

## 9. Stage 2b interpretation rule

The primary comparison is each B model against M0.

A B model is classified **B_CORE_CANDIDATE** only if all of the following are satisfied:

1. pooled Spearman increment over M0 > `+0.0025`;
2. positive Spearman increment in at least `4/6` test years;
3. no recurring material reversal that makes the increment operationally unstable;
4. pooled top-minus-bottom mean RunPerf-delta spread is not worse than M0;
5. pooled RMSE is not materially worse than M0.

If a model has a coherent but smaller or insufficiently stable increment, classify it **B_AUXILIARY_ONLY**.

If the B additions provide no coherent incremental gain or degrade M0, classify them **B_EXCLUDE_FROM_INDEX**.

These are development-period decisions only. A `B_CORE_CANDIDATE` is not independently holdout-confirmed because 2024-2025 has already been consumed.

## 10. Named stable-pattern diagnostics

Named trainer patterns may be reported for interpretability, but they are not the primary model selection mechanism.

A diagnostic discovery/validation split may use:

- discovery: 2013-2017;
- validation: 2018-2023.

Any named rule must report sample size, years observed, discovery effect and validation effect. Retrospective pooled rankings must not be promoted as stable lore without temporal confirmation.

## 11. Controller boundary

Stage 2b decides whether B deserves inclusion in the next Training Edge development cycle.

It does not modify the confirmed Training Edge v0.1 and does not reuse the consumed 2024-2025 holdout as if it were unopened.

If B is retained, final A(+B) index design must be a separately versioned post-v0.1 design and should receive future forward confirmation using genuinely new races (2026+ or later data not used for its design).
