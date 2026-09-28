# RaceNote Reset — Phase 2 Status

Date: 2026-09-28
Status: COMPLETE (v0.1 evidence-note assembly)

## Objective

Implement the first real RaceNote-Evidence-1.0 builder and prove that one actual race can be rendered as a GPT-readable Note without running forecast logic.

## Implemented

### Builder

`horse-racing/jrdb/racenote/src/build_racenote_v1.py`

Inputs:
- Gen0.2 `INDEPENDENT` view as a temporary neutral source adapter
- optional raw stable RaceReview evidence

Explicitly not consumed:
- General Evidence / TrendFirst
- Horse Evidence Card ranking/profile semantics
- all-runner synthesis
- pairwise / semantic ordering
- Mark Policy
- Best Bet
- current market
- current JRDB consensus
- Training Edge
- RL
- EdgeDB

Output:
- `RaceNote-Evidence-1.0`

### Reader renderer

`horse-racing/jrdb/racenote/src/render_racenote_v1.py`

Renders one canonical RaceNote JSON into a Markdown note intended for GPT/human reading.

The renderer does not add forecast conclusions.

## Real-race smoke test

Target:
- 2026-08-16
- Sapporo 11R
- Sapporo Kinen G2
- Turf 2000m
- 16 runners

Source:
- historical RaceNote artifact
- Gen0.2 independent view
- raw RaceReview stable evidence

Boundary result:
- 16 / 16 runners retained
- target result hidden
- current market hidden
- current JRDB consensus hidden
- Training Edge hidden
- RL hidden
- EdgeDB hidden
- no marks/ranks/best-bet/forecast-score fields
- boundary validation PASS

Generated canonical note size in smoke test:
- approximately 453 KB JSON

Generated reader Markdown:
- approximately 18 KB

## Important contextual-read proof

The generated Note preserves run-level venue, distance, grade and IDM together.

### #10 Admire Terra

Recent context visible to the reader includes:
- 2026-05-03 Kyoto / Tenno Sho (Spring) / G1 / 3200m / 3rd / IDM 74
- 2026-03-22 Hanshin / Hanshin Daishoten / G2 / 3000m / 1st / IDM 75
- 2025-12-28 Nakayama / Arima Kinen / G1 / 2500m / 11th / IDM 68
- 2025-10-05 Kyoto / Kyoto Daishoten / G2 / 2400m / 4th / IDM 68

### #15 Shake Your Heart

Recent context visible to the reader includes:
- 2026-06-14 Hanshin / Takarazuka Kinen / G1 / 2200m / 14th / IDM 57
- 2026-03-15 Chukyo / Kinko Sho / G2 / 2000m / 1st / IDM 70
- 2026-02-15 Kyoto / Kyoto Kinen / G2 / 2200m / 4th / IDM 64
- 2025-12-13 Chukyo / Chunichi Shimbun Hai / G3 / 2000m / 1st / IDM 66
- 2025-11-15 Kyoto / Andromeda Stakes / L / 2000m / 2nd / IDM 63

This demonstrates the intended Phase-1 correction:
a high Ability or high-grade result is not detached from the venue/distance where it was earned.

RaceNote does not decide which set of performances is more relevant to Sapporo 2000m.
The Forecast layer will make that judgment.

## Trend status in Phase 2 v0.1

### Base Context
AVAILABLE

The old broad `race_trends` block is retained only as:
- `base_context`

It is explicitly labelled:
- `LEGACY_BROAD_ALL_CLASS_CONTEXT`

It is not treated as Local Trend.

### Named Race Trend
UNAVAILABLE

The Sapporo Kinen historical named-race extractor is not yet implemented.

### Local Context Trend
UNAVAILABLE

The class-preserving local-context extractor is not yet implemented.

This is intentional. Phase 2 v0.1 prefers an explicit missing block over pretending that the old broad aggregate satisfies the new Local/Named definition.

## RaceReview handling

The new builder carries forward:
- stable run-level RaceReview families
- review tags
- pattern counts
- repeated patterns
- source/coverage context

It does not carry forward:
- Horse Evidence Card priority
- strength labels
- hidden-strength candidate status
- fragile-form candidate status
- preferred/ranking semantics

## Current limitations

1. Named-race Trend generation is not yet implemented.
2. Class-preserving Local Trend generation is not yet implemented.
3. Historical smoke-test artifact does not include an independently attached same-day weather/track snapshot, so `race_day` is explicitly UNAVAILABLE.
4. Current-entry neutral running-style distribution is not yet available from the independent adapter, so Field Context is PARTIAL rather than inferred.
5. The builder currently uses the old independent view as a source adapter; a future cleanup may connect directly to the normalized JRDB/history sources.

## Phase 2 conclusion

The redesigned RaceNote is now executable as an evidence-only product.

The first implementation proves:
- real race data can be assembled,
- all runners remain visible,
- recent performance context survives,
- RaceReview can be reused without forecast semantics,
- forecast leakage can remain outside the Note,
- missing new Trend layers can be represented honestly.

The next work should be the missing evidence families, especially Named/Local Trend, before defining the Forecast layer.
