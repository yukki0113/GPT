# RaceNote v1.1-P Polarity-Gated Blind Freeze Addendum — 2026-09-10

Status: **PRE-RESULT DESIGN/TARGET BRIDGE / RESULT DATA MUST REMAIN UNACQUIRED**

## 1. Purpose

This addendum aligns the already-frozen untouched target selection with the latest v1.1-P consumer design before any target result acquisition.

Authoritative candidate for the next blind block:

- `docs/RaceNote_v1_1_Polarity_Gated_Axis_Prediction_Design_Candidate.md`
- design commit: `063b23cb6c2d16baad2abfdd0bff688226423760`

Previously selected target dates remain:

```text
20260704
20260725
20260726
```

The dates were selected and committed before target HJC / SED / finish / payout / final odds / final popularity acquisition. They are not re-randomized after the v1.1-P design refinement.

## 2. Target-selection continuity

`RaceNote_v1_1_P_Target_Selection_20260704_25_26.md` remains the source of truth for date selection.

Its original deterministic seed referenced the earlier polarity-axis candidate. The later polarity-gated design changes the consumer rule but does not invalidate the fact that these dates were selected without target results.

To avoid adding a new researcher degree of freedom, this addendum therefore:

- keeps 2026-07-04 / 07-25 / 07-26 unchanged;
- does not rerun date selection with the new design commit;
- does not inspect Edge activation, race difficulty, payout shape or target outcomes to decide whether to retain them;
- permits replacement only for a documented pre-race source-availability failure, before any target result is read.

At this addendum preflight, repository Issue search for `20260704`, `20260725` and `20260726` returned the target-selection Issue only. No target HJC / SED / result acquisition Issue had been created for these dates.

`result_data_used = false`

## 3. Fixed attribution boundary

Control:

- `RaceNote_v0_2_Tested_Implementation_Spec_144R.md`
- reconstructed control semantics already frozen by `RaceNote_v1_0_Control_Reconstruction_Freeze_20260909.md`

Edge source remains exactly the Phase1 Registry used by the settled v1.0 block:

- Registry Issue: `#572`
- run_id: `34299375131`
- Registry version: `phase1-003-research-2010-2025-d`
- ACTIVE SHA-256: `845d3e1078d2b0d98534c4bfb1a25a7b927f2b6d91b16f181b369a8a8bd64be4`
- predictive status: `ACTIVE` only

The in-progress/newer Edge Registry v0.2 research line must not be substituted into this test.

## 4. v1.1-P rule frozen for this block

The older sign-collapse candidate that numerically added `0.02 * polarity` is not the primary v1.1-P candidate for this block.

Use the polarity-gated design from commit `063b23cb6c2d16baad2abfdd0bff688226423760`:

1. Compute v0.2 unchanged and preserve its top-five membership.
2. Aggregate eligible ACTIVE performance Edges with the existing one-family-vote correlation control.
3. Let `FamilyVoteSum = sum(family_votes)`.
4. Convert only the sign to `PerformanceEdgePolarity = NEGATIVE / NEUTRAL / POSITIVE`; do not use magnitude as Good points.
5. Let `BaseAxis` be the original v0.2 P1 and `BaseGood` its Good.
6. A top-five challenger is `AxisEligible` only when `BaseGood - HorseGood <= 0.04`.
7. A challenger may replace `BaseAxis` only when its polarity is strictly higher than the BaseAxis polarity.
8. Among valid challengers choose higher polarity, then higher original v0.2 Good, then lower horse number.
9. If the axis changes, move only that horse to ◎ and preserve the original relative order of the remaining four horses.
10. Value Edge remains shadow only and cannot change marks.
11. Confidence remains the existing v0.2/v1.0 metadata rule.

No historical ROI, `strength_score`, raw Edge tier magnitude, PROVISIONAL/WATCH Edge, final odds, or target result enters the prediction rule.

## 5. Required pre-result freeze

Before any HJC / SED / result acquisition for the three target dates, generate and immutably hash-anchor a prediction payload containing at least:

- RaceNote / Reader View source provenance and as-of boundary;
- v0.2 Good and AbilityGood for all runners;
- v0.2 top-five marks;
- matched ACTIVE Edge IDs and Edge artifact provenance;
- family votes and `FamilyVoteSum`;
- `PerformanceEdgePolarity`;
- `BaseGood`, Good gap and `AxisEligible`;
- v1.1-P selected axis and final five marks;
- Value Edge shadow diagnostic;
- A/B/C confidence;
- displayed supporting/opposing Edge IDs where applicable;
- Registry run / artifact / SHA;
- canonical prediction payload SHA-256;
- explicit `result_data_used=false`.

Current-race Edge facts must come from pre-race PACI and exact as-of-safe history under the common Matcher contract. No target SED is permitted in this phase.

## 6. Evaluation after freeze

Only after the prediction freeze is committed may target results be acquired.

Primary comparison:

- v0.2 control vs polarity-gated v1.1-P.

Keep frozen v1.0-R as a historical/reference comparator where useful, but do not use it to alter v1.1-P after seeing results.

Primary metrics:

1. ◎ win / top2 / top3;
2. changed-axis head-to-head;
3. axis activation count/rate;
4. single-win return overall and on changed-axis races;
5. Q2 `◎-○ / ◎-▲` hit count and ROI.

Secondary diagnostics include Q4, Trio A6/B5, BaseAxis polarity, challenger polarity, Good-gap bucket, confidence and Edge-family mix.

One block cannot promote v1.1-P. If activation is sparse, carry the exact same rule into another untouched block rather than loosening the `0.04` guard on settled races.

## 7. Immediate next operation

The next operation is pre-result reconstruction only:

```text
20260704 / 20260725 / 20260726
  -> as-of-safe RaceNote inputs
  -> fixed Phase1 ACTIVE Registry Matcher output
  -> v0.2 control + polarity-gated v1.1-P
  -> immutable prediction freeze
```

Do not request target HJC / SED until that freeze has been successfully created and hash-anchored.
