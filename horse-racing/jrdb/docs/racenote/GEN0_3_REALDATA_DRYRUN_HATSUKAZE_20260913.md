# RaceNote Gen0.3 Real-Data Dry Run Audit — 初風ステークス 2026-09-13

Status: COMPLETED / FROZEN / RESULT-COMPARED  
Dry-run date: 2026-09-25

## 1. Target

- race: 2026-09-13 中山10R 初風ステークス
- surface / distance: ダート1200m
- runners: 10
- source RaceNote run: 36105976370
- prepare run: 36106098797
- Synthesis run: 36106810585
- Pairwise run: 36107077556
- Scenario run: 36108625995
- Forecast / Freeze run: 36108827771

The dry run intentionally kept current result, current market, current JRDB consensus,
Training Edge, and Edge Value hidden until after Forecast Freeze.

## 2. Canonical path exercised

```text
RaceNote bundle
  -> Independent Firewall
  -> RaceReviewDB CURRENT
  -> RaceReview Evidence
  -> Horse Evidence Card
  -> General Evidence
  -> Prediction Interpretation
  -> All-Runner Synthesis
  -> Pairwise Comparison
  -> Scenario Robustness
  -> Forecast Gen0.3
  -> Decision Trace
  -> Freeze
  -> Result / market open
```

All deterministic and authored validation stages passed.

## 3. Fixed independent forecast

Final independent order before result / market open:

1. 1 パルデンス
2. 4 スプランドゥール
3. 10 イリフィ
4. 3 コパノヴィンセント
5. 8 ワンダラー
6. 2 ドンレパルス
7. 9 アシャカトベ
8. 5 アデランテ
9. 6 ポッドソル
10. 7 メイショウコバト

Marks:

- ◎ 1 パルデンス
- ○ 4 スプランドゥール
- ▲ 10 イリフィ
- △ 3 コパノヴィンセント
- △ 8 ワンダラー
- △ 2 ドンレパルス

Scenario conclusion:

- axis horse: 1 パルデンス
- axis robustness: CONDITIONAL
- main risk scenario: SLOW
- Pairwise recheck recommended: false

Prediction hash:

`8749c55b58fe267a002a797b3764508c678e509fef4209f01e24f9e95f8d5cb2`

Freeze audit:

`PASS`

## 4. Actual result opened after Freeze

SED race key:

`06264410`

Actual finish:

1. 2 ドンレパルス
2. 8 ワンダラー
3. 9 アシャカトベ
4. 6 ポッドソル
5. 10 イリフィ
6. 4 スプランドゥール
7. 5 アデランテ
8. 3 コパノヴィンセント
9. 7 メイショウコバト
10. 1 パルデンス

Final win odds / popularity:

- 2 ドンレパルス: 5.2 / 4番人気
- 8 ワンダラー: 4.8 / 3番人気
- 9 アシャカトベ: 3.4 / 1番人気
- 6 ポッドソル: 82.9 / 9番人気
- 10 イリフィ: 4.2 / 2番人気
- 4 スプランドゥール: 47.5 / 7番人気
- 5 アデランテ: 7.7 / 6番人気
- 3 コパノヴィンセント: 7.1 / 5番人気
- 7 メイショウコバト: 60.6 / 8番人気
- 1 パルデンス: 180.0 / 10番人気

Independent forecast vs actual finish had poor rank agreement in this one race
(Spearman rank correlation approximately -0.176).

The marked set contained the winner and runner-up through △2 / △8,
but the forecast axis / opponent / third pick did not match the actual top three.

## 5. What worked technically

The first real-data E2E confirmed that the following boundaries work in production-like data:

- RaceNote Independent Firewall
- RaceReviewDB CURRENT read path
- as-of historical Review lookup
- Horse Evidence Card
- Prediction Interpretation
- full-field Synthesis
- Synthesis-bound Pairwise
- Scenario validation
- Decision Trace provenance
- Forecast probability / mark validation
- Freeze hash audit
- result / market opening only after Freeze

A real-data defect was found and repaired during the run:

- DuckDB / Parquet DATE values were returned as Python `datetime.date`
- RaceReview adapter copied `race_date` without JSON normalization
- JSON serialization failed
- adapter now normalizes `race_date` through the existing date-text boundary
- regression coverage was added and CI passed

## 6. What the prediction result exposed

This single race is not sufficient to recalibrate weights or thresholds.
No result-driven tuning is adopted from this sample alone.

However, it exposed several design questions that should be tested across more races.

### 6.1 Trend direction is not the same as trend materiality

Horse 1 was classified SUPPORTIVE with:

- SAME_SURFACE moderate: win +0.4pp / top3 +1.2pp
- SAME_DISTANCE small: win +3.8pp / top3 +8.5pp
- SAME_VENUE small: win +10.0pp / top3 +23.9pp
- DISTANCE_RANGE moderate: win +0.8pp / top3 +2.2pp

The current Interpretation preserves direction and sample band,
but does not yet classify whether the effect size itself is materially strong.

Therefore a runner may receive a SUPPORTIVE state from several positive deltas
even when some moderate-sample deltas are close to neutral in magnitude.

This should be studied as an evidence-quality problem, not solved by a
result-specific threshold.

### 6.2 MIXED currently compresses materially different conflicts

Winner 2 had:

- same-distance support
- distance-band support
- same-venue opposition
- stable, high Ability Anchor
- RaceReview MIXED

Third-place 9 had:

- strong same-venue positive direction
- same-distance mixed direction
- relatively high current Ability Anchor
- RaceReview FRAGILE_FORM

Both were pushed down partly because their trend state was MIXED.

Future research should preserve which dimension is in conflict and its relevance
to today's race instead of treating MIXED as one homogeneous state.

### 6.3 Ability Anchor may need a floor / ceiling guard study

Winner 2 entered with:

- latest 58
- peak 60
- typical 58
- minimum 56
- MAD 2

The current policy correctly forbids Ability-only promotion,
but a stable high Ability profile can currently be pushed well down the order
when Trend is mixed.

Research question:

Should Ability remain only a tie-breaker, or should a stable high floor act as a
guard against excessive downgrade when higher-priority evidence is mixed rather
than clearly opposed?

This is not adopted yet.

### 6.4 Historical position tendency must not become today's assumed position

The Scenario dry run treated historical FRONT / FORWARD / BACK tendencies too
directly when authoring SLOW / FAST scenarios.

The canonical policy already states:

`historical_position_not_current_jrdb_style = true`

and

`exact_today_position_is_not_predicted = true`

but the current Scenario validator cannot prove that the author respected that
boundary.

Actual result illustrates the risk:

- 2 ドンレパルス had historical FRONT tendency
- actual corner positions were 7 -> 6
- the horse won

Thus historical position tendency is useful context, but must not be treated as
a deterministic current-race tactical position.

### 6.5 Scenario provenance is weaker than Forecast provenance

Decision Trace already fails closed on unavailable Evidence codes.

Scenario v0.1 currently validates:

- complete SLOW / MEDIUM / FAST orders
- changed flag consistency
- non-empty reason codes
- reversal-condition presence
- axis robustness derivation

But `key_reason_codes` are not yet bound to General Evidence / Pairwise evidence,
and reversal-condition text is not machine-linked to a specific validated
Pairwise reversal condition.

This is a structural provenance gap discovered by the dry run.
It should be addressed before Scenario evidence is treated as equally auditable
as Forecast Decision Trace.

## 7. No immediate result-driven tuning

Do not make the following changes from this one race alone:

- do not reduce DATA_TREND priority
- do not promote Ability above RaceReview
- do not add points
- do not fit thresholds to this result
- do not use actual popularity / odds in Independent Forecast
- do not rewrite Synthesis order after result

The user preference remains:

```text
DATA / TRENDS > RACEREVIEW >= SIMPLE ABILITY
```

The next research step is to test whether the implementation of DATA / TRENDS
and Scenario authoring faithfully represents that preference across a larger
sample.

## 8. Recommended next validation

Use a small stratified real-data backtest before changing prediction semantics.

Suggested sample dimensions:

- turf / dirt
- sprint / mile / middle distance
- small / medium / large field
- clear Trend support / mixed Trend / sparse Trend
- clear RaceReview hidden-strength / fragile / mixed
- high / medium / low Race Structure pressure

For each race, Freeze before result open and retain:

- Synthesis draft order
- Pairwise order
- Scenario orders
- Forecast order / probabilities / marks
- Decision Trace
- actual result
- post-Freeze market disagreement

Evaluate failure modes by evidence family rather than only hit rate.

## 9. Artifacts

Prepared evidence:

- run 36106098797
- artifact `racenote-gen0-3-prepare-36106098797`

Synthesis:

- run 36106810585

Pairwise:

- run 36107077556
- artifact `racenote-gen0-3-author-36107077556`

Scenario:

- run 36108625995
- artifact `racenote-gen0-3-author-36108625995`

Frozen Forecast:

- run 36108827771
- artifact `racenote-gen0-3-author-36108827771`
- prediction hash `8749c55b58fe267a002a797b3764508c678e509fef4209f01e24f9e95f8d5cb2`
