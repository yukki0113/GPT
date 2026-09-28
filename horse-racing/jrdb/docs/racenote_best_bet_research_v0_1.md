# RaceNote ◎-only Contextual Best Bet Research v0.1

## Purpose

Before redesigning ○/▲/△, isolate ◎ and test whether RaceNote can reproduce the user's human forecasting principle:

> ◎ = 「このレースで、自分が一番買いたい馬」

This is not necessarily:
- the market favorite,
- the horse with the highest Ability number,
- the horse most aligned with Trend,
- or the horse with the fewest concerns.

It is the final contextual judgment after reading the race and every runner.

## Why a separate research layer

The current Semantic Pairwise v0.3 takes only the baseline top 6 into its candidate cluster and the current General Evidence contract states:

`DATA_TREND > RACEREVIEW >= ABILITY_ANCHOR`

Those constraints can prevent two human-style decisions that must both remain possible:

1. **Trend-aligned ◎**
   - Ability is close among leading horses.
   - The local/race-specific tendency points clearly toward one horse.
   - "It is short-priced, but this is still the horse to buy."

2. **Ability-override ◎**
   - Trend is somewhat adverse.
   - The horse's class/ability evidence is materially stronger than the field.
   - "The trend is not ideal, but the ability gap is too large to put another horse above it."

Therefore v0.1 does not replace Semantic v0.3 or Mark Policy. It creates a separate blind research path for ◎ only.

## Contract

### Selection
- Read every runner.
- No top-N candidate cutoff.
- Select exactly one ◎.
- No numeric additive score.
- No universal evidence priority.

### Race Thesis
Before selecting ◎, write a short Race Thesis:
- What kind of race is this?
- Which supplied evidence is most discriminating here?
- Is the field ability-separated or ability-compressed?
- Is supplied Trend strong enough to decide close horses?
- What important evidence is unavailable?

The Race Thesis is constrained explanation, not free-form storytelling.

### Evidence integration

#### Ability / class
Ability must not be reduced only to typical/latest/peak/MAD.

Where supplied evidence permits, recent form should be read in context:
- race class/grade,
- quality of opponents,
- relevance to today's course/distance,
- whether a poor finish is representative,
- whether repeated graded-class performance establishes a meaningful floor/ceiling.

#### Trend
Trend is evidence, not a permanent first-priority rule.

Use:
- to separate horses whose ability cases are close;
- to strengthen a favorite when both ability and race context point the same way;
- to identify a local contrarian pattern when the input supports it.

Do not:
- automatically demote a clearly superior horse because one trend is adverse;
- invent a named-race/local trend that is not supplied.

#### Concerns
A concern is not an automatic veto.
The author must explicitly answer:

> Is this concern strong enough to make another horse more buyable today?

### Decision types
- `TREND_ALIGNED`
- `ABILITY_OVERRIDE`
- `BALANCED_EVIDENCE`
- `CONTEXTUAL_EDGE`
- `MIXED_RACE_BEST_AVAILABLE`

These are explanatory categories, not scores.

## 12-race test format

For one venue / one day, freeze before results and output only:

```text
1R ◎ horse
comment...

2R ◎ horse
comment...
...
12R ◎ horse
comment...
```

Internally retain:
- Race Thesis
- decision type
- ability case
- Trend case
- recent-form case
- suitability/condition case
- concerns
- nearest alternatives

After all 12 selections are frozen, unlock results and evaluate:
- ◎ win / top2 / top3
- win ROI
- which decision type produced each ◎
- misses caused by candidate/evidence omission versus judgment
- whether comments reflect the intended human reasoning

## Local Trend data: current limitation

v0.1 changes the **decision logic**, not the underlying Trend dataset.

The desired future Trend source is hierarchical but does not discard narrow samples:

### Named races
Prefer the same named race under comparable conditions when available, even if only 7-10 editions exist.

Compare it with a broader base trend instead of replacing it.

This makes it possible to detect:
- broad disadvantage,
- but named-race/local historical value that runs against the broad belief,
- which may indicate a market-overreaction opportunity.

### Ordinary races
Use a local race context rather than a huge class-wide average.

Candidate context dimensions:
- venue,
- surface,
- distance,
- meeting/season,
- course rail setting (A/B/C etc.),
- meeting progression / week.

If the narrow sample is too thin, add nearby context as **support**, not as a replacement. For example:
- same meeting / same venue-distance / OP+ races;
- same seasonal meeting / venue-distance;
- broader venue-distance.

The important output is the relationship:
- Local and Base agree;
- Local is weak;
- Local contradicts Base;
- Local suggests a possible contrarian/value hypothesis.

## Safety / blind boundary

Before freeze, keep hidden:
- result,
- current odds / market,
- current JRDB consensus,
- Training Edge,
- EdgeDB match,
- RL index.

JRDB condition remains corroboration/contradiction only.

## Implementation

Research request/validator:
`horse-racing/jrdb/src/racenote_best_bet_research_v0_1.py`

This module is deliberately not wired into the existing Blind Marks workflow yet. The first goal is a controlled one-venue/12R ◎-only blind test.
