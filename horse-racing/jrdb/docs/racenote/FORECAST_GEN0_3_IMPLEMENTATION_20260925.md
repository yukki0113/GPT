# RaceNote Forecast Gen0.3 Implementation Status — 2026-09-25

Status: IMPLEMENTED_NOT_ACTIVATED

## Purpose

Gen0.3 finalizes the trend-first redesign before the first post-Gen0-G000
activation.

Planned activation:

- generation: `Gen0-G001`
- forecast: `RaceNote-Forecast-Gen0.3`
- evidence policy: `TrendFirst-RR-Pairwise-Scenario-v0.1`

Gen0.2 was implemented but never activated. Its planned Gen0-G001 reservation
is superseded by Gen0.3 before any sample manifest or frozen Gen0.2 forecast
was created.

## Implemented chain

```text
Independent RaceNote
  -> General Evidence
  -> Pairwise Comparison
  -> Scenario Robustness
  -> Base Forecast
  -> EdgeDB performance-only overlay
  -> Final Forecast
  -> Freeze
  -> JRDB Consensus / Market / Edge Value / RL Value / Bet Plan
```

## New assets

- `src/racenote_forecast_gen0_3.py`
- `src/racenote_edge_performance_adapter.py`
- `schema/racenote_forecast_gen0_schema_v0_3.json`
- `config/racenote_forecast_gen0_ledger_v0_3.json`
- `tests/test_racenote_forecast_gen0_3.py`
- `tests/test_racenote_edge_performance_adapter.py`
- `.github/workflows/jrdb_racenote_gen0_3_tests.yml`
- `docs/racenote/FORECAST_GEN0_3_PREDICTION_CONTRACT_v0_3.md`

General Evidence now additionally exposes `IndependentRaceStructure-v0.1`
from historical corner-position evidence only.

## Hard boundaries

Before Freeze:

- current JRDB consensus hidden;
- current market hidden;
- EdgeDB Value hidden;
- RL / Value hidden;
- Training Edge excluded;
- target result hidden;
- no fixed weighted score;
- simple ability cannot auto-rank.

EdgeDB is consumed through existing v0.2 matcher semantics. The RaceNote
adapter projects only the Performance channel and does not rematch conditions.

## Activation gate

Implementation completion does not change current generation.

Before Gen0-G001 activation:

1. create and freeze the next sample manifest;
2. register Gen0-G001 in the ledger;
3. activate Gen0.3 settings;
4. resolve official TRUE_FORWARD inputs;
5. freeze each forecast before opening post-Freeze layers;
6. preserve Gen0-G000 and Gen0.2 reference assets unchanged.

Until those steps are explicitly executed, operational status remains
IMPLEMENTED_NOT_ACTIVATED.
