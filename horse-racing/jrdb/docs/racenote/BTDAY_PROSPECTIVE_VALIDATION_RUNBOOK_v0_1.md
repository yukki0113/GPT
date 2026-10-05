# RaceNote BTDAY Prospective Validation Runbook v0.1

Status: **ACTIVE FOR NEW UNUSED BTDAYs — v0.4.6 CANDIDATE ONLY**  
Date: 2026-10-05

## 1. One operating path

Use this path only:

```text
reserve unused BTDAY
-> commit one prepare request JSON
-> permanent prepare workflow builds clean forecast prep
-> model predicts one venue continuously
-> commit authored_decisions/<venue>.json
-> continue to next venue without waiting
-> when all expected venue files exist:
     permanent finalizer
     -> venue validation/batch materialization
     -> complete-day bind
     -> preflight / Freeze / Validator
     -> archive / render
-> STOP before results
```

Do not reconstruct older v0.4.4/v0.4.5 checkpoint/chunk/Coverage workflows.

Prediction contract:
`FORECAST_HUMAN_CONTEXT_READER_v0_4_6_CANDIDATE.md`.

## 2. Prepare request

Create:

`horse-racing/jrdb/backtests/requests/BTDAY-XXXX.json`

against:

`schema/racenote_btday_v046_request.json`.

Required request information:

- selection id;
- target date;
- target-date PACI Drive file id;
- Analysis artifact run id and artifact name;
- Analysis generation id.

Current RRDB and legacy Next-Watch file ids are read from
`config/racenote_forecast_logic_current.json` unless explicitly overridden.

The permanent workflow
`.github/workflows/racenote_btday_v046_prepare.yml`
then performs DAY PREP and the clean market-stripped bind.

A successful prepare must leave:

- DAY PREP status PASS;
- full built race count;
- `market_blind=true`;
- `target_market_opened=false`;
- `result_opened=false`;
- clean Reader manifest hash fixed;
- RRDB v0.3 contract.

No temporary per-BTDAY workflow is part of the normal route.

## 3. Predict one venue continuously

The authoritative model input is the clean Reader under
`forecast_prep/reader/`.

Read the complete information for every runner in the race. Tool transport may
split large content losslessly, but no chunk artifact or one-horse loop is a
prediction requirement.

For each race make the single integrated v0.4.6 judgment:

1. race model;
2. final ◎ ○ ▲ △1 △2;
3. four ordinary mainline cases for ◎ ○ △1 △2;
4. independent ▲ case;
5. final △2 versus the closest excluded alternative, or null if none is close;
6. sparse RRDB refs only where RRDB materially changed/sharpened the judgment;
7. one natural reader-facing paragraph.

The comment is racing analysis, not serialized mark metadata. Internal source
names such as RRDB/IDM/index labels should normally be translated into the
underlying racing observation.

## 4. Save recovery work

After completing a venue, commit exactly one model-authored file:

`authored_decisions/<venue>.json`

containing that venue's complete Decision Core array.

That Git file is the recovery point.

After committing it:

- do not ask the user to continue;
- do not create an extra checkpoint;
- do not re-read or re-author the completed venue;
- continue to the next missing venue while execution capacity remains.

If execution genuinely ends, the next execution resumes from the first expected
venue without an authored file.

## 5. Automatic finalization

The permanent workflow
`.github/workflows/racenote_btday_v046_finalize.yml`
runs when an authored venue file is committed.

If the authored venue set is incomplete, it exits successfully without
creating packaging artifacts.

When all expected venues are present, it performs once:

```text
validate each authored venue
-> build deterministic venue_batches
-> bind complete v0.4.6 records
-> Freeze preflight
-> Freeze
-> Human-Context Validator
-> clean-blind archive
-> commit final artifacts
```

The finalizer never chooses a horse or writes prediction prose.

## 6. Freeze boundary

Until final Freeze succeeds, do not open:

- target result;
- payouts;
- final odds/popularity;
- result joins;
- post-race evaluation.

Target-day market stays outside the model input after clean binding.

Result/ROI analysis is a separate post-Freeze operation.

## 7. Validation expectations

Final success requires:

- expected race roster exactly complete;
- five unique marks per race;
- mainline exactly ◎ ○ △1 △2;
- ▲ identical to independent single-shot horse;
- support boundary final △2 identical to final fifth mark;
- boundary alternative outside the final five when present;
- market/result firewall PASS;
- Validator PASS;
- `FROZEN_CLEAN_BLIND`.

Reader prose advisories may identify stylistic drift without invalidating a
historically Frozen prediction. New cards should aim for no such advisories.

## 8. Cohort interpretation

These operational/prose/trace refinements do not create a new prediction
logic cohort. As long as complete Reader evidence and the v0.4.6 horse-selection
judgment are unchanged, the day remains a v0.4.6 sample.

Separate the cohort only when the information shown to the predictor or the
rule by which horses receive ◎ ○ ▲ △1 △2 materially changes.

Track ordinary outcome/ROI metrics plus:

- ▲ performance;
- final △2 versus recorded boundary alternative;
- one-execution completion rate;
- resumed venue count;
- completed venues re-authored (target zero).
