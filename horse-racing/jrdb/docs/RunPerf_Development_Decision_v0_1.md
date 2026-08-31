# RunPerf development decision v0.1

## Status

**FROZEN BEFORE HOLDOUT**

This decision record freezes the provisional independent RunPerf specification before any 2024-2025 holdout result is opened.

- Development workflow issue: `#285 [JRDB_RUNPERF_COMPARE] development-2013-2023-v0.1`
- Workflow run: `33451405005`
- Comparison head SHA: `7e5256795d27372f3dde504c060850d4ab54baed`
- Development years: 2013-2023
- Warm-up / coefficient history: 2010-2012
- Locked holdout at decision time: 2024-2025
- `holdout_touched = false`
- Candidate count: 84
- All Index Base / RunPerf audit gates: PASS

## Frozen provisional RunPerf

```text
family          = T1
baseline_method = EXPANDING
time_variant    = RAW
candidate       = T1|EXPANDING|RAW
```

Semantics:

```text
ExpectedTime = expanding-past-only CourseBaseTime + ClassAdjustment
DayTrackBias = raw median historical RaceBias for completed date x venue x surface
TimeResidual = ExpectedTime - (ActualTime - DayTrackBias)
RunPerf(T1) = fitted intercept
            + beta_time * TimeResidual
            + beta_margin * previous-run margin score
```

The coefficients are not globally backfilled. Every prediction/evaluation year uses an as-of coefficient snapshot fitted only from earlier target years.

## Why T1 is selected

The predeclared independent-core eligible families were `B0 / B1 / T0 / T1`. `T2 / T3` remain diagnostic until carried-weight effects are separately identified, and `J0 / J1` remain JRDB benchmarks.

### Development summary

`T1|EXPANDING|RAW`:

- development-year count: 11
- positive primary years: 11 / 11
- mean primary rank score: `0.4052267311`
- year SD of primary rank score: `0.0101339613`
- mean same-condition rank score: `0.3857713724`
- mean top-pick win rate: `0.1976720914`
- mean top-pick top-3 rate: `0.4647964449`
- mean coverage: `0.9661143431`

Best simple finish/margin benchmark `B1`:

- mean primary rank score: `0.3965969923`
- mean same-condition rank score: `0.3745040249`
- mean coverage: `0.9940253575`

Paired annual difference `T1|EXPANDING|RAW - B1`:

- positive years: 11 / 11
- negative years: 0 / 11
- mean difference: `+0.0086297388`
- median difference: `+0.0087606059`
- minimum annual difference: `+0.0064926760`
- maximum annual difference: `+0.0103991762`

The same-condition subset (`same surface AND distance change <= 400m`) also favors T1 in every development year.

### Time component is incremental

Against `T0|EXPANDING|RAW`, T1 improves the primary rank score in all 11 development years.

- mean paired improvement: approximately `+0.07177`

This supports retaining both the time and margin components rather than using TimeResidual alone.

### DayTrackBias decision

`RAW` is retained instead of `NO_BIAS` because the raw completed-day correction improves the primary development score in 10 / 11 years.

- mean paired `RAW - NO_BIAS`: `+0.0035346435`

`RAW` versus `K2` is much closer:

- mean paired `RAW - K2`: `+0.0002936398`
- RAW better: 9 / 11 years
- K2 better: 2 / 11 years

The shrink variants do not establish a development advantage large enough to justify another tuning parameter. Therefore the simpler RAW form remains frozen.

### Baseline-window decision

The four RAW T1 history windows are practically tied:

- `EXPANDING|RAW`: `0.4052267311`
- `ROLLING_3Y|RAW`: `0.4052200728`
- `ROLLING_2Y|RAW`: `0.4051031360`
- `ROLLING_5Y|RAW`: `0.4050864821`

The top-vs-3Y mean difference is only about `0.0000067`, far below the best candidate's year-to-year SD (`0.01013`) and below the paired annual variation between the two windows. Under the predeclared complexity rule, `EXPANDING` is frozen because it has no rolling-window hyperparameter and is marginally first on the primary metric.

## Coefficient stability

For `T1|EXPANDING|RAW`, all fitted coefficients retain the same sign throughout 2013-2023.

TimeResidual coefficient:

- 2013: `0.0224109`
- 2023: `0.0249850`
- min: `0.0224109`
- max: `0.0249850`
- mean: `0.0241215`
- adjacent sign flips: `0`

Margin-score coefficient:

- 2013: `0.0995823`
- 2023: `0.0962607`
- min: `0.0962607`
- max: `0.0995823`
- mean: `0.0981703`
- adjacent sign flips: `0`

This is sufficiently stable for a provisional holdout freeze.

## JRDB benchmark interpretation

JRDB IDM (`J1`) remains useful as a benchmark. Its race-top-pick win/top-3 rates are strong, but its development primary next-start persistence score is materially below the selected T1 candidate.

This does not mean IDM is useless. It means it is not adopted as the independent RunPerf target. It remains available later for benchmark / incremental-value testing under the JRDB provenance rules.

## Holdout contract

2024-2025 may be opened only after this file exists on `main`.

The holdout must be evaluated as one uninterrupted walk-forward protocol without changing the RunPerf family, baseline method, DayTrackBias variant, fitting features, or adoption rule between 2024 and 2025.

```text
2024 coefficient snapshot <- pairs whose target year <= 2023
2024 evaluation
2025 coefficient snapshot <- pairs whose target year <= 2024
2025 evaluation
```

Using 2024 completed results to update the 2025 coefficient snapshot is allowed because it reproduces live as-of operation. What is forbidden is changing the specification after seeing 2024 and then treating 2025 as an untouched continuation of the same model-generation decision.

Holdout evaluation may report B0/B1/T0/J0/J1 as fixed diagnostic references, but must not re-rank the original 84 candidates or tune a new window/bias variant on holdout.

## Decision after holdout

The holdout is validation, not another development search.

- If T1 remains directionally sound and stable, promote this RunPerf specification to v0.1 official and proceed to Ability.
- If it fails materially, record the failure. Any redesign starts a new model generation and 2024-2025 can no longer be called untouched holdout for that redesigned specification.
