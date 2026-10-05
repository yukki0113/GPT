# RaceNote Forecast Human-Context Reader v0.4.6 Candidate

Status: **UNIFIED PROSPECTIVE CANDIDATE — NOT PRODUCTION**  
Date: 2026-10-05  
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

Read the available RRDB context normally, but keep the audit trace sparse.
`rrdb_refs` is not a list of every horse whose RRDB entry was inspected and
not a second copy of the five marks. Record a horse only when RRDB changed or
materially sharpened the interpretation used in the final judgment.

A useful test is:

> If the same mark and the same reasoning would have been written without the
> RRDB evidence, this horse does not need an rrdb_ref.

RRDB remains non-additive and never automatically changes a mark. The binder
only attaches source metadata to model-selected refs.

Reader-facing prose should express the underlying racing observation rather
than naming RRDB, its internal role labels or signal machinery unless the
source name itself is genuinely useful to the reader.

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
prepare request
  -> permanent workflow builds DAY PREP + clean Reader
  -> model reads one venue continuously
  -> commit one authored_decisions/<venue>.json recovery file
  -> immediately continue to the next venue
  -> when all expected venue files exist:
       permanent workflow validates venue batches
       -> bind full records
       -> preflight / Freeze / Validator
       -> archive / render
```

A venue Decision Core file is the recovery point. There is no reason to create
and push an additional intermediate venue-batch artifact while prediction is
still in progress.

The deterministic venue-batch representation remains part of final packaging
and provenance, but it is built once after the complete authored card exists.

Saving an authored venue is not a conversational stop. Continue automatically
while execution capacity remains.

Repository automation:

- `.github/workflows/racenote_btday_v046_prepare.yml`
- `.github/workflows/racenote_btday_v046_finalize.yml`

These permanent workflows replace per-BTDAY temporary workflows in normal
operation.

## 7. Recovery is separate from normal prediction

Recovery exists only to avoid losing completed model judgment.

If execution actually ends after one or more
`authored_decisions/<venue>.json` files were committed, the next execution:

1. reads the clean forecast prep and existing authored venue files;
2. treats those files as immutable pre-result decisions;
3. resumes from the first expected venue without an authored file.

It does not re-predict completed venues.

The finalizer may run after every authored-file commit, but it performs no
packaging until the complete expected venue set exists. Therefore incomplete
cards cause no extra Git artifacts and no user confirmation step.


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
