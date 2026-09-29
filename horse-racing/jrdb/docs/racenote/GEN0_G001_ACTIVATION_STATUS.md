# RaceNote Gen0-G001 Activation Status

Status: **PAUSED BEFORE ACTIVATION / FORECAST LOGIC UNFROZEN**

Last updated: 2026-09-29

## Current interpretation

Gen0-G001 was prepared while `RaceNote-Forecast-Gen0.3` was being treated as
the next activation candidate. That interpretation is no longer current.

The project has fixed the RaceNote extraction / evidence layer and the
pre-result research discipline, but **has not yet selected the detailed
Forecast decision logic to adopt for Gen0**.

Therefore:

- `RaceNote-Forecast-Gen0.3` is an implemented **research candidate**, not the adopted Gen0 logic.
- `Gen0-G001` must not be activated merely by running one TRUE_FORWARD Freeze.
- `forecast.current_generation` remains `Gen0-G000`.
- the G001 sample manifest, ledger registration, and transport smokes are retained as valid infrastructure / reproducibility evidence.
- activation planning resumes only after a Forecast logic version is explicitly selected through blinded historical research.

## What is fixed now

The following are current project-level invariants and are independent of the
eventual detailed prediction logic.

- RaceNote is the result-independent evidence layer.
- target result / final market / prohibited post-race data must remain hidden before Freeze.
- historical evidence must satisfy the target-date as-of boundary.
- prediction artifacts are immutable after Freeze.
- result acquisition and evaluation occur only after Freeze.
- historical tuning and TRUE_FORWARD validation are separate.
- old prediction artifacts are never rewritten after seeing results.

## What is NOT fixed now

The following remain research variables rather than Gen0 defaults.

- evidence reading priority such as `DATA/TRENDS > RACEREVIEW >= ABILITY`
- whether All-Runner Synthesis is mandatory
- whether Pairwise is mandatory
- whether SLOW / MEDIUM / FAST Scenario Robustness is mandatory
- how Trend / RaceReview / Ability conflicts are resolved
- whether EdgeDB Performance participates pre-Freeze
- confidence semantics beyond the minimum audit record
- probability generation
- detailed mark policy / axis-selection logic
- any numeric weight or score
- prompt wording used to choose ◎ / ○ / ▲ / △

Gen0.3 may be evaluated as one candidate against simpler or alternative
Forecast readers.

## Preserved G001 preparation evidence

The deterministic sample manifest remains valid as a historical research asset.

- Issue: #1594
- Run: `36499756053`
- Artifact ID: `11004733178`
- Artifact: `racenote-gen0-g001-manifest-36499756053`
- status: PASS
- manifest ID: `Gen0-G001-3fcca49d7610`
- manifest SHA-256:
  `3fcca49d76107b91214be08673e1ddd8797733f1a2445d5e67aead86520d2061`
- candidate pool SHA-256:
  `ca76f8979bcb08c14a8f5b7664fe957651f2bfaa9719f4fd42e8c3c26e0a63d6`
- PRIMARY: 50
- RESERVE: 20
- source: Analysis v1.4 Parquet canonical

The queue registered in `RaceNote Forecast Gen0 検証台帳` is retained for
reproducibility. Its previous `READY` label must not be interpreted as
"Forecast logic adopted and ready to activate".

## Preserved transport evidence

The single-race Gen0.3 Prepare transport remains valid engineering evidence.

- Issue: #1597
- Run: `36501017523`
- status: PASS
- artifact ID: `11005616447`
- artifact: `racenote-gen0-3-prepare-36501017523`

This proves the artifact-only / generation-bound transport path can work.
It does **not** establish Gen0.3 as the adopted prediction logic.

## Next gate

The next project gate is **Forecast logic selection**, not TRUE_FORWARD activation.

Use the 2026 PACI blinded historical backtest lane to compare prediction
approaches while preserving the common RaceNote / firewall / Freeze /
evaluation infrastructure.

Only after a detailed Forecast logic version is explicitly selected should a
new activation candidate be declared. At that point:

1. bind the selected logic version to a generation,
2. define its historical validation evidence,
3. define its TRUE_FORWARD activation gate,
4. update the ledger and current-generation plan explicitly.

Do not silently reuse the old G001 READY interpretation.
