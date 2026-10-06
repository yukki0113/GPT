# RaceNote 0.5.x Candidate Reader — Stage D Implementation Instruction

Status: **READY FOR EXECUTION**  
Date: 2026-10-06  
Research lane: RaceNote 0.5.x candidate Reader implementation  
Depends on: Stage C decision `DESIGN_0_5_CANDIDATE`  
Production Reader: v0.4.6 unchanged

## Objective

Implement a **parallel, non-production RaceNote 0.5.x candidate Reader** that applies
the accepted Stage C information-architecture policy.

The implementation goal is not to create a new predictor.

The goal is to take the same clean pre-race RaceNote evidence and present it with:

- less duplicate information;
- explicit information priority;
- preserved source provenance;
- preserved missingness;
- preserved Human-Context reasoning freedom.

The active v0.4.6 Reader and prediction semantics must remain untouched.

## Canonical inputs

Read these before implementation:

1. `docs/racenote/research-work/reports/20261006_JRDB_FEATURE_AUDIT_STAGE_C_REPORT.md`
2. `docs/racenote/research-work/results/stage_c/reader_feature_policy_v0_5_candidate.json`
3. `docs/racenote/research-work/results/stage_c/v046_to_v05_reader_mapping.json`
4. `docs/racenote/FORECAST_HUMAN_CONTEXT_READER_v0_4_6_CANDIDATE.md`
5. current RaceNote Reader builder / normalizer / validator implementation
6. Stage B report and audit for evidence references

Treat the 73-entry Stage C policy as authoritative for presentation behavior.

## Version boundary

This stage introduces a **new candidate Reader version** because the information
surface shown to the predictor changes.

Use a clear version identity such as:

`RaceNote-Human-Context-Reader-0.5.0-candidate`

Do not repoint the production/current pointer.

Do not rename v0.4.6.

Do not mutate v0.4.6 files in-place.

## Required architecture

Implement 0.5.x as a separate Reader path with explicit version selection.

Preferred shape:

```text
same clean RaceNote evidence
        |
        +--> v0.4.6 Reader renderer
        |
        +--> v0.5.0 candidate Reader renderer
```

The same normalized source evidence must be usable by both Readers.

Do not fork upstream evidence extraction merely to support 0.5.x unless a
minimal adapter is unavoidable.

## Reader information groups

The 0.5.x normal view should follow the accepted semantic grouping:

### RACE CONTEXT

Race-level clean context already available to v0.4.6.

### RUNNER IDENTITY

Horse / jockey / trainer / stable identity as currently appropriate.

### ABILITY

Normal-view emphasis:

- IDM as PRIMARY
- information index as SECONDARY
- longshot index as SECONDARY/contextual provider view
- JRDB class where applicable
- total index removed from normal duplicate presentation and retained in detail/provenance
- marks shown only as detail/provenance of their parent evidence, not independent confirmations

### PACE / POSITION

Normal-view emphasis:

- late pace index as PRIMARY
- front / pace / position numeric indices as SECONDARY
- provider-supplied corresponding ranks moved to detail/provenance
- projected margins used as normal trajectory representation
- projected order kept in detail/provenance
- lane/start/late-break context only when relevant/populated

### TRAINING / CONDITION

Normal-view emphasis:

- KYI training index as PRIMARY
- CHA last clock index as SECONDARY
- CYB condition index as SECONDARY
- CYB training index as the normal representation of the shared CHA-total/CYB-training evidence
- CHA total clock index retained in detail/provenance
- arrow / improvement / stable evaluation / raw workout / farm / course-count details remain contextual

### SUITABILITY / CONNECTIONS

- fit fields only when populated and race-relevant
- jockey index shown once as connection context
- expected top-two rate moved to detail/provenance
- stable index as secondary connection context
- reduced-coverage suitability must not generate synthetic defaults

## Tier semantics

Implement the Stage C tiers as presentation behavior:

- `PRIMARY`: normal view, visually/structurally prominent
- `SECONDARY`: normal view, clearly subordinate to PRIMARY
- `CONTEXT_ONLY`: only render when populated and relevant; otherwise omit from normal view
- `REDUNDANT_HIDDEN`: omit from normal view, retain in detail/provenance
- `INSUFFICIENT_COVERAGE`: do not present as normal evidence

Do not convert tiers into numerical weights.

## Provenance / detail block

Every normal-view hidden source leaf must remain recoverable from a
detail/provenance structure.

The detail block may be machine-visible but must not be presented as a second
independent vote.

The implementation must retain:

- source family
- source field / Reader path
- raw value where available
- reason hidden/grouped
- primary representation chosen

## Missingness

Preserve missingness exactly.

Do not:

- fill missing suitability with neutral values;
- substitute correlated features;
- infer provider ranks from numeric values when the provider rank is absent;
- synthesize CHA/CYB equality when only one source exists.

When both CHA total clock index and CYB training index are present and differ,
preserve both values and surface a divergence/provenance note rather than
silently collapsing them.

## Structural validation

Before any prediction comparison, create deterministic structural tests.

At minimum test:

1. the candidate Reader can be generated from the same clean evidence as v0.4.6;
2. all 73 policy entries map to implementation behavior;
3. every `REDUNDANT_HIDDEN` feature is absent from normal view and present in provenance/detail when available;
4. no production/market/result fields enter the candidate Reader;
5. missing values are not synthesized;
6. v0.4.6 output remains byte/semantically unchanged for the same fixture;
7. candidate version identity is explicit;
8. no current pointer is changed.

## Structural comparison

Use committed clean Reader fixtures or other repository-safe clean evidence.

For each tested fixture record:

- v0.4.6 byte count;
- v0.5.x byte count;
- approximate token count using one documented tokenizer or deterministic approximation;
- normal-view scalar field count;
- detail/provenance field count;
- number of duplicate representations removed;
- source families represented;
- whether any unique Stage C-required evidence was lost.

Do not open target-race results.

Do not re-predict yet in Stage D.

## Required deliverables

Create at minimum:

### Candidate specification

A new candidate Reader specification under:

`docs/racenote/`

Suggested name:

`FORECAST_HUMAN_CONTEXT_READER_v0_5_0_CANDIDATE.md`

### Machine policy binding

Create a stable implementation binding or schema artifact showing how the Stage C
73-row policy maps into renderer behavior.

### Candidate renderer / transformer

Implement a deterministic renderer/transformer that produces 0.5.x from the same
clean evidence source used by v0.4.6.

Prefer reuse of existing normalization and evidence-loading code.

### Tests

Add deterministic tests for:

- policy coverage
- duplicate suppression
- provenance retention
- missingness
- version separation
- v0.4.6 non-regression

### Stage D report

Create:

`docs/racenote/research-work/reports/20261006_RACENOTE_V05_CANDIDATE_READER_STAGE_D_REPORT.md`

Include:

- implementation paths
- version identity
- policy coverage result
- structural comparison metrics
- tests
- known limitations
- production impact
- exact next-step recommendation

## Decision at end of Stage D

Choose exactly one:

### READY_FOR_CLEAN_BLIND_A_B

Implementation is structurally sound and can proceed to prospective clean-blind
0.4.6 vs 0.5.x prediction comparison.

### REVISE_READER

Structural implementation has problems that should be fixed before any
prediction comparison.

### ABANDON_0_5_CANDIDATE

The candidate information layout loses too much useful context or provides no
meaningful structural benefit.

## Non-goals

Do not:

- change the current production pointer;
- change active v0.4.6 files or semantics;
- use target results, final odds, popularity or payouts;
- train/tune weights;
- re-run Stage B;
- add 2021-2022;
- perform live prediction evaluation yet;
- delete canonical source evidence.

## Commit / PR discipline

This task is not complete with workspace-only changes.

Before completion:

1. commit only Stage D-related files;
2. push a dedicated branch;
3. create a PR against main;
4. return:
   - commit SHA;
   - PR number / URL;
   - Stage D decision;
   - changed file list;
   - test summary;
   - structural reduction summary.

Do not report completion unless durable repository artifacts exist.

## Production impact

Must remain **zero**.

The current v0.4.6 Reader remains the only active prediction Reader until a
later explicit audit and promotion decision.
