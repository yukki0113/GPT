# Training Edge v0.2 — Development Decision

Date: 2026-09-11
Status: **DEVELOPMENT DESIGN FIXED / NOT YET FORWARD-CONFIRMED**

## 1. Purpose

This document converts the completed A/B/C research into the next Training Edge development design.

Research status at this decision point:

- **A — same-horse vertical comparison**: retained and holdout-confirmed as an incremental signal in Training Edge v0.1.
- **B — stable/rotation/training-process patterns**: Stage 2b development validation completed.
- **C — JRDB processed training evaluation**: retained as the baseline rather than replaced.

The objective of v0.2 is not to relabel JRDB's existing training evaluation as a proprietary Edge. It is to estimate the incremental pre-race information added by A + B beyond C.

## 2. Stage 2b adoption decision

Stage 2b compared the confirmed v0.1 development baseline M0 against generic B, trainer-history B and explicit A×B interactions.

Pooled OOT Spearman on 2018-2023:

- M0: `0.1990277`
- M1 = M0 + generic rotation/training-process B: `0.2165464` (`+0.0175187`)
- M2 = M0 + trainer-specific historical patterns: `0.1991295` (`+0.0001018`)
- M3 = M1 + trainer-specific historical patterns: `0.2168032`
- M4 = M3 + explicit A×B interactions: `0.2168202`

M1 improved M0 in all 6 OOT test years and captured almost all of the B gain. M3 added only about `+0.0002568` Spearman beyond M1; M4 added only about `+0.0000170` beyond M3.

Therefore:

```text
B_CORE = M1_GENERIC_ROTATION_TRAINING_PROCESS
B_TRAINER_HISTORY = AUXILIARY_DIAGNOSTIC_ONLY
B_EXPLICIT_A_X_B_INTERACTIONS = EXCLUDE_FROM_CORE
```

This is a complexity-control decision. It does not claim that trainer-specific preparation patterns never exist; it claims that the aggregate incremental value is too small to justify including them in the core index at this stage.

## 3. Conceptual layers

### C — JRDB Training Base

C is the existing processed-JRDB training baseline:

Numeric:

- `kyi_training_score`
- `finish_index`
- `jrdb_final_segment_index`
- `jrdb_workout_index_cha`

Categorical:

- `kyi_training_arrow_code`

C is a baseline/comparator, not the self-built Edge itself.

### A — Horse Vertical Edge

A is the same-horse selected-main-workout vertical feature:

- `final_self_pct`

Definition remains unchanged from the confirmed v0.1 protocol:

```text
same horse_id
+ same CHA course_code
+ same furlong_count
+ strictly prior race_date
```

Higher `final_self_pct` means the current selected main workout is faster relative to the horse's own comparable workout history.

### B — Generic Rotation / Training-Process Edge

B core contains the generic M1 process facts, including current rest context.

Current rest / rotation:

- fixed current `rest_bucket`
- `previous_days_since_last_run`
- `previous_rest_bucket`
- `gap_log_change`
- `return_after_63d_break`
- `return_after_120d_break`

Workout-process facts:

- `days_before_race`
- `workout_count`
- `course_code`
- `effort_code`
- `chase_state_code`
- `rider_type_code`
- `furlong_count` as categorical context
- pair-work presence/result/effort/class
- `training_type_code`
- `training_course_type_code`
- course-use flags: slope/wood/dirt/turf/pool/jump/polytrack
- `training_distance_code`
- `training_focus_code`
- `training_volume_code`
- `week_ago_course_code`
- `course_x_rest`
- `effort_x_rest`
- `training_type_x_rest`
- `weekago_to_final_course`

JRDB `week_ago_workout_index` remains excluded from B core because it is a processed JRDB numeric evaluation and belongs conceptually to C-like information rather than self-built pattern structure.

## 4. Model architecture

Two fixed model families define the v0.2 Edge architecture.

### C model

Predicts `performance_delta` from C only.

```text
C_hat = model(C)
```

### A+B model

Predicts the same target from C + A + B core.

```text
CAB_hat = model(C + A + B_core)
```

Both use the same preprocessing family and `Ridge(alpha=1.0)` unless a separately versioned protocol explicitly changes that choice before future validation.

Target remains:

```text
performance_delta =
  current Official RunPerf
  - median(strictly-prior Official RunPerf for same horse)
```

## 5. Primary Edge definition

The scientific/raw Training Edge is the incremental prediction over the JRDB baseline:

```text
training_edge_raw = CAB_hat - C_hat
```

Interpretation:

- `> 0`: A+B information raises the expected current-day performance relative to what C alone would imply.
- `< 0`: A+B information lowers the expected current-day performance relative to C alone.
- approximately `0`: A+B adds little information beyond C.

This keeps the Edge semantically separate from the strength of JRDB's existing training evaluation.

The primary stored value should remain `training_edge_raw` in Official RunPerf-delta units. This is the least arbitrary research output and preserves sign and magnitude.

## 6. Display index

A secondary presentation index may be generated from `training_edge_raw`, but it must not replace the raw value in the research/store layer.

Preferred display form:

```text
training_edge_pct = empirical percentile of training_edge_raw
                    against a frozen out-of-time development calibration distribution
```

Suggested interpretation:

- near 50: typical incremental effect
- high percentile: unusually positive A+B Edge
- low percentile: unusually negative A+B Edge

Because percentile 50 and raw zero are different concepts, the UI/API should expose both:

- `training_edge_raw`
- `training_edge_pct`
- `training_edge_direction = sign(training_edge_raw)`

Do not invent fixed point multipliers merely to force the score into a 0-100 scale.

## 7. Optional component diagnostics

For explanation only, counterfactual component models may be exposed:

```text
A_increment = model(C + A) - model(C)
B_increment = model(C + B_core) - model(C)
```

These are diagnostics and need not sum exactly to `training_edge_raw`, because each counterfactual model is refit separately.

Trainer-specific named patterns may also be surfaced as annotations when historically supported, but they must not alter the v0.2 core score unless a future separately versioned study promotes them.

## 8. Version and validation boundary

Training Edge v0.1 remains immutable and confirmed on the one-shot 2024-2025 holdout.

The A+B design in this document is a new cycle:

```text
TRAINING_EDGE_V0_2 = DEVELOPMENT_CANDIDATE
V0_1_2024_2025_HOLDOUT = CONSUMED
V0_2_2024_2025_UNOPENED_HOLDOUT = false
```

Therefore v0.2 must not claim independent confirmation from 2024-2025.

Before production promotion, freeze the exact v0.2 implementation and evaluate it on genuinely new temporal evidence. Preferred options are:

1. 2026 data not used in v0.2 design as an explicitly labeled unseen-by-v0.2 OOT check; and
2. subsequent races scored prospectively before results are known for true-forward confirmation.

## 9. Current controller decision

```text
A = INCLUDE
B_GENERIC_PROCESS = INCLUDE
B_TRAINER_HISTORY = AUXILIARY_ONLY
B_EXPLICIT_INTERACTIONS = EXCLUDE_FROM_CORE
C = BASELINE / COMPARATOR
PRIMARY_EDGE = prediction(C+A+B) - prediction(C)
PRODUCTION = NOT_YET_AUTHORIZED
```

Next implementation task: materialize the v0.2 scorer and frozen calibration contract, then obtain new temporal confirmation without modifying the design after results are inspected.
