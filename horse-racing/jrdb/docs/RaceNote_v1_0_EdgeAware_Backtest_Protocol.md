# RaceNote v1.0 Edge-Aware Backtest Protocol

## Status

**FROZEN TEST PROTOCOL / BEFORE TARGET RESULT ACQUISITION**

This protocol operationalizes `RaceNote_v1_0_EdgeAware_Prediction_Design_Candidate.md` for the first untouched three-day comparison.

## 1. Target chronology

The released Edge Registry is trained/validated through 2025. Therefore targets must be 2026 or later.

Exclude:

- 2026-09-05 and 2026-09-06 (used in EdgeDB reconstruction smoke work);
- any date whose target results were inspected for RaceNote/Edge model design;
- any date lacking a leakage-safe pre-race RaceNote/Edge reconstruction path.

Use RaceNote Archive identity metadata only to form the candidate-date pool, then select three dates with a fixed random seed recorded in the freeze.

## 2. Models frozen before HJC

- `v0.2`: documented-spec-compatible reconstructed control
- `v1.0-R`: same top-five membership, Edge performance tier reordering
- `v1.0-V`: v1.0-R axis plus Edge value-role ▲ shadow

No post-selection threshold changes are allowed.

## 3. Edge input

Use Registry Issue #572/run `34299375131`, ACTIVE only.

For each target date, produce leakage-safe `edge_matches.jsonl` from target pre-race data using the common Edge matcher path. Store/freeze provenance and SHA-256.

Do not use target SED/HJC/final odds/final popularity before prediction freeze.

## 4. Prediction freeze payload

Freeze, per race:

- race identity
- v0.2 top five and Good values
- each top-five horse's PerformanceEdgeTier and family votes
- v1.0-R marks
- ValueEdgeTier
- v1.0-V marks
- confidence
- Edge IDs selected for explanation
- source/provenance hashes

Commit the freeze before requesting HJC.

## 5. Primary settlement

### Predictive layer

Compare v0.2 vs v1.0-R:

- ◎ win/top2/top3
- ◎ win return
- changed-◎ head-to-head
- Q2 hit/return
- changed-mark race diagnostics

### Value-role layer

Compare v1.0-R vs v1.0-V:

- changed-▲ quinella gains/losses
- Q2 hit/return
- ◎-▲ wide
- payout concentration

Secondary diagnostics: Q4, Trio A6/B5, results by PerformanceEdgeTier and ValueEdgeTier.

## 6. Decision rule

One three-day block cannot promote v1.0.

- promising predictive result -> repeat v1.0-R unchanged on a second untouched block;
- promising value-role result -> repeat v1.0-V unchanged on a second untouched block;
- near-zero changes -> inspect coverage/family distribution rather than loosening weights from settled outcomes;
- material degradation -> retire/rethink the aggregation rather than micro-tune `0.02` on the settled block.
