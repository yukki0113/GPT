# RaceNote v1.1-P Polarity-Axis Prediction Design Candidate

## Status

**POST-v1.0 SETTLEMENT PREREGISTERED CANDIDATE / MUST USE A NEW UNTOUCHED BLOCK**

Established: 2026-09-09

This document defines the next RaceNote consumer-side Edge experiment after the settled
`RaceNote_v10_Edge_Blind_Result_20260809_15_22.md` block.

The settled 108-race block is diagnostic evidence used to define this candidate and must not be reused
as fresh blind evidence for v1.1-P.

## 1. Motivation fixed from the settled v1.0 block

The first Edge-aware prospective block supported one finding more clearly than the others:

- Performance Edge polarity generalized out of sample: POSITIVE groups outperformed NEGATIVE groups.
- `+2 > +1 > 0 > -1 > -2` did not generalize as an ordinal strength scale.
- full top-five Edge reordering slightly improved the axis but damaged some pooled ticket economics,
  especially lower-order-sensitive Trio B5.
- Value Edge changed only 2/108 `▲` roles and remains too sparse for promotion.

Therefore v1.1-P changes only the unsupported magnitude/role interaction.
It does not search a new coefficient, expand the candidate set, or change the Registry.

## 2. Frozen sources

Control:

- `RaceNote_v0_2_Tested_Implementation_Spec_144R.md`
- same reconstructed/tested v0.2 `Good` and confidence rules used by v1.0.

Edge source is deliberately held fixed to isolate the RaceNote consumer policy:

- Registry Phase1 baseline: Issue #572 / run `34299375131`
- Registry version: `phase1-003-research-2010-2025-d`
- ACTIVE registry SHA-256: `845d3e1078d2b0d98534c4bfb1a25a7b927f2b6d91b16f181b369a8a8bd64be4`
- consumer input: EdgeDB-produced `edge_matches.jsonl`
- predictive status: **ACTIVE only**

Do not substitute a newer Edge Registry build inside this experiment.
A Registry-version comparison is a separate experiment.

## 3. Leakage boundary

Same as v1.0:

- target must be 2026 or later;
- current-race facts come only from pre-race PACI;
- previous history follows the exact Edge consumer contract;
- no target SED/HJC/final odds/final popularity before prediction freeze;
- no later-dated history may fill an unresolved transition.

Excluded as fresh v1.1-P evidence:

- 2026-08-09 / 2026-08-15 / 2026-08-22 — settled v1.0 diagnostic block;
- 2026-09-05 / 2026-09-06 — Edge development/backfill dates;
- any other date already used for known-result RaceNote logic diagnosis.

## 4. Base candidate set

Keep v0.2 top-five membership unchanged.

Edge cannot pull v0.2 rank 6 or lower into the marked five.

Let the v0.2 ordered five be:

`[P1, P2, P3, P4, P5]`

with their original `Good`, `AbilityGood`, and marks retained as the control record.

## 5. Performance Edge aggregation

Reuse v1.0 aggregation **unchanged** through `PerformanceEdgeTier`.

Eligible match:

- `status == ACTIVE`
- `evidence.performance_signal in {POSITIVE, NEGATIVE}`
- not expired.

Correlation control remains one vote per `evidence.family`.

Confidence voting remains:

- A = magnitude 2
- B = magnitude 1
- review-due A -> 1
- review-due B -> 0
- same strongest-confidence positive and negative direction inside a family -> `MIXED_FAMILY` / 0.

Horse-level diagnostic remains:

`PerformanceEdgeTier = clamp(sum(family_votes), -2, +2)`

No ROI, sample rate, place rate, or `strength_score` enters the numerical rank.

## 6. v1.1-P polarity collapse

For ranking only, collapse the tier to its sign:

```text
PerformanceEdgePolarity =
  +1 if PerformanceEdgeTier > 0
   0 if PerformanceEdgeTier = 0
  -1 if PerformanceEdgeTier < 0
```

`+1` and `+2` therefore receive the same predictive treatment.
`-1` and `-2` likewise receive the same predictive treatment.

Keep the old v1.0 single-step unit without fitting a new constant:

`PolarityAdjustment = 0.02 * PerformanceEdgePolarity`

Maximum adjustment is therefore ±0.02.

For each of the existing v0.2 top five:

`AxisGood = clamp(v0.2_Good + PolarityAdjustment, 0, 1)`

This is a hypothesis simplification, not a coefficient optimization.

## 7. Axis-only role interaction

Choose only the axis from Edge-adjusted scores.

`v1.1-P ◎ = highest AxisGood among the original v0.2 top five`

Tie-breakers:

1. higher original v0.2 `Good`;
2. higher `AbilityGood`;
3. lower horse number.

After the axis is selected, **do not re-sort the other four by Edge**.

Remove the selected axis horse from the original v0.2 order and preserve the relative order of all
remaining horses:

- ○ = first remaining horse in original v0.2 order
- ▲ = second remaining
- △1 = third remaining
- △2 = fourth remaining

If v0.2 P1 remains the axis, the complete mark order is therefore unchanged.

This isolates the most promising v1.0 observation — axis selection — while avoiding unnecessary
lower-role reshuffling.

## 8. Value Edge

Value Edge remains **shadow annotation only** in v1.1-P.

Continue calculating `ValueEdgeTier` under the v1.0 one-family-vote procedure for diagnostics, but:

- it does not replace `▲`;
- it does not change ◎/○/△;
- it does not change confidence;
- it does not change a ticket by itself.

A later value-role experiment requires a separately preregistered rule after more activation evidence.

## 9. Confidence and explanation

A/B/C confidence remains unchanged from the tested v0.2/v1.0 rule.

For ◎ / ○ / ▲, display at most:

- one strongest supporting ACTIVE Edge;
- one strongest opposing ACTIVE Edge.

`confidence_band`, then `strength_score`, may choose explanation order only.
They do not add numerical points beyond the polarity rule above.

## 10. Blind comparators

A new untouched block freezes three predictive policies before result acquisition:

1. `v0.2_control`
2. `v1.0-R_frozen` — the already preregistered full top-five linear-tier policy
3. `v1.1-P_candidate` — this polarity-only axis-focused policy

Running the old v1.0-R unchanged on the new block is important: it separates whether any improvement
comes from Edge itself versus the v1.1 consumer redesign.

Value-role `v1.0-V` may be recorded as shadow diagnostics, but is not a promotion candidate.

## 11. Interpretation rules

Do not promote v1.1-P from one new three-day block.

After a new block:

- if axis changes are sparse, carry the exact unchanged candidate into another untouched block;
- if v1.1-P improves axis metrics while preserving pooled ticket economics better than v1.0-R,
  repeat unchanged;
- if polarity fails against v0.2, do not tune `0.02` on the settled block;
- if v1.0-R beats v1.1-P, preserve that evidence rather than restoring tier magnitude post hoc.

No coefficient, threshold, family weight, candidate-set width, or value-role rule may be altered after
seeing the new block and still claim that same block as blind evidence.

## 12. Explicitly out of scope

Not part of v1.1-P:

- newer Registry v0.2 / HUMAN experimental builds;
- P6+ candidate-set expansion;
- learned Edge coefficients;
- direct use of historical ROI or `strength_score`;
- PROVISIONAL/WATCH Edge;
- confidence recalibration;
- final-odds/value modeling;
- automatic Ability/index mutation.

Those are separately versioned future experiments.
