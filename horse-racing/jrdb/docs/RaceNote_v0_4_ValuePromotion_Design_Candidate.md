# RaceNote v0.4 Value-Promotion Design Candidate

## Status

**CANDIDATE / PREREGISTRATION DESIGN ONLY — NOT YET TESTED**

This design keeps the validated v0.2 axis and the user-facing semantic idea that `▲` can be a value-oriented opponent, while replacing the unstable old v0.3 value selector.

The core principle is **P3 defense**:

> Pure P3 remains ▲ by default. A P4/P5 horse may take ▲ only when it is close enough in underlying strength, has a clear race-specific advantage today, and also offers meaningful market/value disagreement.

This is intentionally stricter than the old v0.3 selector. It is not tuned to maximize settled July/August payouts.

## 1. Fixed base ranking

Use the unchanged tested v0.2 ranking to obtain:

- ◎ = P1
- ○ = P2
- provisional ▲ = P3
- P4
- P5

The top-five membership is unchanged. v0.4 only decides whether P4/P5 may replace P3 in the `▲` role.

If no candidate clears every mandatory gate below, marks remain:

`◎ / ○ / ▲=P3 / △1=P4 / △2=P5`.

## 2. Candidate pool

Only P4 and P5 may challenge P3.

No horse outside the v0.2 top five may be promoted to ▲ in v0.4.

This preserves the current ability/suitability candidate set and prevents a value search from becoming a longshot search.

## 3. Mandatory Gate A — strength proximity

A value candidate must be close enough to P3 in the unchanged v0.2 core score.

Let:

`core_gap = P3.Good - candidate.Good`

where larger `Good` is better.

Eligibility:

- P4: `core_gap <= 0.07`
- P5: `core_gap <= 0.06`

In addition:

- candidate `AbilityGood` may not trail P3 by more than `0.12`.

If these conditions fail, the candidate cannot take ▲ regardless of popularity/value.

Rationale: ▲ may seek price, but must remain genuinely competitive with the orthodox third choice.

## 4. Mandatory Gate B — today-specific reason to prefer the candidate

Market disagreement alone is never sufficient.

Compare the candidate with P3 on already-available pre-race components:

- `SuitabilityGood`
- `ForecastGood`
- condition/current-state score

Define:

`today_edge = 0.60*(candidate.SuitabilityGood - P3.SuitabilityGood) + 0.25*(candidate.ForecastGood - P3.ForecastGood) + 0.15*(candidate.Condition - P3.Condition)`

A candidate must satisfy BOTH:

1. `today_edge >= +0.05`
2. at least one **clear edge**:
   - `SuitabilityGood advantage >= +0.08`, or
   - `ForecastGood advantage >= +0.10`, or
   - `Condition advantage >= +0.12`

This forces every value promotion to have a concrete race-specific explanation.

## 5. Mandatory Gate C — value / market disagreement

Only after Gates A and B pass, require a modest but real market-value signal using the same pre-target-safe base-market information already available in RaceNote.

Candidate must satisfy at least one:

- candidate base-market rank is `>= 2` places worse than P3's base-market rank; or
- candidate base-market rank is `>= 3` places worse than its own pure v0.2 prediction rank.

This threshold is intentionally lower than an extreme longshot filter. The goal is price disagreement, not obscurity.

## 6. Hard rejection conditions

Do NOT promote a P4/P5 candidate if any applies:

- distance evidence is explicitly contradictory under the existing v0.2 rule;
- a material current-condition decline is present and is not offset by a stronger documented race-specific reason;
- race-specific evidence is too sparse to support the asserted advantage;
- the candidate's value case depends only on low popularity / market rank.

When rejected, P3 keeps ▲.

## 7. P3 protection rule

P3 receives extra protection when it is itself strongly supported today.

Define `P3_strong_today = true` when BOTH:

- `P3.SuitabilityGood >= 0.70`
- P3 has no explicit major risk/contradiction under the existing v0.2 evidence

If `P3_strong_today = true`, a challenger must satisfy the stricter conditions:

- `core_gap <= 0.04`
- `today_edge >= +0.08`
- and still pass Gate C.

This is the main safeguard against the failure mode observed in August, where a legitimate orthodox P3 was discarded too easily.

## 8. If both P4 and P5 qualify

Choose the challenger with the highest **promotion margin**:

`promotion_margin = 0.50*today_edge + 0.30*strength_nearness + 0.20*value_support`

where:

- `strength_nearness = max(0, 1 - core_gap/0.07)`
- `value_support` is normalized only from pre-race market disagreement, capped so that popularity cannot dominate.

If the two challengers are effectively tied (`margin difference < 0.03`), prefer P4.

The exact normalized value-support implementation must be frozen before the next blind block; it must not use settled payouts.

## 9. Resulting mark semantics

- ◎: most likely winner under today's conditions
- ○: strongest orthodox opponent
- ▲: P3 by default; replaced only by a P4/P5 horse that passes all value-promotion gates
- △1 / △2: remaining top-five horses in pure v0.2 priority order after ▲ assignment

Example pure order:

`P1=8, P2=5, P3=12, P4=3, P5=7`

If P4=3 passes promotion:

`◎8 / ○5 / ▲3 / △12,7`

If no challenger passes:

`◎8 / ○5 / ▲12 / △3,7`

## 10. User-facing ▲ comment contract

When value promotion occurs, the short comment must be able to explain all three layers:

1. why the horse is strong enough to challenge P3;
2. what today's condition gives it over P3;
3. why the price/evaluation disagreement adds value.

Preferred form:

> 純粋な総合評価では4番手だが、P3との能力差は小さい。今回はハイ想定で差し脚質がより噛み合い、展開面ではこちらを上に取りたい。市場評価も相対的に低く、馬連2点目は妙味込みでこちら。

If this explanation cannot be written honestly from the data, do not promote the horse.

## 11. Expected aggressiveness

This design intentionally aims for a **middle-frequency** value role:

- not every race should have a promoted ▲;
- not only extreme longshots should qualify;
- as a rough engineering expectation, actual P4/P5 promotions around 10–30% of ordinary races would be plausible, but this is NOT a hard target and must not be tuned using settled returns.

If the next untouched pre-result freeze produces a clearly pathological activation rate, that fact may be reviewed before result acquisition, but no payout/outcome information may be used to adjust the rule.

## 12. Next blind test

On a new untouched 72–144R block, freeze before HJC:

- v0.2 pure marks (control)
- old v0.3 value selector (shadow comparison)
- v0.4 P3-defense selector
- confidence A/B/C
- standard comments
- Q2: ◎-○ / ◎-▲ for each selector
- Q4 diagnostic
- trio A6/B5
- optional ◎-▲ wide diagnostic

Primary v0.4 evaluation:

1. changed-role head-to-head gains/losses versus pure P3;
2. Q2 hit count and return;
3. whether value promotion still improves price without materially sacrificing hit rate;
4. whether the user-facing ▲ explanation is concrete and convincing;
5. activation rate and P4/P5 composition.

Do not promote v0.4 from one favorable block. Require replication across at least two untouched blocks or an adequately large combined changed-role sample.
