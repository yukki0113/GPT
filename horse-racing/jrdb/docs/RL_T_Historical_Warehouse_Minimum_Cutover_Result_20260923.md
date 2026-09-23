# RL-T Historical Warehouse Minimum Cutover Result — 2026-09-23

## Decision

`NO-GO (execution pending)`

This change set implements the fail-closed operational path, but does not claim a scientific or production cutover before the real-data gates have run. Existing production workflows and the 2026 PACI/SED route remain unchanged.

## Source and implementation

- Main before: `53e52914aceb3fbb8ed7b1dfc4d3877d24923028`
- Implementation branch: `codex/rl-t-minimum-cutover-20260923`
- Latest implementation commit: `0b2966af754c69d7b93240b7e130387f3db43848`
- Accepted generation: `jrdb_normalized_warehouse_v1_2010_2025_g20260921`
- Historical coverage: 2010–2025
- Warehouse mode: immutable accepted Parquet staging references
- Raw mode: audit/equivalence only; never the default builder input

Changed files:

- `horse-racing/jrdb/src/materialize_jrdb_warehouse_from_drive.py`
- `horse-racing/jrdb/src/run_rl_t_historical_warehouse_minimum_cutover.py`
- `.github/workflows/rlt_historical_warehouse_minimum_cutover.yml`

## Gates

| Gate | Result |
|---|---|
| Accepted manifest/audit, generation and 192-asset contract | Implemented; runtime verification required |
| Drive asset materialization and SHA/size verification | Implemented; runtime verification required |
| Representative Index Base builds (2010/2018/2025) | NOT_RUN |
| Raw vs Warehouse dual-read (schema, rows, hashes, NULL/blank, record_hash, representative, repeat-build, integrity) | NOT_RUN |
| Full 2010–2025 Warehouse Index Base | NOT_RUN |
| RunPerf → Official RunPerf → Training Research | NOT_RUN |
| Frozen runtime fingerprint and development/holdout boundary | Existing guard retained; downstream run required |
| 2026 PACI + settled SED route | Unchanged |
| Production workflow cutover | NOT_PERFORMED |

The workflow fails closed if any gate is missing or non-PASS. It never silently falls back to Raw.

## Frozen scientific contract

The implementation does not modify the frozen Training Edge v0.2 code, calibration, fit boundary, runtime package versions, or prediction semantics. The existing fingerprint remains the required downstream assertion:

- eligible rows: 256701
- fit date range: 2013-01-05 through 2025-12-28
- training semantic SHA-256: 4c59926f41cb213a924285743ffa5c923c5f08b2c0a1fa7b042cd633aa1c5d33
- C prediction SHA-256: 7a30ceb98e2f3bbad281f1aae88611cf51d503ef12eca4d0f639ca859becbe87
- CAB prediction SHA-256: 33d483132623ef8fd714e439702ad000dd3854be4674dc8c053137b9ff3ef250

## Required execution

Open an issue with title `[RL_T_HISTORICAL_WAREHOUSE_CUTOVER]` and a JSON body containing the accepted `manifest_id`, `audit_id`, all ten staging folder IDs, and `from_year=2010`, `to_year=2025`. The workflow downloads immutable assets, fetches Raw only for the dual-read audit, and publishes an evidence artifact.

After the workflow returns PASS, the historical branches of daily/replay/research workflows may be switched to Warehouse. Until then, Raw remains the documented rollback/audit route and no current pointer or Warehouse generation is changed.
