# RaceNote Gen0.3 two-race blind E2E review

Date: 2026-09-25
Scope: post-freeze review only
Targets:
- 2026-09-13 中山10R 初風ステークス / Gen0-G001
- 2026-09-20 中山11R オールカマー / Gen0-G002

## 1. Purpose

Compare two blind Gen0.3 runs after immutable Forecast/Freeze and isolate repeated structural issues without tuning to the observed results.

Current evidence priority remains: DATA / TRENDS > RACEREVIEW >= SIMPLE ABILITY.
No post-result weight fitting or winner-specific rule is introduced.

## 2. Frozen forecasts

Hatsukaze forecast: 1,4,10,3,8,2,9,5,6,7
Hatsukaze actual:   2,8,9,6,10,4,5,3,7,1

Observed issue:
- horse 2 was summarized as FRONT tendency from recent historical corners but raced materially farther back
- horse 1 was summarized as BACK tendency but its historical profile was also mixed
- tendency alone was too easy to read as a position commitment

Local response already adopted:
- dominant_band_count
- dominant_share
- distinct_band_count
- variability_status
- historical_tendency_is_not_position_commitment

No ranking rule was changed.

All Comers forecast: 7,9,8,6,2,3,13,4,12,1,10,11,5
All Comers actual:   8,1,4,7,2,6,13,10,12,3,9,5,11

Notable forecast/actual pairs:
- 8 メイショウゲキリン: forecast 3 -> actual 1
- 1 キャントウェイト: forecast 10 -> actual 2
- 4 ヴーレヴー: forecast 8 -> actual 3
- 7 レガレイラ: forecast 1 -> actual 4
- 2 ワイドエンペラー: forecast 5 -> actual 5
- 9 コスモキュランダ: forecast 2 -> actual 11

The frozen forecast did identify horse 8 as a top-three candidate because its RaceReview was clean HIDDEN_STRENGTH without fragile-form.
However, Race Structure exposed pace_pressure=HIGH and front_or_forward_tendency_count=9 while the actual race allowed horse 8 to obtain the lead without the expected aggregate pressure.

## 3. Shared structural finding

The repeated issue is the historical-position -> race-structure representation layer.
Two ambiguities were identified:
1. Horse-level variability was not explicit enough.
2. Race-level FRONT and FORWARD tendencies were merged into one count, which can be misread as the number of runners contesting the lead.

FRONT tendency != FORWARD tendency != actual lead contest.
Historical positioning is context, not a forecast of today's exact tactical choice.

## 4. Race Structure composition extension

General Evidence race_structure now additionally exposes:
- position_tendency_counts: FRONT / FORWARD / MID / BACK / UNKNOWN
- position_variability_counts: SINGLE_BAND / MULTI_BAND / UNAVAILABLE
- policy.front_or_forward_count_is_not_lead_contest_count = true

The existing pace_pressure calculation is intentionally unchanged for now.

For the All Comers pre-race evidence, composition was:
- FRONT=4
- FORWARD=5
- MID=1
- BACK=2
- UNKNOWN=1
- SINGLE_BAND=2
- MULTI_BAND=11

## 5. Track-condition boundary

Current main already contains a separate pre-result race_day_facts contract for weather and track_condition, but only when supplied from an explicitly result-independent source.
The historical Gen0-G002 Prepare artifact did not have an available race_day_facts source, so the frozen forecast did not consume the rain/heavy-going condition.
This is recorded as a data-availability gap, not a reason to inject post-result track condition into the frozen forecast.

Future work should distinguish:
A. representation issue: historical position composition / variability
B. source availability issue: pre-race weather / going
C. prediction issue: how Scenario should use A + B

## 6. Two-race directional assessment

Hatsukaze:
- top3 overlap: 0/3
- winner forecast rank: 6
- axis actual rank: 10

All Comers:
- top3 overlap: 1/3
- winner forecast rank: 3
- axis actual rank: 4

Interpretation:
- position-variability exposure improved the evidence structure
- it does not by itself solve race-structure forecasting
- RaceReview correctly surfaced All Comers winner 8 into the top group
- coarse pace-pressure aggregation still deserves further blind evaluation

## 7. Current decision

Adopt:
- horse-level position variability fields
- race-level position tendency composition
- explicit policy that front/forward count is not lead-contest count
- pre-result race_day_facts boundary when a valid source exists

Do not adopt yet:
- a new pace-pressure formula
- a FRONT/FORWARD numeric weight
- winner-specific rules for horses 2 or 8
- automatic promotion of UNKNOWN/MULTI_BAND horses
- post-result weather/going injection
- market/popularity as pre-Freeze evidence

Next step:
- run additional blind races with the richer Race Structure representation
- log whether actual lead/position behavior is captured better
- only after repeated evidence consider changing Scenario or pace-pressure semantics
