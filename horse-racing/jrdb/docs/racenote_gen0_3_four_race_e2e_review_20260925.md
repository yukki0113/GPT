# RaceNote Gen0.3 four-race blind E2E review

Date: 2026-09-25
Scope: post-freeze engineering review

## 1. Cohort

- Gen0-G001: 2026-09-13 中山10R 初風ステークス
- Gen0-G002: 2026-09-20 中山11R オールカマー
- Gen0-G003: 2026-09-12 阪神11R チャレンジカップ
- Gen0-G004: 2026-09-12 阪神10R 竹田城ステークス

All target results were opened only after Forecast Freeze PASS.

## 2. Gen0-G004 frozen forecast

Final order:
`5,2,10,15,13,12,9,7,3,4,6,14,8,11,1`

Marks:
- ◎ 5 パシアンジャン
- ○ 2 ペンナヴェローチェ
- ▲ 10 レヴァンテシチー
- △ 15 ルクスフレンジー
- △ 13 タガノマカシヤ
- △ 12 ポルポラジール

Forecast ID: `20260912_阪神_10_Gen0-G004`
Prediction hash: `9d2c2a2cc893c9a176c2858b1af9185ded4728853fa88c5f1a8b3ad0256d471d`
Freeze audit: PASS

Pre-freeze evidence mode:
- field_evidence_summary = ABILITY_FALLBACK_ONLY
- Data Trend directional runners = 0
- RaceReview directional runners = 0
- Ability Anchor available for all runners

Scenario:
- axis horse 5
- axis_robustness = ROBUST
- SLOW/MEDIUM/FAST all retain horse 5 at rank 1
- ROBUST means scenario-order stability only; it does not upgrade fallback evidence quality

## 3. Post-freeze result

Actual podium:
1. 5 パシアンジャン
2. 2 ペンナヴェローチェ
3. 10 レヴァンテシチー

The frozen top3 exactly matched the actual top3 in exact order.
Axis horse 5 won.
Observed race pace was MEDIUM.

## 4. Two ABILITY_FALLBACK_ONLY races

Challenge Cup / Gen0-G003:
- evidence mode = ABILITY_FALLBACK_ONLY
- axis robustness = CONDITIONAL
- forecast top4 contained all actual podium horses
- forecast top3 vs actual top3 overlap = 2/3
- axis horse forecast rank 1 -> actual 11

Takeda Castle Stakes / Gen0-G004:
- evidence mode = ABILITY_FALLBACK_ONLY
- axis robustness = ROBUST
- forecast top3 = actual top3 exactly
- axis horse forecast rank 1 -> actual 1

Current hypothesis only:
`field evidence coverage` and `scenario axis robustness` may need to be read together when describing axis confidence.

This is not yet a ranking rule and not calibration evidence. Sample size is only two fallback races.

## 5. Four-race directional findings

Hatsukaze exposed horse-level historical-position variability.
All Comers exposed FRONT/FORWARD aggregate ambiguity.
Challenge Cup exposed candidate-set quality vs single-axis confidence under fallback evidence.
Takeda Castle Stakes shows that fallback evidence can also produce a fully correct top cluster and axis when scenario ordering is robust.

Therefore the current evidence does not support either of these simplistic conclusions:
- `ABILITY_FALLBACK_ONLY means weak forecast`
- `ABILITY_FALLBACK_ONLY means Ability ranking is sufficient`

Instead, fallback mode should remain an evidence-quality label, while Scenario robustness remains a separate order-stability label.

## 6. Current decision

Keep ranking logic unchanged.
Do not introduce Ability weights or mark suppression from these samples.

Continue tracking per race:
- field_evidence_summary.status
- scenario_axis_robustness
- winner forecast rank
- top3 overlap
- top4/top5 podium coverage
- axis actual rank
- actual pace when independently available

Research question for the next blind cohort:
Does `ABILITY_FALLBACK_ONLY + ROBUST` repeatedly yield stronger axis performance than `ABILITY_FALLBACK_ONLY + CONDITIONAL`, while candidate-set quality remains useful in both?
