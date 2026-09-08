# JRDB Edge Registry Phase1 v0.1

## 1. Purpose

`JRDB Edge Registry` is a persistent statistical knowledge layer built from the long-term JRDB history. It stores reusable, machine-verifiable conditions such as course bias, pedigree fit, condition changes, and human combinations for three consumers:

- PWA newspaper: concise `EDGE MEMO` display
- RaceNote/GPT: pre-race supporting or opposing evidence
- PWA independent index: candidate information for the existing `Edge` layer

It is **not** a replacement for Raw, Canonical, Analysis Lite, Stats Mart, RunPerf, Ability, or RaceNote. JRDB source data remains the source truth; the Registry is a derived research asset.

## 2. Boundary with the existing PWA index

The existing index design separates `Ability / Edge / Value`. This project keeps that boundary.

- `Performance signal`: whether the factor is associated with better/worse performance than an appropriate parent baseline.
- `Value signal`: whether realized betting return is better/worse than the market after sample/robustness gates.
- Registry `Edge` records may contain either or both signals.
- Popularity/odds are label/evaluation information only and are not allowed into the pre-race Performance input.
- Registry statistics are not automatically added to the index score in Phase1. Index integration is a later addition test.

## 3. Phase1 completion definition

Phase1 is complete when the following reproducible path exists:

```text
JRDB longitudinal source
  -> Edge Feature Mart (1 race x 1 runner)
  -> canonical candidate templates
  -> factor-specific temporal validation
  -> Edge Registry SQLite
  -> active JSONL / audit CSV
  -> pre-race Edge Matcher output
```

The first implementation package freezes the temporal validation contract and the Registry schema. Discovery execution, mart builder, and matcher are subsequent Phase1 packages under this contract.

## 4. Leakage contract

A condition must be decidable before the target race starts.

Allowed as condition inputs:

- current BAC/KYI pre-race facts
- current pre-race pedigree/profile facts
- previous races reachable from KYI previous-result links
- historical aggregates with `as_of_exclusive = target_date`

Forbidden as condition inputs:

- target-race finish/result
- target-race final odds/popularity
- target-race win/place payout
- target-race actual track result context when unavailable pre-race
- any later race/result

The forbidden fields may be used only as evaluation labels.

## 5. Candidate complexity

Phase1 uses:

```text
one Anchor + up to two Modifiers
```

Examples:

- sire + right turn + 1600m
- course + outer frame
- sire + distance extension
- trainer + jockey

Unbounded arbitrary intersections are prohibited. Canonical buckets are defined before discovery and may only be changed by a version bump.

## 6. Temporal validation classes

A single fixed 2010-2025 split is not the universal rule. Each candidate is routed by factor nature.

### STRUCTURAL

Typical factors: venue/course/surface/distance/turn/frame structure.

Validation: several calendar blocks, minimum sample in each block, and direction stability across blocks. Long-run aggregate ROI alone is insufficient.

### LIFECYCLE

Typical factors: established sire / sire line / broodmare-sire factors.

Validation: split the factor's actual observed lifecycle into relative periods. A sire with ten observed years and a sire with three observed years are not forced through the same calendar cutoffs.

### DYNAMIC

Typical factors: jockey, trainer, jockey x trainer.

Validation: fixed rolling windows. Current form and decay matter more than a ten-year average. Records have mandatory review cadence and expiry.

### EMERGING

Typical factors: new sire, rookie/young jockey, newly formed human combination.

Validation: `WATCH -> PROVISIONAL -> eligible for mature class` as samples accumulate. Unique horses/races and concentration controls are required so one exceptional horse or payout cannot create an Edge.

## 7. Policy versioning

Thresholds are code/data contracts, not numbers adjusted after inspecting attractive ROI.

Policy catalog:

`config/jrdb_edge_validation_policies_v0_1.json`

Any threshold change requires a policy version bump and revalidation. Previous validation events remain in the Registry audit trail.

Initial thresholds are conservative Phase1 defaults. A later distribution audit may propose v0.2, but v0.1 results must not be silently recomputed under changed gates.

## 8. Policy routing

Policy selection is based primarily on the temporal nature of the **Anchor**.

Examples:

```text
COURSE / course anchor -> STRUCTURAL
PEDIGREE / mature sire -> LIFECYCLE
PEDIGREE / young or low-sample sire -> EMERGING
HUMAN / established jockey -> DYNAMIC
HUMAN / low-sample jockey-trainer pair -> EMERGING
```

A PEDIGREE family record can therefore move from EMERGING to LIFECYCLE as data accumulates. A HUMAN record can move from EMERGING to DYNAMIC.

## 9. Registry state machine

```text
WATCH
  -> PROVISIONAL
  -> ACTIVE
  -> REVIEW_DUE
  -> ACTIVE or DECAYING
  -> EXPIRED / RETIRED
```

`REJECTED` is kept for candidates that fail domain/robustness gates. Historical records are not deleted merely because an Edge has expired.

## 10. Positive and negative Edge

Negative Edge is not defined as `ROI < 100%`. Because takeout makes sub-100% common, a negative signal requires persistent underperformance relative to an appropriate parent/baseline and the same temporal robustness gates.

This permits the Registry to support both:

- positive adjustment / buy evidence
- negative adjustment / caution evidence

without treating ordinary market loss as a special disadvantage.

## 11. Robustness fields

Every promoted candidate must retain enough evidence to detect lucky outliers:

- sample_n
- unique_horses
- unique_races
- win/place rate
- win/place ROI
- parent/baseline rates
- performance lift
- largest return share
- top-3 return share
- largest horse sample share
- per-segment/per-window direction

Bootstrap/confidence calculations are planned for the validator package; the schema leaves room in `metrics_json` without changing core identities.

## 12. Storage contract

Drive stores generated large assets; Git stores source, schema, config, and reproducibility contracts.

Planned generated artifacts:

```text
JRDB/edge-registry/
  edge_registry.sqlite
  edge_registry_active.jsonl
  edge_registry_active.csv
  manifest.json
  audit/
```

GPT/RaceNote/PWA should consume the active projection or a matcher result, not load the entire historical Registry into prompt context.

## 13. Phase1 implementation order

1. Freeze validation policies and Registry schema.
2. Build leakage-safe Edge Feature Mart from the longitudinal index source.
3. Freeze canonical condition buckets and candidate templates.
4. Implement STRUCTURAL / LIFECYCLE / DYNAMIC / EMERGING validators.
5. Generate Registry + JSONL/CSV projections.
6. Implement pre-race matcher.
7. Shadow-run during 2026 without automatic index scoring.
8. After shadow evidence, define index/RaceNote/PWA integration contracts.
