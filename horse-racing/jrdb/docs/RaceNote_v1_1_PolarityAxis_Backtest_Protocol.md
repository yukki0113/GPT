# RaceNote v1.1-P Polarity-Axis Blind Backtest Protocol

## Status

**PREREGISTER BEFORE NEW TARGET RESULT ACQUISITION**

Established: 2026-09-09

Design source:

- `RaceNote_v1_1_PolarityAxis_Prediction_Design_Candidate.md`

Control and legacy challenger:

- v0.2 tested/reconstructed control
- frozen `RaceNote_v1_0 Edge-Aware Prediction Design Candidate` as `v1.0-R_frozen`

## 1. Scientific boundary

The settled 2026-08-09 / 08-15 / 08-22 108-race block was used to define v1.1-P and is training/
diagnostic evidence only from this point forward.

The next target block must be selected without consulting target HJC, SED, finish, payout, final odds,
or final popularity.

2026-09-05 / 09-06 are excluded because they were used in Edge development/backfill work.

## 2. Fixed Registry

All policies in the new block that consume Edge use exactly:

- Issue #572
- run `34299375131`
- Registry `phase1-003-research-2010-2025-d`
- ACTIVE SHA-256 `845d3e1078d2b0d98534c4bfb1a25a7b927f2b6d91b16f181b369a8a8bd64be4`

Do not switch to Registry v0.2 during this comparison.

## 3. Target selection

Select a new three-day 2026 JRA block with complete pre-race RaceNote inputs.

Selection must occur before target result acquisition and must be recorded in a freeze manifest.

Do not choose dates by inspecting race difficulty, favorite strength, payout shape, Edge activation,
or settled performance.

If a chosen date cannot be reconstructed from pre-race sources, replace it for a documented source-
availability reason before any target result is read.

## 4. Freeze contents per race

Before HJC/SED/result acquisition freeze:

- race identity and input provenance;
- v0.2 top five / Good / AbilityGood;
- matched ACTIVE Edge IDs and Edge freeze SHA;
- PerformanceEdgeTier;
- PerformanceEdgePolarity;
- v0.2 control marks;
- `v1.0-R_frozen` marks;
- `v1.1-P_candidate` marks;
- ValueEdgeTier shadow diagnostic;
- A/B/C confidence;
- concise displayed Edge IDs/comments;
- Registry run/artifact/SHA;
- canonical prediction payload SHA-256.

The freeze record must explicitly state `result_data_used=false`.

## 5. Primary comparisons

### A. v1.1-P vs v0.2

Primary:

1. ◎ win / top2 / top3
2. ◎ single-win ROI
3. changed-axis head-to-head
4. Q2 hit count / ROI

Secondary:

- Q4 ROI
- Trio A6 / B5 ROI
- changed-race payout concentration
- confidence A/B/C diagnostics.

### B. v1.1-P vs frozen v1.0-R

Primary redesign questions:

1. number of changed axes
2. axis win / top2 / top3
3. Q2 hit / ROI
4. lower-order mark churn
5. Trio B5 / other lower-order-sensitive ticket impact.

This comparison tests polarity collapse plus axis-only interaction, not a new Edge Registry.

## 6. Edge diagnostics

Report at minimum:

- all-runner outcomes by `PerformanceEdgePolarity` {-1,0,+1};
- v0.2 top-five outcomes by polarity;
- positive vs negative win/top3 differences;
- race-cluster bootstrap confidence intervals;
- PerformanceEdgeTier table retained only as a diagnostic, not interpreted as an assumed ordinal scale.

Do not claim `+2 > +1` unless a later preregistered test directly supports it.

## 7. Value diagnostics

Continue to record ValueEdgeTier activation and outcomes, but v1.1-P does not alter `▲`.

Report activation count and hypothetical value-role outcome separately.
Do not mix hypothetical Value Edge gains/losses into v1.1-P primary ticket metrics.

## 8. Decision discipline

One three-day block cannot promote v1.1-P.

If the block has too few changed axes for a meaningful comparison, extend the same frozen candidate to
a second untouched block with no rule changes.

Any redesign after settlement starts a new candidate/version and requires a new untouched block.

The already settled 2026-08-09 / 08-15 / 08-22 block remains available for explanation and
post-hoc diagnosis only, never as fresh validation.
