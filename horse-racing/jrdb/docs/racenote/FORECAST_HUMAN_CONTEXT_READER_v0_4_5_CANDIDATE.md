# RaceNote Forecast Human-Context Reader v0.4.5 Candidate

Status: **EXECUTION-STABLE PROSPECTIVE CANDIDATE — NOT PRODUCTION**
Date: 2026-10-04
Logic id: `RaceNote-Human-Context-Reader-0.4.5-candidate`
Prediction semantics: **inherit v0.4.4**
Execution contract: `RACENOTE_EXECUTION_V0.4.5`
RRDB: `rrdb-recommendation-signals-v0.3`

## 1. Purpose

v0.4.5 is not a prediction-quality retune.

Its purpose is to preserve the v0.4.4 five-horse Human-Context judgment while
removing avoidable LLM execution load and making interrupted day authoring
recoverable without re-predicting completed races.

The principal changes are execution changes:

1. lossless semantic Reader chunking;
2. compact model-authored Decision Core;
3. immutable one-race checkpoints;
4. deterministic audit materialization;
5. resume from the first missing race.

## 2. Prediction semantics inherited unchanged

The model still:

- reads every horse from the full clean Reader information;
- forms a race model;
- compares four ordinary mainline horses;
- identifies ▲ independently;
- checks hierarchy consistency;
- checks the ▲ promotion gate;
- performs the narrow provisional-△2 Coverage boundary comparison;
- returns exactly ◎ ○ ▲ △1 △2.

Coverage remains `KEEP / SWAP / NO_ELIGIBLE_CHALLENGER`.

No score, fixed weight, popularity/odds rule, sixth horse, automatic RRDB
promotion, automatic ▲ promotion, broad outsider hunting, or forced swap is
introduced.

The known research question about day-to-day SWAP-rate stability is deliberately
not retuned in v0.4.5. Mixing a prediction-rule change with an execution change
would make attribution impossible.

## 3. Clean input and lossless chunking

The market-stripped clean Reader remains the authoritative model input.

`racenote_chunk_clean_readers_v045.py` may split that Reader for transport,
but must not summarize or omit fields. Horse objects are split only at horse
boundaries. Race-level context is stored separately.

Every race chunk set records:

- source Reader file and SHA-256;
- source semantic SHA-256;
- chunk index / count;
- horse numbers;
- per-chunk SHA-256;
- reassembled semantic SHA-256.

Reassembly must be semantically identical to the source clean Reader or the
chunker fails closed.

A shortened projection is not a substitute for these chunks.

## 4. Model-authored Decision Core

The model authors only prediction-relevant judgments and prose.

Required conceptual shape:

```json
{
  "venue": "東京",
  "race_no": 1,
  "race_model": "...",
  "boundary_marks": [5, 8, 11, 4, 12],
  "mainline_cases": [
    {"horse_no": 5, "case": "..."},
    {"horse_no": 8, "case": "..."},
    {"horse_no": 4, "case": "..."},
    {"horse_no": 12, "case": "..."}
  ],
  "single_shot_case": {"horse_no": 11, "case": "..."},
  "mark_reason": "...",
  "rrdb_evidence": {
    "available": true,
    "reviewed": true,
    "used_in_decision": false,
    "horse_refs": [],
    "reason_not_used": "..."
  },
  "hierarchy": {"changed": false},
  "single_shot_promotion": {"promoted": false},
  "coverage": {
    "shortlist": [6],
    "challenger": 6,
    "direct_condition": "DELTA2_STRONGER",
    "ability": "ROUGHLY_EQUAL",
    "race_model": "ROUGHLY_EQUAL",
    "verdict": "KEEP",
    "reason": "..."
  },
  "final_marks": [5, 8, 11, 4, 12],
  "reader_facing_reason": "..."
}
```

`boundary_marks` are the five marks immediately before the Coverage swap
decision. Coverage may directly modify only the fifth mark.

When hierarchy or single-shot promotion does not change the marks, the model
does not write a boilerplate reason. A substantive reason is required only
when the corresponding change flag is true.

## 5. What the model no longer authors

The model does not manually author deterministic audit facts such as:

- unmarked horse count;
- Coverage changed boolean;
- change attribution;
- horse names derived from horse numbers;
- whether challenger belongs to shortlist;
- whether KEEP preserves provisional △2;
- whether SWAP makes challenger the final △2;
- RRDB source-run metadata already present in the Reader.

These are validated or materialized mechanically.

This does not automate horse selection. The model must still choose every mark,
shortlist, challenger, comparison label, verdict, substantive reason and
reader-facing prose.

## 6. One-race immutable checkpoint

After one race Decision Core is authored, run
`racenote_checkpoint_authored_v045.py`.

The checkpoint validates:

- clean Reader identity;
- source and chunk hashes;
- roster membership;
- five unique marks;
- independent ▲ identity;
- mainline completeness;
- RRDB reference structure;
- Coverage shortlist/challenger/verdict invariants;
- Coverage-only fifth-mark mutation;
- reader-facing prose minimum structure.

It does not select or rewrite any predictive field.

A checkpoint file is append-only. Existing race checkpoints are never
overwritten. Intentional revision requires a separate revision path and must
not silently replace the original pre-result checkpoint.

## 7. Resumable day execution

`checkpoint_manifest.json` is the authoritative progress state.

Allowed working states:

- `IN_PROGRESS_CHECKPOINTED`
- `COMPLETE_READY_TO_FREEZE`

If execution stops after N races, the next run reads the manifest and resumes
from the first missing race. Completed race Readers are not reread and
completed predictions are not regenerated.

A resource-limit stop with valid checkpoints is not a failed prediction run.

## 8. Deterministic audit materialization

When every expected race is checkpointed,
`racenote_bind_checkpoints_v045.py` materializes full research records.

It deterministically derives:

- horse names;
- `unmarked_count = field_size - 5`;
- `coverage_changed = verdict == SWAP`;
- `change_attribution`;
- final RRDB source metadata.

The final record uses:

- schema `RaceNote-Forecast-Research-Record-0.4.5`;
- prediction semantics `INHERIT_V0.4.4`;
- execution contract `RACENOTE_EXECUTION_V0.4.5`.

No new predictive prose is generated by the binder.

## 9. Freeze and final validation

Only a `COMPLETE_READY_TO_FREEZE` checkpoint set can be materialized.

The complete materialized card then passes the ordinary strict Freeze
preflight, Freeze packager and Human-Context Validator.

Final working status becomes:

- `FROZEN_CLEAN_BLIND`, or
- `FAILED_INVARIANT` when a deterministic gate actually fails.

The target result and target-day market remain unopened through Freeze.

## 10. Research interpretation

v0.4.5 must be tracked as its own prospective cohort because input
serialization and authoring contract changed, even though prediction semantics
are intentionally inherited from v0.4.4.

Primary evaluation goals are:

### Prediction-quality preservation

- ◎ win / Top2 / Top3;
- winner in five;
- all Top3 in five;
- established ROI set;
- Coverage KEEP / SWAP / NO_ELIGIBLE rates;
- net Coverage gain;
- ▲ role integrity.

### Execution reliability

- full clean Reader coverage = 100%;
- chunk semantic reconstruction failures = 0;
- checkpoint rate = 100% for completed races;
- completed-race regeneration after interruption = 0;
- loss of authored races after interruption = 0;
- ordinary one-horse-at-a-time Reader retrieval = 0;
- deterministic audit fields manually authored by the model = 0.

## 11. Summary

```text
v0.4.4 prediction semantics
  + lossless Reader chunks
  + compact Decision Core
  + immutable 1R checkpoints
  + deterministic audit materialization
  + resume from first missing race
  = v0.4.5 candidate
```

The design principle is: **remove non-predictive work from the LLM before
removing predictive evidence from the Reader.**
