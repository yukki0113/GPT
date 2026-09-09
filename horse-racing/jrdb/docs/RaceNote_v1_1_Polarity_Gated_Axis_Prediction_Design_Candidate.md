# RaceNote v1.1-P Polarity-Gated Axis Prediction Design Candidate

## Status

**POST-HOC HYPOTHESIS FROM THE SETTLED v1.0 BLOCK / MUST BE FROZEN BEFORE A NEW UNTOUCHED OR TRUE_FORWARD BLOCK**

Established: 2026-09-10

This document defines the next RaceNote Edge consumer experiment after the settled 2026-08-09 / 08-15 / 08-22 v1.0 Edge-aware block.

The settled block is used only to formulate this new hypothesis. Its 108 races must not be reused as fresh validation evidence for v1.1-P.

## 1. Motivation from the settled v1.0 block

The first Edge-aware block showed:

- Performance Edge polarity generalized out of sample.
- Among all runners, POSITIVE (+1/+2) versus NEGATIVE (-1/-2) separated by win +3.06pp and top3 +8.90pp under race-cluster bootstrap.
- Among the pre-existing v0.2 top five, the same comparison separated by win +8.04pp and top3 +11.16pp.
- v1.0-R improved the axis by one win / one top2 / one top3 over 108 races.
- The current tier magnitude was not monotonic: +1 outperformed +2 inside the v0.2 top-five subset.
- Lower-order reshuffling did not improve pooled ticket economics; Q2 ROI and trio B5 ROI fell.
- Value-role activation was only 2/108 and remains too sparse for promotion.

Therefore v1.1-P tests a narrower claim:

> Edge polarity may be useful for choosing the axis among already-close v0.2 candidates, without treating Edge tier magnitude as an ordinal score and without broadly reordering the lower marks.

This is a post-hoc design hypothesis, not a result already established by the settled block.

## 2. Fixed sources and attribution boundary

Control model remains:

- `RaceNote_v0_2_Tested_Implementation_Spec_144R.md`

Edge consumer contract remains:

- `JRDB_Edge_Consumer_Integration_v0_1.md`

For the first v1.1-P test, keep the same Phase1 Registry used by v1.0 so that only the RaceNote consumer policy changes:

- Registry build Issue: `#572`
- run_id: `34299375131`
- Registry version: `phase1-003-research-2010-2025-d`
- ACTIVE registry SHA-256: `845d3e1078d2b0d98534c4bfb1a25a7b927f2b6d91b16f181b369a8a8bd64be4`
- default status: `ACTIVE` only

Do not substitute the later Edge Registry v0.2 research builds into this comparison. A Registry change and a RaceNote consumer-policy change must be tested separately.

## 3. Leakage boundary

The v1.0 leakage boundary remains unchanged.

Allowed before prediction freeze:

- target pre-race PACI facts;
- exact previous history resolved under the common Edge Matcher contract;
- RaceNote / Reader View data with `as_of_exclusive = target_date`;
- the fixed Phase1 ACTIVE Registry and its published Matcher output.

Forbidden before prediction freeze:

- target SED;
- target HJC;
- finish / payout;
- final odds / final popularity;
- later-dated history;
- any manual result knowledge used to alter marks.

For a retrospective 2026 block, candidate dates must not have been used for RaceNote model calibration, Edge smoke/calibration, or known-result diagnosis.

TRUE_FORWARD dates are preferred when operationally practical.

## 4. Preserve the v0.2 candidate set

Compute v0.2 exactly as the tested specification:

`Good = 0.42*AbilityGood + 0.38*SuitabilityGood + 0.10*Condition + 0.10*ForecastGood`

with the tested contradiction and weak-ability penalties unchanged.

Take the existing v0.2 top five only.

v1.1-P cannot pull P6+ into the marked five.

This preserves the tested ability/suitability scaffold and isolates axis selection.

## 5. Performance Edge family voting

Eligible predictive Edge matches remain the same as v1.0:

- `status == ACTIVE`;
- `evidence.performance_signal in {POSITIVE, NEGATIVE}`;
- not expired.

`value_signal`, historical ROI, place ROI, `strength_score`, sample rate and raw lift do not enter the predictive mark numerically.

Within each Edge family, use the existing v1.0 correlation control:

1. collect eligible matches by family;
2. determine the strongest confidence magnitude separately for POSITIVE and NEGATIVE;
3. confidence A = 2, B = 1;
4. `review_due` downgrades magnitude by one step;
5. same strongest magnitude in both directions => family vote 0;
6. otherwise family vote takes the stronger direction.

The family-vote implementation is unchanged from v1.0 so that the experiment changes only horse-level use of the aggregate.

## 6. Collapse tier magnitude to polarity

Let:

`FamilyVoteSum = sum(family_votes)`

Do not clamp or use its magnitude as a prediction score.

Define:

- `PerformanceEdgePolarity = POSITIVE` when `FamilyVoteSum > 0`
- `PerformanceEdgePolarity = NEUTRAL` when `FamilyVoteSum == 0`
- `PerformanceEdgePolarity = NEGATIVE` when `FamilyVoteSum < 0`

For deterministic comparison, map only for ordering:

- POSITIVE = +1
- NEUTRAL = 0
- NEGATIVE = -1

The values are categorical labels, not additive Good points.

No distinction is made between former `+1` and `+2`, or between former `-1` and `-2`.

## 7. Axis eligibility guard

Let the original v0.2 axis be `BaseAxis`, with score `BaseGood`.

A v0.2 top-five horse is `AxisEligible` only when:

`BaseGood - HorseGood <= 0.04`

Because higher Good is better, this keeps only horses no more than 0.04 below the v0.2 axis.

The `0.04` guard is inherited from the preregistered maximum absolute Edge adjustment in v1.0. It is re-used as a bounded closeness guard, not recalibrated from the settled 108 races.

The guard prevents Edge from promoting a materially weaker base candidate solely because a condition match fires.

## 8. v1.1-P axis selection

Among `AxisEligible` horses:

1. compare `PerformanceEdgePolarity` with the original `BaseAxis` polarity;
2. only horses with a **strictly higher** polarity than `BaseAxis` may replace it;
3. choose the challenger with the highest polarity;
4. if multiple challengers share that polarity, choose higher original v0.2 `Good`;
5. final deterministic tie-break: lower horse number.

If no eligible horse has strictly higher polarity, keep the original v0.2 axis.

Examples:

- BaseAxis NEGATIVE, close POSITIVE challenger => challenger may become ◎.
- BaseAxis NEGATIVE, close NEUTRAL challenger and no POSITIVE => NEUTRAL challenger may become ◎.
- BaseAxis NEUTRAL, close POSITIVE challenger => challenger may become ◎.
- BaseAxis POSITIVE => no Edge-based axis replacement.
- A POSITIVE horse more than 0.04 below BaseGood => cannot become ◎.

There is no numerical Edge addition to `Good`.

## 9. Marks after an axis change

If the axis does not change, all five v0.2 marks remain unchanged.

If a challenger becomes ◎:

1. place the challenger first;
2. remove it from its original v0.2 position;
3. append the other four horses in their original v0.2 relative order;
4. assign ○ / ▲ / △1 / △2 in that order.

Thus v1.1-P performs one axis promotion and the minimum deterministic shift required to keep a complete five-mark ordering.

It does not independently optimize ○, ▲, △1 or △2 by Edge.

## 10. Value Edge

Value Edge remains **shadow only**.

Continue to record:

- eligible ACTIVE value matches;
- family votes;
- `ValueEdgeTier` or an equivalent diagnostic aggregate;
- whether a hypothetical value-role change would have occurred.

However Value Edge must not change ◎ / ○ / ▲ / △ under v1.1-P.

The settled 2/108 activation is insufficient to justify a new value-role rule.

## 11. Confidence and explanation

Keep the existing v0.2/v1.0 A/B/C confidence rule unchanged.

For user-facing explanation, if the axis changes, explicitly state both sides:

- the v0.2 base candidates were close enough to enter the 0.04 guard;
- the selected ◎ had a stronger Edge polarity than the original axis.

Do not claim that POSITIVE Edge proves the horse is stronger in absolute terms.

Display at most one strongest supporting and one strongest opposing ACTIVE Edge, using confidence and `strength_score` only for explanation ordering.

## 12. Required freeze payload

Before any target result / HJC acquisition, freeze for every race:

- source RaceNote / Reader View provenance;
- v0.2 Good for all runners;
- v0.2 top-five marks;
- eligible Edge IDs by horse;
- family votes;
- `FamilyVoteSum`;
- `PerformanceEdgePolarity`;
- `AxisEligible`;
- BaseGood and Good gap from the original axis;
- v1.1-P selected axis and final marks;
- confidence;
- explanation / displayed Edge IDs;
- Registry run_id / artifact / registry SHA;
- Edge match artifact / SHA / manifest provenance.

The freeze must be immutable and hash-anchored before settlement.

## 13. Next evaluation design

Primary comparison:

- v0.2 control vs v1.1-P

Keep v1.0-R only as a historical reference; do not use the settled 108 races to select between variants.

Primary metrics:

1. ◎ win / top2 / top3;
2. changed-axis head-to-head;
3. number and rate of axis activations;
4. single-win return for all races and changed-axis races;
5. Q2 `◎-○ / ◎-▲` hit count and ROI.

Secondary:

- Q4;
- trio A6 / B5;
- activation by BaseAxis polarity;
- challenger polarity;
- Good-gap bucket;
- confidence;
- Edge family mix.

The key falsification question is:

> Does polarity-gated axis replacement improve the axis without recreating the broad lower-order ticket degradation seen in v1.0-R?

## 14. Promotion rule

Do not promote v1.1-P from one block.

Minimum path:

1. freeze this specification before the next untouched / TRUE_FORWARD block;
2. settle the block without changing the rule;
3. if directionally useful and operationally active enough, repeat unchanged on a second independent block;
4. only then consider replacing v0.2 axis selection.

If activation is too sparse, record that outcome. Do not loosen the 0.04 guard on the settled block.

If it loses materially, retire or redesign the polarity-gated axis rule rather than tuning thresholds against the same results.

## 15. Explicit exclusions

Not part of v1.1-P:

- Registry v0.2 substitution;
- P6+ candidate-set expansion;
- direct `PerformanceEdgeTier` magnitude;
- learned Edge coefficients;
- historical ROI as prediction weight;
- `strength_score` as prediction weight;
- PROVISIONAL / WATCH Edge;
- Value Edge mark replacement;
- final odds / popularity value modeling;
- changes to v0.2 Ability / Suitability / Condition / Forecast components.

Each of those requires a separately versioned experiment.
