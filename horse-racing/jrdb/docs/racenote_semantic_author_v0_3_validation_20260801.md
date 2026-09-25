# RaceNote Semantic Author v0.3 blind validation — 2026-08-01

Date reviewed: 2026-09-26
Target day: 2026-08-01
Races: 36
Venues: 中京 / 新潟 / 札幌

## 1. Research integrity

Semantic Author v0.3 was defined after analysis of the 2026-07-25 and
2026-07-26 72-race development sample.

Therefore those 72 races are development data, not validation data.

The first blind validation day for v0.3 was 2026-08-01.

The complete result-hidden flow was fixed before opening the 2026-08-01 result:

```text
RaceNote source
→ Gen0.3 Prepare 36/36
→ DayRehearsal-v0.1 control Freeze 36/36
→ Semantic Pairwise Packet v0.2 36/36
→ Semantic Author v0.3 36/36
──────── result firewall boundary ────────
→ 2026-08-01 result open
→ control vs v0.3 audit
```

Runs:
- source: 36198385140
- prepare: 36198436762
- control author/freeze: 36198549649
- semantic packet: 36198592288
- semantic author v0.3: 36198634088

v0.3 result visibility at author time: HIDDEN.

## 2. Why v0.3 exists

v0.2 changed the axis in 36 / 72 development races.

34 / 36 axis changes were caused by RACEREVIEW_CONTENT alone.

Across those 34 changes:
- old axis top3: 15
- new axis top3: 11

The issue was not that RaceReview was useless.
The issue was allowing transferability / fragility / contradiction structure
to act as a scalar horse rating and dethrone the axis by itself.

v0.3 therefore changed the semantic rule:

- content-level Data Trend may remain decisive;
- RaceReview may support an override;
- RaceReview alone may not automatically dethrone the baseline axis;
- a RaceReview-based reversal requires corroboration from Ability when Trend
  is unresolved;
- cross-lane conflict remains unresolved rather than being forced.

No additive score was introduced.

## 3. 2026-08-01 blind result

v0.3 changed the axis in only 1 / 36 races.

Control DayRehearsal-v0.1:
- axis wins: 4 / 36 = 11.1%
- axis top2: 9 / 36 = 25.0%
- axis top3: 11 / 36 = 30.6%
- winner mean forecast rank: 5.08
- winner median forecast rank: 5
- winner in top3: 14 / 36
- winner in top5: 19 / 36
- mean top3 overlap: 1.056
- mean Spearman: +0.196
- mean absolute rank error: 3.650

Semantic Author v0.3:
- axis wins: 4 / 36 = 11.1%
- axis top2: 9 / 36 = 25.0%
- axis top3: 12 / 36 = 33.3%
- winner mean forecast rank: 5.08
- winner median forecast rank: 5
- winner in top3: 15 / 36
- winner in top5: 19 / 36
- mean top3 overlap: 1.139
- mean Spearman: +0.205
- mean absolute rank error: 3.642

## 4. The single axis change

2026-08-01 中京9R:

- control axis: horse 9 — actual 8th
- v0.3 axis: horse 2 — actual 3rd
- race winner: horse 7

The semantic reversal did not find the winner, but it improved axis
survivability from outside the ticket area to the top three.

This is consistent with the intended v0.3 behavior:
make fewer reversals, and require stronger cross-lane support before moving
the axis.

## 5. Interpretation

One 36-race validation day is not enough to claim v0.3 superiority.

However, the first out-of-development test supports three narrower statements:

1. The v0.2 over-reversal problem was materially reduced.
2. Conservative content-aware semantic reading did not degrade aggregate order.
3. The one axis reversal improved actual axis placement.

The effect size is small, which is expected from a conservative rule.

The goal remains:
`read evidence meaningfully, not maximize retrospective swaps`.

## 6. Current decision

Keep:
- DayRehearsal-v0.1 as control
- Semantic Pairwise Packet v0.2
- Semantic Author v0.3 as research candidate

Do not yet replace production Gen0.3 with v0.3.

The next independent layer is Mark Policy research:

```text
◎ = Forecast Best
○ = Stability Partner
▲ = Upside Partner
```

The mark layer must be evaluated separately from full-order accuracy.

Primary betting diagnostics:
- ◎ win
- ◎ top3
- ◎ single win bet
- Quinella ◎-○
- Quinella ◎-▲
- Quinella ◎-○▲ 2 points
- Quinella box ◎○▲ 3 points

The next blind validation day should be used to test the mark policy without
changing its rules after results are opened.
