# RaceNote Forecast Gen0.3 Prediction Contract

Status: IMPLEMENTED / NOT YET ACTIVATED  
Date: 2026-09-25

## 1. Decision principle

Current RaceNote forecast preference:

    DATA / TRENDS > RACEREVIEW >= SIMPLE ABILITY

This is an ordinal reading policy, not a weighted score.

The complete pre-Freeze chain is:

    Independent RaceNote
      -> General Evidence
      -> Pairwise Comparison
      -> Scenario Robustness
      -> Base Forecast
      -> EdgeDB performance-only overlay
      -> Final Forecast
      -> Freeze

After Freeze:

    JRDB consensus
      -> Market
      -> EdgeDB Value
      -> RL / Value
      -> Bet Plan

## 2. Version boundary

Gen0.2 was implemented but never activated.

The 2026-09-25 redesign is materially different, so Gen0.2 remains a retained
reference and Gen0.3 becomes the planned first activation contract.

Planned generation:

    Gen0-G001

Current live/ledger generation remains Gen0-G000 until explicit activation.

## 3. RaceReviewDB operational input

Normal RaceReview evidence input resolves the accepted operational CURRENT:

```text
stable Drive RaceReviewDB_CURRENT.zip
  -> RaceReview CURRENT resolver
  -> RaceReviewReader
  -> RaceNote RaceReview adapter
  -> Horse Evidence Card
  -> General Evidence
```

Stable Drive file ID:

`1UwNfrupMTHRPhkzULPvClGre4MWz2TFg`

RaceNote records the consumed RaceReviewDB `generation_id` and resolver
provenance. It joins history by JRDB blood registration number and enforces
`race_date < target_date`. Name fallback and same-day Review are forbidden.

The resolver is an artifact-delivery boundary only; it does not change Review
semantics or Forecast priority.

See `docs/racenote/RACEREVIEW_CURRENT_CONSUMER_v0_1.md`.

## 4. General Evidence

General Evidence v0.1 supplies three ordered lanes:

1. DATA_TREND
2. RACEREVIEW
3. ABILITY_ANCHOR

DATA_TREND includes:

- same-surface history
- same-distance history
- relevant distance-range history
- same-venue history
- frame trend
- sire trend
- jockey trend
- historical running-style trend
- independent Race Structure

Simple ability is retained as an anchor only and cannot auto-rank horses.

## 5. Prediction Interpretation

Before Pairwise, each runner receives `PredictionInterpretation-v0.1`.

The profile organizes, without scoring:

- DATA_TREND direction and sample size;
- redundant trend families;
- Race Structure context;
- RaceReview hidden-strength / fragile-form / contradiction;
- RaceReview repeatability and exact target-condition overlap;
- Ability Anchor as floor / ceiling context;
- positive / concern case components.

Pairwise reads this profile first, then verifies raw Evidence lanes.
Interpretation itself cannot create final rank, mark or probability.

Canonical document:
`docs/racenote/PREDICTION_INTERPRETATION_v0_1.md`.

## 6. Independent Race Structure

Race Structure is reconstructed only from historical pre-race-visible evidence.

v0.1 uses prior corner-position history to produce broad tendencies:

- FRONT
- FORWARD
- MID
- BACK
- UNKNOWN

and race-level front/forward pressure:

- LOW
- MEDIUM
- HIGH
- UNKNOWN

The following are explicitly not consumed:

- current JRDB running-style classification
- current JRDB forecast pace
- current JRDB forecast finish position

Race Structure is context, not a deterministic pace prediction.

## 7. Pairwise Comparison

Pairwise Comparison v0.1 validates authored relative judgments.

Required direct comparisons include:

- every adjacent final-order pair
- rank 1 vs rank 3
- rank 1 vs rank 4 when present

Every pair records:

- DATA_TREND relation
- RACEREVIEW relation
- ABILITY_ANCHOR relation
- preferred horse
- decisive lane
- comparison summary
- reversal condition

If lower-priority evidence overrides protected higher-priority evidence, an
explicit override reason is required.

## 8. Scenario Robustness

Scenario Robustness v0.1 requires:

- SLOW
- MEDIUM
- FAST

Pairwise rank 1 is classified:

- ROBUST: rank 1 in 3/3
- CONDITIONAL: rank 1 in 2/3
- FRAGILE: rank 1 in 0-1/3

If Scenario audit says Pairwise recheck is required, Gen0.3 forecast validation
fails closed. Pairwise must be re-authored and Scenario rerun before forecast.

Scenario order does not mechanically replace Pairwise order.

Any base-rank change relative to Pairwise must have a scenario adjustment
reason.

## 9. Base Forecast

Base Forecast is the independent forecast before EdgeDB.

GPT authors for every runner:

- base rank
- p_win_base
- p_top2_base
- p_top3_base
- primary reason
- secondary support
- main concern
- why above next horse
- scenario adjustment reason when applicable

Probability estimates are model judgments, not a formula derived from rank.

Validation checks:

- complete runner coverage
- contiguous ranks
- probability nesting
- race-level probability totals
- source hashes
- firewall
- Pairwise / Scenario consistency

## 10. EdgeDB performance overlay

Only EdgeDB performance evidence may alter the Base Forecast.

Normal serving profile:

    STANDARD

Allowed evidence levels:

- CONFIRMED
- SUGGESTIVE

The Forecast layer consumes matcher output semantics rather than reimplementing
Edge conditions.

The normalized overlay preserves:

- edge_id
- family
- performance_evidence_level
- signal
- presentation role
- conflict
- redundancy_group_id

The following are forbidden before Freeze:

- value_evidence_level
- value_signal
- value_p_value
- value_q_value
- value_edge

If final rank differs from base rank, the affected runner must have USED
performance evidence and an explicit adjustment reason.

Edge count is not a score. Redundant Edge matches must not act as independent
votes.

## 11. Final Forecast

Every runner stores:

- base_rank
- final_rank
- mark
- base probabilities
- final probabilities
- structured reasons
- Edge performance overlay

Mark semantics:

- ◎: most likely winner in Final Forecast
- ○: main rival
- ▲: plausible reversal candidate
- △: other win candidate
- blank: no mark

Validation requires:

- exactly one ◎
- at most one ○
- at most one ▲
- final rank 1 = ◎
- ◎ has maximum p_win_final

Marks are not a betting rule.

## 12. Freeze

Forecast must freeze before current consensus/market/value is opened.

Freeze records:

- immutable prediction hash
- frozen_at
- source-chain hashes
- final probabilities/ranks/marks/reasons

A frozen forecast is re-hashable.

Post-Freeze layers may open only when freeze audit PASSes.

## 13. Firewall

Before Freeze, Gen0.3 forbids:

- current JRDB IDM / total index / marks as forecast evidence
- current JRDB pace prediction
- current market odds / popularity
- EdgeDB Value signal
- RL / Value signal
- Training Edge
- target result

Historical performance and historical race results are legitimate evidence when
strictly prior to target date.

## 14. Post-Freeze order

Open in this order:

1. JRDB_CONSENSUS
2. MARKET
3. EDGE_VALUE
4. RL_VALUE
5. BET_PLAN

These layers may evaluate or price the frozen prediction but may not mutate it.

## 15. Decision Trace

Every Forecast horse must include
`RaceNote-Decision-Trace-0.1`.

It binds the authored Forecast reasons to actual upstream evidence:

- primary evidence lane / codes
- secondary evidence lane / codes
- concern evidence lane / codes
- direct Pairwise support
- derived Scenario risk IDs
- used Edge IDs
- comment evidence codes

Forecast rejects unknown evidence codes, hidden Scenario risks, unsupported
Pairwise claims, and Edge use without an Edge ID trace.

If `secondary_support` prose is non-empty, secondary trace must exist.
If `why_above_next` prose is non-empty, direct Pairwise support against the
next horse or traced Edge evidence is required.

Decision Trace is part of the immutable Forecast hash.

Canonical document:
`docs/racenote/DECISION_TRACE_v0_1.md`.

## 16. Short comments

The future reader-facing comment should be derived from the same forecast
record:

    primary reason
    + secondary support
    + main concern
    + Pairwise comparison summary
    + Scenario sensitivity

Example:

    同距離傾向と近走内容を上位評価。地力も足りる。
    流れが速くなると○に逆転余地はあるが、通常想定なら中心。

No unrelated post-hoc reason should be generated after the result.

## 17. Activation gate

Implementation does not itself activate Gen0-G001.

Before activation:

1. fix sample manifest;
2. register Gen0-G001 in the forecast ledger;
3. set Gen0.3 as active forecast version;
4. confirm official TRUE_FORWARD input chain;
5. run formal pre-result Freeze;
6. keep Gen0-G000 immutable.

## 18. Canonical assets

- src/racenote_racereview_current.py
- src/racenote_racereview_adapter.py
- src/racenote_general_evidence.py
- src/racenote_pairwise_comparison.py
- src/racenote_scenario_robustness.py
- src/racenote_forecast_gen0_3.py\n- docs/racenote/DECISION_TRACE_v0_1.md
- schema/racenote_general_evidence_schema_v0_1.json
- schema/racenote_pairwise_comparison_schema_v0_1.json
- schema/racenote_scenario_robustness_schema_v0_1.json
- schema/racenote_forecast_gen0_schema_v0_3.json
- config/racenote_forecast_gen0_ledger_v0_3.json
