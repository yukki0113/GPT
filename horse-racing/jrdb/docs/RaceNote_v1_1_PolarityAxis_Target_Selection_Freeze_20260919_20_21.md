# RaceNote v1.1-P Polarity-Axis Target Selection Freeze — 2026-09-19 / 09-20 / 09-21

## Status

**TARGET DATES FROZEN BEFORE TARGET RESULT ACQUISITION**

Frozen: 2026-09-10

`result_data_used = false`

This file freezes the next evaluation dates for `RaceNote_v1_1_PolarityAxis_Prediction_Design_Candidate.md`
under `RaceNote_v1_1_PolarityAxis_Backtest_Protocol.md`.

No target HJC, SED, finish, payout, final odds, final popularity, Edge activation count, or target RaceNote
prediction outcome was inspected to choose these dates.

## 1. Selected block

Selected JRA dates:

- 2026-09-19
- 2026-09-20
- 2026-09-21

Planned venues from the published JRA calendar:

- 中山
- 阪神

Published program currently schedules 12 races per venue per day, for an expected total of:

`3 dates × 2 venues × 12 races = 72 races`

The actual pre-race PACI snapshot is authoritative for the realized race set.
Schedule changes, cancellations, or source-availability failures must be handled by audit status rather than
by choosing replacement races after results are known.

## 2. Selection rationale

The block is selected because:

- it occurs after the v1.1-P design and protocol were established;
- all three dates are future dates at target-selection time;
- it is a coherent three-day JRA meeting block;
- it is not one of the settled v1.0 diagnostic dates 2026-08-09 / 08-15 / 08-22;
- it is not one of the Edge development/backfill dates 2026-09-05 / 09-06;
- no race-level filtering was performed.

The block was not selected using favorite strength, race grade, expected payout, Edge coverage, predicted
activation, or known performance.

## 3. Frozen model comparators

Before result acquisition, each supported target race must freeze all three predictive policies:

1. `v0.2_control`
2. `v1.0-R_frozen`
3. `v1.1-P_candidate`

The v1.1-P rule is the already preregistered polarity-axis design:

- reuse v1.0 family aggregation through `PerformanceEdgeTier`;
- collapse the tier to polarity {-1, 0, +1};
- `PolarityAdjustment = 0.02 * PerformanceEdgePolarity`;
- compute `AxisGood = clamp(v0.2_Good + PolarityAdjustment, 0, 1)`;
- select only ◎ by highest AxisGood among the original v0.2 top five;
- preserve the original v0.2 relative order of the remaining four marks;
- Value Edge remains shadow annotation only.

No 0.04 eligibility guard or other later alternative rule is part of this block.

## 4. Fixed Registry

All Edge-consuming comparators must use exactly the same Phase1 Registry:

- Issue: `#572`
- run_id: `34299375131`
- Registry version: `phase1-003-research-2010-2025-d`
- ACTIVE registry SHA-256: `845d3e1078d2b0d98534c4bfb1a25a7b927f2b6d91b16f181b369a8a8bd64be4`
- predictive statuses: `ACTIVE` only

Do not substitute Registry v0.2 / HUMAN experimental builds into this target block.

## 5. Pre-race execution requirements

For each selected date:

1. confirm latest `main`;
2. obtain target-date pre-race PACI;
3. acquire RaceNote / Reader View with `as_of_exclusive = target_date`;
4. obtain the common EdgeDB pre-race Freeze / `edge_matches.jsonl` from the fixed Registry;
5. generate v0.2 / frozen v1.0-R / v1.1-P predictions;
6. freeze the complete canonical prediction payload and provenance;
7. record `result_data_used=false`;
8. hash-anchor the prediction freeze before target HJC/SED/result acquisition.

For TRUE_FORWARD Edge operation, use the canonical `[JRDB_EDGE_FORWARD_FREEZE]` path before the earliest
scheduled post time. If that pre-race time guard is missed, do not relabel later reconstruction as TRUE_FORWARD.

## 6. Per-race freeze contents

Freeze at minimum:

- race identity;
- RaceNote / Reader View provenance;
- v0.2 Good and AbilityGood;
- v0.2 top five;
- matched ACTIVE Edge IDs;
- PerformanceEdgeTier;
- PerformanceEdgePolarity;
- v0.2 marks;
- frozen v1.0-R marks;
- v1.1-P marks;
- ValueEdgeTier shadow diagnostic;
- A/B/C confidence;
- displayed Edge IDs / concise comments;
- Registry provenance;
- Edge Freeze provenance and hashes;
- canonical prediction payload SHA-256.

## 7. Source-availability rule

Do not replace an individual race because it appears difficult, inactive, low-value, or unfavorable.

If a race cannot be scored because the required pre-race source is genuinely unavailable or invalid:

- fail closed for that race;
- record the exact source-availability reason;
- do not inspect its result before deciding treatment;
- keep the date in the target block.

If an entire date cannot be executed from valid pre-race sources, any replacement date must be selected
and documented before reading that target date's results.

## 8. Settlement boundary

Only after the prediction freeze for a date is successfully anchored may target HJC/SED/results be acquired
for RaceNote settlement.

The Edge TRUE_FORWARD ledger settlement remains a separate canonical EdgeDB operation and must consume the
exact pre-race Edge Freeze artifact rather than recomputing matches after the race.

## 9. Primary evaluation

Follow `RaceNote_v1_1_PolarityAxis_Backtest_Protocol.md`.

Primary v1.1-P vs v0.2:

- ◎ win / top2 / top3;
- ◎ single-win ROI;
- changed-axis head-to-head;
- Q2 hit count / ROI.

Primary v1.1-P vs frozen v1.0-R:

- changed-axis count;
- axis win / top2 / top3;
- Q2 hit / ROI;
- lower-order mark churn;
- lower-order-sensitive ticket impact.

One block does not promote v1.1-P.
