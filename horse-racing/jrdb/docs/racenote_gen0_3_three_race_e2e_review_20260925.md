# RaceNote Gen0.3 three-race blind E2E review

Date: 2026-09-25
Scope: post-freeze engineering review

## 1. Blind E2E cohort

1. 2026-09-13 中山10R 初風ステークス / Gen0-G001
2. 2026-09-20 中山11R オールカマー / Gen0-G002
3. 2026-09-12 阪神11R チャレンジカップ / Gen0-G003

All target results remained hidden until each Forecast Freeze audit passed.

## 2. Challenge Cup frozen forecast

Forecast final order:
`10,15,8,7,4,12,13,9,5,3,11,14,1,16,6,2`

Frozen marks:
- ◎ 10 タガノデュード
- ○ 15 ジョバンニ
- ▲ 8 カラマティアノス
- △ 7 ジーティーアダマン
- △ 4 ガイアメンテ
- △ 12 レーゼドラマ

Forecast ID: `20260912_阪神_11_Gen0-G003`
Prediction hash: `4cef088f4b1b57a2ab5665891754f6eb13818266c5f47cc1c94e93d367d603a7`

## 3. Post-freeze result reading

Actual top three:
- 1st: 15 ジョバンニ
- 2nd: 8 カラマティアノス
- 3rd: 7 ジーティーアダマン

Frozen forecast ranks for those horses:
- 15: rank 2
- 8: rank 3
- 7: rank 4

Forecast-top3 vs actual-top3 overlap was 2/3 (15 and 8).
All actual podium horses were nevertheless contained in the forecast top4 (15, 8, 7).

However, frozen axis horse 10 タガノデュード finished 11th.


## 4. Scenario interpretation

The observed race pace was reported as MEDIUM.
The authored SLOW scenario happened to move horse 15 above horse 10, but this must not be treated as a correct causal explanation because the actual race was not SLOW.

Therefore:
- do not credit the SLOW scenario as a winner-prediction success
- do not tune SLOW logic toward this result
- record the stronger finding instead: the candidate cluster was useful while the single-axis choice was weak

## 5. Evidence condition before Freeze

The important property of this race was already visible before result opening:

- all 16 runners: Data Trend = INSUFFICIENT
- all 16 runners: RaceReview = INSUFFICIENT
- all 16 runners: Ability Anchor available

Synthesis intentionally used `UNCERTAINTY` for every runner and did not invent top-lane direction.
Pairwise retained Data Trend and RaceReview as UNKNOWN and used Ability Anchor only as the fallback comparison lane.

This produced a useful top cluster, but the contract still required a complete order and allowed a hard axis mark even though the field had no directional evidence in the two preferred lanes.

## 6. New field-level evidence coverage

General Evidence now exposes `field_evidence_summary`.

Fields:
- `status`
- `runner_count`
- `data_trend_directional_runner_count`
- `racereview_directional_runner_count`
- `top_lane_directional_runner_count`
- `ability_available_runner_count`
- `ability_only_runner_count`

Statuses:
- `FULL_TOP_LANE_EVIDENCE`
- `PARTIAL_TOP_LANE_EVIDENCE`
- `ABILITY_FALLBACK_ONLY`
- `INSUFFICIENT`

Policy:
- descriptive only
- may_auto_rank = false
- may_auto_change_marks = false
- mixed-context-only is not directional
- Ability fallback is not top-lane evidence

Challenge Cup production-like smoke result:

```text
status = ABILITY_FALLBACK_ONLY
runner_count = 16
data_trend_directional_runner_count = 0
racereview_directional_runner_count = 0
top_lane_directional_runner_count = 0
ability_available_runner_count = 16
ability_only_runner_count = 16
```

Prepare smoke:
- Issue #1402
- run `36117553062`
- status PASS

## 7. Position representation across three races

Three races now support the same conservative statement:

`historical position tendency != exact tactical commitment today`

Hatsukaze exposed horse-level position variability.
All Comers exposed the ambiguity of merging FRONT and FORWARD into one aggregate count.
Challenge Cup again had a highly variable field: 15/16 runners were MULTI_BAND, while Race Structure contained FRONT=6 and FORWARD=4.

The richer representation is useful, but no new numeric pace-pressure formula is justified yet.

## 8. Current design decision

Adopt now:
- horse-level position variability metadata
- field-level position composition metadata
- explicit front/forward-count-is-not-lead-contest policy
- field-level evidence coverage summary
- explicit `ABILITY_FALLBACK_ONLY` status

Do not adopt yet:
- winner-specific rules
- new FRONT/FORWARD weights
- automatic rank changes from field information status
- automatic removal of the axis mark
- calibrated probability transformation based on three races

## 9. Next research question

The next blind cohort should test whether `ABILITY_FALLBACK_ONLY` repeatedly shows:
- useful broad/top-cluster identification
- weak axis certainty
- excessive confidence from forced complete ordering

If reproduced, the next contract change should target forecast confidence / mark semantics rather than horse ranking itself.
