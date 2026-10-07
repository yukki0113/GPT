# RaceNote v0.5.2 Single-Day Runbook v0.1

Status: **CURRENT BASELINE OPERATION — NON-A/B**
Date: 2026-10-07
Logic: `RaceNote-Human-Context-Reader-0.5.2-candidate`

## Purpose

This is the ordinary prospective RaceNote path after the BTDAY-0057..0060
v0.5.1/v0.5.2 comparison.

The same path is used for:

- a historical BTDAY;
- a normal forward JRA day.

A/B session creation, sibling lanes and a two-lane Freeze barrier are not
required.

The operational shape is:

```text
one PACI ZIP
  -> RaceNote daily build
  -> market-blind forecast_prep
  -> one sealed v0.5.2 Reader set
  -> model authors v0.5.2 Decision Cores
  -> venue save
  -> immutable single-day Freeze
  -> verify
  -> publication / later settlement
```

Target results, target final odds/popularity and payouts remain forbidden until
the single-day Freeze is complete.

## 1. TURN 1 — DAY PREP / prediction-thread orchestration responsibility

The **prediction thread owns the entire pre-result operation from PACI through Verify** when the user asks for a day's prediction.

TURN 1 and TURN 2 are internal phases of the same prediction request, not separate threads.

The prediction thread must:
- acquire or resolve the target PACI;
- run/route Analysis and RRDB enrichment;
- build the daily RaceNote package;
- create the market-blind forecast_prep;
- create the sealed v0.5.2 Reader/session;
- then continue into race-by-race authoring, Freeze and Verify.

If the current local runtime lacks DuckDB or another required dependency, the prediction thread must **route TURN 1 through an execution environment that supports the canonical pipeline** rather than omit the stage or create a provisional Reader/Freeze.

The analysis/research thread is not a prerequisite for ordinary daily prediction. Its normal responsibilities are date reservation, post-race settlement, research aggregation and logic development.

Before authoring begins, the following handoff must exist:

```text
<output-root>/operation_handoff.json
<output-root>/forecast_prep/
<output-root>/v052/session.json
<output-root>/v052/reader_manifest.json
<output-root>/v052/reader/*.json
```

Required handoff state:

- `status=READY_FOR_V052_AUTHORING`
- `market_blind=true`
- `result_opened=false`
- canonical v0.5.2 Reader/session materialized

The prediction thread's TURN 1 orchestration may use the PACI entrypoint below.

Historical BTDAY:

```bash
python horse-racing/jrdb/src/racenote_v052_from_paci.py \
  --date YYYY-MM-DD \
  --paci /path/to/PACIyymmdd.zip \
  --selection-id BTDAY-XXXX \
  --main-sha <40-char-main-sha> \
  --analysis-root <canonical-analysis-root> \
  --racereview-current-cache <rrdb-current-cache> \
  --output-root horse-racing/jrdb/backtests/BTDAY-XXXX/YYYYMMDD/v052_day
```

Normal forward day:

```bash
python horse-racing/jrdb/src/racenote_v052_from_paci.py \
  --date YYYY-MM-DD \
  --paci /path/to/PACIyymmdd.zip \
  --selection-id DAILY-YYYYMMDD \
  --main-sha <40-char-main-sha> \
  --analysis-root <canonical-analysis-root> \
  --racereview-current-cache <rrdb-current-cache> \
  --output-root horse-racing/jrdb/daily/YYYYMMDD/v052_day
```

`--racereview-root` may be used instead of `--racereview-current-cache`.

The command performs:

1. `build_racenote_daily.py` equivalent day build;
2. `racenote_prepare_forecast_input.py` market stripping/binding;
3. v0.5.2 normal_view derivation;
4. a sealed one-lane session.

Required final handoff status:

`READY_FOR_V052_AUTHORING`

and:

- `ab_required=false`;
- `market_blind=true`;
- `result_opened=false`.

## 2. TURN 2 — model authoring responsibility

After TURN 1 reaches `READY_FOR_V052_AUTHORING`, the same prediction thread changes phase from mechanical preparation to model judgment.

It must not:
- bypass a failed TURN 1;
- create an alternative/provisional Reader;
- invent a provisional Freeze status when canonical input is unavailable;
- silently omit Analysis/RRDB enrichment.

If the canonical handoff is not ready, repair or reroute TURN 1 before authoring. Do not proceed with a degraded prediction input.

## 2.1 Authoring input

Only read:

```text
<output-root>/v052/reader/*.json
<output-root>/v052/reader_manifest.json
<output-root>/v052/session.json
```

Do not use:

- target-day result files;
- target final market;
- an old v0.5.1/v0.5.2 sibling prediction;
- prior BTDAY marks as prediction evidence.

Follow the promoted v0.5.2 contract:

`FORECAST_HUMAN_CONTEXT_READER_v0_5_2_CANDIDATE.md`

The Decision Core must retain:

- protected `ordinary_five`;
- `WIN_FIRST_NOT_PLACE_FIRST` ◎ selection;
- `ASYMMETRIC_PAYOUT_ROUTE_NOT_ORDINARY_RANK` ▲ mode;
- audited six-to-five compression.

## 3. Save each venue

Place one full venue Decision Core array at:

```text
<output-root>/v052/incoming/<venue>.json
```

Then:

```bash
python horse-racing/jrdb/src/racenote_v052_single_day.py save \
  --root <output-root>/v052 \
  --decisions <output-root>/v052/incoming/<venue>.json
```

Save is immutable per venue. A second materially different write must not
silently replace an authored venue.

## 4. Freeze the day

After all expected venues have been saved:

```bash
python horse-racing/jrdb/src/racenote_v052_single_day.py freeze \
  --root <output-root>/v052
```

Required status:

`FROZEN_CLEAN_BLIND`

Freeze produces:

```text
v052/frozen/
  records.json
  day_handoff.json
```

No A/B barrier is required.

## 5. Verify before publication or settlement

```bash
python horse-racing/jrdb/src/racenote_v052_single_day.py verify \
  --root <output-root>/v052
```

Verification re-checks:

- sealed forecast_prep identity;
- Reader hashes;
- race/horse roster;
- all authored Decision Core hashes;
- v0.5.2 Decision Core validation;
- frozen record binding;
- `market_blind=true`;
- `result_opened=false`.

Only after verify succeeds may downstream publication consume the Freeze.

Historical BTDAY settlement may open results only after this point.

## 6. Existing A/B infrastructure

The following remain valid for historical reproduction and new research when a
real two-version comparison is desired:

- `racenote_ab_session.py`
- `racenote_ab_lane.py`
- `racenote_ab_freeze_barrier.py`
- `RACENOTE_CLEAN_BLIND_V051_V052_AB_RUNBOOK_v0_1.md`

They are not required for normal v0.5.2 operation.

## 7. Operational principle

v0.5.2 is now the baseline, not merely one lane of an experiment.

Therefore the default mental model is:

```text
PACI -> one evidence package -> one v0.5.2 judgment -> one immutable Freeze
```

A/B machinery should be introduced only when there are actually two competing
forecast contracts to compare.
