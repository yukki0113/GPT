# RaceNote Horse Evidence Card v0.1

Status: IMPLEMENTED RESEARCH LAYER / NOT YET FORECAST-ACTIVE  
Date: 2026-09-25

## 1. Purpose

RaceReviewDB sidecar を、そのまま GPT へ大量に渡すのではなく、
RaceNote が全馬比較しやすい Horse Evidence Card へ圧縮する。

v0.1 は general Horse Evidence Card のうち、RaceReviewDB historical review
evidence のみを対象とする最初の slice である。

    RaceReviewDB
      -> RaceReview Evidence Adapter
      -> Horse Evidence Card v0.1
      -> future Pairwise Comparison
      -> future Scenario Robustness
      -> future Independent Forecast

Card は予想スコアではない。

- evidence を加点しない
- 同じ事実を複数票として数えない
- positive / concern / mixed / uncertainty を同時に保持する
- current market / current JRDB consensus / Training Edge を読まない
- hidden strength は「市場から見て妙味がある」という意味ではない
- fragile form は「人気馬」という意味ではない

## 2. Inputs and outputs

Input:

- RaceReview-Evidence-0.1

Output:

- RaceNote-Horse-Evidence-Card-0.1

Implementation:

- src/racenote_horse_evidence_card.py

Schema:

- schema/racenote_horse_evidence_card_schema_v0_1.json

The source sidecar remains immutable. Card construction is a separate
deterministic transformation.

## 3. Evidence item contract

Each card-level item preserves:

- evidence_id
- code
- family
- direction
- priority
- strength
- evidence_quality
- redundancy_group_id
- source_run_refs
- facts

Families in v0.1:

- ABILITY
- FINISH
- POSITION
- PACE_POSITION

Priorities:

1. REPEATABILITY
2. DIRECT_PERFORMANCE
3. CONTEXTUAL

Priority is presentation/selection order only. It is not a numeric weight.

## 4. Initial direct evidence rules

v0.1 intentionally starts with narrow, explainable rules.

### 4.1 RESULT_UNDERRATES_TIME

Conditions:

- historical finish > 3
- RaceReview tag = TIME_ABOVE_DECLARED_CLASS

Interpretation:

The visible top-three result was absent, but reconstructed time-class
performance was above the declared class.

This is a hidden-strength candidate, not proof of future superiority.

### 4.2 RESULT_OVERRATES_TIME

Conditions:

- historical finish <= 3
- RaceReview tag = TIME_BELOW_DECLARED_CLASS

Interpretation:

The visible top-three result was good, but reconstructed time-class
performance was below the declared class.

This is a fragile-form candidate, not an instruction to oppose the horse.

### 4.3 LOSS_WITH_FASTEST_LAST3F

Conditions:

- historical finish > 3
- FASTEST_LAST3F

This remains supporting evidence because fastest closing split alone does not
prove a stronger total performance.

### 4.4 MOVE_THEN_FADE

RaceReview MOVE_THEN_FADE is retained as MIXED context.

It is not automatically positive because an in-race move can express ability,
inefficiency, pace exposure, stamina limitation, or multiple causes.

## 5. Pace-position research rule

v0.1 uses only observed pace shape and normalized fourth-corner position.

Position bands:

- front third: fourth-corner frontness >= 2/3
- rear third: fourth-corner frontness <= 1/3

A positive against-pace candidate additionally requires a top-half finish.

Examples:

- FRONT_LOADED + front third + top-half finish
  -> PACE_POSITION_AGAINST_GOOD_RUN
- BACK_LOADED + rear third + top-half finish
  -> PACE_POSITION_AGAINST_GOOD_RUN

An aided-result concern requires a top-three finish.

Examples:

- FRONT_LOADED + rear third + top-three finish
  -> PACE_POSITION_AIDED_RESULT
- BACK_LOADED + front third + top-three finish
  -> PACE_POSITION_AIDED_RESULT

These are coarse research interpretations. They are intentionally marked
evidence_quality=MIXED and do not create a score.

## 6. Repeatability

A repeated pattern is more useful than a one-off event, but still must not
become additive vote counting.

v0.1 promotes repeated evidence into dedicated REPEATABILITY items.

Examples:

- REPEATED_ABOVE_CLASS_PERFORMANCE
- REPEATED_BELOW_CLASS_PERFORMANCE
- REPEATED_FASTEST_LAST3F
- REPEATED_MOVE_THEN_FADE
- REPEATED_RESULT_UNDERRATES_TIME
- REPEATED_RESULT_OVERRATES_TIME
- REPEATED_PACE_POSITION_AGAINST
- REPEATED_PACE_POSITION_AIDED

The original per-run evidence remains traceable through source_run_refs.

## 7. Duplicate evidence

Card items preserve redundancy_group_id.

Examples:

- one run's time-class interpretation
  - TIME_CLASS:<run_ref>
- one run's pace-position interpretation
  - PACE_POSITION:<run_ref>
- one run's closing evidence
  - LAST3F:<run_ref>

This allows later GPT comparison to know that multiple labels may originate
from one underlying performance event.

There is no "three tags = three votes" rule.

## 8. Hidden strength

hidden_strength means:

Historical visible results may understate reconstructed running content.

It does NOT mean:

- the horse is unpopular
- current odds are attractive
- the horse should be bought
- the horse is stronger than every rival

Status:

- NONE
- CANDIDATE

Confidence:

- LOW: one supporting historical run
- MEDIUM: at least two source runs
- HIGH: repeated-pattern evidence exists

Representative reason codes:

- RESULT_UNDERRATES_TIME
- PACE_POSITION_AGAINST_GOOD_RUN
- LOSS_WITH_FASTEST_LAST3F
- REPEATED_ABOVE_CLASS_PERFORMANCE
- REPEATED_RESULT_UNDERRATES_TIME
- REPEATED_PACE_POSITION_AGAINST
- REPEATED_FASTEST_LAST3F

Only after Independent Forecast Freeze may market/value logic determine whether
a hidden-strength horse is actually a value horse.

## 9. Fragile form

fragile_form means:

Historical visible good results may overstate reconstructed running content or
contain a favorable pace-position context.

It does NOT mean:

- the horse is currently popular
- the horse should be downgraded automatically
- the horse cannot repeat the result

Representative reason codes:

- RESULT_OVERRATES_TIME
- PACE_POSITION_AIDED_RESULT
- REPEATED_BELOW_CLASS_PERFORMANCE
- REPEATED_RESULT_OVERRATES_TIME
- REPEATED_PACE_POSITION_AIDED

Popularity is checked only after Forecast Freeze.

## 10. Contradiction

A horse may contain both hidden-strength and fragile-form evidence.

The Card must preserve this.

Example:

    two races ago:
      RESULT_UNDERRATES_TIME

    last race:
      RESULT_OVERRATES_TIME

Output:

- hidden_strength = CANDIDATE
- fragile_form = CANDIDATE
- contradiction.status = MIXED

Do not force one side to disappear.

This mixed state is expected input for later GPT relative comparison.

## 11. Primary / supporting / concern selection

Positive evidence is sorted by:

1. priority class
2. strength class
3. deterministic code order

At most two primary_positive items are selected, with distinct evidence
families where possible.

Remaining positive items are supporting_positive.

Negative items remain under concerns.

Mixed items remain under mixed_context.

This is not a ranking score. It only keeps the Card readable.

## 12. Uncertainty

v0.1 records at least:

- NO_HORSE_ID
- NO_RACEREVIEW_HISTORY
- PARTIAL_RACEREVIEW_HISTORY
- NO_CARD_LEVEL_COMPOSITE_EVIDENCE

A missing history must never be silently converted to neutral evidence.

## 13. Short-comment bridge

The Card includes comment_evidence.

It contains only selected codes and source evidence IDs.

It does not generate prose.

    Horse Evidence Card
      -> comment_evidence
      -> future short-comment renderer

This preserves one important principle:

The short comment must explain evidence actually used by RaceNote rather than
create a separate post-hoc story.

Future examples may therefore become:

- 「近2走は着順以上。前走も前傾戦を前で運び、時計水準は現級上位。」
- 「前走2着は見栄えするが、時計水準は一枚下。展開利も含み評価は慎重。」

Those sentences are future renderer output, not hard-coded v0.1 decisions.

## 14. Current boundary and next step

v0.1 Card uses RaceReview historical evidence only.

Still not integrated:

- Base Ability Profile from all RaceNote history
- current Condition Fit
- independent Race Structure
- EdgeDB common evidence envelope
- Pairwise Comparison
- Scenario Robustness
- final Prediction Contract

The next structural step is to merge:

    RaceReview Card
    + Base Ability Profile
    + Condition Fit
    + Race Structure
    + EdgeDB performance evidence

into the general RaceNote Evidence Card, then implement pairwise comparison.

Forecast Gen0.2 activation remains unchanged until a separate generation
contract explicitly authorizes the new evidence pipeline.
