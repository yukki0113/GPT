# RaceNote v0.6a Pair-Compatibility Mark — Pre-Result Engineering Correction

## Status

**PRE-RESULT CORRECTION / PREREGISTRATION — HJC NOT YET ACQUIRED**

v0.6 design commit:

`c6c424f5c681222a797b01fd3ad49099d5901398`

The first untouched 72-race pre-result application (2025-09-15 / 09-21 / 09-27) produced **0/72 promotions**. No target HJC, result, final payout, final odds/popularity, or Web result had been opened.

The v0.6 design explicitly declared activation below 2% as an engineering-feasibility stop condition. Therefore v0.6 was not frozen for settlement. The formulas were reviewed using only pre-race RaceNote inputs and activation behavior.

## 1. Why v0.6 was mechanically too strict

Original:

`PairScore = 0.75*Top2Survival + 0.25*PairInteraction`

but Gate C required:

`P4.PairScore - P3.PairScore >= +0.05`

When P3 and P4 have equal Top2Survival, a +0.05 PairScore edge requires a +0.20 PairInteraction edge. If P4 is even 0.02 lower on Top2Survival, it requires roughly +0.26 interaction improvement.

That was materially stricter than the intended meaning of “pair compatibility can compensate for a small individual disadvantage.” The correction below fixes this weighting inconsistency rather than fitting any settled outcome.

## 2. Unchanged parts

Keep unchanged from v0.6:

- v0.2 axis and pure top-five membership;
- candidate pool: only P4 may replace P3;
- Top2Survival formula and all component weights;
- PairInteraction bonuses/penalties;
- strength guard:
  - `P3.Good - P4.Good <= 0.08`
  - `P3.AbilityGood - P4.AbilityGood <= 0.12`
- basic race-specific safety gate;
- confidence A/B/C;
- Q2 / wide / trio evaluation policy.

## 3. Corrected Gate B — Top2 floor

Original:

`P4.Top2Survival >= P3.Top2Survival - 0.02`

v0.6a:

`P4.Top2Survival >= P3.Top2Survival - 0.05`

Rationale: a candidate may be modestly weaker individually if the pair interaction with ◎ is materially better. Five percentage points is still a hard protection against promoting a clearly inferior top2 horse.

## 4. Corrected Gate C — net pair advantage

Require BOTH:

- `P4.PairScore - P3.PairScore >= +0.015`
- and either:
  - `P4.PairInteraction - P3.PairInteraction >= +0.08`; or
  - P3 has a severe shared-failure condition with ◎ and P4 does not.

The 0.015 threshold is consistent with the 75/25 PairScore weighting: an interaction improvement of +0.20 offsets a Top2Survival disadvantage of about 0.046 and still leaves a small positive net pair edge.

The selector must therefore still prefer P4 as a pair overall; pair diversity cannot justify a negative PairScore.

## 5. Gate E — value path plus rare pair-override path

### 5.1 Normal value promotion

After Gates A-D, promote when the original market/value confirmation passes:

- P4 base win rank at least 1 worse than P3; or
- P4 base place rank at least 1 worse than P3; or
- P4 base win rank >=6 in fields of 10+.

This remains the normal ▲=value path.

### 5.2 Pair-override when no market value exists

If the market confirmation does **not** pass, P4 may still take ▲ only when ALL are true:

- `P4.PairScore - P3.PairScore >= +0.05`
- `P4.Top2Survival - P3.Top2Survival >= +0.04`
- P3 has a severe shared-failure condition with ◎
- P4 does not have a severe shared-failure condition with ◎

This is not labeled a value promotion. It is a **pair-compatibility override** for a race where no legitimate value horse exists but the ordinary P3 is materially worse as the second quinella opponent.

User-facing wording must explicitly say that this is not a value/mispricing ▲.

Example:

> 妙味枠ではなくペア適性を優先。純粋評価はP4だが、P3は◎と同じ展開リスクを抱える。こちらは連対残存性と◎との組み合わせが明確に上で、馬連2点目はこちらを取る。

## 6. Pre-result activation check

Applying v0.6a to the same untouched 72-race RaceNote inputs, still before any HJC/result acquisition:

- promotions: **2/72 = 2.8%**
- both are P4 -> ▲
- one is normal value promotion
- one is pair-compatibility override without value labeling

This is above the preregistered pathological <2% boundary. No further calibration is allowed on this block.

## 7. Blind boundary

After this file is committed:

1. regenerate the 72-race v0.2/v0.6a prediction payload;
2. commit the complete pre-HJC freeze and payload SHA-256;
3. only then acquire HJC for 2025-09-15 / 09-21 / 09-27;
4. settle unchanged.

No threshold or formula may be altered after target HJC/result acquisition.

## 8. Interpretation standard

This remains a first blind block. Even if both promotions succeed, do not promote v0.6a immediately.

The primary question is whether the new information target — **Top2 survival + ◎ pair interaction** — produces useful changed-role decisions at all. Replication on another untouched block remains required before production promotion.
