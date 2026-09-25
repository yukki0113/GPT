# RaceNote Forecast Gen0.2 Implementation Status — 2026-09-17

Status: IMPLEMENTED / NEVER ACTIVATED / SUPERSEDED BY GEN0.3

## 1. Purpose

Gen0-G000 / RaceNote-Forecast-Gen0.1 の50R検証後に確定したGen0.2方針を、Gen0.1を変更せず別versionとして実装した記録。

Historical planned activation (cancelled before activation):

- generation: `Gen0-G001`
- forecast: `RaceNote-Forecast-Gen0.2`
- factor set: `FSET-Gen0.2`
- firewall: `Gen0.2-Firewall-0.1`

2026-09-25: Gen0.2 was superseded before activation by
`RaceNote-Forecast-Gen0.3`. No Gen0.2 sample manifest or frozen Gen0-G001
forecast was created. `Gen0-G001` is now reserved for the first Gen0.3
activation.

Gen0-G001のsample manifestはまだ作成していない。台帳のcurrent generation / current forecast versionはGen0-G000 / Gen0.1のまま。

## 2. Implemented assets

- `src/racenote_gen0_2_input_firewall.py`
  - RaceNote v1.0をIndependent / JRDB Consensus / Marketへ物理分離
  - source / view semantic SHA-256
  - Independent view audit
- `src/racenote_forecast_gen0_2.py`
  - base/final probabilities
  - base snapshot hash
  - EdgeDB performance-only provenance
  - forecast freeze/hash/audit
  - post-freeze JRDB comparison
  - post-freeze market fair-odds / raw-EV projection
  - legacy ledger compatibility mapping
- `schema/racenote_forecast_gen0_schema_v0_2.json`
- `config/racenote_forecast_gen0_ledger_v0_2.json`
- `tests/test_racenote_gen0_2_input_firewall.py`
- `tests/test_racenote_forecast_gen0_2.py`
- `.github/workflows/jrdb_racenote_gen0_2_tests.yml`
- `docs/racenote/FORECAST_GEN0_2_DESIGN_20260917.md`
- `docs/racenote/FORECAST_GEN0_2_PREDICTION_CONTRACT_v0_2.md`

## 3. Hard boundaries implemented

Before RaceNote forecast Freeze:

- current JRDB IDM hidden
- current JRDB total/composite index hidden
- JRDB marks/ratings hidden
- JRDB current pace ranks / forecast finish position hidden
- current market/base odds/ranks hidden
- EdgeDB value signal hidden
- Training Edge not used
- target result/final market/payout forbidden

Forecast-visible proprietary overlay:

- EdgeDB `performance_signal` only
- as-of-safe provenance required when used/evaluated
- old fixed `0.02 * tier`, Good-gap gate, polarity axis-promotion rule not used

After RaceNote Freeze:

- JRDB consensus may be opened for comparison only; forecast mutation prohibited
- market may be opened for Fair Odds / Value research
- TE remains outside RaceNote forecast and is intended for newspaper/PWA side-by-side display and human purchase overlay

## 4. Probability contract

Every runner stores base and final:

- `p_win`
- `p_top2`
- `p_top3`
- rank

Validation checks nesting and race-level probability totals. Final rank 1 must be ◎ and must have maximum `p_win_final`.

Initial probabilities are uncalibrated model estimates and must later be evaluated with calibration, Brier Score and Log Loss.

## 5. Ledger implementation

Existing Gen0.1 tables remain unchanged. Added native Sheet tabs:

- `確率評価`
- `EdgeDB補正`
- `JRDB照合`
- `市場Snapshot`
- `馬券Plan`

`設定` contains `gen0.2.*` planned-state keys while `forecast.current_generation`, `forecast.version`, `factor_set.version` remain Gen0-G000 / Gen0.1.

`変更履歴` records `CHG-20260917-020` for this implementation. No frozen Gen0-G000 forecast was changed.

## 6. Verification

Local implementation tests: 6 passed before remote final compatibility patch.

GitHub Actions after compatibility patch:

- workflow: `JRDB RaceNote Gen0.2 tests`
- run: `35167443324`
- job/check: `105031594633`
- head: `2d2f0614720bfddfdc88d1d936a04f71b8349508`
- status: completed
- conclusion: success

The compatibility patch additionally guarantees:

- Gen0.2 `impact STRONG/MEDIUM/WEAK/NOT_USED` maps to existing ledger `importance HIGH/MEDIUM/LOW/NOT_USED`.
- `reader_view_version` and `firewall_version` remain distinct provenance fields.

## 7. Activation gate

Do not change current generation merely because implementation exists.

Before Gen0-G001 starts:

1. fix the next generation sample manifest before any prediction;
2. register the generation in `世代管理` / `対象Rキュー`;
3. explicitly activate Gen0-G001 / Gen0.2 settings;
4. confirm EdgeDB as-of policy for the chosen evaluation mode;
5. keep all Gen0-G000 records immutable.
