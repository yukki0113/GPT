# RaceNote v1.1-P TRUE_FORWARD Target Selection — 2026-09-12 / 09-13

Status: **FROZEN / PRE-RACE / TRUE_FORWARD STAGE 1**

Frozen before target results are available.

`result_data_used = false`

## 1. Purpose

Advance the validated RaceNote v1.1-P polarity-gated axis rule from historical untouched blocks into genuine TRUE_FORWARD / shadow evaluation without parameter retuning.

The governing historical decision is:

- `RaceNote_v1_1_Polarity_Gated_Repeat_Blind_Result_20260705_11_12.md`
- decision: `KEEP_UNCHANGED / ADVANCE_TO_TRUE_FORWARD`

No settled 216-race result is used to alter the policy below.

## 2. Target block

Target dates:

- 2026-09-12
- 2026-09-13

Planned JRA venues:

- 中山
- 阪神

Expected scheduled races at target selection time:

`2 dates × 2 venues × 12 races = 48 races`

The target block is the complete scheduled weekend population. No race is selected or excluded by expected favorite strength, race class, Edge coverage, predicted axis activation, payout shape, model confidence, or subjective difficulty.

The realized pre-race PACI race set is authoritative if a schedule change or cancellation occurs.

## 3. Frozen prediction policy

Use the already validated v1.1-P rule unchanged:

1. compute the frozen v0.2 reconstructed control;
2. preserve the original v0.2 top-five membership;
3. aggregate eligible ACTIVE performance Edges with one-family-vote correlation control;
4. collapse only the sign to NEGATIVE / NEUTRAL / POSITIVE;
5. original v0.2 P1 is BaseAxis;
6. challenger eligibility requires `BaseGood - HorseGood <= 0.04`;
7. replace BaseAxis only when challenger polarity is strictly higher;
8. choose by higher polarity, then higher original Good, then lower horse number;
9. move only the selected challenger to ◎ and preserve remaining relative order;
10. Value Edge remains shadow only;
11. confidence is unchanged.

Policy implementation:

- `src/racenote_edge_prediction_policy.py`
- policy version: `1.1-P-gated-0.1`

Control implementation:

- `src/racenote_v02_reconstructed.py`
- control: `v0.2-reconstructed-20260909-a`

## 4. Edge attribution boundary for validated v1.1-P

For this first TRUE_FORWARD validation stage, the mark-changing v1.1-P path continues to use exactly the Edge source used for the historical validation so that the consumer policy is tested unchanged:

- Registry Issue: `#572`
- run_id: `34299375131`
- artifact: `jrdb-edge-registry-v2-phase1-003-full-2010-2025-d-34299375131`
- Registry version: `phase1-003-research-2010-2025-d`
- ACTIVE registry SHA-256: `845d3e1078d2b0d98534c4bfb1a25a7b927f2b6d91b16f181b369a8a8bd64be4`
- predictive status: `ACTIVE` only

EdgeDB v0.2 STANDARD may be collected separately for operational/shadow observation, but SUGGESTIVE evidence must not alter marks in this validated v1.1-P stage unless a later consumer-policy validation explicitly authorizes it.

## 5. TRUE_FORWARD boundary

For each target date, before the earliest scheduled post:

1. obtain target-date pre-race PACI;
2. obtain RaceNote v1.0 bundles from pre-race information only;
3. freeze Edge matches from the fixed Phase1 ACTIVE Registry with the canonical TRUE_FORWARD pre-race guard;
4. compute v0.2 and unchanged v1.1-P predictions;
5. hash-anchor the complete prediction payload before HJC / SED / race result acquisition;
6. record `result_data_used=false` and the exact freeze timestamp;
7. only after the prediction freeze exists may settlement data be acquired.

If the earliest-post pre-race guard is missed, that date must not be relabeled TRUE_FORWARD by historical reconstruction.

## 6. Required prediction freeze contents

At minimum preserve:

- date / venue / race identity and full runner membership;
- RaceNote source provenance and hashes;
- v0.2 Good / AbilityGood for all runners;
- v0.2 top-five marks;
- matched ACTIVE Edge IDs and Edge freeze provenance;
- family votes / FamilyVoteSum / polarity;
- BaseGood / Good gap / AxisEligible;
- v1.1-P selected axis and marks;
- Value Edge shadow diagnostics;
- A/B/C confidence;
- canonical payload SHA-256;
- `result_data_used=false`;
- TRUE_FORWARD pre-race guard status and freeze timestamp.

## 7. Primary settlement metrics

Use the same predeclared primary definitions as the historical validation:

- ◎ win / top2 / top3;
- ◎ single-win ROI;
- changed-axis head-to-head;
- axis activation count/rate;
- Q2 `◎-○ / ◎-▲` hit count and ROI.

Secondary diagnostics may include Q4, Trio A6/B5, confidence, Good-gap, family mix and polarity diagnostics, but they must not be used to retune this target block.

## 8. Decision discipline

This TRUE_FORWARD block is an operational confirmation stage, not a new tuning set.

- do not alter the `0.04` guard;
- do not alter family-vote aggregation;
- do not convert Edge magnitude to Good points;
- do not add SUGGESTIVE to the mark-changing path;
- do not exclude races after seeing predictions or results;
- do not tune on this block before settlement is complete.

After settlement, compare the 48-race TRUE_FORWARD results with the historical 216-race evidence and decide whether to continue unchanged, downgrade to shadow-only, or open a separately versioned consumer-policy research line.
