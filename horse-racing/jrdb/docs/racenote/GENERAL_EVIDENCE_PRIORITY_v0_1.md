# RaceNote General Evidence Priority v0.1

Status: IMPLEMENTED RESEARCH INPUT / NOT YET FORECAST-ACTIVE  
Date: 2026-09-25

## 1. Core preference

The current RaceNote prediction preference is:

    DATA / TRENDS > RACEREVIEW >= SIMPLE ABILITY

This is an ordinal reading order, not a numeric weighting formula.

The intended prediction style is data-first and historical-run-review-heavy:

1. read race / condition trends first;
2. compare each horse against those conditions;
3. use RaceReviewDB to reconstruct whether recent visible results overstate or
   understate the actual running content;
4. use simple historical ability only as an anchor;
5. compare horses relatively;
6. preserve positive evidence, concerns, contradiction, and uncertainty;
7. decide marks only after the all-runner comparison.

No single index is allowed to become the answer.

## 2. Why ability is an anchor

Past IDM and similar historical performance summaries remain useful.

However, they answer a narrower question:

    How much raw performance has this horse shown?

They do not directly answer:

    Is today's condition favorable?
    Is the historical result misleading?
    Is today's race shape likely to expose or help the horse?
    Is the apparent advantage repeatable here?

Therefore simple ability is retained as:

    ABILITY_ANCHOR

It provides floor / ceiling / normal-level context.

It does not auto-rank horses.

## 3. General evidence lanes

The v0.1 general evidence view has three ordered lanes.

### Priority 1: DATA_TREND

Current sources:

- horse same-surface historical record
- horse same-distance historical record
- horse target-relevant distance-range record
- horse same-venue historical record
- frame statistics
- sire statistics
- jockey statistics
- race-level running-style historical trend

Current trend observations expose:

- starts
- wins / top3
- win rate / top3 rate
- sample-size band
- condition-vs-career rate delta where applicable

A positive delta is an observed association, not proof of causality.

Small samples remain visible and are never silently upgraded to strong evidence.

### Priority 2: RACEREVIEW

RaceReviewDB supplies reconstructed historical running content.

Current Horse Evidence Card includes:

- result-underrates-time
- result-overrates-time
- pace-position against / aided
- fastest-last3F support
- move-then-fade mixed context
- repeatability
- hidden-strength candidate
- fragile-form candidate
- contradiction
- uncertainty

RaceReview is second only to data/trend context and may be effectively equal to
ability or stronger than it when the visible result and reconstructed content
disagree.

### Priority 3: ABILITY_ANCHOR

v0.1 ability anchor uses only historical prior-run IDM from the Independent
view.

It records:

- latest
- peak
- typical median
- minimum
- median absolute deviation
- source-run observations

It explicitly does not use:

- current-entry IDM
- current total/composite index
- current JRDB marks
- current JRDB pace prediction

## 4. Trend interpretation

The highest-priority lane is not a simple trend score.

For each trend, RaceNote keeps:

- condition summary
- career baseline where available
- observed rate delta
- sample-size band
- provenance

GPT later compares these across horses.

Example:

    Horse A
      same-distance top3: 75%
      career top3: 30%
      sample: small

    Horse B
      same-distance top3: 0%
      career top3: 62.5%
      sample: small

This is useful context, but it is not enough by itself to force A above B.

RaceReview and ability still matter, especially when the trend sample is weak.

## 5. Running-style trend

Running-style trend is historical race-level evidence built from Analysis
canonical with:

    race_date < target_date

The target horse's current JRDB running-style classification is not required
and is not opened.

Current style categories:

- 逃げ
- 先行
- 差し
- 追込
- 好位差し
- 自在

For each style, RaceNote stores as-of-safe exact-distance and target-relevant
distance-range performance.

The later Pairwise Comparison layer may combine this race-level trend with
observed historical positioning / RaceReview evidence.

## 6. Popularity boundary

The earlier human prediction style also used popularity trends.

That remains useful, but current popularity is market information.

Therefore:

    pre-Freeze:
      no current popularity / current market rank

    post-Freeze:
      historical popularity tendency
      + current market popularity / odds
      -> value / betting interpretation

Popularity trend must not mutate the Independent Forecast.

This preserves the distinction between:

    prediction strength
    and
    market value

## 7. Current and future trend sources

Current pre-Freeze trend sources:

- FRAME
- RUNNING_STYLE
- horse condition history
- SIRE
- JOCKEY

Planned pre-Freeze expansion:

- pace pattern
- track-condition pattern
- course-layout pattern

Post-Freeze only:

- popularity pattern joined to current popularity / odds

## 8. Comparison rules

The next Pairwise Comparison contract must read lanes in this order:

    DATA_TREND
    -> RACEREVIEW
    -> ABILITY_ANCHOR

Rules:

- a higher raw ability value cannot automatically override stronger trend/RR
  evidence;
- lower-priority override requires an explicit reason;
- missing high-priority evidence is UNKNOWN, not NEGATIVE;
- small-sample trend evidence remains lower-confidence but visible;
- contradiction must remain visible;
- same underlying fact must not vote multiple times;
- comparison must record why A is above B and what could reverse that relation.

No numeric weights are authorized by v0.1.

## 9. Short-comment relationship

Short comments should ultimately explain the same evidence used in prediction.

Target structure:

    condition/trend
    + RaceReview
    + ability/support where useful
    + concern

Example style:

    同距離実績と枠傾向は好材料。近2走も着順以上の内容で、
    現級水準の時計は確保。展開が極端に速くならなければ上位候補。

Or:

    能力値は上位だが、同距離実績は弱く、前走好走も展開利を含む。
    人気ほど盤石とは見ない。

The renderer is future work. v0.1 only preserves structured comment evidence.

## 10. Version boundary

Forecast Gen0.2 remains an implemented, non-activated historical contract.

The 2026-09-25 trend-first redesign is materially different and must not be
silently injected into Gen0.2.

Any future activation using this priority policy must use a new forecast
version / generation contract.

Current downstream sequence:

    General Evidence v0.1
      -> Pairwise Comparison v0.1 [IMPLEMENTED CONTRACT]
      -> Scenario Robustness v0.1 [NEXT]
      -> Forecast next-generation contract
      -> Independent Freeze
      -> post-Freeze consensus / market / value

Pairwise contract:

- `src/racenote_pairwise_comparison.py`
- `schema/racenote_pairwise_comparison_schema_v0_1.json`
- `docs/racenote/PAIRWISE_COMPARISON_v0_1.md`
