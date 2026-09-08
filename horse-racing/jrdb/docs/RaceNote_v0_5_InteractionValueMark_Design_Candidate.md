# RaceNote v0.5 Interaction-Value Mark Design Candidate

## Status

**CANDIDATE / PREREGISTRATION — NOT YET TESTED**

This candidate keeps the validated v0.2 axis and changes only the opponent-role assignment below ○.

The goal is not to search for a longshot. The goal is to promote a value-oriented ▲ only when the ordinary pure P3 is vulnerable today and pure P4 has multiple independent reasons to be preferred, while still remaining close enough in underlying strength.

Core idea:

> `P3 remains ▲ by default. P4 may take ▲ only when P3 is vulnerable, P4 is close enough in strength, P4 has at least two independent race-specific advantages, P4 is not badly correlated with ◎'s failure mode, and market disagreement provides the final value confirmation.`

P5 cannot take ▲ in v0.5.

## 1. Fixed base ranking

Use the unchanged v0.2 core ranking:

- ◎ = P1
- ○ = P2
- provisional ▲ = P3
- challenger = P4
- △2-side horse = P5

If P4 does not clear every gate below:

`◎=P1 / ○=P2 / ▲=P3 / △1=P4 / △2=P5`

If P4 clears every gate:

`◎=P1 / ○=P2 / ▲=P4 / △1=P3 / △2=P5`

Top-five membership never changes.

## 2. Gate A — strength proximity

P4 must remain a genuine contender rather than a price-only horse.

Require BOTH:

- `P3.Good - P4.Good <= 0.06`
- `P3.AbilityGood - P4.AbilityGood <= 0.10`

If either fails, P3 keeps ▲.

## 3. Gate B — P3 vulnerability

P4 may challenge only when P3 has at least one concrete weakness under today's conditions.

Count one vulnerability for each condition below:

1. `PaceStyleFit <= 0.42`
2. `DistanceFit <= 0.40` OR existing v0.2 distance evidence is contradictory
3. `FrameFit <= 0.35`
4. `Condition <= 0.40`
5. `ForecastGood <= 0.35`
6. `SurfaceFit <= 0.35`

Require:

`P3_vulnerability_count >= 1`

This is the principal change from v0.4a: a good P4 alone is not enough. There must also be a reason not to trust the orthodox P3 as the quinella second ticket.

## 4. Gate C — two independent today-specific advantages

Compare P4 with P3 in six evidence groups. Each group can contribute at most one advantage flag.

### C1. Development / position

Flag if either:

- `P4.PaceStyleFit - P3.PaceStyleFit >= +0.10`, or
- `P4.ForecastGood - P3.ForecastGood >= +0.10`

### C2. Distance / clock

Flag if either:

- `P4.DistanceFit - P3.DistanceFit >= +0.10`, or
- `P4.TimeFit - P3.TimeFit >= +0.10`

TimeFit remains the narrow tested same-venue/surface/distance clock evidence and is not treated as a full adjusted speed figure.

### C3. Frame / course geometry

Flag if:

- `P4.FrameFit - P3.FrameFit >= +0.10`

### C4. Surface / going compatibility

Flag if:

- `P4.SurfaceFit - P3.SurfaceFit >= +0.20`

### C5. Current condition

Flag if:

- `P4.Condition - P3.Condition >= +0.10`

Require BOTH:

- at least **two** flags among C1..C5;
- at least one flag must be from C1, C2, or C3.

Thus condition/market alone can never create ▲.

## 5. Gate D — absolute minimum suitability

Even if P4 beats P3 relatively, reject a candidate that is still weak in absolute terms.

Require:

- `P4.SuitabilityGood >= 0.50`
- `P4.PaceStyleFit >= 0.40`
- no contradictory distance flag

## 6. Gate E — ◎ interaction / failure-mode diversification

▲ is intended as the second quinella ticket against ◎. Avoid selecting a horse that is exposed to the same obvious pace failure mode as ◎.

Define broad style groups:

- front = 逃げ / 先行
- closing = 差し / 追込

Reject P4 if either condition holds:

### High-pace shared front risk

- race forecast is High;
- ◎ and P4 are both in `front`;
- both `PaceStyleFit < 0.50`.

### Slow-pace shared closing risk

- race forecast is Slow;
- ◎ and P4 are both in `closing`;
- both `PaceStyleFit < 0.50`.

This does not reward diversity for its own sake. It only rejects a candidate when the same forecast explicitly threatens both horses.

## 7. Gate F — market/value confirmation comes last

Market disagreement is a confirmation layer, not the discovery engine.

After Gates A-E pass, require at least one:

- P4 base-market rank is at least **1 place worse** than P3 base-market rank; or
- P4 base-market rank is at least **2 places worse** than its pure prediction rank (=4).

For fields of 7 runners or fewer, require the stricter form:

- P4 base-market rank at least **2 places worse** than P3; or
- P4 base-market rank at least **3 places worse** than pure prediction rank.

If base-market rank is missing, do not promote.

## 8. No score optimization / no payout fitting

v0.5 uses hard gates rather than a fitted promotion score.

Reasons:

- previous v0.3/v0.4 work showed strong payout concentration;
- hard gates keep the explanation auditable;
- no settled July/August payout is used to optimize these thresholds.

Activation rate is diagnostic only. Do not tune v0.5 toward a target percentage after result acquisition.

If an untouched pre-result block produces a clearly pathological activation rate (<2% or >35%), stop before HJC and review only the engineering feasibility of the gates. Any such pre-result revision becomes v0.5a and must be frozen before outcomes are opened.

## 9. User-facing mark semantics

- ◎: today's best win candidate
- ○: strongest orthodox opponent
- ▲: P3 by default; P4 only when the full v0.5 interaction-value case is satisfied
- △1: the remaining P3/P4 horse
- △2: P5

When P4 is promoted, the ▲ comment must explain four things:

1. pure rank is only fourth but strength gap is small;
2. what makes P3 vulnerable today;
3. at least two independent reasons P4 is better suited today;
4. why the market price/evaluation leaves value.

Preferred structure:

> 純粋評価では4番手だがP3との能力差は小さい。P3は今回は展開面に不安があり、こちらは展開と距離適性の二方向で条件が良い。◎と同じ失敗パターンにも寄りにくく、市場評価まで考えて馬連2点目は▲を優先。

If those four layers cannot be stated honestly from pre-race evidence, do not promote.

## 10. Blind comparison

On the next untouched block freeze before HJC:

- v0.2 pure marks — control
- v0.4a — prior conservative candidate shadow
- v0.5 — new candidate
- confidence A/B/C unchanged
- standard user-facing comments

Primary betting checks:

- Q2: `◎-○ / ◎-▲`
- changed-role `◎-▲` head-to-head against pure P3
- `◎-▲` wide
- trio A6 and B5

Primary evaluation is not ROI alone:

1. changed-role gains vs losses;
2. hit-rate sacrifice versus payout gain;
3. whether P3 vulnerability was real often enough to justify replacement;
4. whether promoted ▲ comments are concretely explainable;
5. replication on a second untouched block before promotion.

## 11. Promotion standard

Do not promote v0.5 from one favorable three-day block.

At minimum require either:

- two untouched blocks pointing in the same direction; or
- a materially larger changed-role sample with no clear evidence of systematic P3 destruction.

Until then, production/default remains pure v0.2 P3 assignment.
