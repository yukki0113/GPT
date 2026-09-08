# RaceNote v0.6 Pair-Compatibility Mark Design Candidate

## Status

**CANDIDATE / PREREGISTRATION — NOT YET TESTED**

v0.6 keeps the validated v0.2 axis and changes only the opponent-role assignment below ○.

The previous v0.3 / v0.4a / v0.5 work tried to decide whether P4 should replace pure P3 by comparing the two horses mainly as individuals. Two untouched v0.5 blocks did not show incremental value. v0.6 therefore changes the information target itself:

> `Do not ask only whether P4 is better than P3 today. Ask whether ◎ + P4 is a better quinella pair than ◎ + P3.`

The production/default before this test remains pure v0.2 P3.

## 1. Fixed base ranking and candidate pool

Use the unchanged v0.2 core ranking:

- ◎ = P1
- ○ = P2
- provisional ▲ = P3
- challenger = P4
- △2-side horse = P5

Only P4 may challenge P3 in v0.6. P5 cannot take ▲.

If P4 does not clear every v0.6 gate:

`◎=P1 / ○=P2 / ▲=P3 / △1=P4 / △2=P5`

If P4 clears every gate:

`◎=P1 / ○=P2 / ▲=P4 / △1=P3 / △2=P5`

Top-five membership never changes.

## 2. New information layer A — Top2 Survival

v0.6 introduces an opponent-specific score aimed at survival into the first two places rather than pure win ranking.

For each horse define:

`Top2Survival = 0.30*AbilityGood + 0.20*ForecastGood + 0.15*PaceStyleFit + 0.10*DistanceFit + 0.10*Condition + 0.10*RecentTop2 + 0.05*JockeyTop2`

All components are pre-race only and scaled to [0,1].

### 2.1 RecentTop2

Use up to the available RaceNote detailed/compact history, maximum 8 starts:

- `recent_runs` first, in stored recency order;
- then `older_runs` only for races strictly older than the recent layer.

For valid completed starts:

- finish 1 or 2 = 1
- otherwise = 0
- abnormal/non-finish records are excluded from the denominator.

Shrink the observed top2 rate toward 0.25:

`RecentTop2 = w*observed_top2_rate + (1-w)*0.25`

where:

`w = starts / (starts + 4)`

If no valid history is available, use 0.25.

This is not a career-completeness claim; it is a bounded recent-history signal from the RaceNote coverage actually present.

### 2.2 JockeyTop2

Use `jrdb_ratings.jockey_expected_top2_rate / 100` when present, clamped to [0,1].

If missing, use 0.50.

This component is deliberately small (5%) so jockey expectation cannot dominate the horse-level evidence.

## 3. New information layer B — Pair Interaction with ◎

For candidate `x`, define an interaction score beginning at 0.50:

`PairInteraction(◎,x) = clamp(0.50 + bonuses - penalties)`

Only explicit pre-race pace/position structures are used.

Style groups:

- front = 逃げ / 先行
- closing = 差し / 追込

### 3.1 High-pace shared-front penalty

If race forecast pace is `ハイ` and both ◎ and x are front-group:

- if both PaceStyleFit < 0.55: `-0.20`
- otherwise: `-0.10`

### 3.2 Slow-pace shared-closing penalty

If race forecast pace is `スロー` and both ◎ and x are closing-group:

- if both PaceStyleFit < 0.55: `-0.20`
- otherwise: `-0.10`

### 3.3 Front-position contention penalty

If ◎ and x are both front-group and both forecast mid-race order <= 3:

- `-0.12`

This is applied in addition to a pace penalty when both conditions exist, because the pair is exposed both to the broad race shape and to direct early-position competition.

### 3.4 Rear-position congestion penalty under Slow

If forecast pace is `スロー`, ◎ and x are both closing-group, and both forecast mid-race order are in the rear 30% of the field:

- `-0.10`

### 3.5 Compatible-route bonus

If ◎ and x belong to different broad style groups, and both PaceStyleFit >= 0.55:

- `+0.08`

This is a small bonus only. Diversity by itself is not sufficient for promotion.

No bonus or penalty is created solely from market rank.

## 4. PairScore

For opponent candidate x:

`PairScore(◎,x) = 0.75*Top2Survival(x) + 0.25*PairInteraction(◎,x)`

The candidate horse's own top2 survival remains the main component. Pair interaction can change the decision but cannot rescue a weak horse by itself.

Calculate the score for P3 and P4.

## 5. Mandatory Gate A — strength guard

P4 must remain close enough to the orthodox P3 in the unchanged v0.2 core.

Require BOTH:

- `P3.Good - P4.Good <= 0.08`
- `P3.AbilityGood - P4.AbilityGood <= 0.12`

If either fails, keep P3 as ▲.

## 6. Mandatory Gate B — individual top2 survival floor

P4 may not obtain ▲ only through interaction structure while being materially weaker as a top2 horse.

Require:

`P4.Top2Survival >= P3.Top2Survival - 0.02`

Thus a small individual deficit is allowed, but a clearly weaker P4 cannot be promoted merely for stylistic diversity.

## 7. Mandatory Gate C — pair advantage

Require:

`P4.PairScore - P3.PairScore >= +0.05`

In addition require at least one of:

- `P4.PairInteraction - P3.PairInteraction >= +0.08`; or
- P3 has a severe shared-failure condition with ◎ while P4 does not.

A severe shared-failure condition means either:

- High pace + ◎/P3 both front + both PaceStyleFit < 0.55; or
- Slow pace + ◎/P3 both closing + both PaceStyleFit < 0.55; or
- ◎/P3 both front with forecast mid order <=3 for both.

This makes v0.6 genuinely pair-driven rather than another P3-vs-P4 suitability threshold model.

## 8. Mandatory Gate D — basic race-specific safety

P4 is rejected if any applies:

- existing v0.2 contradictory-distance flag is true;
- `P4.PaceStyleFit < 0.35`;
- `P4.SuitabilityGood < 0.45`;
- current training arrow is `やや下降気味` and Top2Survival does not exceed P3 by at least 0.04.

## 9. Mandatory Gate E — market/value confirmation comes last

▲ remains a value-oriented ticket role when it replaces P3.

After Gates A-D pass, require at least one pre-race market disagreement:

- P4 `base_win_rank` is at least 1 place worse than P3 `base_win_rank`; or
- P4 `base_place_rank` is at least 1 place worse than P3 `base_place_rank`; or
- P4 `base_win_rank >= 6` in fields of 10+ while P4 remains pure rank 4.

If both win/place market ranks needed for the comparison are missing, do not promote.

Market data never contributes numerically to Top2Survival or PairScore. It only confirms that a pair-compatibility upgrade also has a value rationale.

## 10. Resulting mark semantics

- ◎: today's best win candidate
- ○: strongest orthodox opponent
- ▲: P3 by default; P4 only when `◎+P4` is a materially better top2 pair and the market still leaves value
- △1: the remaining P3/P4 horse
- △2: P5

When P4 is promoted, the user-facing ▲ comment must explain:

1. P4 is still close enough to P3 in underlying strength;
2. why P4 has comparable or better top2 survival;
3. what specific shared-risk or pair interaction makes `◎+P4` preferable to `◎+P3`;
4. why the market evaluation leaves value.

Preferred form:

> 純粋評価では4番手だがP3との能力差は小さい。P3は◎と同じ前受け型でハイ想定の共倒れリスクがあり、こちらは差しで展開適性も保てる。連対残存性も大きく劣らず、市場評価まで考えて馬連2点目は▲をこちらへ。

If that explanation cannot be written honestly from frozen pre-race evidence, do not promote.

## 11. Confidence and betting policy

No change to the existing A/B/C confidence rule.

Blind betting comparison remains:

- control Q2: `◎-○ / ◎-pure P3`
- candidate Q2: `◎-○ / ◎-v0.6 ▲`
- wide diagnostic: `◎-▲`
- Q4 and Trio A6 remain membership-invariant
- Trio B5 is retained as a secondary diagnostic

## 12. No tuning on settled September results

The v0.6 formula and thresholds above are preregistered without fitting to the settled July/August/September payouts.

The already-settled v0.3/v0.4a/v0.5 races may be used for conceptual failure analysis only. Do not sweep these thresholds against their outcomes.

For the first untouched v0.6 block:

- activation rate is diagnostic only;
- if activation is <2% or >30% before HJC, stop and review engineering feasibility only;
- otherwise freeze exactly as-is and acquire HJC;
- do not alter v0.6 after any target result is opened.

## 13. Promotion standard

Do not promote v0.6 from one favorable block.

At minimum require:

- two untouched blocks pointing in the same direction; or
- a materially larger changed-role sample where gains exceed losses without one payout dominating the conclusion.

Primary judgment order:

1. changed-role gains vs losses;
2. changed-role hit count;
3. changed-role payout/ROI;
4. all-race Q2 effect;
5. wide effect;
6. whether promoted comments genuinely describe a pair-specific reason rather than generic suitability.

Until then, production/default remains pure v0.2 P3.
