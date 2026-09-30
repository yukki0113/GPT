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
