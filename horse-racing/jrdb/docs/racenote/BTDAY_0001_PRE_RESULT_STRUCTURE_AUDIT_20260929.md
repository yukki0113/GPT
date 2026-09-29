# BTDAY-0001 Pre-Result Forecast Structure Audit

Status: **COMPLETE / RESULT STILL UNOPENED**
Date: 2026-09-29
Turn: `BTDAY-0001`
Logic: `RaceNote-Baseline-Reader-0.1`

## 1. Scope

This audit inspects only the frozen prediction artifacts and handoff structure.
Target results are not used.

Turn facts from handoff:

- selected dates: 2026-02-08 / 2026-05-23
- total races: 47
- frozen races: 47
- technical skips: 0
- result_opened: false

## 2. Structural finding

The prediction records satisfy the original minimal output contract but do not
preserve enough race-specific comparison context to support reliable post-race
logic research.

Observed pattern:

- many axis comments use the same generic skeleton:
  - compare ability / recent form / preparation
  - list aggregate / training / stable / prior-finish values
  - conclude that the horse is "most balanced"
- many concern comments use a generic statement that upper candidates are close
  and pace/position may reverse the order
- `candidate_trace` often records only a compact evidence value summary plus
  the common baseline-reader label
- the record does not make explicit:
  - why ◎ is above ○
  - which evidence was decisive vs merely present
  - what evidence was consciously downweighted
  - the strongest case against ◎
  - the specific condition under which ○/▲ would reverse ◎

Therefore a later miss cannot reliably be classified as a reading error,
comparison error, missing-evidence problem, or merely an outcome variance.

## 3. Interpretation

This is an **experiment observability defect**, not yet a performance conclusion.

Do not use BTDAY-0001 results to justify this fix.
The fix is allowed before result open because it addresses the recording /
execution contract visible in the frozen pre-result artifacts themselves.

## 4. Corrective action

Current research baseline advances to:

`RaceNote-Baseline-Reader-0.2`

v0.2 keeps the v0.1 no-fixed-weight / all-runner comparison philosophy, but
requires a structured Decision Trace for every usable race.

Canonical additions:

- `docs/racenote/FORECAST_DECISION_TRACE_CONTRACT_v0_1.md`
- `schema/racenote_forecast_research_record_v0_2.json`
- `src/validate_racenote_forecast_decision_trace.py`

The new Freeze gate requires:

- race thesis
- 2–4 decisive factors with observation + interpretation
- explicit ◎ vs ○ comparison
- strongest counter-case against ◎
- downweighted evidence
- reversal condition
- race-specific trace quality audit

## 5. BTDAY-0001 preservation

Do not rewrite BTDAY-0001 forecasts into v0.2 format after the fact.

Its v0.1 predictions remain immutable evidence of the first baseline execution.
Post-race evaluation may still measure objective hit/rank metrics, but detailed
causal diagnosis must acknowledge the weak decision-trace coverage.
