# JRDB Feature Audit — Stage C Instruction

Status: **READY FOR EXECUTION**  
Date: 2026-10-05  
Research lane: RaceNote 0.5.x candidate research  
Depends on: Stage B audit ACCEPT  
Active prediction cohort: v0.4.6 unchanged

## Objective

Turn the accepted Stage B findings into a conservative Reader-information
design proposal.

Stage C does **not** build a new score and does **not** modify production
prediction behavior.

Primary question:

> Which JRDB fields should be emphasized, de-duplicated, demoted to context, or
> hidden from a future 0.5.x Reader so that the model sees less redundant
> evidence without losing materially distinct racing information?

## Canonical Stage B evidence

Use:

- `audits/20261005_JRDB_FEATURE_AUDIT_STAGE_B_AUDIT.md`
- `results/stage_b_2023_2025/ARTIFACT_MANIFEST.md`
- the accepted Stage B report and machine outputs when available.

Do not re-open 2026 BTDAY outcomes for this design.

Do not extend the historical window to five years.

## Design principles

### 1. Preserve Human-Context judgment

Do not replace the current approach with fixed weights, a composite score, or
mechanical feature voting.

0.5.x should improve **what the model sees and how redundant evidence is
presented**, not dictate the final marks numerically.

### 2. Remove duplicate cognitive weight, not provenance

When two fields carry effectively the same ordering, the Reader should not
present them as independent confirmations.

Examples requiring explicit treatment:

- CHA total clock index vs CYB training index;
- jockey index vs jockey expected top-two rate;
- IDM vs total index;
- pace numeric index vs provider-supplied corresponding rank;
- projected position order vs projected margin.

For each pair/group decide whether to:

- retain one primary representation;
- retain the second only as provenance/detail;
- combine visually under one evidence block;
- keep both only if a materially different semantic role is documented.

Do not delete source fields from canonical data storage merely because the
Reader hides or groups them.

### 3. Distinguish headline evidence from context

Candidate Reader tiers:

- **PRIMARY** — high-information, stable, broadly useful evidence;
- **SECONDARY** — materially distinct but weaker or more conditional evidence;
- **CONTEXT_ONLY** — available when a race-specific reason makes it relevant;
- **REDUNDANT_HIDDEN** — duplicate representation not normally shown to the model;
- **INSUFFICIENT_COVERAGE** — not suitable for general Reader presentation.

These are information-presentation tiers, not prediction weights.

## Required Stage C decisions

At minimum address the following families.

### Ability / provider composites

- IDM
- total index
- information index
- longshot index
- JRDB marks corresponding to those indices

Determine whether the Reader currently gives too much cognitive weight to
multiple strongly correlated provider summaries.

Do not assume the highest raw win-rate field should become the sole primary
ability feature.

### Jockey / stable

- jockey index
- jockey expected top-two rate
- stable index
- related JRDB marks

The Stage B audit found near-identity between jockey index and expected top-two
rate. Propose one clear presentation rule.

### Pace / projected position

- front / pace / late / position numeric indices
- supplied ranks
- projected mid / last3f / finish order and margin
- start index / late-break rate

Prefer the representation that preserves useful racing interpretation while
avoiding duplicate rank/order information.

Do not promote start index or late-break rate to headline status solely because
they exist.

### Training / condition

Keep KYI / CHA / CYB source semantics visible where genuinely distinct.

Explicitly handle:

- KYI training index;
- CHA total clock index;
- CHA last clock index;
- CYB training index;
- CYB condition index;
- improvement / training arrow / stable evaluation;
- farm information.

Because CHA total clock index and CYB training index were identical in the
three-year sample, they must not appear as independent confirmations in the
future Reader.

### Suitability

Account for substantial missingness in some fit fields.

Do not make reduced-coverage suitability categories mandatory headline
features for every runner.

## Required outputs

Create:

1. a machine-readable Reader feature policy proposal;
2. a Markdown Stage C report;
3. a proposed **0.5.x Reader evidence layout**;
4. a field-by-field mapping from current v0.4.6 exposure to proposed 0.5.x
   presentation;
5. a migration / compatibility note explaining what canonical data remains
   stored even when Reader presentation changes.

Suggested policy columns:

| feature_id | current_v046_state | proposed_tier | display_group | primary_representation | retained_for_provenance | rationale | evidence_reference |
|---|---|---|---|---|---|---|---|

## Reader-layout proposal

The Stage C report should show a concrete example of the future information
shape.

Prefer semantic blocks such as:

```text
ABILITY
  primary provider ability view
  supporting distinct ability context

PACE / POSITION
  interpretable pace evidence
  projected shape without duplicate ranks

TRAINING / CONDITION
  distinct KYI/CHA/CYB evidence
  duplicate representations collapsed

SUITABILITY / CONNECTIONS
  conditional evidence when available
```

This is an information architecture proposal only.

Do not write a new prediction prompt yet unless a minimal example is required
to demonstrate the layout.

## Validation against v0.4.6

Stage C must explicitly identify:

- fields currently visible in v0.4.6 that would disappear from the normal
  0.5.x Reader;
- fields that remain but move to a lower tier;
- fields grouped under one representation;
- fields unchanged;
- any field proposed for stronger prominence.

For every proposed change, state whether it changes:

- information availability;
- information prominence only;
- presentation redundancy only.

This distinction is required for later cohort interpretation.

## Optional simulation

A **structural simulation** is allowed:

- take committed clean Reader examples;
- transform only their presentation according to the proposed policy;
- compare token/field count and retained information.

Do not re-predict the races and do not use race results.

Useful measurements:

- Reader byte/token reduction;
- scalar field count reduction;
- number of duplicate evidence representations removed;
- number of source families still represented.

## Decision at end of Stage C

Choose exactly one:

### DESIGN_0_5_CANDIDATE

The evidence supports a concrete 0.5.x Reader candidate for later clean-blind
testing.

### KEEP_0_4_READER

The practical benefit of pruning/re-prioritization is too small or risks
removing useful context.

### NEED_TARGETED_RESEARCH

A small number of unresolved feature groups require a narrowly scoped follow-up
before designing 0.5.x.

Do not request a broad additional historical sweep.

## Non-goals

Do not:

- modify the active v0.4.6 Reader;
- modify active v0.4.6 prediction logic;
- create fixed numerical weights;
- fit/train a prediction model;
- optimize for historical ROI;
- reopen 2026 BTDAY results;
- add 2021-2022 historical data;
- delete canonical raw/source fields;
- promote 0.5.x to production.

## Acceptance criteria

Stage C is acceptable only if:

- every proposed Reader change is traceable to Stage B evidence;
- redundant information is distinguished from merely correlated but
  semantically distinct information;
- canonical storage is preserved;
- no active v0.4.6 behavior changes;
- a concrete Reader layout is provided;
- the report makes one explicit Stage C decision.
