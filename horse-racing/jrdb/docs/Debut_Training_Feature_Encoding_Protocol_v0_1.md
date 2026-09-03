# Debut Training Feature Encoding Protocol v0.1

## Status

**FROZEN BEFORE DEBUT ABILITY PREDICTIVE COMPARISON**

This document defines only feature type/encoding semantics for target PRE_RACE CHA/CYB data. It does not select a model, coefficient, category effect, or regularization setting.

Source semantics follow the JRDB fixed-width definitions used by Index Base.

## 1. General rule

A JRDB code is not a continuous/ordinal number merely because its raw representation contains digits or letters.

Initial Debut Ability linear comparisons must:

- one-hot categorical codes with an explicit missing/unknown state;
- preserve genuine numeric measurements/indices as numeric values plus missing flags;
- preserve binary course-use flags as binary values;
- fit all preprocessing on the training fold only.

No target result field may be used.

## 2. CHA — numeric fields

Treat as numeric when populated:

```text
workout_count
furlong_count
first_segment_sec
middle_segment_sec
final_segment_sec
jrdb_first_segment_index
jrdb_middle_segment_index
jrdb_final_segment_index
jrdb_workout_index_cha
pair_age
```

`training_date` is provenance/timing, not a raw scalar model input in the first comparison. A later explicitly designed timing feature may derive a pre-race lag from it.

## 3. CHA — categorical fields

Treat as categorical:

```text
workout_course_code
effort_code
chase_state_code
rider_type_code
pair_result_code
pair_effort_code
pair_class_code
```

In particular, `effort_code` represents named states such as 一杯 / 強目 / 馬なり and must not be assumed linearly spaced.

## 4. CYB — numeric fields

Treat as numeric when populated:

```text
jrdb_workout_index_cyb
finish_index
week_ago_workout_index
```

## 5. CYB — binary course-use fields

Treat as binary indicators:

```text
used_slope
used_wood
used_dirt
used_turf
used_pool
used_jump
used_polytrack
```

## 6. CYB — categorical fields

Treat as categorical:

```text
training_type_code
training_course_type_code
training_distance_code
training_focus_code
training_volume_code
finish_change_code
training_evaluation_code
week_ago_course_code
```

Known semantic examples include:

```text
training_distance_code: 長め / 普通 / 短め / 2本 / 他
training_focus_code:    テン / 中間 / 終い / 平均 / 他
training_volume_code:   A / B / C / D
training_evaluation:    ◎ / ○ / △ categories
```

Do not impose `A > B > C > D` or `◎ > ○ > △` as a numeric distance in the first comparison. One-hot encoding lets development evidence estimate separate category effects without inventing spacing.

## 7. Missingness

`cha_missing` and `cyb_missing` remain group-level missing indicators.

Within a present CHA/CYB row, field-level missing values must also remain explicit during preprocessing. Categorical missing values receive an explicit missing token; numeric missing values use training-fold imputation plus missing flags.

Do not convert missing categorical codes to zero if zero is a real JRDB category such as `0: other`.

## 8. High-cardinality course codes

Workout course codes can be high-cardinality. The later comparison protocol must predeclare one of:

- exact one-hot with rare-category handling fitted on training only;
- documented coarse grouping from the JRDB course master;
- exclusion from the first model family.

Do not derive grouping from target-year outcomes.

## 9. Boundary

This encoding protocol is structural. Structural coverage from 2010-2023 may determine whether a field is practical enough to include in the candidate grid, but no 2024-2025 Debut predictive metric may influence encoding or inclusion decisions.
