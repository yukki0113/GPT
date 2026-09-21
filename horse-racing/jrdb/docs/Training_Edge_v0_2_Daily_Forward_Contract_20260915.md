# Training Edge v0.2 — Daily Forward Contract

Date: 2026-09-15

## Status

- `MODEL = Training Edge v0.2 frozen`
- `2026_OOT_STATUS = OPENED_AND_CONSUMED`
- `FORWARD_MODE = ACTIVE_AFTER_2026-09-13`
- `POST_OOT_RETUNING = PROHIBITED`
- `MARKET_FIELDS = PROHIBITED`
- `RUNTIME_FINGERPRINT = FROZEN`
- `PRODUCTION_DEPLOYMENT = NOT_AUTOMATICALLY_AUTHORIZED`

This document defines the operational path that produces one pre-race Training Edge index file for a JRA business date. It does not change the scientific v0.2 model.

Scientific source of truth:

- `Training_Edge_v0_2_Freeze_20260915.md`
- Freeze commit `1ae1b424597d391fdca57c8fe826d99df123221b`
- `Training_Edge_v0_2_2026_OOT_Evidence_20260915.md`

Operational runtime source of truth:

- `config/training_edge_v0_2_runtime_fingerprint.json`
- runtime-freeze Issue `#975`
- runtime-freeze run `34933935199`
- runtime-freeze execution SHA `16f53078af35cce4de9d951e3924b0c02a598967`
- source boundary: 2010-2025 only; no 2026 rows

## 1. Daily boundary

The user-facing new input for one run is the target business date / target PACI snapshot.

Internally the scorer also needs historical state because v0.2 contains strictly-prior features:

- prior same-horse Official RunPerf history;
- prior same-horse comparable CHA course + furlong history;
- previous race-gap history;
- frozen 2013-2025 model-fit population;
- frozen development percentile calibration.

The target race result is never required for scoring.

For the correctness-first reference implementation, the historical state is deterministically reconstructed from the audited JRDB history and settled SED available before the target race. This is intentionally heavier than a cached incremental implementation. A future cache/state optimization is permitted only if its outputs are regression-identical to this reference path and the scientific assets remain unchanged.

## 2. PWA / Newspaper handoff CSV

Canonical filename:

`独自指数_YYYYMMDD.csv`

Canonical columns, in this exact order:

```csv
date,venue_code,race_no,horse_no,training_edge_index
```

Identity key:

`date + venue_code + race_no + horse_no`

Rules:

- `date`: ISO `YYYY-MM-DD`;
- `venue_code`: two-character JRDB venue code;
- `race_no`: integer 1-12;
- `horse_no`: integer horse number;
- `training_edge_index`: frozen development percentile on 0-100 scale;
- display value is rounded to exactly one decimal using `ROUND_HALF_UP`;
- example: `73.46 -> 73.5`;
- every target-day runner is emitted;
- when frozen pre-race history eligibility is not satisfied, the row remains present and `training_edge_index` is blank.

The five-column CSV is a display/join boundary. It deliberately does not expose raw Edge or model internals.

## 3. Audit output

Every daily CSV must be accompanied by a machine-readable audit JSON containing, per runner:

- exact race identity;
- eligibility and ineligible reason;
- prior RunPerf count;
- prior comparable-workout count;
- `final_self_pct`;
- unrounded `training_edge_raw`;
- unrounded development percentile;
- one-decimal display value;
- direction.

The audit also records source hashes, scorer/core versions, fit-year guard, target date, and confirms that target result and market fields are not required/used.

The daily CLI must additionally record the runtime-fingerprint validation result. No CSV is written when the runtime guard fails.

## 4. Frozen scoring semantics

The daily scorer imports the frozen v0.2 assets rather than copying or redefining them:

- `src/training_edge_v0_2_core.py`
- `src/evaluate_training_edge_v0_2_oot.py` chronology / feature-materialization helpers
- `config/training_edge_v0_2_calibration.json`

Model fit remains fixed to eligible 2013-2025 rows.

For a target runner, pre-race score eligibility requires:

- prior same-horse Official RunPerf count >= 3;
- prior same-horse comparable workout count >= 3;
- `final_self_pct` available.

Current-day `performance_delta` is not an eligibility condition because the result does not yet exist.

The score is:

`training_edge_raw = CAB_hat - C_hat`

and the reader-facing index is the frozen development percentile transform of that raw value.

## 5. Runtime fingerprint freeze

The scientific model Freeze fixes feature/model semantics. The runtime fingerprint additionally freezes the operational realization of the 2013-2025 fit population.

The expected runtime values were generated once from 2010-2025 only, before daily forward use:

- eligible fit rows: `256701`;
- fit date range: `2013-01-05` through `2025-12-28`;
- semantic SHA-256: `4c59926f41cb213a924285743ffa5c923c5f08b2c0a1fa7b042cd633aa1c5d33`;
- C training-prediction SHA-256: `7a30ceb98e2f3bbad281f1aae88611cf51d503ef12eca4d0f639ca859becbe87`;
- CAB training-prediction SHA-256: `33d483132623ef8fd714e439702ad000dd3854be4674dc8c053137b9ff3ef250`;
- prediction normalization: 12 decimals;
- NumPy `2.5.3`;
- pandas `3.0.5`;
- SciPy `1.18.1`;
- scikit-learn `1.9.1`.

`src/score_training_edge_v0_2_daily.py` runs this validation before daily scoring. A mismatch in the fit rows, semantic inputs, fitted C/CAB predictions, or numerical package versions is a hard failure. This is an operational reproducibility guard, not a new model-selection step.

## 6. Forward integrity guards

A formal forward daily run must fail closed when any of the following occurs:

- frozen scientific asset hash mismatch;
- runtime fingerprint mismatch;
- target PACI is absent;
- target-day SED/result is already present in the input acquisition path;
- target date is absent from Index Base / projection;
- duplicate `date + venue_code + race_no + horse_no` output key;
- CSV row count differs from the target runner count;
- any nonblank display index is outside 0.0-100.0 or is not exactly one decimal;
- model fit contains a year after 2025.

This preserves a genuine pre-result forward record.

## 7. Current reference execution route

Entrypoint:

`.github/workflows/jrdb_training_edge_v02_daily_issue.yml`

Issue prefix:

`[JRDB_TRAINING_V02_DAILY]`

Issue body:

```json
{"date":"20260919"}
```

Reference flow:

```text
target date
  -> resolve public Drive 2026 PACI / settled SED inventory
  -> require target PACI
  -> require target SED absent
  -> fetch authenticated audited annual JRDB history 2010-2025
  -> bundle 2026 PACI through target / SED through latest settled date
  -> build Index Base
  -> build EXPANDING RunPerf + Official RunPerf
  -> project Training Edge v0.2 input
  -> verify frozen 2013-2025 runtime fingerprint
  -> fit frozen 2013-2025 C and CAB models
  -> score target pre-race rows
  -> frozen development percentile
  -> ROUND_HALF_UP to one decimal
  -> `独自指数_YYYYMMDD.csv`
  -> full audit JSON
  -> artifact + Issue result
```

The first implementation intentionally uses this full deterministic path as the reference oracle. Incremental state caching can be added later as an execution optimization, not as a new model.

## 8. Newspaper / PWA responsibility boundary

This module does not modify the Newspaper JSON itself.

The Newspaper/PWA consumer receives `独自指数_YYYYMMDD.csv`, joins by the canonical four-part identity key, and may expose the one-decimal value in its compact smartphone layout.

The consumer must not:

- recompute Training Edge;
- rescale the index from current-day runners;
- add odds/popularity information to the score;
- fill an ineligible blank with an inferred value;
- change the one-decimal value after handoff except normal string/number serialization preserving the same numeric value.

## 9. Post-race forward ledger

After SED becomes available, the result may be joined into a separate forward-validation ledger. The daily pre-race CSV and audit remain immutable evidence.

Post-race evaluation may summarize forward performance over accumulated races, but may not retune v0.2 and then reuse those same races as fresh evidence.


## 10. Historical Warehouse migration status — 2026-09-21

Project policy now designates JRDB Warehouse as the standard Historical input for
2010–2025. The frozen RL-T/Training Edge scientific semantics do not change.

The current daily workflow still reconstructs its 2010–2025 segment from annual Raw.
That Historical segment must not be switched by path substitution alone. Cutover is
gated on a Warehouse-to-existing-Index-Base compatibility adapter plus formal
Raw-vs-Warehouse logical equivalence and downstream runtime-fingerprint non-regression.
Until that gate passes, Raw remains the reference/rollback/audit route.

The 2026 route remains exactly as defined above: target PACI plus settled SED/Raw.
No 2026 PACI normalization or scientific/model change is authorized by this migration.

See: `docs/RL_T_Historical_Warehouse_Migration_Work_Request_20260921.md`.
