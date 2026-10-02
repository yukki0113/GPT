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

## Current prospective validation cohorts (2026-10-02)

- Fixed v0.4.2 clean-blind historical comparator: BTDAY-0023–0032.
- New unused BTDAYs: v0.4.3 candidate alone. Do not generate a same-day
  v0.4.2 pair.
- BTDAY-0035 is a preserved v0.4.2-only Freeze outside the defined cohorts.

See `docs/racenote/BTDAY_PROSPECTIVE_VALIDATION_RUNBOOK_v0_1.md`.
The older same-day A/B runbook is superseded.
