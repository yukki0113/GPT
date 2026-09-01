# Ability development protocol v0.1

## Status

**PRE-MODEL PROTOCOL — FROZEN BEFORE ABILITY MODEL COMPARISON**

This document defines the chronology, feature-snapshot contract, development periods, and initial Ability-core feature candidates after official RunPerf v0.1 was completed.

It does not select an Ability model or coefficients.

## 1. Definition

Ability is the expected official RunPerf under the target race conditions if the horse performs normally.

```text
Ability(target race, horse) = E[official RunPerf v0.1 | information available before target race]
```

Official RunPerf v0.1 is `T1|EXPANDING|RAW` and must not be redesigned inside Ability work.

Ability is separate from Edge. Hidden trouble, start shock, unusual training changes, pace interaction, condition-change uplift/downside, and other expected residual effects belong to Edge unless a later incremental test explicitly promotes them.

Odds, popularity, and market-derived information are forbidden from Ability.

## 2. Chronology

For target date D:

```text
historical result input: race_date < D
current pre-race input:  available before the target publication snapshot
current result input:    forbidden
```

Same-day completed race results are not historical input for another target race on D in the published Ability snapshot.

Official RunPerf rows used as history must preserve their own annual as-of coefficient provenance. Ability must never recompute old RunPerf with a later coefficient snapshot.

## 3. Period policy

RunPerf used 2013-2023 for development and 2024-2025 for its frozen validation. Therefore 2024-2025 are no longer described as a pristine project-level holdout for Ability.

Ability policy:

- 2010-2012: warm-up / feature-history formation
- 2013-2023: Ability development walk-forward and model freeze
- 2024-2025: post-freeze temporal confirmation only; not model tuning
- 2026 onward: preferred prospective/live evaluation for the final published pipeline

During Ability development, no result metric from 2024-2025 may be used to select decay, shrinkage, feature definition, model family, regularization, calibration, or acceptance criteria.

Ability model comparison begins only after the feature snapshot builder/audit is accepted and a separate decision record fixes the exact development comparison protocol.

## 4. Snapshot grain and availability

One row per target race x runner.

Logical key:

```text
race_date
race_key
horse_no
horse_id
```

Every target runner must remain represented when pre-race runner data exists, including debut horses.

Availability classes are explicit:

- `HISTORICAL`: strictly earlier result/history
- `PRE_RACE`: target-race information available before publication
- `CURRENT_RESULT`: target result; target/evaluation only, never feature input

A race context synthesized from current-result fallback is not valid pre-race context for Ability and must be excluded or explicitly marked unavailable.

## 5. Immediate existing-horse core

The first feature snapshot build creates the following candidate components without selecting their final tuning parameters.

### 5.1 Career evidence

```text
career_scored_run_count
recent_scored_run_count
last_scored_run_date
rest_days
is_debut
```

Only official RunPerf rows with a valid scored status and `history_date < target_date` enter performance history.

### 5.2 Recent performance candidates

Use at most the latest 5 valid official RunPerf rows.

Create separate candidate columns for recency decay:

```text
recent_perf_d070
recent_perf_d080
recent_perf_d090
recent_perf_d100
```

Newest historical run has weight 1.0; each older run is multiplied by the stated decay.

Persist for each candidate where applicable:

```text
_n
_neff
_missing
```

No decay is selected in the snapshot phase.

### 5.3 Peak and gap candidates

Within the same latest-5 valid history window, persist transparent components:

```text
peak_best1_last5
peak_best2_mean_last5
```

Do not invent a fixed best1/best2 blend before model comparison.

For each recent candidate, a derived peak gap may be materialized, but the underlying peak and recent values must remain stored.

### 5.4 Performance stability

Initial robust candidate:

```text
performance_mad_last5
```

Require at least 3 valid historical runs; otherwise NULL with explicit missing flag.

Retain n and missing status. Do not map insufficient history to zero stability.

## 6. Aptitude components

Aptitude must represent conditional historical performance relative to the horse's own broader evidence, not a raw absolute average that simply re-encodes general ability.

Use up to the latest 12 valid official RunPerf histories for the first build and persist raw components, sample counts/effective sample sizes, and missing flags. Final shrinkage is selected later.

### 6.1 Surface

For current target surface, compute the horse's same-surface historical RunPerf summary and an own-history contrast against the broader historical baseline.

Persist at minimum:

```text
surface_same_mean_raw
surface_overall_mean_raw
surface_fit_delta_raw
surface_fit_n
surface_fit_neff
surface_fit_missing
```

Unknown/untried surface is NULL + missing, never zero fit.

### 6.2 Distance

Distance fit is continuous. Build candidate kernel summaries using absolute distance difference and no future rows.

Initial bandwidth candidates:

```text
200m
400m
600m
800m
```

Use a documented monotone kernel such as `exp(-abs(distance_diff)/bandwidth)` and persist each candidate separately, including neff. No bandwidth is selected in this phase.

Also retain the raw distance difference to the nearest historical scored run and exact-distance sample count for diagnostics.

### 6.3 Course

Persist exact venue x surface evidence separately from hierarchical backoff evidence.

At minimum:

```text
course_exact_mean_raw
course_exact_delta_raw
course_exact_n
course_exact_neff
course_surface_backoff_mean_raw
course_fit_missing
```

Do not force an exact-course estimate when evidence is absent. Final hierarchical shrink/backoff weight is a later development choice.

### 6.4 Going

Historical going labels may come from completed historical results.

The **target current-going code must come from a verified PRE_RACE source**. The target SED/final result track-condition code is forbidden.

If no trustworthy PRE_RACE target-going source exists in the historical archive at the intended publication timing:

- set current-going-dependent Ability feature(s) to NULL/missing,
- report availability coverage,
- do not backfill from target result,
- do not silently remove the feature from the registry.

Persist same-going/same-surface raw evidence and counts when target-going is valid.

## 7. Jockey general effect v0 infrastructure

The Registry requires a horse-quality-adjusted residual rather than raw jockey win rate or raw jockey RunPerf average.

For each historical ride R used to estimate a jockey effect:

1. construct a horse-only expected baseline using only that horse's scored runs strictly earlier than R;
2. exclude rides for which a valid horse-only baseline cannot be formed from the initial jockey residual estimator, while counting them for coverage diagnostics;
3. compute

```text
jockey_residual_R = official_runperf_R - horse_only_expected_before_R
```

4. for target date D, aggregate only jockey residuals from rides with `ride_date < D`.

The first infrastructure build must persist raw past-only jockey residual mean, n, recency metadata, and missing flag. Final shrinkage and optional surface-specific effect are later model-development choices.

No target result or same-day prior race result enters the published target snapshot.

## 8. Current carried weight

`weight_relative` is PRE_RACE:

```text
current runner carried weight - current race mean carried weight
```

Use only target pre-race runner information. If the runner weight or sufficient field weights are unavailable, retain NULL/missing rather than impute a future/result value.

Store current raw carried weight, field mean, relative value, and field valid-weight count for audit.

## 9. Debut horses

Debut horses remain in the Ability snapshot.

For `career_scored_run_count = 0`:

- historical performance and aptitude features remain NULL with missing flags;
- do not emit zero Ability evidence;
- preserve PRE_RACE jockey/weight/training/profile fields that are independently available;
- mark `is_debut = 1`.

A later dedicated Debut Ability phase will add time-aware pedigree, workout, jockey-debut, and trainer-debut priors on the same official RunPerf scale.

The first snapshot infrastructure must therefore not drop debut rows simply because recent/aptitude features are missing.

## 10. Target/evaluation separation

Current official RunPerf for the target race is an evaluation label, not an Ability feature.

Prefer a physically/logically separate target table or clearly separated target columns with an explicit `CURRENT_RESULT` contract.

Feature-builder code must not select target result columns into feature calculations.

Structural audits may verify target-label join coverage. During the feature-infrastructure phase, do not rank feature candidates using 2024-2025 target outcomes.

## 11. Persistence contract

Do not persist only finalized feature values.

For shrinkable/candidate features keep where applicable:

```text
*_raw
*_n
*_neff
*_missing
*_config
```

Every snapshot stores:

```text
race_date
race_key
horse_no
horse_id
as_of_exclusive
feature_builder_version
formula_version
source_snapshot
calculated_at
validation_status
```

Audit provenance must make it possible to prove the latest historical source date is strictly earlier than the target date.

## 12. Snapshot audit gates

The Ability feature-snapshot audit fails closed on at least:

- duplicate target business keys
- missing mandatory target pre-race identity
- any historical source date `>= target_date`
- any current-result column used by feature SQL/calculation
- target SED going used as current-going feature
- official RunPerf row recomputed with a later/non-recorded coefficient snapshot
- debut runner dropped solely for no history
- missing/unknown aptitude converted to zero without an explicit missing flag
- non-finite scored numeric feature
- market/odds/popularity column in Ability feature schema
- fallback current-result race context treated as valid PRE_RACE context
- inconsistent n/neff/missing contracts

Report annual feature coverage, debut coverage, career-count distribution, each candidate's missing rate, and source-date lag diagnostics.

## 13. Ability model phase after snapshot acceptance

Model comparison is a later work package.

Planned candidates remain:

- `A0`: transparent/simple Ability baseline
- `A1`: Ridge / Elastic Net family
- `A2`: nonlinear challenger only after A0/A1 are established

The exact target transform, feature set, regularization grid, recent-decay selection, aptitude shrinkage, and model acceptance rule must be frozen before 2024-2025 temporal confirmation metrics are opened for Ability.

Small performance differences favor simpler models.

## 14. Evaluation principles for later model comparison

Primary evaluation should operate on the official RunPerf raw scale and race-relative ordering, with equal-year aggregation so large years do not dominate.

At minimum later comparison should report:

- correlation / rank correlation with target official RunPerf
- race-within rank quality
- top-pick win/top3 diagnostics
- calibration/error on RunPerf raw scale
- coverage
- debut vs existing-horse strata
- career-count strata
- surface/distance-condition strata
- year-by-year stability

Popularity/odds are excluded from all Ability model selection metrics except a later separate Value analysis.

## 15. Current work boundary

The immediate next work package builds and audits the pre-race Ability feature snapshot infrastructure only.

It must not:

- select recent decay,
- select distance bandwidth,
- select shrinkage constants,
- fit/choose A0/A1/A2,
- inspect 2024-2025 Ability performance for tuning,
- redesign official RunPerf v0.1.
