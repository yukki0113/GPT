# Debut Ability Snapshot Protocol v0.1

## Status

**PRE-MODEL PROTOCOL — FROZEN BEFORE DEBUT ABILITY PREDICTIVE COMPARISON**

This protocol defines the structural pre-race feature snapshot for horses with no prior scored official RunPerf. It does not select a Debut Ability model or hyperparameters.

## 1. Scope

Debut target:

```text
career_scored_run_count = 0
```

Target label for later development:

```text
official RunPerf v0.1 = T1|EXPANDING|RAW
```

The target result is evaluation only and must remain physically/logically separate from pre-race features.

Existing-Horse Ability v0.1 must not be applied to debut horses as a substitute for this workstream.

## 2. Chronology

For target date D:

```text
pedigree/profile target data: latest valid UKC observation available by D
historical debut labels:       prior horse race_date < D
current workout/training:      target CHA/CYB PRE_RACE row
current jockey/trainer:        target KYI PRE_RACE row
current carried weight:        target KYI PRE_RACE row
current result:                forbidden as input
same-day earlier results:      forbidden as historical input
```

All historical aggregate priors must use only races strictly before D.

UKC profile observation is identity/profile data, not result data. Same-date UKC may be used only when its archive semantics are verified as available pre-race for the target publication snapshot; otherwise use the latest earlier observation and report the availability rule.

## 3. Period policy

- 2010-2012: history formation / warm-up
- 2013-2023: later Debut Ability development walk-forward
- 2024-2025: later post-freeze temporal confirmation only
- 2026 onward: prospective evaluation preferred

No 2024-2025 Debut Ability predictive metric may be inspected during snapshot construction or candidate-definition tuning.

The years 2024-2025 are not pristine project-level holdout years, but Debut Ability predictive metrics from those years remain unopened at protocol freeze.

## 4. Snapshot grain

One row per debut target runner.

Logical key:

```text
race_date
race_key
horse_no
horse_id
```

Every valid PRE_RACE debut runner must remain represented even when pedigree or training evidence is missing.

## 5. Target pedigree identity

Resolve from time-aware `horse_profile_observation`:

```text
sire_name
broodmare_sire_name
sire_line_code
broodmare_sire_line_code
dam_name
birth_date
sex_code
profile_data_date
```

Persist exact source observation date and missing flags.

Do not use horse name alone as identity where `horse_id` exists.

`dam_name` is retained for future sibling/dam priors but must not be treated as a stable dam identity until duplicate/name-collision audit is completed.

## 6. Time-aware pedigree priors

Historical source cohort for each target date D consists only of prior debut races with valid official RunPerf and race_date < D.

Persist raw prior components and sample counts. Do not select shrinkage in this phase.

### 6.1 Sire / broodmare-sire debut level

```text
sire_debut_runperf_raw
sire_debut_n
broodmare_sire_debut_runperf_raw
broodmare_sire_debut_n
```

The target horse's own result can never enter its prior.

### 6.2 Line backoff

```text
sire_line_debut_runperf_raw
sire_line_debut_n
broodmare_sire_line_debut_runperf_raw
broodmare_sire_line_debut_n
```

These provide explicit backoff for new or low-sample sires.

### 6.3 Surface-conditioned pedigree evidence

Persist same-target-surface prior means and counts separately from overall debut means:

```text
sire_surface_debut_runperf_raw
sire_surface_debut_n
broodmare_sire_surface_debut_runperf_raw
broodmare_sire_surface_debut_n
```

Unknown/untried evidence remains NULL + missing, never zero.

### 6.4 Distance-conditioned pedigree candidates

Use the same transparent monotone kernel family as the existing-horse infrastructure and materialize all candidates without selection:

```text
bandwidth = 200 / 400 / 600 / 800m
weight = exp(-abs(history_distance-target_distance)/bandwidth)
```

For sire and broodmare sire separately persist weighted debut RunPerf, n, neff, and missing flags for each bandwidth.

Do not select a bandwidth in the snapshot package.

## 7. Current target training/workout features

Use target PRE_RACE `workout_main` and `training_analysis` only.

Persist raw fields rather than prematurely combining them:

### CHA / workout_main

```text
training_date
workout_count
course_code
effort_code
chase_state_code
rider_type_code
furlong_count
first_segment_sec
middle_segment_sec
final_segment_sec
jrdb_first_segment_index
jrdb_middle_segment_index
jrdb_final_segment_index
jrdb_workout_index
pair_result_code
pair_effort_code
pair_age
pair_class_code
```

### CYB / training_analysis

```text
training_type_code
training_course_type_code
used_slope
used_wood
used_dirt
used_turf
used_pool
used_jump
used_polytrack
training_distance_code
training_focus_code
jrdb_workout_index
finish_index
training_volume_code
finish_change_code
training_evaluation_code
week_ago_workout_index
week_ago_course_code
```

Do not infer a hidden numeric ordering for categorical codes unless a later comparison protocol explicitly defines it.

Missing CHA/CYB rows remain explicit missingness; do not fill them from result data.

## 8. Jockey / trainer debut prior infrastructure

Persist current PRE_RACE:

```text
jockey_code
trainer_code
```

Also persist raw past-only debut history summaries:

```text
jockey_debut_runperf_raw
jockey_debut_n
trainer_debut_runperf_raw
trainer_debut_n
```

These raw averages are **not** the final designed jockey/trainer effects. Final model candidates should use quality-adjusted residual effects after a horse-only/pedigree-training baseline is established.

Snapshot infrastructure must therefore keep enough chronology/count provenance to build later residualized versions without rereading future labels.

## 9. Other PRE_RACE baseline fields

Persist:

```text
current_carried_weight
race_mean_carried_weight
weight_relative
sex_code
age_in_months_if_derivable_pre_race
```

Age is derived only from target race date and UKC birth date.

No body weight or result field may be substituted when a target PRE_RACE value is unavailable.

## 10. Target/evaluation separation

If target official RunPerf is stored in the Debut snapshot database, it must be in a separate table explicitly classified `CURRENT_RESULT`.

The feature builder must never query that table while computing priors or current features.

Structural audits may reconcile label coverage, but 2024-2025 labels must not be used for feature selection or model ranking in this phase.

## 11. Persistence contract

For shrinkable/conditional priors retain where applicable:

```text
*_raw
*_n
*_neff
*_missing
*_config
```

Every target row must retain:

```text
race_date
race_key
horse_no
horse_id
as_of_exclusive
profile_data_date
feature_builder_version
formula_version
source_snapshot
calculated_at
validation_status
```

## 12. Audit gates

Fail closed on at least:

- duplicate target business key;
- target is not actually debut under official RunPerf history;
- any historical prior source race_date >= target_date;
- same-day prior-result use;
- target result used as feature input;
- target SED final going use;
- odds/popularity/market feature contamination;
- profile observation from a disallowed future date;
- debut target dropped solely for missing pedigree/training;
- missing pedigree/training silently encoded as zero evidence;
- non-finite populated numeric prior;
- invalid n/neff/missing relationships;
- current workout/training row mismatched to target race_key+horse_no.

Report annually:

- debut target count;
- target label coverage (structural only);
- sire/damsire/line availability;
- sire/damsire sample-size distributions;
- each distance bandwidth coverage/neff;
- CHA coverage;
- CYB coverage;
- jockey/trainer history coverage;
- weight coverage;
- profile observation lag;
- all violation counts.

## 13. Model-development boundary

This snapshot package must not:

- select pedigree shrinkage;
- select distance bandwidth;
- assign arbitrary numeric order to training categories;
- select a model family;
- residualize jockey/trainer using target/future labels;
- inspect 2024-2025 Debut Ability predictive performance;
- promote a Debut Ability model.

After structural snapshot acceptance, Controller will freeze a separate Debut Ability comparison protocol before predictive development begins.
