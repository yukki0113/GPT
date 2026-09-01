# RunPerf v0.1

## Status

**OFFICIAL v0.1 — PROMOTED AFTER FROZEN 2024-2025 HOLDOUT PASS_STRONG**

RunPerf v0.1 is the official one-run demonstrated-performance target for the JRDB PWA independent-index project.

It was selected on 2013-2023 development data, frozen before holdout, and then evaluated once on the predeclared 2024-2025 holdout without reranking or tuning alternative candidates.

## Official specification

```text
candidate       = T1|EXPANDING|RAW
family          = T1
baseline_method = EXPANDING
time_variant    = RAW
```

For one completed flat-race run:

```text
ExpectedTime = CourseBaseTime + ClassAdjustment
RaceBias = RaceRepresentativeTime - ExpectedTime
DayTrackBiasRaw = median(RaceBias | completed date x venue x surface)
AdjustedTime = ActualTime - DayTrackBiasRaw
TimeResidual = ExpectedTime - AdjustedTime
MarginScore = -margin_seconds_per_1000m

RunPerfRaw = intercept
           + beta_time * TimeResidual
           + beta_margin * MarginScore
```

Higher RunPerfRaw means a stronger demonstrated run.

### ExpectedTime chronology

For target date D, all baseline statistics use only races with dates strictly earlier than D.

```text
history_date < D
```

No result from D enters ExpectedTime for another race on D.

DayTrackBiasRaw is a historical-result value. It is calculated only after the completed date and may then be attached to that completed run when the run is used as history for a later target.

## Coefficient chronology

T1 coefficients are not backfilled globally from future data.

For calendar year Y:

```text
coefficient snapshot for Y
    <- literal-next-start training pairs whose target year <= Y-1
```

Examples:

```text
2013 RunPerf rows <- snapshot fitted through 2012 target-year pairs
2014 RunPerf rows <- snapshot fitted through 2013 target-year pairs
...
2024 RunPerf rows <- snapshot fitted through 2023 target-year pairs
2025 RunPerf rows <- snapshot fitted through 2024 target-year pairs
```

2010-2012 are warm-up history. When those completed runs are materialized for use by the 2013 Ability fold, they use the 2013 snapshot fitted through 2012 and are explicitly tagged as warm-up retrospective rows. A later coefficient snapshot must never be written backward into those rows.

## Development evidence

Development protocol:

- 2010-2012: warm-up / coefficient history
- 2013-2023: annual walk-forward development
- 2024-2025: locked during selection
- 84 candidates compared
- market inputs: none

Selected `T1|EXPANDING|RAW`:

- development years: 11
- positive primary years: 11 / 11
- mean primary rank score: `0.4052267311`
- year SD: `0.0101339613`
- mean same-condition rank score: `0.3857713724`
- mean top-pick win rate: `0.1976720914`
- mean top-pick top-3 rate: `0.4647964449`
- mean coverage: `0.9661143431`

Against B1:

- T1 primary advantage positive in 11 / 11 years
- mean paired difference: `+0.0086297388`
- median paired difference: `+0.0087606059`
- minimum annual difference: `+0.0064926760`
- maximum annual difference: `+0.0103991762`
- same-condition subset also favored T1 in every development year

The time component is incremental: T1 exceeded `T0|EXPANDING|RAW` in every development year.

The four RAW T1 history windows were practically tied. EXPANDING was frozen because it was marginally first while avoiding a rolling-window hyperparameter.

RAW DayTrackBias was retained because it exceeded NO_BIAS in 10 / 11 development years. K2 was nearly tied but did not establish enough advantage to justify another shrink parameter.

## Frozen holdout evidence

Holdout issue:

```text
#286 [JRDB_RUNPERF_HOLDOUT] 2024-2025-v0.1
```

Workflow run:

```text
33453220612
```

Workflow head SHA:

```text
ac9c8eb09344e35c06bc3f8899624303f36a824e
```

Artifact:

```text
jrdb-runperf-holdout-2024-2025-v0.1-33453220612
artifact id = 9780816352
sha256 = 7ef6def9436d692caea3db3867dec411dea5332c670768a38dd1ffd5d036598b
```

Frozen validation classification:

```text
PASS_STRONG
```

Reason:

```text
T1 primary score exceeded B1 in both holdout years
```

Two-year mean:

- mean T1 - B1 primary difference: `+0.0099736784`
- mean same-condition difference: `+0.0132063492`

### 2024

T1:

- primary: `0.3940310843`
- same-condition primary: `0.3750484131`
- coverage: `0.9664939221`
- top-pick win rate: `0.2046193884`
- top-pick top-3 rate: `0.4651919323`

B1:

- primary: `0.3864974610`
- same-condition primary: `0.3651691923`

Difference:

- primary: `+0.0075336233`
- same-condition: `+0.0098792208`

2024 coefficient snapshot, as-of through 2023:

```text
training pairs = 585014
intercept      = 0.6046142161
beta_time      = 0.0250611457
beta_margin    = 0.0947088164
```

### 2025

T1:

- primary: `0.4052428920`
- same-condition primary: `0.3875303737`
- coverage: `0.9662351089`
- top-pick win rate: `0.2102364755`
- top-pick top-3 rate: `0.4868804665`

B1:

- primary: `0.3928291586`
- same-condition primary: `0.3709968961`

Difference:

- primary: `+0.0124137334`
- same-condition: `+0.0165334776`

2025 coefficient snapshot, as-of through 2024:

```text
training pairs = 625484
intercept      = 0.6045819996
beta_time      = 0.0252398396
beta_margin    = 0.0942773218
```

Both fitted coefficients remained finite, positive, and close to their development magnitudes.

## Fixed diagnostic interpretation

The holdout did not rerank the 84 development candidates. It evaluated only the frozen T1 specification plus fixed references.

2024 primary scores:

- T1: `0.3940310843`
- B1: `0.3864974610`
- B0: `0.3755214337`
- T0 RAW: `0.3269635364`
- J1 IDM: `0.3180785645`
- J0 raw score: `0.2953353807`

2025 primary scores:

- T1: `0.4052428920`
- B1: `0.3928291586`
- B0: `0.3758928940`
- T0 RAW: `0.3406182338`
- J1 IDM: `0.3220840503`
- J0 raw score: `0.2985843933`

JRDB IDM remains a useful benchmark. In particular its race-top-pick win/top-3 rates are strong, but its next-start persistence score is below official T1. IDM therefore remains benchmark / later incremental-value material and is not the independent RunPerf target.

## Data-quality / exclusion status

The full 2010-2025 foundation used for the holdout passed Index Base and RunPerf audits.

- runner pre/result match: `781161 / 781161`
- horse-id comparable/match: `781161 / 781161`
- previous links resolved: `2740251 / 2919703`
- fallback race contexts: `53`

2024 EXPANDING RunPerf calculation statuses:

- `OK`: 45437
- `EXCLUDED_OBSTACLE`: 1315
- `EXCLUDED_ABNORMAL`: 429

2025:

- `OK`: 45456
- `EXCLUDED_OBSTACLE`: 1312
- `EXCLUDED_ABNORMAL`: 387
- `EXCLUDED_FALLBACK_CONTEXT`: 729 runner rows across 53 fallback race contexts

The fallback rows are explicit structural exclusions. They are not silently imputed as normal RunPerf rows.

## Market isolation

Odds and popularity are not RunPerf inputs. They remain outside RunPerf, Ability, and Edge and enter only the later Value layer.

## Stored provenance requirement

Official materialized RunPerf rows must keep both the final raw score and transparent components.

At minimum:

```text
race_key
race_date
horse_no
horse_id
calculation_status
expected_time_sec
day_bias_raw_sec
time_raw_bias_sec
margin_score
runperf_raw
coefficient_snapshot_target_year
coefficient_asof_through_year
coefficient_intercept
coefficient_beta_time
coefficient_beta_margin
score_provenance
builder_version
source_snapshot
```

Never persist only an opaque final score.

## Role in later layers

RunPerf v0.1 is a historical target/material for Ability and later Edge construction. It is not itself the PWA display index.

The initial Ability phase should model expected current RunPerf on this raw scale. Any publication-scale transform is a later, versioned, as-of calibration step and must not use future data.

## Canonical supporting documents

- `RunPerf_Development_Decision_v0_1.md`
- `RunPerf_Holdout_Protocol_v0_1.md`
- `README_build_jrdb_runperf.md`
- `README_compare_jrdb_runperf_candidates.md`
- `JRDB_PWA_Index_Design_v0_1.md`
