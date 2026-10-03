# RaceNote Backtest Artifacts

This directory is the canonical Git handoff area for RaceNote clean-blind daily backtests.

## Layout

```text
backtests/
  BTDAY-xxxx/
    YYYYMMDD/
      README.md
      day_prep/
      venues/
      day_merge/
```

Analysis/research threads should start from the target day's `README.md`, then read `day_merge/forecast_YYYYMMDD_all.json` as the canonical merged pre-result forecast.

Rules:

- Forecast artifacts are immutable after Freeze.
- DAY MERGE is deterministic packaging only; marks are not changed there.
- Target results are not stored in this pre-result artifact tree.
- Post-race result joins and review belong to the analysis/research flow.

## Current prospective validation cohorts (2026-10-03)

- Fixed v0.4.2 clean-blind historical comparator: BTDAY-0023–0032, 336R.
- Fixed v0.4.3 prospective cohort: BTDAY-0036 / 0037 / 0040 / 0041, 132R.
- New unused BTDAYs: v0.4.4 candidate alone. BTDAY-0042 and
  BTDAY-0043 have already been selected in the pool, so resume those IDs
  without a second draw. A selection alone is not a completed Freeze.
- BTDAY-0038 and 0039 remain excluded from formal clean-blind comparison.

The current operator sequence and preflight gate are in
`docs/racenote/BTDAY_PROSPECTIVE_VALIDATION_RUNBOOK_v0_1.md`.
The same-day A/B runbook is superseded. Target results and target-day market
remain unopened until after Freeze and Validator PASS.
