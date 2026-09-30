# RaceNote Daily Forecast Operation v0.1

Status: AGREED OPERATION BASELINE  
Updated: 2026-09-30

## 1. Purpose

This document records the agreed operating shape for RaceNote daily forecasting after the CAL-001 through CAL-006 calibration phase.

The same execution shape is used for:

- historical backtests on eligible 2026 JRA dates
- normal forward daily operation for the next JRA race day

The intent is to keep the forecasting path itself common between backtest and production-like operation. Backtest-only and publication-only behavior should live at the boundary, not inside race prediction logic.

Current forecast logic is resolved from:

- `config/racenote_forecast_logic_current.json`

At the time this agreement was recorded, current logic is:

- `RaceNote-Human-Context-Reader-0.3.2`
- phase: `CALIBRATION_HOLD`

This document does not override the current logic pointer. Forecast execution must always re-resolve latest main/current before a new day starts.

---

## 2. Daily unit

One target date is one Daily Forecast unit.

A normal JRA day contains two or three venues, normally 24 to 36 races.

The daily flow is intentionally split into separate turns:

```text
DAY PREP
  -> VENUE FORECAST #1
  -> VENUE FORECAST #2
  -> VENUE FORECAST #3, when present
  -> DAY MERGE
  -> STOP before post-race work
```

The GPT forecasting work unit is **one venue / up to 12 races per turn**, not the whole day at once.

Each race inside a venue is still forecast independently.

---

## 3. Stage A — DAY PREP

### 3.1 Target-date resolution

Backtest:

- choose a target date from the approved 2026 historical pool
- obey the current pool / eligibility / already-used rules
- the selection mechanism must not expose target-race results

Normal forward operation:

- use the requested next/current JRA race date, for example tomorrow's Saturday card
- do not use backtest random selection

### 3.2 RaceNote generation

For the target date:

1. resolve or acquire the target day's PACI
2. run the existing daily RaceNote orchestrator
3. generate RaceNote for the entire day in one batch
4. include the currently required enrichment lanes, including P1/P2 and formal RRDB when current contract requires them
5. enforce all as-of / pre-result boundaries

Expected scope:

- 2 venues: normally 24 races
- 3 venues: normally 36 races

DAY PREP is a data-preparation stage.

**No forecast marks are assigned here.**

### 3.3 Daily input manifest

DAY PREP should leave a machine-readable day manifest that identifies at least:

- target date
- venues
- expected race count per venue
- RaceNote input identities
- logic/current resolution used for the day
- source/provenance identities needed for reproducibility
- result leakage guard state

Exact handoff schema and filename are to be formalized next.

---

## 4. Stage B — VENUE FORECAST

### 4.1 One venue = one turn

GPT handles one venue at a time.

Typical examples:

```text
東京 1R-12R
京都 1R-12R
新潟 1R-12R
```

A three-venue day therefore normally requires three Forecast turns after DAY PREP.

This boundary is deliberate:

- prevents whole-day context inflation
- keeps evidence reading manageable
- makes venue-level audits and retry boundaries clear
- lets venue/course context remain visible without turning the day into one giant ranking task

### 4.2 Race independence

Within the venue:

- each race is one independent forecast
- do not rank horses across different races
- do not weaken or strengthen one race's marks because another race on the same day looks stronger
- do not use later-race prediction choices to repair earlier-race choices

Venue context may inform interpretation of course/trend evidence where the RaceNote contract permits it, but prediction decisions remain race-local.

### 4.3 Reader behavior

The Reader should flexibly integrate relevant evidence such as:

- ground ability
- current-race condition fit
- Trend
- P1/P2 pedigree context
- training
- RRDB reinterpretation of prior visible results

No fixed universal weighting or aggregate score is introduced merely for daily operation.

RRDB keeps the current semantics:

```text
visible prior result
  -> reinterpret as UPGRADE / DOWNGRADE / CONFIRM / NEUTRAL
  -> return to the current race
  -> re-compare candidates
  -> assign marks
```

RRDB labels, Next-Watch S/A, Trend, pedigree statistics, or training figures do not directly determine marks by themselves.

### 4.4 Internal trace vs reader-facing reason

Canonical forecast records retain the internal audit trail, including:

- race model
- candidate comparison
- evidence usage
- RRDB interpretation
- counterargument
- reversal condition
- evidence gaps

Reader-facing text is separate.

Reader-facing forecast reasons must explain **why the horse is worth buying in this race**.

Avoid publication text that sounds like internal model repair, for example:

- "RRDBでUPGRADEしたから"
- "前回の評価を修正したため"
- "CALで印を戻したため"

Those belong to internal audit/research trace, not the newspaper-facing reason.

### 4.5 Venue Freeze

After all usable races at the venue are complete:

- validate the canonical records
- Freeze the venue prediction set
- record prediction hashes
- keep `result_opened=false`
- emit a venue-level handoff

A Frozen venue is immutable for that target day.

If a technical defect requires regeneration, it must be explicitly identified and audited rather than silently overwriting the forecast.

Exact venue handoff schema and filenames are to be formalized next.

---

## 5. Stage C — DAY MERGE

DAY MERGE begins only after all target venues are Frozen.

### 5.1 Merge is not a forecasting stage

The merge step is deterministic packaging only.

It may:

- combine venue canonical records
- sort races into daily order
- verify completeness
- verify hashes / identities
- generate a one-day simple HTML
- generate a consumer payload for Newspaper PWA in forward operation

It must not:

- change marks
- rewrite the selected main horse
- re-run candidate comparison
- rebalance confidence across venues
- decide that one venue's main pick looks weaker after seeing the full day

Example of prohibited behavior:

```text
東京◎ / 京都◎ / 新潟◎ are already Frozen
-> look at the whole day
-> replace 東京◎ because another race now looks stronger
```

That is not merge behavior and is forbidden.

### 5.2 Daily outputs

The merged day should contain, at minimum:

- all Frozen race prediction records
- venue/source identity
- prediction hashes
- daily completeness audit
- `result_opened=false`
- simple one-day HTML

Normal forward operation additionally produces:

- Newspaper PWA-compatible payload

Backtest:

- PWA publication payload is optional / unnecessary
- the simple HTML and canonical merged records are sufficient before post-race evaluation

Exact final file contract is to be formalized next.

---

## 6. Stage D — POST-RACE boundary

Post-race work is a separate phase and should not occur inside Forecast execution.

Only after the daily Forecast is fully Frozen may another research/review path:

- acquire results
- join result/performance data
- calculate forecast evaluation
- perform review
- propose logic changes

The Forecast execution path must not open target results before Freeze.

Post-race evidence must not flow backward into already Frozen forecasts.

---

## 7. Backtest and forward-operation parity

The preferred design is one shared pipeline.

### Historical backtest

```text
approved/random historical date
  -> DAY PREP
  -> venue forecast(s)
  -> DAY MERGE
  -> STOP
  -> separate result/research phase
```

### Normal forward operation

```text
next JRA race date
  -> DAY PREP
  -> venue forecast(s)
  -> DAY MERGE
  -> Newspaper PWA payload
  -> STOP
  -> separate post-race phase after results exist
```

The core Reader, RaceNote input, canonical forecast record, Freeze semantics, and merge behavior should be the same in both modes.

Do not maintain a special backtest-only prediction implementation unless a contract explicitly requires it.

---

## 8. Immutability and retry rules

The following are operational invariants:

1. RaceNote input identity is fixed before venue forecasting starts.
2. A venue Forecast is immutable after successful Freeze.
3. DAY MERGE consumes Frozen venue outputs only.
4. Merge never changes prediction judgment.
5. Target results remain unopened until the whole requested Forecast scope is Frozen.
6. Technical retry does not silently become a second prediction attempt.
7. A failed or skipped race is explicit; it is not silently filled with guessed marks.
8. Reader-facing publication text is derived from Frozen prediction records and does not redefine the prediction.

---

## 9. Suggested directory shape

The following is an agreed direction, not yet a finalized file contract:

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

Filename/schema details remain a follow-up design task.

---

## 10. Next formalization work

The operating sequence above is agreed.

The next design task is to formalize three machine contracts:

1. **DAY PREP handoff**
   - complete day input manifest
   - RaceNote identities / source provenance
   - expected venue/race inventory

2. **VENUE FORECAST handoff**
   - venue Freeze state
   - canonical record paths
   - race/frozen/skip counts
   - prediction hashes
   - result-open guard

3. **DAY MERGE handoff / output contract**
   - deterministic venue merge
   - daily completeness/hash audit
   - simple HTML contract
   - Newspaper PWA payload boundary

Until those schemas are committed, the sequence and invariants in this document are the operational baseline, while example filenames remain provisional.

---

## 11. Summary

The agreed normal unit is:

```text
one day of RaceNote generated in one batch
  -> GPT forecasts one venue (12R) per turn
  -> venue Freeze
  -> repeat for 2-3 venues
  -> deterministic daily merge
  -> simple HTML
  -> PWA payload only when needed
  -> result work remains outside Forecast
```

This structure is the common basis for both practical daily operation and production-like historical backtesting.
