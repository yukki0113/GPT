# RaceNote v0.2 Tested Implementation Spec — Prospective 144R

## Status

**AUDIT SPECIFICATION OF THE IMPLEMENTATION ALREADY TESTED — NOT A NEW MODEL CHANGE**

This document records the concrete scoring scaffold used for the preregistered 2025-03-01/02 and 2025-06-28/29 prospective comparisons.

The June freeze committed the implementation SHA-256 before HJC:

`31a0000a88de3f8288f5c01535133dbe9104f274da8109815c22652e8d78bbd7`

The purpose of this file is disclosure/reproducibility. It does not retroactively alter the predictions.

## 1. Normalized ordinal ranks

Most numeric horse features are converted to a normalized ordinal rank where lower is better:

`normalized_rank = (ordinal_rank - 1) / (field_size - 1)`

Ties receive an average rank. Missing observations are assigned the median rank of the available observations rather than an assumed average performance value.

## 2. v0.1 control reproduced in the prospective harness

The control score is the equal average of eight normalized ranks:

1. IDM
2. total_index
3. recent IDM average of up to the latest 3 observed runs
4. shrunk same-distance top3 quality
5. shrunk same-venue top3 quality
6. condition_index rank
7. forecast finish-order rank
8. base market rank

`v0.1_score = mean(eight ranks)`

Lower is better.

This preserves the consensus/ability-heavy character diagnosed in the 219R development sample.

## 3. v0.2 ability component

`ability_rank = mean(IDM rank, total_index rank, recent-IDM rank)`

`ability_good = 1 - ability_rank`

The tested implementation therefore still gives ability a substantial role; suitability re-ranks viable ability candidates rather than ignoring ability.

## 4. Suitability component

The tested composite is:

`SuitabilityGood = 0.18*FrameFit + 0.25*PaceStyleFit + 0.30*DistanceFit + 0.12*SurfaceFit + 0.15*TimeFit`

### 4.1 FrameFit

- use target race `race_trends.frame` for the horse's frame;
- shrink top3 rate for sample size;
- 45% shrunk top3 quality is treated as the strong reference level;
- missing frame evidence -> 0.5.

**Limitation:** the tested score evaluates frame trend and running style separately. It does not yet estimate a true frame × running-style interaction table.

### 4.2 PaceStyleFit

Start at 0.5 and apply heuristic adjustments from forecast pace × running style:

High pace:
- 逃げ -0.18
- 先行 -0.05
- 差し +0.15
- 追込 +0.10

Slow pace:
- 逃げ +0.22
- 先行 +0.14
- 差し -0.08
- 追込 -0.18

Average/other:
- 逃げ +0.08
- 先行 +0.08
- 差し +0.02
- 追込 -0.05

Additional position adjustments:

- 差し/追込 with forecast mid-position deeper than 70% of field: -0.10
- JRDB position rank <=3: +0.08
- position rank near the tail (`>= max(8, field_size-2)`): -0.08

Clamp to [0,1].

### 4.3 DistanceFit

Direct/nearby history quality uses top3 rate shrunk toward 33% with:

`weight = starts / (starts + 5)`

Distance-fit category mapping relative to target bucket:

- exact bucket: 1.00
- one bucket away: 0.55
- two buckets away: 0.20
- three buckets away: 0.05
- 万能: 0.90
- unknown: 0.50

Target buckets:

- <=1400: 短距離
- <=1800: マイル
- <=2200: 中距離
- >2200: 長距離

Evidence priority:

1. same-distance history if present;
2. target-containing distance range;
3. closest distance range within 400m, discounted by 0.85;
4. categorical distance_fit only;
5. insufficient.

If categorical compatibility <=0.20 and same-distance starts=0, mark `contradictory` and apply an additional final penalty.

### 4.4 SurfaceFit

RaceNote surface-fit mark:

- ◎ = 1.00
- ○ = 0.75
- △ = 0.35
- missing = 0.50

### 4.5 TimeFit

The tested clock feature is deliberately narrow:

- search recent runs for exact same **venue + surface + distance**;
- take the fastest observed raw `time_sec` for each horse;
- use the cross-horse time rank only when at least 3 horses in the target race have comparable observations;
- otherwise use neutral 0.5.

**Important limitation:** the tested implementation does not yet normalize that raw time for track condition, class, carried weight, pace, or date-specific track speed. Although those fields are available for interpretation, they are not part of this numerical TimeFit. This is substantially simpler than the user's intended 'comparable clock' handicapping method and should be treated as a future model-development target rather than silently claimed as complete clock analysis.

## 5. Condition component

Use available training/condition indices scaled to [0,1], then adjust training arrow:

- デキ抜群 +0.12
- 上昇 +0.07
- 平行線 0
- やや下降気味 -0.08

Missing numeric state evidence starts from neutral 0.5.

## 6. Forecast component

`forecast_good = 1 - normalized forecast finish-order rank`

Target-race base market rank is **excluded from the v0.2 core score**. Market evidence is used only in the separate ☆ diagnostic.

## 7. Final v0.2 score

`Good = 0.42*AbilityGood + 0.38*SuitabilityGood + 0.10*Condition + 0.10*ForecastGood`

Then:

- distance contradiction: `Good -= 0.08`
- ability rank outside upper 60% of the field: `Good -= 0.05`

`v0.2_score = 1 - Good`

Lower is better. Top five become ◎ / ○ / ▲ / △1 / △2.

## 8. ☆ value/disagreement diagnostic

After the top five are fixed, a ☆ candidate may be selected from those five only.

For each selected horse:

- compare base market rank against the better of prediction rank / ability rank;
- require market disagreement gap >=3;
- require `PaceStyleFit + DistanceFit + FrameFit >= 1.45`;
- choose the candidate with largest disagreement, then support score.

This does not alter prediction marks.

## 9. User-facing comment implementation gap

The v0.2 design contract requires concrete, human-auditable reasons. The tested automatic comment renderer currently exposes:

- IDM / total_index;
- pace/style-fit phrase where triggered;
- frame-trend phrase where triggered;
- same/nearby-distance history and sample size;
- state/risk phrases.

However, in the 2025-06-28/29 72R block:

- 68/72 ◎ comments mentioned direct/nearby distance evidence;
- 24/72 explicitly mentioned pace/style fit;
- 14/72 mentioned frame trend;
- **0/72 displayed an actual clock/time value**.

Therefore prediction ranking and user-facing explanation must be evaluated separately. A future comment-only revision should expose the comparable run/time evidence or explicitly say it is not comparable, without changing the already-tested ranking score.

## 10. Frozen boundary

Any change to the numerical definitions above is a new prediction-model version and requires a new untouched blind comparison.

Presentation-only improvements that expose already-consumed evidence without changing ranking may be versioned separately as an output/comment contract.