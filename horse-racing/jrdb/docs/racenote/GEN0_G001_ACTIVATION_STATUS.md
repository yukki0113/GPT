# RaceNote Gen0-G001 Activation Status

Status: **READY / TRUE_FORWARD FREEZE PENDING**

Last updated: 2026-09-29

## Contract

- Forecast: `RaceNote-Forecast-Gen0.3`
- Planned generation: `Gen0-G001`
- current operational generation remains: `Gen0-G000`
- activation requires the first formal TRUE_FORWARD pre-result Freeze PASS

## Fixed sample manifest

The deterministic Gen0-G001 sample manifest was generated from validated
Analysis v1.4 Parquet canonical data.

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
- seed: `GEN0-G001-SEED-001`
- PRIMARY: 50 races
- RESERVE: 20 races
- unique race keys: 70
- result columns selected for sampling: false

Source identity:

- Analysis generation:
  `analysis-v1_4-canonical-20260928-02`
- Analysis manifest SHA-256:
  `e9c391e76fac86a15526e8ab453558e68fc00400a18674e26edf64aad9feec9e`
- schema: v1.4
- storage: Parquet

The full ordered 70-race queue is registered in the operational Google Sheets
ledger. The manifest ID / SHA / seed / pool SHA above bind that queue to the
formal Actions artifact.

## Ledger registration

Spreadsheet: `RaceNote Forecast Gen0 検証台帳`

Spreadsheet ID:
`1z9TJQJ61WEcrVSDxhAWP9D48plP1ixU0hCH-QGZrhnU`

- `世代管理`: Gen0-G001 registered as `READY`
- `対象Rキュー`: rows A72:Y141, 70 races
- PRIMARY rows: 50
- RESERVE rows: 20
- frozen races: 0
- evaluated races: 0
- `forecast.current_generation`: intentionally remains `Gen0-G000`
- sampler version: `0.2.0`
- sampler source: validated Analysis v1.4 Parquet current

## Single-race Prepare transport

The formal single-race Gen0.3 prepare path is now artifact-only and generation-bound.

- workflow: `.github/workflows/racenote_gen0_3_realdata_prepare.yml`
- RaceNote source: explicit GitHub Actions run + artifact
- RaceReview source: explicit GitHub Actions run + artifact
- RaceReview generation: explicit expected generation, fail-closed on mismatch
- direct Actions -> Google Drive transport: prohibited / absent

Regression evidence:

- Issue: #1597
- Run: `36501017523`
- status: PASS
- artifact ID: `11005616447`
- artifact: `racenote-gen0-3-prepare-36501017523`
- target used only for routing regression: 2026-09-13 中山10R 初風ステークス
- runners: 10
- RaceReview generation:
  `jrdb_race_review_v0_1_incremental_g36094708797`

This smoke is transport / evidence-preparation evidence only. It does not
activate Gen0-G001 and must not be treated as a new TRUE_FORWARD prediction.

## Remaining activation gate

Only the first formal TRUE_FORWARD Freeze remains.

Until that run passes:

- do not change `forecast.current_generation` to Gen0-G001
- do not mark Gen0-G001 `ACTIVE`
- do not acquire the target race result before Freeze
- do not open current market / current JRDB consensus / Edge Value / RL-Value
  before Freeze
- do not tune Gen0.3 from the one-race Hatsukaze dry-run result

After the first formal TRUE_FORWARD Freeze PASS, update the generation ledger,
current-generation setting, and this document in the same activation change.
