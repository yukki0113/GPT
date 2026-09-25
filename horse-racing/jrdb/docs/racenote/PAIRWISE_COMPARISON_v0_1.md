# RaceNote Pairwise Comparison v0.1

Status: IMPLEMENTED RESEARCH CONTRACT / NOT YET FORECAST-ACTIVE  
Date: 2026-09-25

## 1. Purpose

RaceNoteの全馬評価を「各馬を独立採点して最後に並べる」方式から、
相対比較を明示的に残す方式へ移す。

上流のreading policyは固定する。

    DATA_TREND
      -> RACEREVIEW
      -> ABILITY_ANCHOR
      -> PAIRWISE COMPARISON

Pairwise Comparisonは勝者を機械生成しない。
GPTがGeneral Evidenceを読んで作った比較判断を、deterministic validatorが
監査する。

## 2. Why pairwise

単純能力だけを並べると、次のようなRaceNoteの価値が消えやすい。

- 条件傾向に合う / 合わない
- RaceReviewで着順以上 / 着順ほどではない
- Evidenceの小母数
- positiveとconcernの同居
- 近い2頭のどちらを上にするかという理由
- 条件が変わった場合の逆転可能性

Pairwiseでは最終順位の境界ごとに理由を残す。

## 3. Two-stage ordering

GPTはまずGeneral Evidenceを全馬分読んでdraft orderを作る。

draft orderは最終予想ではない。

次にrequired pairを直接比較し、必要なら順序を入れ替える。

    all-runner read
      -> draft order
      -> required pairwise checks
      -> final order
      -> Scenario Robustness

validatorはdraftからfinalへの移動も記録する。

## 4. Required comparisons

全組み合わせは要求しない。

18頭なら全組み合わせは153 pairになり、Evidenceの読みが冗長になるため。

v0.1 required pairs:

1. final orderの全adjacent pair
2. rank 1 vs rank 3
3. rank 1 vs rank 4

したがって最終順位の各境界は必ず直接比較され、◎候補は主要対抗とも
直接比較される。

final orderがdraftから変わった場合、final orderに対してrequired pairを
満たす必要がある。

## 5. One comparison

1 pairについて、3つのEvidence laneを順番に読む。

### DATA_TREND

記録:

- relation: A / B / EVEN / UNKNOWN
- concise summary
- evidence codes
- source refs

候補材料:

- same distance / surface / venue
- distance-range history
- frame
- running-style race trend
- sire
- jockey
- future pace/course/track-condition trends

### RACEREVIEW

記録:

- relation
- hidden strength
- fragile form
- repeatability
- contradiction
- primary/support/concern
- source refs

### ABILITY_ANCHOR

記録:

- relation
- latest / peak / typical prior IDM
- consistency / MAD
- source-run refs where useful

Ability is an anchor, not an automatic winner.

## 6. Preference and decisive lane

Each required pair records:

- preference: A or B
- confidence: LOW / MEDIUM / HIGH
- decisive_lane:
  - DATA_TREND
  - RACEREVIEW
  - ABILITY_ANCHOR
  - MIXED
  - UNCERTAINTY
- comparison_summary
- reversal_conditions

The summary is an auditable reason summary, not private chain-of-thought.

## 7. Lower-priority override

The user preference is ordinal:

    DATA_TREND > RACEREVIEW >= ABILITY_ANCHOR

Therefore a lower lane may override a higher lane only with an explicit reason.

Examples:

DATA_TREND favors B, RACEREVIEW favors A, choose A:

    lower_priority_override = true
    override_reason =
      "同距離傾向はB優位だが2戦のみ。AはRRで3走連続して着順以上。"

DATA_TREND and RACEREVIEW favor B, ABILITY favors A, choose A:

    lower_priority_override = true
    override_reason required

MIXED / UNCERTAINTY cannot be used as a loophole.
If DATA_TREND or RACEREVIEW explicitly favors the losing horse, choosing the
other horse still requires an override reason.

This preserves the desired reading priority without introducing fixed weights.

## 8. Reversal condition

Every comparison must state at least one reversal condition.

Examples:

- pace becomes much faster than expected
- track bias moves strongly to the inside/front
- the trend sample is judged too small to trust
- RaceReview concern is considered non-repeatable
- the ability gap is larger than condition evidence can reasonably offset

This becomes direct input to Scenario Robustness.

## 9. Final-order consistency

For every required pair, the preferred horse must be the horse ranked higher
in final_order.

If pair judgment and final rank disagree, validation fails closed.

This prevents the final marks from silently contradicting the comparison work.

## 10. No score

v0.1 does not authorize:

- pair score
- evidence point totals
- weighted sums
- Elo-like rating
- automatic rank from prior IDM
- automatic rank from number of positive tags

Evidence duplication remains handled semantically, including RaceReview
redundancy groups.

## 11. Firewall

Pairwise is pre-Freeze.

Forbidden:

- current JRDB consensus
- current market / odds / popularity
- Training Edge
- result information

Historical popularity trends are also kept out of the Independent Pairwise
stage when they would act as a proxy for current market judgment.

Current popularity/value belongs after Freeze.

## 12. Output and next stage

Implementation:

- src/racenote_pairwise_comparison.py

Schema:

- schema/racenote_pairwise_comparison_schema_v0_1.json

The validator emits RaceNote-Pairwise-Audit-0.1.

A successful audit sets:

    next_stage = SCENARIO_ROBUSTNESS / READY

Scenario Robustness v0.1 is now implemented:

- `src/racenote_scenario_robustness.py`
- `schema/racenote_scenario_robustness_schema_v0_1.json`
- `docs/racenote/SCENARIO_ROBUSTNESS_v0_1.md`

It tests whether the Pairwise axis survives SLOW / MEDIUM / FAST pace
scenarios rather than accepting one expected scenario.

## 13. Short-comment relationship

Pairwise comparison adds the piece needed for comments such as:

    同距離傾向と近走内容ではAを上位。
    Bは能力値で上だが、今回は条件面でAを取る。

or:

    データ面は互角だが、Aは近2走が着順以上。
    Bの地力は警戒も、今回はAを一枚上に評価。

The future short-comment renderer should reuse comparison_summary,
reversal_conditions, Horse Evidence Card comment_evidence, and final forecast
reason. It must not create unrelated post-hoc reasons.
