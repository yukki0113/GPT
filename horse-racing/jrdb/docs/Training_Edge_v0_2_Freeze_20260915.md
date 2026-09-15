# Training Edge v0.2 Freeze — 2026-09-15

## 0. Freeze status

This document freezes the scientific and execution contract for **Training Edge v0.2** before any v0.2 evaluation metric is inspected on 2026 outcomes.

- `TRAINING_EDGE_V0_2_SPEC = FROZEN`
- `2026_OOT_STATUS = UNOPENED`
- `2026_OOT_TEST_YEAR = 2026`
- `2026_OOT_DATA_AVAILABLE_THROUGH = 2026-09-13`
- `POST_2026_OPEN_RETUNING = PROHIBITED`
- `PRODUCTION_DEPLOYMENT = NOT_AUTOMATICALLY_AUTHORIZED`

The 2026-09-13 boundary is an input-availability boundary only. It was not selected from model performance.

The corrected Drive-first input preflight completed successfully in Issue #952 / Actions run `34920441686` with `UNIT=0`, `HISTORY=0`, `DRIVE=0`, `BUNDLE=0`. That preflight did **not** execute the v0.2 evaluator and did **not** inspect 2026 model metrics.

## 1. Research role

RaceNote and other ability-oriented systems estimate ordinary competitive ability and race-level expectation. Training Edge is deliberately narrower:

> `Edge = 今回、平常能力以上に走る材料がどれだけあるか`

The v0.2 model is therefore not an odds model, popularity model, or complete race prediction model.

Hard boundary:

- odds and popularity are forbidden from Edge generation;
- Ability and Edge must not be merged into one learned target here;
- JRDB processed training ratings are treated as the baseline `C`, not as an additional Edge to add again;
- market information may be used later for Value analysis only, outside this frozen Training Edge contract.

## 2. Frozen target and chronology

Target:

`PerformanceDelta = current Official RunPerf - median(strictly-prior same-horse Official RunPerf)`

History is materialized chronologically. Same-day rows are snapshotted before any same-day information is inserted into horse/workout history.

Eligibility is fixed to:

- strictly-prior same-horse Official RunPerf count `>= 3`;
- strictly-prior comparable workout count `>= 3`;
- comparable workout = same horse + same CHA course + same furlong count;
- `PerformanceDelta` is not missing;
- `final_self_pct` is not missing.

`final_self_pct` is the strictly-prior same-horse comparable-workout percentile using final-segment seconds, where smaller seconds are faster. Ties receive half credit.

History formation may use 2010-2012 rows. Model fit rows are 2013-2025. The only v0.2 test year is 2026.

2024-2025 were already opened and consumed as the v0.1 holdout. For v0.2 they are ordinary pre-2026 training history and must never be described as an unopened holdout.

## 3. Frozen signal decomposition

Training Edge v0.2 uses two Ridge models with the same target and preprocessing family.

### 3.1 C — JRDB processed-training baseline

Numeric:

- `kyi_training_score`
- `finish_index`
- `jrdb_final_segment_index`
- `jrdb_workout_index_cha`

Categorical:

- `kyi_training_arrow_code`

`C` represents the processed JRDB training-state baseline.

### 3.2 A — same-horse vertical workout signal

Numeric:

- `final_self_pct`

This is the weak-but-reproducible same-horse vertical component validated before v0.2 design.

### 3.3 B — generic preparation/process context

Numeric/binary:

- `days_before_race`
- `workout_count`
- `previous_days_since_last_run`
- `gap_log_change`
- `return_after_63d_break`
- `return_after_120d_break`
- `pair_work_present`
- `used_slope`
- `used_wood`
- `used_dirt`
- `used_turf`
- `used_pool`
- `used_jump`
- `used_polytrack`

Categorical:

- `rest_bucket`
- `previous_rest_bucket`
- `course_code`
- `effort_code`
- `chase_state_code`
- `rider_type_code`
- `b_furlong_count`
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

`training_type_code` remains an opaque categorical code unless/until a complete primary-source semantic definition is established. No label meaning may be invented for modeling or explanation.

`rest_bucket` is intentionally part of B in the current v0.2 contract. The fixed buckets are:

- `<=20`
- `21-34`
- `35-62`
- `63-119`
- `120+`
- `missing`

### 3.4 Excluded from the core score

The following are explicitly outside the frozen core:

- `trainer_code`
- `trainer_name`
- `week_ago_workout_index`
- `jrdb_workout_index_cyb`
- `training_evaluation_code`

Trainer-specific history remains auxiliary / explanation / diagnostics only. Stage2b showed that the generic B process captured essentially all of the useful incremental signal while trainer-specific structure added only a negligible increment.

## 4. Frozen model and preprocessing

Both C and C+A+B use:

- estimator: `Ridge`
- `alpha = 1.0`
- `solver = lsqr`

Numeric preprocessing:

1. median imputation;
2. missing-indicator addition;
3. standard scaling.

Categorical preprocessing:

1. most-frequent imputation;
2. one-hot encoding;
3. unknown categories ignored at transform time.

No feature selection, alpha selection, calibration change, threshold search, or category reinterpretation may be performed using 2026 outcomes.

## 5. Frozen Training Edge definition

Fit on eligible 2013-2025 rows:

- `C_hat = prediction from C-only model`
- `CAB_hat = prediction from C+A+B model`

Scientific raw value:

`training_edge_raw = CAB_hat - C_hat`

Therefore Training Edge is the estimated incremental A+B contribution beyond the processed JRDB baseline C. This avoids counting the C baseline itself as Edge.

Direction:

- positive: raw Edge `> 1e-12`
- neutral: `abs(raw Edge) <= 1e-12`
- negative: raw Edge `< -1e-12`

The raw value is the primary scientific value.

## 6. Frozen display percentile calibration

Display value:

`training_edge_pct = development-derived empirical percentile(training_edge_raw)`

Calibration asset:

`horse-racing/jrdb/config/training_edge_v0_2_calibration.json`

Frozen calibration provenance recorded in that asset:

- source period: 2013-2023;
- annual walk-forward OOT period: 2018-2023;
- OOT n: 112,766;
- 0..100 empirical percentile knots;
- linear interpolation between knots;
- clipping to 0 / 100 outside the observed development range.

The calibration status is `development_only_not_forward_confirmed` until the one-shot 2026 OOT is opened.

Percentile 50 is the historical median, not mathematical neutrality. Raw zero is approximately the 53.59th development percentile. Raw sign, not percentile 50, defines positive/neutral/negative direction.

The percentile knots must not be recomputed from 2026 data.

## 7. Frozen 2026 one-shot OOT evaluation

Input span required by the evaluator: 2010-2026.

Fit population:

- eligible 2013-2025 only.

Test population:

- eligible 2026 only;
- no 2026 test row may enter fit.

Primary reported blocks are frozen as follows.

### C and CAB blocks

For each model:

- Spearman correlation vs `PerformanceDelta`;
- RMSE;
- score deciles with n, mean target, median target, positive rate;
- top-decile minus bottom-decile spreads.

Increment block:

- `CAB Spearman - C Spearman`;
- `CAB RMSE - C RMSE`.

### Edge block

- raw Edge vs C residual Spearman;
- raw Edge vs target Spearman;
- raw mean;
- raw sample standard deviation;
- raw `>= 0` rate;
- negative / neutral / positive counts;
- raw-Edge deciles against C residual;
- percentile deciles against C residual.

Guard fields must record:

- fit max year = 2025;
- test min/max year = 2026;
- test rows in fit = 0;
- `v0_1_2024_2025_holdout_reused_as_unopened = false`.

The 2026 result is evidence, not a tuning set. Once opened, v0.2 feature blocks, target, eligibility, preprocessing, Ridge parameters, calibration knots, and reporting contract are not to be changed in response to the 2026 metrics.

## 8. Frozen implementation assets on pre-OOT main

Audited immediately before this Freeze document was created:

- `horse-racing/jrdb/src/training_edge_v0_2_core.py`
  - blob `fd54df516520a38bbeba895f08a510ebeffa16f8`
- `horse-racing/jrdb/src/project_training_edge_v0_2_input.py`
  - blob `a8e38fffc3e426fcd85042fcd7d55765cb0b3e65`
- `horse-racing/jrdb/src/evaluate_training_edge_v0_2_oot.py`
  - blob `ee19330559720b148636a451ef6ea8182e766157`
- `horse-racing/jrdb/config/training_edge_v0_2_calibration.json`
  - blob `8c0dfb83824c3ddf5aabe4488b50746435acbe62`
- `horse-racing/jrdb/tests/test_training_edge_v0_2_core.py`
  - blob `bfa42afc8c1bbae56c94856cc11aaa75361e5bd1`
- `horse-racing/jrdb/tests/test_project_training_edge_v0_2_input.py`
  - blob `47dda84a5dfaebe261670b34a9394c826df91864`

Pre-write main HEAD observed during the audit:

`116d4c6e4db9d87ac344fb19099a98213ce5be08`

A separately named `test_evaluate_training_edge_v0_2_oot.py` was not present on this main snapshot; it is therefore not claimed as a frozen test asset.

## 9. OOT workflow gate before execution

The existing workflow

`.github/workflows/jrdb_training_edge_v02_2026_oot_issue.yml`

is **not authorized for execution in its pre-Freeze state**. Its audited blob is:

`63da05ecfbf87f96da81ae4efdb3eb8a15d83d53`

Reasons:

1. it checks out older frozen source SHA `b0865a25f743d2cda34928a6603266ce520c0ba9`;
2. its fixed OOT cutoff is `2026-09-06`, while the corrected audited common input boundary is `2026-09-13`;
3. it uses the older direct JRDB acquisition route rather than the corrected Drive-first input route validated by Issue #952.

Before opening 2026 metrics, the OOT execution workflow must be updated so that its immutable source reference, input route, and cutoff agree with this Freeze and the successful Drive-first preflight. Updating execution plumbing without changing the frozen scientific contract does not constitute retuning.

No 2026 evaluator execution is authorized until that workflow audit/update is complete.

## 10. Irreversible opening rule

Immediately before the first authorized 2026 evaluator run, record the exact Freeze commit / source reference used by the workflow.

After the evaluator has successfully produced any 2026 model metric:

- `2026_OOT_STATUS = OPENED_AND_CONSUMED`;
- 2026 must never again be represented as unopened;
- no metric-driven retuning of v0.2 is permitted;
- any later model redesign must be versioned separately and must not present the already-seen 2026 evidence as a fresh holdout.

Until that event occurs, this document remains at:

`2026_OOT_STATUS = UNOPENED`
