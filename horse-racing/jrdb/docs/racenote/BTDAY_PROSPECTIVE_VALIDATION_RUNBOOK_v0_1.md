# RaceNote BTDAY Prospective Validation Runbook v0.1

Status: **ACTIVE FOR NEW UNUSED BTDAYs — v0.4.5 CANDIDATE ONLY**
Date: 2026-10-04

## 1. Cohorts

Fixed comparison cohorts remain immutable:

- v0.4.2 historical baseline: BTDAY-0023 through BTDAY-0032 / 336R
- v0.4.3 prospective: BTDAY-0036, 0037, 0040, 0041 / 132R
- v0.4.4 prospective: completed clean-blind v0.4.4 BTDAYs only
- v0.4.5: new unused clean-blind BTDAYs selected after this activation

BTDAY-0038 and BTDAY-0039 remain excluded.

Do not rerun an old version on the same new day. The production Forecast
pointer remains unchanged pending explicit promotion.

## 2. Prediction contract

Read:

- `FORECAST_HUMAN_CONTEXT_READER_v0_4_5_CANDIDATE.md`
- `FORECAST_HUMAN_CONTEXT_READER_v0_4_4_CANDIDATE.md`
- `FORECAST_REASONING_MECHANICAL_BOUNDARY_v0_1.md`
- `FORECAST_READER_FACING_PROSE_v0_1.md`

v0.4.5 inherits v0.4.4 prediction semantics unchanged.

The model still reads the full clean information for every horse, creates the
race model, four ordinary mainline cases, independent ▲, hierarchy review,
single-shot promotion review, provisional-△2 Coverage review, five final marks
and reader-facing prose.

## 3. DAY PREP and clean binding

Use the ordinary deterministic DAY PREP path and RRDB v0.3.

Bind a clean immutable Reader before model judgment:

```sh
python horse-racing/jrdb/src/racenote_prepare_forecast_input.py \
  --day-prep-root "$DAY_PREP" \
  --output-root "$FORECAST_PREP" \
  --selection-id "$BTDAY_ID" \
  --date "$TARGET_DATE" \
  --main-sha "$MAIN_SHA"
```

Require market blind, result unopened, full race count and manifest hash PASS.

Never expose the lossless market-bearing DAY PREP Reader to the prediction
context after clean binding.

## 4. Lossless Reader chunks

Immediately chunk the clean Readers:

```sh
python horse-racing/jrdb/src/racenote_chunk_clean_readers_v045.py \
  --prep-root "$FORECAST_PREP" \
  --output-root "$WORKING/reader_chunks"
```

Require top manifest `status=PASS`.

The chunks are the ordinary transport unit for model reading. They are not
summaries. All original clean Reader fields must survive semantic reassembly.

Do not fall back to one-horse-at-a-time reads in normal execution.

## 5. Race-by-race Decision Core

Author one race at a time using
`schema/racenote_decision_core_v0_4_5.json`.

The model authors only substantive predictive choices:

- race model;
- five pre-Coverage boundary marks;
- four mainline cases;
- independent ▲ case;
- RRDB use/review;
- hierarchy changed flag and reason only when changed;
- single-shot promotion flag and reason only when changed;
- Coverage shortlist/challenger/comparisons/verdict/reason;
- five final marks;
- mark reason and reader-facing prose.

The model does **not** author deterministic audit derivatives such as
unmarked-count, Coverage-changed, change-attribution or horse-name binding.

## 6. One-race checkpoint

After each race Decision Core:

```sh
python horse-racing/jrdb/src/racenote_checkpoint_authored_v045.py \
  --prep-root "$FORECAST_PREP" \
  --chunks-root "$WORKING/reader_chunks" \
  --decision "$WORKING/current_decision.json" \
  --output-root "$WORKING/authored"
```

A successful checkpoint is immutable.

The checkpoint verifies Reader/chunk identity, roster and five-mark invariants,
▲ identity, mainline completeness, RRDB reference shape, Coverage
KEEP/SWAP/NO_ELIGIBLE invariants and prose minimum structure.

It does not choose or rewrite horses.

### Normal interruption

If execution ends before the card is complete and all completed races are
checkpointed:

- status is `IN_PROGRESS_CHECKPOINTED`;
- report completed/remaining count;
- preserve all checkpoint files;
- next execution starts from the first missing race;
- do not reread or regenerate completed races.

This is a valid recoverable state, not an invariant failure.

## 7. Complete-card materialization

Only when `checkpoint_manifest.json` is
`COMPLETE_READY_TO_FREEZE`:

```sh
python horse-racing/jrdb/src/racenote_bind_checkpoints_v045.py \
  --prep-root "$FORECAST_PREP" \
  --checkpoints-root "$WORKING/authored" \
  --output "$WORKING/prepared_v045.json" \
  --selection-id "$BTDAY_ID" \
  --date "$TARGET_DATE" \
  --main-sha "$MAIN_SHA"
```

The binder may only derive deterministic metadata:

- horse names from Reader horse numbers;
- unmarked count;
- Coverage changed boolean;
- change attribution;
- RRDB source-run metadata.

It must not select horses, change verdicts or write new predictive prose.

## 8. Preflight, Freeze and Validator

```sh
python horse-racing/jrdb/src/racenote_freeze_prepared_forecast.py \
  --prep-root "$FORECAST_PREP" \
  --prepared-records "$WORKING/prepared_v045.json" \
  --output-root "$FROZEN_V045" \
  --selection-id "$BTDAY_ID" \
  --date "$TARGET_DATE" \
  --main-sha "$MAIN_SHA" \
  --logic-version RaceNote-Human-Context-Reader-0.4.5-candidate \
  --preflight-only

python horse-racing/jrdb/src/racenote_freeze_prepared_forecast.py \
  --prep-root "$FORECAST_PREP" \
  --prepared-records "$WORKING/prepared_v045.json" \
  --output-root "$FROZEN_V045" \
  --selection-id "$BTDAY_ID" \
  --date "$TARGET_DATE" \
  --main-sha "$MAIN_SHA" \
  --logic-version RaceNote-Human-Context-Reader-0.4.5-candidate

python horse-racing/jrdb/src/validate_racenote_forecast_human_context.py \
  --records "$FROZEN_V045/day_merge/forecast_${COMPACT_DATE}_all.json" \
  --output "$FROZEN_V045/day_merge/validator.json"
```

Final success requires:

- complete race-key equality;
- market blind and result unopened;
- Reader and chunk hashes fixed;
- all expected checkpoint hashes present;
- v0.4.5 materialized record invariants;
- Freeze PASS;
- Human-Context Validator PASS.

## 9. Working-state interpretation

Use these states:

- `IN_PROGRESS_CHECKPOINTED`: valid partial authored day; resume later
- `COMPLETE_READY_TO_FREEZE`: all race checkpoints exist
- `FROZEN_CLEAN_BLIND`: final successful clean-blind day
- `FAILED_INVARIANT`: a deterministic integrity gate failed

A resource/token stop is not `FAILED_INVARIANT` when valid checkpoints exist.

## 10. Git archival

Only final Frozen assets belong in the canonical immutable BTDAY archive.

Working checkpoints may be retained in an explicit working/recovery path when
needed, but they must not be mistaken for Frozen forecasts.

Use the existing archive staging path after Validator PASS. Ensure it accepts
the v0.4.5 Frozen root and read back the merged record count and semantic
prediction hashes.

## 11. Evaluation

Continue established prediction metrics and v0.4.4 Coverage diagnostics.

Additionally measure v0.4.5 execution reliability:

- chunk semantic-reassembly failures;
- completed-race checkpoint rate;
- completed races regenerated after interruption;
- lost authored races after interruption;
- normal one-horse-at-a-time Reader reads;
- complete-card authoring success rate;
- number of turns required per BTDAY.

The objective is prediction-quality preservation plus substantially improved
execution stability.
