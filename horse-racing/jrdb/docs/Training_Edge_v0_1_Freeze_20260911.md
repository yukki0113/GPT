# Training Edge v0.1 — Pre-Holdout Freeze

Date: 2026-09-11
Status: **FROZEN FOR ONE-SHOT 2024-2025 HOLDOUT**
Source development DB: `jrdb_training_research_2010_2023_development_lite_v0_1.sqlite`

## 1. Purpose

Freeze the minimum Training Edge candidate before any 2024-2025 predictive outcome inspection.
No feature, bucket, eligibility rule, model hyperparameter or scoring direction may be changed after holdout inspection.

## 2. Outcome

```text
performance_delta =
  current official_runperf_raw
  - median(strictly-prior official_runperf_raw for same horse)
```

Same-day results must not enter the prior history for another runner on the same date.
Minimum strictly-prior valid Official RunPerf count: **3**.

## 3. Same-horse vertical workout feature

Workout value: CHA selected main-workout `final_segment_sec`.
Comparable prior history:

```text
same horse_id
+ same CHA course_code
+ same furlong_count
+ strictly earlier race_date
```

```text
final_self_pct =
  (count(prior final_sec > current final_sec)
   + 0.5 * count(prior final_sec == current final_sec))
  / prior comparable count
```

Higher = faster/better relative to that horse's own prior comparable main workouts.
Minimum prior comparable workout count: **3**.

## 4. Fixed model feature set

Processed JRDB numeric features:

- `kyi_training_score`
- `finish_index`
- `jrdb_final_segment_index`
- `jrdb_workout_index_cha`

Processed JRDB categorical feature:

- `kyi_training_arrow_code`

Context categorical feature:

- fixed `days_since_last_run` bucket:
  - `<=20`
  - `21-34`
  - `35-62`
  - `63-119`
  - `120+`
  - `missing`

Incremental self-vertical numeric feature:

- `final_self_pct`

No trainer interaction is included in v0.1.
No odds, popularity, payout or other market variable is included.

## 5. Preprocessing and estimator

Numeric columns:

1. median imputation fitted on training data only;
2. missing-indicator columns added for numeric variables with missing values;
3. StandardScaler fitted on training data only.

Categorical columns:

1. most-frequent imputation fitted on training data only;
2. one-hot encoding with unknown categories ignored.

Estimator:

```text
sklearn.linear_model.Ridge(alpha=1.0)
```

No alpha tuning is permitted for the holdout evaluation.
Higher predicted score = stronger expected positive RunPerf delta.

## 6. Development protocol already completed

Walk-forward test years: 2018-2023.
For each test year, training uses only earlier development years.

Frozen-model reproduction, 2018-2023:

| year | processed-only Spearman | frozen full Spearman |
|---:|---:|---:|
| 2018 | 0.18189 | 0.20979 |
| 2019 | 0.16069 | 0.18533 |
| 2020 | 0.15978 | 0.20328 |
| 2021 | 0.15663 | 0.18370 |
| 2022 | 0.17747 | 0.20912 |
| 2023 | 0.17091 | 0.20246 |

The full model improves rank association in all six years.

Pooled year-relative deciles for the frozen full model:

- bottom 10% mean RunPerf delta: `-0.050735`
- top 10% mean RunPerf delta: `+0.003577`
- top-minus-bottom mean spread: `+0.054311`
- top-minus-bottom median spread: `+0.048129`
- top-minus-bottom positive-delta-rate spread: `+30.089 pt`

## 7. One-shot holdout protocol

Holdout years: **2024 and 2025**.

Training for holdout scoring is fixed to eligible **2013-2023** development rows only.
The estimator and preprocessing are fitted once on that frozen development set, then applied without modification to 2024 and 2025.

Report separately for 2024, 2025 and pooled 2024-2025:

- eligible row count;
- Spearman(predicted Training Edge, `performance_delta`);
- RMSE;
- year-relative score deciles;
- top10-bottom10 mean RunPerf-delta spread;
- top10-bottom10 median spread;
- top10-bottom10 `P(delta>0)` spread;
- top-decile mean RunPerf delta and positive rate;
- processed-only baseline vs frozen full model on the exact same eligible population.

Do not tune thresholds or refit using 2024 results before evaluating 2025.
Both years constitute one unopened holdout package.

## 8. Decision rule

Controller interpretation after holdout:

- **CONFIRMED**: full model retains clear positive ranking/spread and improves processed-only baseline in both years or strongly pooled without a material year reversal.
- **PARTIAL**: overall signal remains positive but incremental gain is inconsistent by year.
- **FAILED**: ranking/spread materially collapses or reverses.

This rule is interpretive, not a trigger for automatic production deployment.

## 9. Prohibited post-holdout changes

After 2024-2025 inspection, do not redefine v0.1 by changing:

- feature list;
- rest buckets;
- history minimums;
- `final_self_pct` definition;
- imputation/scaling;
- Ridge alpha;
- score direction;
- eligibility rules.

Any such change must become a separately named v0.2 development cycle and must not reuse 2024-2025 as an unopened holdout.
