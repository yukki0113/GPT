# RaceNote Daily Forecast Operation v0.1

Status: **AGREED OPERATION BASELINE — TWO-TURN DAILY DEFAULT**  
Updated: 2026-09-30

## 1. Purpose

This document records the agreed operating shape for RaceNote daily forecasting.

The same execution shape is used for:

- historical backtests on eligible 2026 JRA dates
- normal forward daily operation for the next JRA race day

The forecasting path itself should remain common between backtest and production-like operation. Backtest-only and publication-only behavior belongs at the boundary, not inside race prediction logic.

Forecast logic must always be re-resolved from latest `main` before a new day starts. This operation document does not override the current/candidate logic contract selected for that test.

As of 2026-10-07, the ordinary prospective baseline is RaceNote v0.5.2. Normal BTDAY and forward daily operation should use `RACENOTE_V052_SINGLE_DAY_RUNBOOK_v0_1.md`; the v0.5.1/v0.5.2 A/B harness is retained for research/audit and is not required for ordinary daily operation.

---

## 2. Daily unit and standard turn shape

One target date is one Daily Forecast unit.

A normal JRA day contains two or three venues, normally 24 to 36 races.

The current default is **two turns per target day**:

```text
TURN 1 — DAY PREP
  -> resolve / fix target date
  -> acquire PACI
  -> generate the full-day RaceNote in one batch
  -> validate source / as-of / leakage boundaries
  -> fix DAY PREP handoff
  -> STOP before forecasting

TURN 2 — FULL-DAY FORECAST
  -> forecast all venues / all races for the day
  -> Freeze each venue independently
  -> verify prediction hashes / completeness
  -> deterministic DAY MERGE
  -> generate simple one-day HTML
  -> STOP before post-race work
```

For a normal three-venue day, TURN 2 therefore handles up to **36 races in one turn**.

This two-turn shape became the default after `BTDAY-0005 / 2026-06-28` successfully completed all 36 race forecasts, venue-level Freeze, hash checks, and DAY MERGE in one Forecast turn with `result_opened=false`.

Each race remains an independent forecast decision even when the whole day is processed in one turn.

---

## 3. Stage A — DAY PREP / TURN 1

### 3.1 Target-date resolution

Backtest:

- choose one target date from the approved historical pool
- obey eligibility / already-used rules
- the selection mechanism must not expose target-race results
- once selected, fix the date in the pool before Forecast begins

Normal forward operation:

- use the requested next/current JRA race date
- do not use backtest random selection

### 3.2 RaceNote generation

For the target date:

1. resolve or acquire the target day's PACI
2. run the existing daily RaceNote orchestrator
3. generate RaceNote for the entire day in one batch
4. include the currently required enrichment lanes, including P1/P2 and formal RRDB when required
5. enforce all as-of / pre-result boundaries
6. validate the Reader View / manifest / source provenance

Expected scope:

- 2 venues: normally 24 races
- 3 venues: normally 36 races

DAY PREP is strictly a data-preparation stage.

**No forecast marks are assigned in TURN 1.**

### 3.3 DAY PREP handoff

TURN 1 should end with a machine-readable handoff identifying at least:

- target date
- selection id when backtesting
- venues
- expected race count per venue
- RaceNote identities
- Analysis / RRDB / Next-Watch provenance
- forecast logic or candidate logic intended for TURN 2
- validation state
- result leakage guard state
- `result_opened=false`

After this handoff is fixed, RaceNote input identity is immutable for the day's Forecast.

---

## 4. Stage B — FULL-DAY FORECAST / TURN 2

### 4.1 Default: one day = one Forecast turn

After DAY PREP completes, GPT normally forecasts the entire target day in one turn.

Typical three-venue shape:

```text
Venue #1 1R-12R
  -> venue Freeze
Venue #2 1R-12R
  -> venue Freeze
Venue #3 1R-12R
  -> venue Freeze
DAY MERGE
```

The whole-day turn is an execution boundary only. It must **not** become one combined ranking task across races or venues.

### 4.2 Race independence

Within the full-day turn:

- each race is one independent forecast
- do not rank horses across different races
- do not strengthen or weaken a pick because another race on the same day looks stronger
- do not use later-race choices to repair earlier-race choices
- do not revise a venue after that venue has been Frozen
- do not rebalance marks across venues before DAY MERGE

Venue/course context may inform RaceNote evidence where the active contract permits it, but prediction decisions remain race-local.

### 4.3 Reader behavior

The active Reader should flexibly integrate relevant evidence such as:

- ground ability
- current-race condition fit
- Trend
- P1/P2 pedigree context
- training
- RRDB reinterpretation of visible prior results
- any additional evidence lane explicitly allowed by the active logic contract

No fixed universal weighting or aggregate score is introduced merely because the whole day is processed in one turn.

RRDB retains the existing semantic flow:

```text
visible prior result
  -> reinterpret prior run
  -> return to current race
  -> re-compare candidates
  -> assign marks
```

Internal RRDB labels, Next-Watch grades, Trend, pedigree statistics, or training values do not directly determine marks by themselves.

### 4.4 Internal trace vs reader-facing reason

Canonical forecast records retain the audit trail required by the active logic contract.

Reader-facing forecast reasons explain **why the horse is worth buying in this race**.

Do not expose internal research labels as the reason itself.

### 4.5 Venue Freeze remains mandatory

Even inside a one-day Forecast turn, each venue must be Frozen independently after its usable races are complete.

Venue Freeze requires:

- canonical record validation
- prediction hashes
- `result_opened=false`
- venue-level handoff
- explicit technical skips when any race could not be completed

A Frozen venue is immutable for that target day.

---

## 5. Safety fallback — one venue per turn

The prior `one venue / up to 12 races per Forecast turn` design remains the mandatory fallback when the full-day turn becomes operationally unsafe.

Fallback triggers include:

- approaching turn / execution time limits
- evidence review becoming too shallow or compressed
- context / artifact / tool limits
- a venue cannot be completed cleanly
- validation or Freeze cannot be finished reliably
- any other issue that risks prediction quality, completeness, or auditability

When a fallback is required:

1. finish and Freeze only the venue(s) genuinely completed
2. do not rush or abbreviate the remaining races
3. end the turn
4. resume with the next unfinished venue in a new turn
5. run DAY MERGE only after every target venue is Frozen

The fallback is an execution-safety boundary, not a change in forecast logic.

---

## 6. Stage C — DAY MERGE

DAY MERGE begins only after every target venue is Frozen.

DAY MERGE is deterministic packaging only.

It may:

- combine venue canonical records
- sort races into daily order
- verify completeness
- verify identities and prediction hashes
- generate daily audit / handoff
- generate a simple one-day HTML
- generate Newspaper PWA payload when forward operation requires it

It must not:

- change marks
- rewrite ◎ / ○ / ▲ / △
- rerun candidate comparison
- rebalance confidence across venues
- modify a reader-facing reason in a way that changes prediction meaning

Backtests normally require only canonical merged records, audit/handoff, and simple HTML before post-race evaluation.

---

## 7. Stage D — POST-RACE boundary

Post-race work is a separate phase.

Only after the full requested Forecast scope is Frozen and DAY MERGE is complete may another research/review path:

- acquire results
- join performance data
- calculate forecast evaluation
- perform diagnosis
- propose logic changes

The Forecast execution path must not open target results before Freeze.

Post-race evidence must never flow backward into Frozen forecasts.

---

## 8. Backtest and forward-operation parity

### Historical backtest

```text
TURN 1:
approved/random historical date
  -> DAY PREP
  -> STOP

TURN 2:
full-day Forecast
  -> venue Freeze x all venues
  -> DAY MERGE
  -> STOP

then separate result/research phase
```

### Normal forward operation

```text
TURN 1:
next JRA race date
  -> DAY PREP
  -> STOP

TURN 2:
full-day Forecast
  -> venue Freeze x all venues
  -> DAY MERGE
  -> Newspaper PWA payload when required
  -> STOP

then separate post-race phase after results exist
```

If TURN 2 cannot be completed safely, split only at venue boundaries and continue with the fallback described above.

---

## 9. Immutability and retry rules

Operational invariants:

1. RaceNote input identity is fixed at the end of TURN 1.
2. TURN 1 ends before any forecast marks are assigned.
3. TURN 2 may cover 24–36 races, but every race remains independent.
4. A venue is immutable after successful Freeze.
5. DAY MERGE consumes Frozen venue outputs only.
6. DAY MERGE never changes prediction judgment.
7. Target results remain unopened until the entire requested Forecast scope is Frozen.
8. Technical retry does not silently become a second prediction attempt.
9. Failed / skipped races are explicit and never filled with guessed marks.
10. Reader-facing publication text does not redefine the Frozen prediction.
11. If a full-day Forecast turn must stop early, Freeze completed venue(s) only and resume unfinished venues later.

---

## 10. Suggested directory shape

```text
daily/YYYYMMDD/
  input/
    day_manifest.json
  forecast/
    <venue>.jsonl
    <venue>_handoff.json
  frozen/
    day_forecast.json
    day_forecast.jsonl
  publish/
    forecast.html
    newspaper_payload.json
```

Backtests may omit `publish/newspaper_payload.json`.

---

## 10.1 One-request orchestration and reasoning boundary

From BTDAY-0024 onward, DAY PREP and FULL-DAY FORECAST may be completed within one user request.

This changes the interaction boundary, not the forecast reasoning boundary.

Required internal flow:

```text
mechanical DAY PREP
  -> STOP FOR RACE-BY-RACE REASONING
  -> model inspects the full field and authors marks + prose + decision trace
  -> deterministic Freeze packager
  -> validator
  -> immutability guard
  -> canonical publish
```

The reasoning checkpoint must not be replaced by a scoring script, fixed-pick generator, RRDB-driven selector, or prose template.

`src/racenote_freeze_prepared_forecast.py` is the canonical deterministic Freeze packager. It consumes complete prepared records and must not choose horses or generate prose.

`src/racenote_finalize_fixed_picks.py` is intentionally disabled because it mixed forecast authorship with deterministic packaging.

`src/racenote_freeze_immutability_guard.py` protects an existing canonical Freeze: identical semantic prediction hashes are an identical retry; different hashes are a conflict and must not overwrite silently.

Prediction semantic hashes exclude execution-only metadata such as Git SHA and timestamps, so a technical retry cannot change the forecast identity merely because the runtime changed.

The detailed boundary contract is `docs/racenote/FORECAST_REASONING_MECHANICAL_BOUNDARY_v0_1.md`.

---
## 11. Summary

The current default is:

```text
TURN 1
  full-day RaceNote generation + validation
  -> DAY PREP handoff fixed
  -> STOP

TURN 2
  forecast all 24–36 races
  -> Freeze each venue independently
  -> deterministic DAY MERGE
  -> simple HTML / required payload
  -> STOP before results
```

Operational fallback:

```text
If the one-day Forecast turn approaches practical limits:
  -> Freeze completed venue(s)
  -> end the turn
  -> resume one venue at a time
  -> DAY MERGE after all venues are Frozen
```

`BTDAY-0005 / 2026-06-28` is the first successful reference run for the two-turn daily shape.

Keep the two-turn structure as the default while it remains stable. Revert to the venue-per-turn fallback whenever quality, completeness, timing, context, or tooling becomes a concern.
