# RaceNote BTDAY Prospective Validation Runbook v0.1

Status: **LEGACY v0.4.6 PROCEDURE; current v0.5.2 uses `RACENOTE_V052_SINGLE_DAY_RUNBOOK_v0_1.md`**  
Date: 2026-10-05

For a 2010–2025 BTDAY using accepted Historical Warehouse, use the current
v0.5.2 single-day runbook and the Raw/Warehouse equivalence PASS gate. For
2026, keep the existing PACI → v0.5.2 path. The v0.4.6 workflow below is
retained only for its historical operation record.

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

## 6. Freeze and post-Freeze result flow

Prediction and result acquisition are separated by the Freeze boundary.

Until final Freeze succeeds, do not open target results, payouts, final
odds/popularity, result joins, or post-race evaluation. Target-day market
stays outside the model input after clean binding.

Once the relevant forecast or both A/B lanes are Frozen and the required
Freeze barrier has passed, use JRDB Raw as the canonical result source.

The normal post-Freeze path is:

```text
Freeze / A-B barrier PASS
-> jrdb_result_query_runner.py --plan --date YYYY-MM-DD
-> materialize the exact Drive Raw files named by the plan
-> jrdb_result_query_runner.py --date YYYY-MM-DD
-> SED parses finish/order and runner result data
-> HJC parses all eight payout types
-> SED/HJC win/place cross-validation
-> racenote_daily_result_from_jrdb.py builds one canonical full-day result JSON
-> evaluation / settlement consumes that daily result
```

For 2026 daily Raw, the runner resolves:

- `/Google Drive/GPT/horse-racing/00_raw/SED/SEDyymmdd.zip`
- `/Google Drive/GPT/horse-racing/00_raw/HJC/HJCyymmdd.zip`

For 2025 and earlier it resolves the corresponding annual SED/HJC archives.

The GPT/Work layer materializes those exact Drive files into the local paths
returned by the plan. Raw is intentionally not stored in Git. Its absence from
the repository is expected and is not a reason to search the Web.

A date-only result query is the default for RaceNote evaluation. It returns
every JRA race available for that day, so do not loop over individual races or
scrape separate race pages when the day-level SED/HJC path is available.
Venue/race filters exist only for focused inspection.

`racenote_daily_result_from_jrdb.py` is the canonical RaceNote adapter. It
uses SED for the official top three and HJC for win, place, frame quinella,
quinella, wide, exacta, trio and trifecta payouts. Any SED/HJC win/place
cross-validation mismatch is `review_required` and must not be silently
settled.

Web-based daily-result acquisition is a fallback/convenience route only when
the canonical target-date JRDB Raw is genuinely unavailable after checking
Drive. It is not the default BTDAY result-confirmation path.

Result/ROI analysis starts only after this daily result has been built.

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
