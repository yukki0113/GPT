# JRA Course Profile — CourseStats Phase 4 v0.1

Status: INITIAL IMPLEMENTATION  
Date: 2026-10-13

## Scope

Phase 4 builds period-dependent historical course tendencies from accepted JRDB Historical Warehouse SED.

Per current project decision, **obstacle races are excluded from Phase 4 v0.1**. Only turf and dirt are aggregated.

The primary grain is `course_key`. A secondary `course_key × geometry_key` view preserves A/B/C/D rail geometry when the JRA official geometry configuration can be resolved.

## Temporal contract

Every row has:

```text
period_from
period_to_exclusive
stats_definition_version
population_filter_id
source_generation
generated_at
```

v0.1 uses `population_filter_id=ALL_FLAT_RESULTS_V0_1`. Future good-track-only, class-restricted, age-restricted, or other populations must use a different filter ID rather than silently changing the meaning of the same row.

The interval is half-open:

```text
period_from <= race_date < period_to_exclusive
```

Prediction-time use must satisfy:

```text
period_to_exclusive <= target_race_date
```

The 2010–2025 build is an audit/research baseline, not permission to use future races in historical prediction replay.

## Population

- JRA venue codes 01–10
- surface_code 1 turf / 2 dirt
- latest SED row by `race_key_raw × horse_no`
- runner outcome metrics use normal finishers only: abnormal_code blank/0 and finish within 1..field_size
- race-level metrics require a normal winner

## Pace

Race pace uses:

- `race_pace_code`: H / M / S
- `metric_race_pace_index`
- race first 3F: minimum valid `first3f_sec` among normal finishers, representing the leading 3F clock
- race time: winner `time_raw`, decoded using the JRDB 1-minute-byte + tenths-second format

Rates are calculated only across races with a valid H/M/S code.

## Running style

Source: post-race `SED.race_running_style_code`.

v0.1 groups:

- front: 1 逃げ
- stalker: 2 先行 + 5 好位差し
- midpack: 3 差し
- closer: 4 追込

Win/top3 rates use normal runners in that style as denominator.

## Last-3F

For each race, normal finishers with a valid `last3f_sec` are ranked.

```text
last3f_speed_percentile
= 1 - percent_rank(last3f_sec ASC)
```

Thus 1.0 is fastest and 0.0 is slowest.

`late_speed_importance_delta` is:

```text
avg_top3_last3f_percentile
-
avg_all_last3f_percentile
```

This is a descriptive dependence indicator, not a causal effect.

## Draw band

Phase 4 does not require KYI `frame_no`. Draw position uses the SED horse number normalized by field size:

```text
draw_position = (horse_no - 0.5) / field_size
```

- inside: <= 1/3
- middle: > 1/3 and <= 2/3
- outside: > 2/3

This keeps the meaning comparable across different field sizes.

`inside_draw_advantage` and `outside_draw_advantage` are the band's top3 rate minus the overall top3 rate. They are unadjusted descriptive deltas in v0.1.

## Geometry stats

`course_geometry_stats` joins SED `course_code` to the JRA official geometry configuration from Phase 3.

If geometry cannot be resolved, the race remains in ordinary `course_stats` but is not placed into a geometry row.

Geometry rows are emitted for audit regardless of sample size. `eligible_for_use=true` requires at least 30 races by default.

## Historical geometry caveat

The stable `course_key` statistics can span course renovation eras until historical `course_version` periods are fully populated. The all-2010–2025 output is therefore a baseline characterization artifact.

Consumers requiring physical-version purity must wait for version-aligned periods or explicitly constrain the aggregation window.

## Outputs

`build_jra_course_stats_phase4.py` emits:

- `course_stats_v0_1.parquet`
- `course_stats_v0_1.jsonl`
- `course_geometry_stats_v0_1.parquet`
- `course_geometry_stats_v0_1.jsonl`
- `phase4_summary.json`

`validate_jra_course_stats_phase4.py` emits a separate validation report and fails closed on key/range/period/eligibility violations.
