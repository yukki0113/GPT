# RaceNote Forecast Human-Context Reader v0.4.6 Candidate

Status: **UNIFIED PROSPECTIVE CANDIDATE — NOT PRODUCTION**  
Date: 2026-10-04  
Logic id: `RaceNote-Human-Context-Reader-0.4.6-candidate`  
Execution contract: `RACENOTE_EXECUTION_V0.4.6`  
RRDB: `rrdb-recommendation-signals-v0.3`

## 1. Why v0.4.6 exists

v0.4.6 is a clean rewrite of the Human-Context prediction contract.

v0.4.2–0.4.5 established several useful ideas: read the whole field, keep ▲
distinct from ordinary rank 3, protect the clean-blind boundary, inspect the
fifth-mark boundary, and separate deterministic packaging from model judgment.

They also accumulated too many procedural layers. By v0.4.5 the model was
asked to reason about the race while simultaneously tracking hierarchy passes,
promotion gates, Coverage state, chunk state, checkpoint state and audit
fields. That made the operating procedure itself compete with prediction.

v0.4.6 keeps the useful prediction ideas but expresses them as one coherent
decision instead of a sequence of passes.

## 2. Three invariants

Everything in v0.4.6 serves exactly three invariants.

### A. Evidence completeness

For each race, read the complete market-blind clean Reader for every runner.
Do not predict from a shortened summary that omits Reader evidence.

How the runtime transports a large Reader is an implementation detail. There
is no mandatory chunk workflow and no one-horse-at-a-time ritual.

### B. Human-context judgment

Predict from the race as a whole. Do not reduce the field to a fixed numeric
score, fixed weights, popularity, odds or a mechanical signal count.

### C. Clean freeze

Target result and target-day market remain unopened until the complete
prediction card has passed deterministic validation and Freeze.

These are the governing rules. Other behavior should be derived from them
rather than added as independent prohibitions.

## 3. One-race judgment

After reading the whole race, make one integrated decision:

1. State the race model: what is likely to decide the race.
2. Choose four ordinary support/mainline horses: ◎, ○, △1, △2.
3. Choose ▲ independently as the best asymmetric single-shot case.
4. Before finalizing △2, compare it with the strongest excluded alternative.
5. Finalize exactly five unique marks: ◎ ○ ▲ △1 △2.
6. Write one concise reader-facing explanation.

There is no separate hierarchy pass, ▲ promotion pass or Coverage scan pass.
Their useful intent is already contained in steps 2–4.

### ◎

◎ is the horse with the clearest win route under the authored race model, not
merely the horse with the largest quantity of positive evidence.

### ○ / △1 / △2

These are ordinary support roles. Their ordering should reflect the race model,
directly transferable form, class/ability and relevant contextual evidence.

### ▲

▲ is selected independently from the ordinary support order. It represents
the best credible asymmetric win/upset route. It is not generic rank 3.

### Fifth-mark boundary

Before finalizing △2, ask one question:

> Is there an excluded horse I would rather own than this △2 under today's
> race model and transferable evidence?

Record only the closest excluded alternative, or null when there is no close
alternative. The final △2 is the model's answer to that comparison.

This is not a second field rerank and there is no KEEP/SWAP state machine.

## 4. RRDB

RRDB is contextual evidence inside the same race reading.

Use it when it materially changes interpretation of recent form,
repeatability, counter-evidence or hidden strength. It is never an additive
vote and never automatically changes a mark.

The Decision Core records only RRDB horses that materially influenced the
decision. The binder supplies source metadata mechanically.

## 5. Compact Decision Core

The model authors one compact object per race:

```json
{
  "venue": "東京",
  "race_no": 1,
  "race_model": "...",
  "marks": [5, 8, 11, 4, 12],
  "mainline_cases": [
    {"horse_no": 5, "case": "..."},
    {"horse_no": 8, "case": "..."},
    {"horse_no": 4, "case": "..."},
    {"horse_no": 12, "case": "..."}
  ],
  "single_shot_case": {"horse_no": 11, "case": "..."},
  "boundary_review": {
    "alternative_horse_no": 6,
    "reason": "..."
  },
  "rrdb_refs": [
    {"horse_no": 5, "decision_role": "SUPPORT_REPEATABILITY"}
  ],
  "reader_facing_reason": "..."
}
```

The first, second, third, fourth and fifth entries of `marks` are
◎, ○, ▲, △1 and △2.

The model does not author derived audit facts, horse names, hashes, workflow
states or boilerplate review flags.

## 6. Day execution

Normal execution is deliberately simple:

```text
DAY PREP
  -> clean market-blind Reader bind
  -> read one venue continuously
  -> author that venue's Decision Cores
  -> save one immutable venue batch
  -> immediately continue to the next venue
  -> bind all venue batches into full records
  -> validate
  -> Freeze
  -> archive / render
```

A 36-race / three-venue day therefore normally has three recovery writes, not
36 per-race workflow cycles.

Saving a venue batch is not a conversational stop. After a successful save,
continue automatically while execution capacity remains.

## 7. Recovery is separate from normal prediction

Recovery exists only to avoid losing completed work.

If execution actually ends after one or more venue batches were saved, the
next execution:

1. reads the batch manifest;
2. treats saved venue decisions as immutable pre-result work;
3. resumes from the first unsaved venue.

It does not re-predict completed venues.

A recovery boundary never asks the user for permission merely because a batch
was saved. User input is needed only for a genuine unresolved asset,
integrity failure, or a new instruction.

## 8. Deterministic responsibilities

Modules may:

- verify clean Reader identities and hashes;
- bind horse number to horse name;
- verify marks and cited horses belong to the race;
- attach RRDB source metadata already present in Reader;
- compute semantic hashes;
- verify complete card coverage;
- package, validate, Freeze and render.

Modules must not:

- choose marks;
- choose the boundary alternative;
- invent a race model;
- invent a case for a horse;
- write or rewrite reader-facing prediction prose.

## 9. Research interpretation

v0.4.6 is a new prospective cohort because its authoring context is materially
simpler than v0.4.4/0.4.5.

Its purpose is not to add a new predictive feature. The target is to recover
the fast research cadence of the earlier Human-Context versions while
retaining the useful fifth-mark and ▲ discipline learned later.

Evaluate the ordinary prediction/ROI metrics plus:

- boundary alternative present rate;
- final △2 versus recorded excluded alternative outcome;
- ▲ role performance;
- full-day completion rate;
- venue-batch recovery count;
- number of prediction-tool cycles per day.

## 10. Mental model

The entire v0.4.6 operating rule is:

> Read the complete clean race, understand how it is likely to be decided,
> choose four ordinary support horses and one independent ▲, sanity-check the
> fifth horse against the best excluded alternative, save decisions in
> practical batches, and Freeze the full card before opening results.

If an implementation detail makes that sentence harder to follow, the
implementation detail should be simplified rather than adding another rule.
