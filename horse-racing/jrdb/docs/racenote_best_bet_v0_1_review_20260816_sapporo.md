# RaceNote Best Bet v0.1 Review — 2026-08-16 Sapporo

Frozen prediction commit:
- dca4973d080be55c02a5d694d434c60a88559ba2

Scope:
- Sapporo 1R-12R
- ◎ only
- predictions frozen before result lookup

## Result summary

New Contextual Best Bet v0.1:
- win: 2/12 = 16.7%
- top2: 5/12 = 41.7%
- top3: 7/12 = 58.3%
- 100 JPY win-bet stake: 1,200 JPY
- return: 390 JPY
- win ROI: 32.5%

Old Mark Policy v0.1 ◎ on same 12 races:
- win: 2/12 = 16.7%
- top2: 3/12 = 25.0%
- top3: 4/12 = 33.3%
- old wins were 4R #8 and 12R #2

Thus the first ◎-only research pass materially improved top2/top3 placement, while win count remained unchanged.

## Race-by-race

| R | New ◎ | Result | Finish | Old ◎ | New decision |
|---|---|---|---:|---|---|
| 1 | #5 ルージュリヴィエラ | 10-3-14 | out | #5 | BALANCED_EVIDENCE |
| 2 | #3 タイフーンナイン | 3-7-2 | 1 | #5 | ABILITY_OVERRIDE |
| 3 | #10 クリスレジーナ | 5-11-10 | 3 | #14 | ABILITY_OVERRIDE |
| 4 | #8 アルジェンタム | 8-13-12 | 1 | #8 | CONTEXTUAL_EDGE |
| 5 | #11 レジームチェンジ | 12-11-9 | 2 | #1 | MIXED_RACE_BEST_AVAILABLE |
| 6 | #10 ヨドノゴールド | 11-4-10 | 3 | #7 | BALANCED_EVIDENCE |
| 7 | #16 ミナヅキ | 14-5-9 | out | #7 | ABILITY_OVERRIDE |
| 8 | #4 グレイスフルマーチ | 7-4-5 | 2 | #5 | CONTEXTUAL_EDGE |
| 9 | #3 エコロハート | 16-13-12 | out | #8 | TREND_ALIGNED |
| 10 | #10 パールフロント | 12-10-2 | 2 | #10 | TREND_ALIGNED |
| 11 | #10 アドマイヤテラ | 15-8-14 | out | #6 | ABILITY_OVERRIDE |
| 12 | #6 アスクデッドヒート | 2-12-13 | out | #2 | BALANCED_EVIDENCE |

## Initial findings

### 1. The all-runner / contextual ◎ layer improved placement quality

Old top3:
- 4/12

New top3:
- 7/12

Old top2:
- 3/12

New top2:
- 5/12

This supports continuing the ◎-only research path before redesigning ○/▲/△.

### 2. Ability Override is necessary, but the override threshold is not yet well specified

Successful / useful examples:
- 2R #3 won.
- 3R #10 finished 3rd.

Misses:
- 7R #16 missed while #14 won.
- 11R #10 missed while #15 won.

The concept itself should remain. The unresolved question is not "allow Ability Override or not", but:
- when is an Ability edge truly large enough,
- how much should current/recent class performance matter,
- when does positive Trend/condition on a slightly lower Ability horse deserve to overturn it.

### 3. Sapporo Kinen exposes the next major ability-context problem

New ◎:
- #10 アドマイヤテラ
- recent: G1 3rd -> G2 1st
- Ability: typical 71 / latest 74 / peak 75
- Trend: MIXED
- condition: SUPPORTIVE

Winner:
- #15 シェイクユアハート
- recent excluding G1 14th included repeated graded-level success:
  G2 1st, G2 4th, G3 1st
- Ability: typical 64 / latest 57 / peak 70
- condition: SUPPORTIVE

The new logic correctly stopped using TrendFirst and did not return to #6 ローシャムパーク. However it chose the strongest numeric/class Ability case (#10), while the winner was another proven graded performer (#15).

This suggests that "ability/class context" must not become a new fixed first-priority rule replacing TrendFirst.

### 4. 12R shows another side of the same issue

New ◎:
- #6 アスクデッドヒート
- proven 2-win-class record
- typical Ability 58

Winner:
- #2 ダノンヒストリー
- moving up from 1-win class
- latest/peak Ability 65
- SUPPORTIVE Trend
- HIDDEN_STRENGTH RaceReview
- no concern components

The research choice preferred proven class stability and discounted the emerging horse. The result suggests the Best Bet layer needs an explicit concept for:
- current ability breakthrough,
- class-rise but already class-competitive performance signal,
- hidden-strength / ceiling cases.

### 5. Newcomer race remains structurally unsupported

5R had no prior-run Ability for any runner.
The v0.1 choice #11 finished 2nd, but this does not validate the logic.

The selection relied mainly on:
- available population context,
- jockey context,
- JRDB condition/training arrow.

Newcomer races should later receive a separate evidence contract rather than being treated as ordinary Best Bet races.

### 6. Trend-aligned decisions were mixed

9R:
- #3 missed
- winner #16 had lower historical baseline but a recent maiden win, SUPPORTIVE Trend and SUPPORTIVE condition.

10R:
- #10 finished 2nd and the reasoning remained coherent.

This again suggests Trend should be contextual and comparative, but the system still needs better reading of "current trajectory" versus historical Ability baseline.

## Next research direction

Do not redesign ○/▲/△ yet.

For ◎ v0.2, focus on the following conceptual split:

1. **Established Ability**
   - repeated performance at today's class or above
   - class/grade context
   - opponent/race strength

2. **Current Expression / Trajectory**
   - latest performance
   - repeated recent improvement
   - class-rise signal
   - hidden-strength evidence

3. **Local / Race Trend**
   - local context
   - named-race context when available
   - broad-vs-local agreement or contradiction

4. **Suitability / Condition**
   - course/distance
   - race structure
   - JRDB condition as corroboration

5. **Concern severity**
   - whether the concern is actually strong enough to choose another horse

The final question remains:
> Which horse has the strongest combined reason to buy *in this race*, and is any negative evidence strong enough to overturn that case?

No fixed hierarchy should be introduced between Established Ability, Trajectory and Trend.
