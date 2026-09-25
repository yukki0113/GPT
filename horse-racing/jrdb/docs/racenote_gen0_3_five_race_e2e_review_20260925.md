# RaceNote Gen0.3 five-race blind E2E review

Date: 2026-09-25
Scope: post-freeze engineering review

## 1. Cohort

- Gen0-G001: 2026-09-13 中山10R 初風ステークス
- Gen0-G002: 2026-09-20 中山11R オールカマー
- Gen0-G003: 2026-09-12 阪神11R チャレンジカップ
- Gen0-G004: 2026-09-12 阪神10R 竹田城ステークス
- Gen0-G005: 2026-09-12 中山10R レインボーステークス

All target results were opened only after Forecast Freeze PASS.

## 2. Gen0-G005 frozen forecast

Final order:
`1,10,8,2,6,7,3,5,11,9,4`

Forecast ID: `20260912_中山_10_Gen0-G005`
Prediction hash: `c7475d43a2a4c2c7eef2bdd5b1478fabaa17dd0f68cffa624a238b9d6650646a`
Freeze audit: PASS

Pre-freeze mode:
- field_evidence_summary = ABILITY_FALLBACK_ONLY
- all 11 runners Data Trend = INSUFFICIENT
- all 11 runners RaceReview = INSUFFICIENT
- Ability Anchor available for all 11 runners
- race_structure pace_pressure = HIGH
- FRONT=4 / FORWARD=4 / MID=1 / BACK=1 / UNKNOWN=1
- SINGLE_BAND=3 / MULTI_BAND=8

Scenario:
- axis horse 1 デルアヴァー
- axis_robustness = ROBUST
- horse 1 retained rank 1 under SLOW/MEDIUM/FAST
- FAST only reversed ranks 2 and 3 (8 over 10)

## 3. Post-freeze result

Actual order:
`5,2,4,7,6,8,1,3,9,11,10`

Key deltas:
- actual winner 5 アマイ: forecast rank 8
- actual 2nd 2 マイネルブリックス: forecast rank 4
- actual 3rd 4 マイネルフーガ: forecast rank 11
- axis 1 デルアヴァー: actual rank 7
- forecast rank 2 horse 10 ダンツファイター: actual rank 11

Metrics:
- top3 overlap = 0/3
- top5 overlap = 2/5
- winner forecast rank = 8
- axis actual rank = 7
- Spearman rank correlation ≈ -0.136
- mean absolute rank error ≈ 3.64

Observed netkeiba pace label: M.

## 4. Fallback + robustness hypothesis check

After Gen0-G004, a tentative hypothesis was recorded:
`ABILITY_FALLBACK_ONLY + ROBUST` might indicate stronger axis performance than fallback + CONDITIONAL.

Gen0-G005 is a direct counterexample:
- evidence mode = ABILITY_FALLBACK_ONLY
- axis robustness = ROBUST
- axis finished 7th
- winner was forecast 8th
- top3 overlap was 0/3

Therefore Scenario robustness must NOT be interpreted as forecast confidence or axis confidence.

Scenario robustness means only:
`the authored order is stable across the modeled SLOW/MEDIUM/FAST scenario set`

It does not measure:
- whether the input evidence is sufficient
- whether the scenario set captures the actual race
- whether Ability fallback is informative enough
- whether the axis is likely to finish near rank 1

## 5. Five-race design implication

Current labels must remain orthogonal:
- field_evidence_summary.status = evidence coverage/quality mode
- scenario_axis_robustness = order sensitivity inside the authored scenario family

Do not combine them into one implicit confidence label yet.

Gen0-G004 and Gen0-G005 show that the same pair of labels (`ABILITY_FALLBACK_ONLY + ROBUST`) can correspond to opposite outcomes.

## 6. Current decision

Keep horse ranking logic unchanged.
Do not add a rule that ROBUST upgrades an axis.
Do not add a rule that ABILITY_FALLBACK_ONLY suppresses or promotes marks.
Do not alter pace-pressure thresholds from this result.

Next research priority:
- collect more blind races with genuine Data Trend and/or RaceReview directional evidence
- compare those against ABILITY_FALLBACK_ONLY races
- evaluate whether evidence coverage itself, not robustness, explains candidate-set quality

Continue tracking:
- field_evidence_summary.status
- scenario_axis_robustness
- winner forecast rank
- top3 overlap
- top5 overlap
- axis actual rank
- Spearman
- actual pace label when independently available
