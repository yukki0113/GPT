# JRDB Post-Race Review Design v0.1

Status: DESIGN / implementation-ready  
Date: 2026-09-25  
Repository: `yukki0113/GPT`

## 1. Purpose

JRDB Historical Warehouse / current Raw result dataから、着順だけでは失われる「走った内容」を再構成し、RaceNote・RL指数・研究用途へ共通提供する post-race review layer を定義する。

本layerの主目的は次の5軸である。

1. Time Performance — 時計・クラス水準
2. Pace Performance — レース全体の前傾/後傾と位置取り負荷
3. Position Dynamics — 出負け後の回復、序盤/中盤の押し上げ、捲り、押し上げ後失速
4. Track Bias — コース取り・脚質・枠の当日/開催バイアス
5. Trouble / JRDB Context — JRDB出遅・位置取・不利等の補助情報

Reviewは予想そのものではない。観測事実から再現可能な派生評価を作る evidence layer とする。

## 2. Architectural boundary

```text
JRDB Raw / PACI
      |
      v
Common Reader
      |
      v
Historical Warehouse / current result source
      |
      v
Post-Race Review v0.1
      |
      +----> RaceNote history enrichment
      |
      +----> RL shadow features
      |
      +----> research / audit
```

責務を次のように固定する。

- Warehouse: JRDB fixed-width dataのneutral / normalized facts。
- Analysis v1.3: current lightweight history / consumer compatibility mart。
- Post-Race Review: result後にのみ生成可能な派生解釈。
- RaceNote: Reviewをhistorical evidenceとしてconsumeする。
- RL: Review signalをshadow featureとして検証し、別calibration contractなしに自動加点しない。

Warehouse schemaへReview fieldを書き戻さない。Analysis v1.3の34列logical schemaもReview都合で拡張しない。

## 3. Current source decision

現行Analysis v1.3 `fact_entry_result_lite` は race/horse identity、condition、finish、odds、running style等の軽量履歴を持つが、Reviewに必要な以下の詳細SED result fieldsを保持しない。

- `time_raw`
- `first3f_sec`
- `last3f_sec`
- `first3f_leader_diff_sec`
- `last3f_leader_diff_sec`
- `corners[1..4]`
- `course_lane_code`
- `fourth_corner_lane_code`
- `race_pace_code`
- `horse_pace_code`
- JRDB result metrics / trouble fields

したがってReviewのprimary sourceは次とする。

### Historical 2010-2025

Accepted JRDB normalized Warehouse:

`GPT/horse-racing/10_warehouse/jrdb/v1/current.json`

minimum relations:

- BAC
- KYI
- SED

optional / future:

- UKC
- SKB / ZKB
- HJC

### Current 2026+

現行運用を変更せず、PACI / SED Raw-direct result inputを使用する。

PACI daily normalizationは別scopeであり、Review v0.1の導入条件にしない。

## 4. Stable identity

Canonical keys:

```text
race_key = raw 8-character JRDB race key
race_horse_key = race_key + 2-digit horse_no
```

race keyの日digitはhex-capableでありdecimal化しない。

Review relation grain:

- `fact_race_review`: 1 race
- `fact_race_context`: 1 race
- `fact_horse_performance`: 1 race x 1 horse
- `dim_time_standard`: 1 standard condition bucket
- `fact_track_bias`: 1 date x venue x surface x bias dimension x bucket

## 5. Storage contract

Drive placement:

```text
GPT/horse-racing/20_mart/postrace_review/v0_1/
  current.json
  generations/
    <generation_id>/
      manifest.json
      audit.json
  objects/
    dim_time_standard/
    fact_race_context/
    fact_race_review/
    fact_horse_performance/
    fact_track_bias/
```

Long-term canonical format:

- Parquet
- ZSTD
- immutable content-addressed objects
- generation manifest
- audit sidecar
- fail-closed `current.json` promotion

Do not store a DuckDB database as canonical. DuckDB is the query engine.

## 6. Versioning

Every row produced by Review must be traceable to:

- `review_schema_version = v0.1`
- `review_logic_version`
- `baseline_version`
- `warehouse_generation_id` or current source provenance
- `generated_at`

Algorithm changes that alter semantic values require `review_logic_version` change.

Threshold-only tuning also requires version change when persisted labels change.

## 7. Source fields

### 7.1 BAC

Use when available:

- `race_key_raw`
- race date / source member date
- distance
- surface
- turn
- layout
- race type
- race class
- symbol
- weight rule
- grade
- field size
- course code

### 7.2 KYI

Use when available:

- `race_horse_key`
- `horse_no`
- `blood_registration_no`
- `frame_no`
- declared running style
- carried weight
- start index
- late break rate

Pre-race KYI fields are supporting context only. They do not replace observed result dynamics.

### 7.3 SED

Required or preferred observed result fields:

- `race_key_raw`
- `horse_no`
- `blood_registration_no`
- `date_raw`
- `distance_m`
- `surface_code`
- `track_condition_code`
- `race_class_code`
- `grade_code`
- `field_size`
- `finish`
- `abnormal_code`
- `time_raw`
- `carried_weight_tenths`
- `idm`
- `metrics.raw_score`
- `metrics.track_diff`
- `metrics.pace_score`
- `metrics.late_break_score`
- `metrics.position_score`
- `metrics.trouble_score`
- `metrics.prev_trouble_score`
- `metrics.mid_trouble_score`
- `metrics.late_trouble_score`
- `metrics.race_score`
- `metrics.front_index`
- `metrics.late_index`
- `metrics.pace_index`
- `metrics.race_pace_index`
- `course_lane_code`
- `result_class_code`
- `race_pace_code`
- `horse_pace_code`
- `first3f_sec`
- `last3f_sec`
- `corners[1..4]`
- `first3f_leader_diff_sec`
- `last3f_leader_diff_sec`
- `fourth_corner_lane_code`
- body weight fields when available

JRDB-derived metrics must remain distinguishable from self-derived Review fields.

## 8. Time parsing

`time_raw` must be normalized through one explicit parser.

JRDB SED fixed-length specification defines the 4-byte value as:

- byte 1: minutes
- bytes 2-4: seconds in 0.1-second units

Therefore:

```text
time_sec =
  int(time_raw[0]) * 60
  + int(time_raw[1:4]) / 10
```

Example: `1123 -> 72.3 sec`.

Output:

`time_sec REAL NULL`

Blank, non-4-digit, malformed, or seconds-part >= 60.0 values are invalid and produce NULL. Abnormal-result applicability is evaluated separately; do not impute.

The parser must have characterization tests for valid, blank, malformed, and invalid-seconds values.

## 9. Class taxonomy

Review-owned normalized class groups:

```text
NEWCOMER
MAIDEN
CLASS_1
CLASS_2
CLASS_3
OPEN
G3
G2
G1
OTHER
```

The mapping must be a dedicated config or function and must preserve the original JRDB `race_class_code` and `grade_code`.

Initial v0.1 mapping from JRDB master definitions:

```text
A1 -> NEWCOMER
A2 -> NEWCOMER
A3 -> MAIDEN
04 / 05 -> CLASS_1
08 / 09 / 10 -> CLASS_2
15 / 16 -> CLASS_3
OP -> OPEN

grade 1 -> G1
grade 2 -> G2
grade 3 -> G3
```

Grade G1/G2/G3 takes precedence over the broad race-class group. Other codes remain `OTHER` unless a later explicitly documented mapping is added.

Do not overwrite JRDB source codes.

## 10. dim_time_standard

### Grain

One baseline bucket.

Logical columns:

```text
standard_id
venue_code
surface_code
distance_m
age_group
race_class_group
sample_start_date
sample_end_date
sample_count
median_winner_time_sec
trimmed_mean_winner_time_sec
p10_time_sec
p25_time_sec
p50_time_sec
p75_time_sec
p90_time_sec
mad_time_sec
stddev_time_sec
standard_time_sec
standard_method
scope_level
confidence
baseline_version
review_logic_version
```

### Baseline estimator

v0.1 default:

`standard_time_sec = median(winner_time_sec)`

Historical Review rows must use an as-of-safe baseline:

```text
baseline_sample_end_date < target_race_date
```

No future race may contribute to a historical race's persisted standard. This is mandatory because Review is intended for RL / RaceNote forward evaluation. Early-history rows without sufficient prior samples fall back explicitly or remain low-confidence/NULL; future data must not be borrowed to fill them.

Store trimmed mean and distribution statistics for audit, but do not silently switch methods.

### Initial confidence bands

These are initial operational bands, not statistical significance claims:

- HIGH: n >= 100
- MEDIUM: 30 <= n < 100
- LOW: 10 <= n < 30
- FALLBACK: n < 10

Before production promotion, distribution audit may revise these thresholds only with a logic-version change.

### Fallback hierarchy

Preferred order:

1. venue x surface x distance x age_group x class
2. venue x surface x distance x class
3. venue x surface x distance x adjacent class
4. surface x distance x class

Persist:

- `scope_level`
- `sample_count`
- `confidence`

Never hide fallback use.

## 11. Day track adjustment

Raw winner-time comparisons must not be used as race level directly.

For each race with a valid historical standard:

```text
raw_delta_sec =
  winner_time_sec
  - historical_standard_time_sec
```

Normalize for distance:

```text
delta_per_1000m =
  raw_delta_sec / (distance_m / 1000)
```

Day adjustment grain:

`race_date x venue_code x surface_code`

Estimator:

`median(delta_per_1000m)`

For each target race's persisted Review value, use leave-one-race-out (LOO) estimation: exclude that target race from the same-day residual set before calculating its day adjustment. Persist the inclusive daily estimate separately for descriptive audit if useful, but do not use a race's own time to correct itself.

When LOO evidence is insufficient, use an explicit low-confidence/fallback path rather than silently reverting to the inclusive estimate.

Target-race adjustment:

```text
day_track_adjustment_sec =
  day_adjustment_per_1000m
  * distance_m / 1000
```

Adjusted standard:

```text
adjusted_standard_time_sec =
  historical_standard_time_sec
  + day_track_adjustment_sec
```

Turf and dirt are always separated.

Persist quality fields:

- races used
- distance coverage
- class coverage
- residual dispersion
- confidence

JRDB `metrics.track_diff` is stored as a comparison signal, not used as the self-derived day adjustment by default.

## 12. fact_race_context

Logical columns:

```text
race_key
race_date
venue_code
surface_code
distance_m
field_size

first3f_reference_sec
last3f_reference_sec
pace_balance_sec
pace_balance_percentile
pace_shape
race_pace_code

front_runner_count
closer_count

winner_horse_no
winner_time_sec
winner_corner4_position
winner_last3f_sec

day_track_adjustment_sec
day_track_adjustment_confidence

review_logic_version
```

### Pace shape

Define the signed balance so that a larger positive value means a more front-loaded race:

```text
pace_balance_sec =
  last3f_reference_sec
  - first3f_reference_sec
```

When the opening 3F is faster than the closing 3F, this value is positive. This sign convention is normative.

Do not compare the raw balance across unrelated distances.

Build historical distribution by suitable venue/surface/distance scope and map `pace_balance_sec` to percentile.

Initial labels:

- <= 10 percentile: VERY_BACK_LOADED
- <= 30 percentile: BACK_LOADED
- 30-70: BALANCED
- >= 70: FRONT_LOADED
- >= 90: VERY_FRONT_LOADED

Threshold semantics must be explicitly tested.

## 13. fact_race_review

Logical columns:

```text
race_key
race_date
venue_code
surface_code
distance_m

declared_class_group
winner_time_sec
historical_standard_time_sec
day_track_adjustment_sec
adjusted_standard_time_sec
time_delta_sec
time_delta_per_1000m
time_delta_z
time_delta_percentile

race_time_score_shadow
equivalent_class_group
class_equivalent_numeric
class_gap_steps
race_level_confidence

pace_shape

review_schema_version
review_logic_version
baseline_version
generated_at
```

### Equivalent class

For each target condition, compare the target winner time to the same-day-adjusted standards for available class groups.

Store:

- nearest discrete `equivalent_class_group`
- continuous `class_equivalent_numeric`

The continuous value is preferred for downstream research. Discrete class labels are presentation.

Do not use a human-chosen RL point mapping in v0.1.

## 14. Horse time performance

For each valid finisher:

```text
horse_adjusted_delta_sec =
  horse_time_sec
  - adjusted_standard_time_sec
```

Store the horse's own class-equivalent position against adjusted class standards.

Do not infer a horse performance only from winner gap when an own time is available.

v0.1 does not apply carried-weight time correction. Keep the raw carried weight and a difference-from-race field for future v0.2 research.

## 15. Position normalization

Raw position numbers are field-size dependent.

For a valid position `p` and field size `n > 1`:

```text
frontness =
  1 - (p - 1) / (n - 1)
```

1.0 means front, 0.0 means last.

Persist both original corner position and normalized frontness.

## 16. Position Dynamics

Position change must be described as observed movement first. Do not label every early backward position as a gate delay.

Derived features:

```text
corner1_frontness
corner2_frontness
corner3_frontness
corner4_frontness

early_position_gain
middle_position_gain
late_position_gain

early_gap_recovery_sec
closing_gain_sec

early_move_load_score
middle_move_score
late_move_score
move_then_fade_score
position_dynamics_score
```

Suggested phase definitions:

- early move: initial / first observed position -> corner2
- middle move: corner2 -> corner4 or corner2 -> corner3 where available
- late move: corner4 -> finish rank

Exact definitions must be stable in code and fixture-tested.

## 17. Start delay / second-gear interpretation

Separate two concepts:

### start_delay

Evidence that the horse lost position at or immediately after the start.

Inputs may include:

- JRDB late-break result metric
- pre-race late-break rate as background only
- first observed corner position
- first3f leader gap

### early_recovery_load

Observed cost paid to recover position after being behind early.

This can be computed even when start delay cause is unknown.

Confidence labels:

- CONFIRMED
- LIKELY
- POSSIBLE
- NONE / UNKNOWN

Rules:

- The supplied SED specification identifies the JRDB late-break field but does not define a documented numeric threshold/scale for CONFIRMED/LIKELY classification.
- Therefore v0.1 persists the raw JRDB late-break metric and validates its empirical distribution before assigning threshold-based start-delay confidence.
- Position sequence alone must not assert a gate delay.
- Sequence such as 8 -> 2 -> 2 -> 3 -> 9 supports a strong early recovery / move-then-fade observation, but cause must remain UNKNOWN unless independently calibrated start evidence exists.

Reader-facing wording must distinguish:

- "出遅れ"
- "序盤の位置取り回復"
- "二の脚が鈍かった可能性"

The last is an inference and requires lower confidence or multi-race repeated profile evidence.

## 18. Movement pattern examples

Example A:

```text
8 -> 2 -> 2 -> 3 -> 9
```

Possible derived event chain:

```text
EARLY_POSITION_RECOVERY
  -> EARLY_MOVE_LOAD
  -> PACE_EXPOSURE
  -> LATE_FADE
```

Do not add all components as independent additive points.

Example B:

```text
10 -> 9 -> 3 -> 1 -> 2
```

Possible observed code:

`MIDDLE_LONG_MOVE`

Repeated strong positive middle move can become a horse-profile feature, but not in the single-race v0.1 total score.

## 19. closing_gain_sec

When SED provides a last3f leader gap:

```text
closing_gain_sec =
  last3f_leader_diff_sec
  - finish_gap_sec
```

Positive value means the horse reduced its leader deficit from the last3f reference point to finish.

Handle winner / dead heat / abnormal result explicitly.

Do not synthesize missing leader gaps.

## 20. Pace x Position performance

Pace/position review measures whether a horse occupied a costly or favored location relative to the observed pace.

Examples:

- very front-loaded + high frontness + small final gap => positive context
- very front-loaded + rear position => possible pace assistance
- very back-loaded + rear position + top closing split + small final gap => positive context

The v0.1 output must store components separately from any aggregate label.

Initial fields:

```text
pace_position_score_shadow
pace_position_label
pace_position_reason_codes[]
```

No production RL weight is assigned.

## 21. Track Bias

Track bias is a separate derived dimension.

Bias axes:

1. lane bias
2. running-style bias
3. gate/frame bias

Do not collapse these into one source field.

### Lane bias

Prefer observed result course/lane information over frame when available.

Possible buckets:

- INNER
- MIDDLE
- OUTER

Exact mapping of JRDB `course_lane_code` / `fourth_corner_lane_code` must come from master definitions and be tested.

### Running-style bias

Observed style should use result position pattern when possible.

Initial categories:

- FRONT
- STALK
- MID
- CLOSER

Do not rely only on declared KYI running style.

### Gate bias

Bucket from frame/gate position normalized by field size.

Keep raw frame/gate values.

## 22. Bias estimator

A simple raw average is insufficient because horse ability and pace composition can confound the signal.

v0.1 should calculate two levels:

### Level A: descriptive raw bias

For audit:

- finish residual by bucket
- time residual by bucket
- last3f residual by bucket
- sample count

### Level B: adjusted bias

Primary research signal:

```text
performance_residual =
  actual_performance
  - expected_performance
```

Bias construction is two-pass.

```text
Pass A
  prior-date Review / historical ability
      -> expected performance for today's runners

Pass B
  today's actual performance - pre-day expected performance
      -> same-day lane/style/frame residuals
      -> shrink toward recent-meeting/historical prior
      -> horse-level bias context
```

Expected performance may use only evidence whose race date is strictly before the bias target date. It must not use a leakage feature derived from the same target result. Horses without a usable pre-day expectation may contribute to descriptive Level A but not to adjusted Level B.

Recommended initial control set:

- prior historical time performance / prior Review only
- declared class
- pace context
- field size
- distance / venue / surface

The adjusted estimator must remain auditable; do not introduce an opaque model as the first production implementation.

## 23. Small-sample shrinkage

Same-day lane/style/gate buckets can have very low n.

Use a hierarchy:

```text
same day
  + recent meeting days
  + historical prior
```

v0.1 may use a documented weighted shrinkage formula.

Persist:

- raw same-day estimate
- shrunk estimate
- same-day n
- prior n
- confidence

Do not present n=1-2 same-day observations as a confident bias.

When a same-day bias is applied back to an individual horse, prefer leave-one-race-out bucket estimation so the target race does not materially create the bias used to judge itself. Inclusive same-day bucket summaries may still be stored as descriptive audit evidence.

## 24. fact_track_bias

Logical grain:

`race_date x venue_code x surface_code x bias_dimension x bias_bucket`

Logical columns:

```text
race_date
venue_code
surface_code
bias_dimension
bias_bucket

same_day_sample_count
prior_sample_count

raw_time_residual
raw_finish_residual
raw_last3f_residual

adjusted_performance_residual
shrunk_bias_score

bias_direction
confidence

review_logic_version
baseline_version
```

Bias direction:

- AGAINST
- NEUTRAL
- ASSISTED

for horse-level use, map the bucket score to the route actually taken by each horse.

## 25. Horse-level bias adjustment

Add to horse performance:

```text
lane_bias_score
style_bias_score
gate_bias_score
bias_adjustment_score_shadow
bias_direction
bias_reason_codes[]
```

Example reason codes:

- `INNER_LANE_AGAINST`
- `OUTER_LANE_ASSISTED`
- `CLOSER_STYLE_AGAINST`
- `FRONT_STYLE_ASSISTED`
- `BIAS_AGAINST_RUN`
- `BIAS_ASSISTED_RUN`

Do not treat bias score as proven causal effect. Confidence must be available to consumers.

## 26. Trouble / JRDB context

Keep JRDB-provided result interpretation separately:

```text
jrdb_late_break_score
jrdb_position_score
jrdb_trouble_score
jrdb_prev_trouble_score
jrdb_mid_trouble_score
jrdb_late_trouble_score
```

Self-derived Review fields must not overwrite these.

This separation allows validation such as:

- self-derived start-delay vs JRDB late-break
- self-derived pace-position vs JRDB position score
- self-derived day track adjustment vs JRDB track diff

Agreement is an audit signal, not a requirement for equality.

## 27. fact_horse_performance

Logical columns:

```text
race_key
race_horse_key
horse_no
horse_id
horse_name

finish
abnormal_code
time_sec
winner_gap_sec
carried_weight_kg

historical_standard_time_sec
adjusted_standard_time_sec
horse_adjusted_delta_sec
time_delta_z
time_delta_percentile
time_class_equivalent

first3f_sec
last3f_sec
last3f_rank
last3f_percentile
first3f_leader_diff_sec
last3f_leader_diff_sec
closing_gain_sec

corner1_position
corner2_position
corner3_position
corner4_position
corner1_frontness
corner2_frontness
corner3_frontness
corner4_frontness

early_position_gain
middle_position_gain
late_position_gain
early_gap_recovery_sec

start_delay_score
start_delay_confidence
early_move_load_score
middle_move_score
late_move_score
move_then_fade_score
position_dynamics_score

pace_position_score_shadow
pace_position_label

lane_bias_score
style_bias_score
gate_bias_score
bias_adjustment_score_shadow
bias_direction

jrdb_track_diff
jrdb_pace_score
jrdb_late_break_score
jrdb_position_score
jrdb_trouble_score
jrdb_prev_trouble_score
jrdb_mid_trouble_score
jrdb_late_trouble_score

performance_label
reason_codes_json

review_schema_version
review_logic_version
baseline_version
generated_at
```

Parquet implementation may use additional audit columns. Schema additions require backward-compatible handling or a schema version bump.

## 28. Reason codes

Initial controlled vocabulary:

### Time

- FAST_CLASS_TIME
- SLOW_CLASS_TIME
- ABOVE_DECLARED_CLASS_TIME
- BELOW_DECLARED_CLASS_TIME

### Pace

- FRONT_SURVIVED_FAST_PACE
- REAR_ASSISTED_FAST_PACE
- CLOSER_FROM_SLOW_PACE
- FRONT_ASSISTED_SLOW_PACE

### Position dynamics

- EARLY_POSITION_RECOVERY
- EARLY_MOVE_LOAD
- MIDDLE_LONG_MOVE
- LATE_MOVE
- MOVE_THEN_FADE
- STRONG_CLOSING_GAIN

### Start

- START_DELAY_CONFIRMED
- START_DELAY_LIKELY
- START_DELAY_POSSIBLE

### Bias

- INNER_LANE_AGAINST
- OUTER_LANE_AGAINST
- FRONT_STYLE_AGAINST
- CLOSER_STYLE_AGAINST
- BIAS_AGAINST_RUN
- BIAS_ASSISTED_RUN

### JRDB context

- JRDB_TROUBLE_PRESENT
- JRDB_LATE_BREAK_PRESENT

Reason codes are evidence descriptors, not additive scores.

## 29. Event-chain / double-count prevention

Related observations may belong to one causal chain.

Example:

```text
START_DELAY
  -> EARLY_POSITION_RECOVERY
  -> PACE_EXPOSURE
  -> LATE_FADE
```

Do not score this as four independent votes.

v0.1 must therefore persist:

- primitive observed features
- reason codes
- optional `event_chain_id` / chain classification
- component scores

Any future total score must define de-duplication before calibration.

## 30. performance_label

For reader convenience:

- STRONG_PLUS
- PLUS
- NEUTRAL
- MINUS
- STRONG_MINUS
- UNKNOWN

The label is an interpretation summary. Consumers must retain access to components and confidence.

v0.1 does not define one universal additive formula for this label. Initial implementation may use rule-based labels only when component confidence is sufficient.

## 31. RaceNote integration

RaceNote authoritative facts remain source truth.

Recommended addition:

```json
"review": {
  "version": "postrace-review-v0.1",
  "race_level": {
    "declared_class": "NEWCOMER",
    "equivalent_class": "CLASS_1",
    "confidence": "MEDIUM"
  },
  "performance": {
    "time_class_equivalent": "CLASS_1",
    "pace_position": "PLUS",
    "position_dynamics": "PLUS",
    "bias": "AGAINST"
  },
  "reason_codes": [
    "FAST_CLASS_TIME",
    "EARLY_POSITION_RECOVERY",
    "BIAS_AGAINST_RUN"
  ]
}
```

Review is a compressed interpretation of already related race evidence, not a new independent vote.

RaceNote must not add raw first3f / corner / JRDB metric / Review summary as if each were unrelated evidence.

## 32. As-of / leakage boundary

Review is post-race by definition.

For a target prediction at `target_date`:

```text
review.race_date < target_date
```

is the safe default.

Same-day earlier-race Review may only be used if the runtime explicitly models actual result availability before target post time. v0.1 RaceNote integration does not enable this complexity.

Thus production RaceNote v0.1 Review enrichment is date-exclusive.

No target race result or same-day future race result may affect prediction features.

## 33. RL integration

v0.1 integration is shadow-only.

Expose separately:

```text
review_time_signal
review_pace_position_signal
review_position_dynamics_signal
review_bias_signal
review_confidence
```

Do not change production RL score from these features until a separate calibration / forward-validation contract is accepted.

Do not hand-pick additive alpha/beta weights as production defaults.

## 34. Multi-race horse profile research

Single-race Review rows allow later horse-profile features:

- start_delay_rate
- early_position_gain_avg
- early_move_frequency
- early_move_then_fade_rate
- middle_long_move_rate
- closing_gain_avg
- bias_against_performance_rate

These are future derived features and not part of the base v0.1 canonical relation.

Repeated patterns may support a horse characteristic interpretation such as slow second gear or strong long-sprint ability, but one race must not assert a stable trait.

## 35. NULL policy

Never guess missing observations.

Examples:

- no valid `first3f_sec` -> first3f-based score NULL
- no corner position -> corresponding movement feature NULL
- no bias sample -> bias score NULL / confidence NONE
- abnormal result with unusable time -> time performance NULL

NULL is distinct from neutral / zero.

## 36. Abnormal results

Abnormal / non-standard finish records must be excluded from baseline standard-time estimation unless a specific result code is explicitly accepted.

They may remain in horse-level Review with:

- observed fields retained
- non-applicable performance metrics NULL
- reason / status code explaining exclusion

## 37. Dead heat

Winner selection and winner gap logic must handle tied rank 1.

For race-level winner time:

- all valid rank-1 times must agree within source semantics
- otherwise fail or mark the race invalid for standard-time calculations

Do not arbitrarily choose one tied row if times conflict.

## 38. Track-bias causality wording

Bias is observational.

Reader-facing wording should use formulations such as:

- "内が伸びにくい傾向の中で"
- "外差し有利の傾向に乗った"
- "当日サンプルでは先行優勢"

Avoid claiming deterministic causal proof from small samples.

## 39. Audit gates

A generation is promotable only when all hard gates PASS.

Hard gates:

- manifest/source identity valid
- race key duplicate = 0
- race-horse key duplicate = 0
- orphan horse->race = 0
- invalid required source relation mapping = 0
- non-finite persisted numerics = 0
- future leakage = 0
- Review version fields present
- row counts internally consistent
- object SHA / size match
- repeated deterministic build hash equal for fixed input/config

Soft warnings:

- low baseline sample
- fallback baseline scope
- low track-bias sample
- missing optional SED observation
- unusual track-diff disagreement
- unclassified class code

Warnings do not silently become neutral scores.

## 40. Validation metrics before operational promotion

At minimum, audit:

### Time standard

- sample distribution by venue/surface/distance/class
- fallback rate
- median/MAD stability by year
- day-adjustment distribution
- JRDB track-diff correlation/sign agreement

### Race level

- class-equivalent distribution by declared class
- adjacent-class consistency
- outlier races

### Position dynamics

- frequency of early/middle/late moves
- sequence sanity
- relationship with JRDB position / late-break metrics

### Bias

- same-day n distribution
- shrunk vs raw estimate
- sign stability across meeting days
- extreme-score frequency

### Horse performance

- missingness profile
- score/label distributions
- reason-code frequency
- component overlap / event-chain frequency

## 41. Predictive research gate

Review's value should be tested against future performance, not declared from intuition.

Recommended comparisons:

- same declared class / similar finish horses: high vs low Review signal
- same popularity band
- next-start time performance
- next-start class movement
- next-start finish as secondary outcome

Do not use next race finish alone because class changes can make a strong prior race look poor.

For production RL integration, use blind / true-forward split and freeze logic separately.

## 42. Implementation modules

Recommended initial modules:

```text
src/jrdb_postrace_review.py
src/jrdb_postrace_review_source.py
src/jrdb_postrace_review_standard.py
src/jrdb_postrace_review_bias.py
src/jrdb_postrace_review_publish.py
src/audit_jrdb_postrace_review.py
```

Tests:

```text
tests/test_jrdb_postrace_review_core.py
tests/test_jrdb_postrace_review_standard.py
tests/test_jrdb_postrace_review_bias.py
tests/test_jrdb_postrace_review_leakage.py
tests/test_jrdb_postrace_review_publish.py
```

Keep modules small enough that pure deterministic core logic is testable without Drive or Actions.

## 43. Implementation phases

### Phase 0 — contract freeze

- freeze this design
- confirm source field names from actual Warehouse SED schema
- confirm class code mapping from master
- characterize `time_raw`
- define fixture races

### Phase 1 — pure core

Implement:

- time parser
- class mapper
- frontness
- pace balance / percentile classification
- position movement
- closing gain
- reason-code primitives
- NULL / abnormal / dead-heat handling

No publication and no RL/RaceNote change.

### Phase 2 — source adapters

Implement:

- Historical Warehouse 2010-2025 DuckDB reader
- current PACI/SED adapter
- unified neutral Review input rows

Do not add fixed-width byte offsets outside `jrdb_raw.py`.

### Phase 3 — standards and race review

Implement:

- `dim_time_standard`
- day track adjustment
- race context
- race-level class equivalent
- horse time performance

### Phase 4 — position dynamics

Implement:

- early/middle/late movement
- start-delay evidence
- move-then-fade
- event-chain de-dup metadata

### Phase 5 — track bias shadow

Implement:

- descriptive same-day bias
- recent-meeting/historical shrinkage
- adjusted residual research signal
- horse bias context

Bias remains shadow until audit.

### Phase 6 — immutable Parquet publication

Implement:

- objects
- manifest
- audit
- fail-closed pointer promotion
- deterministic re-read validation

### Phase 7 — RaceNote read-only integration

- expose historical Review
- enforce `race_date < target_date`
- no prediction policy change
- no same-day target leakage

### Phase 8 — RL shadow integration

- expose component features
- do not alter production RL
- collect forward-validation evidence

## 44. Acceptance criteria for Review v0.1 foundation

Foundation implementation is accepted when:

1. Historical Warehouse remains unchanged.
2. Analysis v1.3 remains unchanged.
3. Common Reader remains sole fixed-width field authority.
4. Core pure-function tests PASS.
5. Actual Warehouse SED schema mapping is audited.
6. One representative historical day produces deterministic race/horse Review rows.
7. Duplicate/orphan/leakage hard gates PASS.
8. Review rows preserve source provenance and logic version.
9. No production RaceNote prediction or RL score changes.
10. Design + implementation docs are on latest main.

## 45. Non-goals for v0.1

Explicitly not required:

- official 200m-by-200m sectional reconstruction
- video-derived trip trouble
- weather/wind adjustment
- carried-weight time correction
- jockey skill adjustment
- frame correction independent of measured bias
- opaque ML track-bias model
- production RL additive weighting
- same-day earlier-race dynamic RaceNote use

These may be future versions after Review v0.1 is measured.

## 46. Reader examples

Example:

```text
新馬 3着 0.2差
時計水準: 1勝級
ペース: 前傾
4角: 2番手
位置推移: 8 -> 2 -> 2 -> 2
当日馬場: 内差し不利傾向
JRDB出遅: あり
```

Possible structured review:

```text
Time             PLUS
Pace             PLUS
PositionDynamics PLUS
TrackBias        PLUS
TroubleContext   PRESENT
```

Reason chain:

```text
START_DELAY_CONFIRMED
 -> EARLY_POSITION_RECOVERY
 -> FRONT_SURVIVED_FAST_PACE
 -> BIAS_AGAINST_RUN
```

Reader-facing summary may state:

"新馬戦ながら時計は1勝級。出負け後に序盤で前へ取り付き、前傾戦を先行して小差。内が伸びにくい傾向にも逆らっており、着順以上の内容。"

The prose is a presentation of structured Review evidence; the canonical data is the structured relation, not the sentence.

## 47. Design invariants

The following invariants are mandatory.

- observed facts and derived interpretation remain distinguishable
- JRDB-provided derived metrics and self-derived Review remain distinguishable
- one causal sequence is not multiplied into several independent votes
- missing data is not imputed into neutral values
- small-sample bias is not presented as confident fact
- source/result date leakage is fail-closed
- Review does not silently change prediction policy
- every persisted interpretation is versioned and reproducible
