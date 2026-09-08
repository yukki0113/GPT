# RaceNote v0.4a — Pre-Result Activation Calibration

## Status

**PREREGISTERED BEFORE TARGET HJC / RESULT ACQUISITION**

Target blind block: 2025-08-16 / 2025-08-17 / 2025-08-31, 中京・新潟・札幌, 108 races.

The dates were randomly selected from unused August dates before any target result lookup. RaceNote pre-race bundles were acquired, but target HJC/result/final target odds-popularity were not acquired or consulted.

## 1. Why v0.4 was adjusted before settlement

The original `RaceNote_v0_4_ValuePromotion_Design_Candidate.md` explicitly stated that P4/P5 promotion should have a middle-frequency character and that a clearly pathological pre-result activation rate may be reviewed before result acquisition.

Applied unchanged to this 108-race block, the original v0.4 gates promoted P4/P5 in only **1/108 races = 0.9%**.

That is materially below the design's rough 10–30% engineering expectation and would make the proposed `▲ = value-oriented challenger with P3 defense` almost indistinguishable from pure P3.

Therefore the border is recalibrated using **activation counts only**. No target payout, finish, HJC, final odds/popularity, or Web result is used.

## 2. Calibration principle

The goal is not to maximize a return metric. The goal is only to restore the intended middle-frequency behavior while changing as little as practical from the original P3-defense design.

Several pre-result threshold variants were inspected only for activation frequency. The conservative accepted variant produces **11/108 = 10.2%** actual P4/P5 promotions, at the lower edge of the preregistered 10–30% range.

This accepted variant is named **v0.4a**.

## 3. v0.4a mandatory Gate A — strength proximity

Relative to pure P3:

- P4: `core_gap <= 0.08`
- P5: `core_gap <= 0.07`
- candidate `AbilityGood` may trail P3 by at most `0.15`

This is only modestly looser than original v0.4 (`0.07 / 0.06 / 0.12`).

## 4. v0.4a mandatory Gate B — today's reason

Keep the same definition:

`today_edge = 0.60*(SuitabilityGood diff) + 0.25*(ForecastGood diff) + 0.15*(Condition diff)`

Require BOTH:

1. `today_edge >= +0.025`
2. at least one clear edge:
   - `SuitabilityGood advantage >= +0.05`, or
   - `ForecastGood advantage >= +0.08`, or
   - `Condition advantage >= +0.10`

This is deliberately less strict than original v0.4 but still requires a positive today-specific case. Market disagreement alone remains insufficient.

## 5. v0.4a mandatory Gate C — value / market disagreement

Candidate must satisfy at least one:

- base-market rank is at least **1 place worse than P3's**; or
- base-market rank is at least **2 places worse than its own pure v0.2 rank**.

The purpose is to require some price disagreement without demanding an extreme longshot profile.

## 6. Hard rejection

Unchanged in principle:

- explicit contradictory distance evidence -> reject;
- material condition decline -> reject unless a stronger documented suitability/forecast edge offsets it;
- popularity alone cannot justify promotion.

For a `やや下降気味` challenger, require an additional edge equivalent to either:

- Suitability edge >= `0.09`, or
- Forecast edge >= `0.13`.

## 7. P3 protection

`P3_strong_today = true` when:

- P3 `SuitabilityGood >= 0.70`;
- no explicit distance contradiction;
- no `やや下降気味` training arrow.

When true, challenger must satisfy:

- `core_gap <= 0.06`
- `today_edge >= +0.045`
- Gate C still required.

This preserves the core idea that a well-supported P3 is not displaced casually.

## 8. Multiple challengers

Define:

- `value_gap = max(candidate_market_rank - P3_market_rank, candidate_market_rank - pure_rank)`; missing P3 market comparison contributes zero.
- `value_support = clamp((value_gap - 1) / 5, 0, 1)`
- `strength_nearness = max(0, 1 - core_gap / 0.08)`
- `promotion_margin = 0.50*today_edge + 0.30*strength_nearness + 0.20*value_support`

If two challengers' margins differ by `< 0.03`, prefer P4.

## 9. Frozen activation check

Before target HJC acquisition:

- original v0.4: 1/108 = 0.9%
- accepted v0.4a: **11/108 = 10.2%**
- accepted promotions are all P4 in this particular block; no P5 cleared all gates.

The lack of P5 promotions is recorded but is not used to loosen the rule further.

## 10. Blind-test comparison

Freeze before HJC:

- v0.2 pure marks
- old v0.3 selector (shadow)
- v0.4a P3-defense selector
- confidence A/B/C
- standard comments
- Q2 for each selector
- Q4
- trio A6 and B5
- optional `◎-▲` wide diagnostics

Primary v0.4a question: does a lower-frequency, P3-defended value promotion improve the old v0.3 trade-off between payout and hit loss without simply reverting to pure P3?

No additional threshold adjustment is allowed after target HJC/result acquisition.