# RaceNote BTDAY Prospective Validation Runbook v0.1

Status: **ACTIVE FOR NEW UNUSED BTDAYs — v0.4.6 CANDIDATE ONLY**  
Date: 2026-10-04

## 1. Operating principle

v0.4.6 uses one simple prediction loop.

```text
prepare clean day
  -> read complete race
  -> make one integrated five-horse judgment
  -> continue through the venue
  -> save one venue batch
  -> continue automatically
  -> bind full day
  -> validate
  -> Freeze
  -> archive / render
```

Do not recreate the v0.4.4/v0.4.5 sequence of separate hierarchy,
promotion, Coverage, per-race checkpoint and chunk-management passes.

The prediction contract is:
`docs/racenote/FORECAST_HUMAN_CONTEXT_READER_v0_4_6_CANDIDATE.md`.

## 2. Cohorts

Preserve all prior cohorts and exclusions as recorded. New unused BTDAYs after
v0.4.6 activation use v0.4.6 only. Do not create same-day old-version A/B
forecasts.

The production Forecast pointer remains unchanged until a separate promotion
decision.

## 3. Select and prepare the day

Use the current BTDAY pool/history and select one unused eligible day according
to the existing clean-blind selection procedure.

Run the standard deterministic DAY PREP.

Bind the market-stripped forecast input:

```sh
python horse-racing/jrdb/src/racenote_prepare_forecast_input.py \
  --day-prep-root "$DAY_PREP" \
  --output-root "$FORECAST_PREP" \
  --selection-id "$BTDAY_ID" \
  --date "$TARGET_DATE" \
  --main-sha "$MAIN_SHA"
```

Require:

- full expected race count;
- `market_blind=true`;
- `result_opened=false`;
- `target_market_opened=false`;
- clean Reader manifest hash fixed;
- RRDB recommendation contract v0.3.

After this point use only the clean forecast Reader for model judgment.

## 4. Read and predict one venue continuously

Use the clean Reader files directly as the authoritative input.

The runtime may read a large Reader in multiple lossless pieces when required
by tool limits, but this is transport only. There is no required chunk artifact
and no normal one-horse-at-a-time loop.

For each race:

1. read the complete race and all runners;
2. state the race model;
3. choose final ◎ ○ ▲ △1 △2;
4. provide four mainline cases for ◎ ○ △1 △2;
5. provide the independent ▲ case;
6. compare final △2 with the strongest excluded alternative, or record no
   close alternative;
7. cite only materially used RRDB horses;
8. write the reader-facing reason.

Author against:
`schema/racenote_decision_core_v0_4_6.json`.

Do not stop between races for workflow bookkeeping.

## 5. Save the venue batch

When all races in one venue are authored, save them together:

```sh
python horse-racing/jrdb/src/racenote_save_venue_batch_v046.py \
  --prep-root "$FORECAST_PREP" \
  --decisions "$WORKING/current_venue.json" \
  --output-root "$WORKING/venue_batches"
```

The save is a recovery write, not a user-interaction boundary.

After PASS, immediately continue to the next unsaved venue in the same request
while execution capacity remains. Do not ask the user to say "continue" merely
because a venue batch was saved.

Expected normal states:

- `IN_PROGRESS_BATCHED`: one or more venues safely saved;
- `COMPLETE_READY_TO_BIND`: all venues safely saved.

## 6. Recovery

Recovery is used only if execution actually ends before the day is complete.

On the next execution, read
`$WORKING/venue_batches/batch_manifest.json`.

- Existing venue batches are immutable pre-result predictions.
- Do not reread/re-author completed venues.
- Resume with the first venue in `remaining_venues`.

Do not introduce per-race checkpoints as a normal recovery layer.

## 7. Bind the complete day

When the batch manifest is `COMPLETE_READY_TO_BIND`:

```sh
python horse-racing/jrdb/src/racenote_bind_venue_batches_v046.py \
  --prep-root "$FORECAST_PREP" \
  --batches-root "$WORKING/venue_batches" \
  --output "$WORKING/prepared_v046.json" \
  --selection-id "$BTDAY_ID" \
  --date "$TARGET_DATE" \
  --main-sha "$MAIN_SHA"
```

The binder may only attach deterministic identities and source metadata. It
must not choose a horse, change a mark, select the boundary alternative or
write prediction prose.

## 8. Preflight, Freeze and Validator

```sh
python horse-racing/jrdb/src/racenote_freeze_prepared_forecast.py \
  --prep-root "$FORECAST_PREP" \
  --prepared-records "$WORKING/prepared_v046.json" \
  --output-root "$FROZEN_V046" \
  --selection-id "$BTDAY_ID" \
  --date "$TARGET_DATE" \
  --main-sha "$MAIN_SHA" \
  --logic-version RaceNote-Human-Context-Reader-0.4.6-candidate \
  --preflight-only

python horse-racing/jrdb/src/racenote_freeze_prepared_forecast.py \
  --prep-root "$FORECAST_PREP" \
  --prepared-records "$WORKING/prepared_v046.json" \
  --output-root "$FROZEN_V046" \
  --selection-id "$BTDAY_ID" \
  --date "$TARGET_DATE" \
  --main-sha "$MAIN_SHA" \
  --logic-version RaceNote-Human-Context-Reader-0.4.6-candidate

python horse-racing/jrdb/src/validate_racenote_forecast_human_context.py \
  --records "$FROZEN_V046/day_merge/forecast_${COMPACT_DATE}_all.json" \
  --output "$FROZEN_V046/day_merge/validator.json"
```

Only after Freeze and Validator PASS may target results be opened.

## 9. Archive and output

Use the existing BTDAY archive stager after Validator PASS.

Render ordinary reader-facing output only from Frozen records.

Archive evidence should prove:

- clean Reader identity;
- full-card race count;
- v0.4.6 logic/schema;
- prediction semantic hashes;
- target result unopened at Freeze;
- target market unopened at Freeze;
- Validator PASS.

Working venue batches are recovery assets. They are not themselves Frozen
forecasts.

## 10. When execution should stop

Normal batch saves do not stop execution.

Stop only when:

- the full day is Frozen and archived;
- a required source is genuinely unavailable;
- a deterministic integrity gate fails;
- the execution environment actually ends before more work can be performed.

If the environment ends after valid venue batches exist, report the saved
venues and first remaining venue. Do not convert a recoverable partial day into
a request for confirmation after every save.

## 11. Evaluation

Continue the established outcome and ROI metrics.

For v0.4.6 also record:

- rate of races with a close excluded boundary alternative;
- final △2 versus that excluded alternative after results;
- ▲ result profile;
- full-day completion in one execution;
- number of venue recovery writes;
- number of resumed venues;
- number of completed venues re-authored (target: zero).

The primary execution target is to restore rapid prospective iteration without
weakening complete-reader or clean-blind safeguards.
