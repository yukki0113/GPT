# RaceNote Gen0.3 four-race blind E2E review

Date: 2026-09-25

## 1. Cohort

- Gen0-G001: 2026-09-13 中山10R 初風ステークス
- Gen0-G002: 2026-09-20 中山11R オールカマー
- Gen0-G003: 2026-09-12 阪神11R チャレンジカップ
- Gen0-G004: 2026-09-12 阪神10R 竹田城ステークス

Every result was opened only after Forecast Freeze passed.

## 2. New field evidence status

`field_evidence_summary` was added after Gen0-G003 exposed a field where all runners lacked directional Data Trend and RaceReview evidence.

Status values:
- FULL_TOP_LANE_EVIDENCE
- PARTIAL_TOP_LANE_EVIDENCE
- ABILITY_FALLBACK_ONLY
- INSUFFICIENT

The status is descriptive only:
- may_auto_rank = false
- may_auto_change_marks = false

## 3. Gen0-G003 Challenge Cup

Pre-Freeze field status:
`ABILITY_FALLBACK_ONLY`

Frozen order head:
`10,15,8,7,...`

Actual top three:
`15,8,7`

Observed:
- actual top-three set was forecast ranks 2/3/4
- top-three overlap = 3/3
- frozen axis 10 finished 11th

This showed that Ability fallback could identify a useful top cluster while a forced axis could still fail.

## 4. Gen0-G004 Takedajo Stakes

Pre-Freeze field status:
`ABILITY_FALLBACK_ONLY`

Frozen order head:
`5,2,10,15,...`

Actual top three:
`5,2,10`

Observed:
- exact top-three order = 3/3
- frozen axis 5 won
- rank 2 horse 2 finished second
- rank 3 horse 10 finished third

Therefore the Challenge Cup axis miss does not reproduce as a general Ability-fallback axis failure.

## 5. Consequence for mark/confidence design

Current evidence does NOT justify:
- banning ◎ in ABILITY_FALLBACK_ONLY races
- automatically flattening all marks
- automatically replacing the top horse
- changing Ability ranking weights from these two races

Current evidence DOES justify:
- exposing that the entire field is Ability fallback
- keeping this information visible to Forecast authoring and audit
- separating evidence-quality status from scenario robustness

In particular:

`scenario_axis_robustness = ROBUST`

means the axis is stable across SLOW/MEDIUM/FAST scenario ordering. It does not mean the preferred evidence lanes are rich.

`field_evidence_summary.status = ABILITY_FALLBACK_ONLY`

means the top two preferred evidence lanes provide no directional runner evidence. It does not mean the axis must fail.

Both dimensions are required.

## 6. Position representation continues to hold

Gen0-G004 pre-race Race Structure:
- FRONT = 4
- FORWARD = 6
- MID = 2
- BACK = 2
- UNKNOWN = 1
- MULTI_BAND = 12/15

Actual top-three positions again show why tendency is not exact tactical commitment:
- 5 had historical FORWARD/MULTI_BAND and raced 1-1-1-1
- 2 had historical FORWARD/SINGLE_BAND and raced 6-5-5-4
- 10 had historical UNKNOWN/MULTI_BAND and raced 8-7-8-7

The position-variability and composition extensions remain appropriate descriptive context.

## 7. Current decision

Keep:
- historical position variability fields
- race-level position composition
- front_or_forward_count_is_not_lead_contest_count
- field_evidence_summary
- ABILITY_FALLBACK_ONLY as descriptive evidence quality

Do not change yet:
- pace-pressure formula
- mark assignment contract
- rank generation contract
- probability calibration
- Ability weights

## 8. Next phase

Continue blind E2E across races with both:
- top-lane evidence available
- ABILITY_FALLBACK_ONLY

Collect enough cases to separate:
1. evidence coverage quality
2. scenario robustness
3. ranking accuracy
4. probability calibration
5. mark/axis reliability

Only then change Forecast confidence or mark semantics.
