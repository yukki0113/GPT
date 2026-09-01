# RunPerf holdout protocol v0.1

## Status

**FROZEN BEFORE 2024-2025 OUTCOMES ARE EVALUATED**

This protocol is subordinate to `RunPerf_Development_Decision_v0_1.md` and must not change during the 2024 -> 2025 holdout run.

## Frozen candidate

```text
T1|EXPANDING|RAW
```

Features:

- `time_raw_bias`
- `prev_margin_score`

No other RunPerf candidate, rolling window, DayTrackBias shrink parameter, or carried-weight term may be selected or tuned from the holdout.

## Walk-forward coefficient snapshots

```text
2024 beta <- literal-next-start training pairs with target year <= 2023
2025 beta <- literal-next-start training pairs with target year <= 2024
```

The 2024 completed outcomes may therefore enter the 2025 coefficient snapshot, exactly as they would in live annual updating. The specification itself may not be changed after 2024 is seen.

## Primary diagnostic reference

`B1` is the primary fixed reference because it was the strongest simple independent finish/margin benchmark in development.

Fixed secondary diagnostics:

- B0
- T0|EXPANDING|RAW
- J0
- J1

These are references only. The holdout workflow must not re-run the original 84-candidate ranking.

## Frozen validation classification

For each holdout year compute:

```text
delta_primary_y = primary(T1|EXPANDING|RAW)_y - primary(B1)_y
```

Then classify the two-year holdout:

### PASS_STRONG

- `delta_primary_2024 > 0`
- `delta_primary_2025 > 0`
- mean holdout `delta_primary > 0`
- both fitted T1 coefficients remain finite and positive for both annual snapshots

### PASS_MIXED

- mean holdout `delta_primary > 0`
- exactly one of 2024 / 2025 has `delta_primary <= 0`
- both fitted T1 coefficients remain finite and positive

### FAIL

Any of the following:

- mean holdout `delta_primary <= 0`
- a required T1 coefficient is missing / non-finite
- a required T1 coefficient changes to a non-positive sign
- the selected candidate cannot be evaluated at useful coverage because of an implementation/data failure

`same_surface AND abs(distance_change) <= 400m` performance is reported as a secondary validity check. It does not override the frozen primary classification by itself, but a materially opposite pattern must be called out before Ability development begins.

## Coverage interpretation

Coverage is reported for T1 and B1 separately. The known lower T-family coverage must not be hidden by comparing only complete cases unless the report explicitly labels that subset.

The workflow should also report calculation-status counts so intentional exclusions such as obstacle races are not mislabeled as ordinary missing data.

## After the holdout

- `PASS_STRONG`: promote RunPerf v0.1 and begin Ability development.
- `PASS_MIXED`: RunPerf may remain provisional, but the mixed year must be documented and Ability development should preserve B1/J1 diagnostics.
- `FAIL`: do not tune on 2024-2025 and call it the same holdout. Record the failed generation and start a new development generation with the holdout considered opened.
