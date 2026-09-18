# Training Edge v0.2 — Daily Forward Implementation Status

Date: 2026-09-15

## Status

- `DAILY_FORWARD_IMPLEMENTATION = READY`
- `RUNTIME_FINGERPRINT = FROZEN_AND_ENFORCED`
- `DAILY_RUNTIME_TESTS = PASS`
- `FIRST_LIVE_FORWARD_DAY = NOT_YET_RUN`
- `POST_OOT_RETUNING = PROHIBITED`

The implementation is ready for the first genuinely pre-race business date after the 2026-09-13 OOT cutoff. Readiness here means the deterministic production path and handoff contract are implemented and tested; it does not mean the first live forward CSV has already been produced.

## Work-thread handoff

Daily generation, operational replay validation, artifact/audit retention, and Newspaper/PWA handoff are moved to a dedicated Work thread.

Canonical handoff document:

`horse-racing/jrdb/docs/Training_Edge_v0_2_Work_Handoff_20260915.md`

The first Work-thread validation is a retrospective operational replay for `2026-09-13`. It must emulate the pre-race boundary by using PACI through 2026-09-13 while excluding SED 2026-09-13 from the scoring input. This replay is not a new holdout and not the first live forward day. The production fail-closed rule that rejects a target date whose SED already exists must not be weakened for the replay.

## Implemented

- pre-race daily scorer: `src/score_training_edge_v0_2_daily.py`
- exact five-column Newspaper/PWA handoff
- development percentile display index `0.0-100.0`
- `ROUND_HALF_UP` to exactly one decimal
- complete target-day runner population; frozen-history-ineligible runner remains present with blank index
- raw/unrounded values and eligibility reasons isolated in audit JSON
- formal daily Issue/Actions route: `.github/workflows/jrdb_training_edge_v02_daily_issue.yml`
- target PACI required
- target SED must be absent, otherwise fail closed
- 2010-2025 history + settled 2026 history reconstructed before target scoring
- frozen scientific asset hash checks
- frozen runtime fingerprint validation before CSV generation
- output row/key/one-decimal validation

## Frozen runtime fingerprint

Canonical asset:

`config/training_edge_v0_2_runtime_fingerprint.json`

Formal runtime-freeze evidence:

- Issue `#975`
- run `34933935199`
- execution SHA `16f53078af35cce4de9d951e3924b0c02a598967`
- source boundary `2010-2025 only; no 2026 rows`
- eligible 2013-2025 fit rows `256701`
- fit dates `2013-01-05` through `2025-12-28`
- semantic SHA-256 `4c59926f41cb213a924285743ffa5c923c5f08b2c0a1fa7b042cd633aa1c5d33`
- C training-prediction SHA-256 `7a30ceb98e2f3bbad281f1aae88611cf51d503ef12eca4d0f639ca859becbe87`
- CAB training-prediction SHA-256 `33d483132623ef8fd714e439702ad000dd3854be4674dc8c053137b9ff3ef250`
- NumPy `2.5.3`
- pandas `3.0.5`
- SciPy `1.18.1`
- scikit-learn `1.9.1`

The daily CLI recomputes the runtime fingerprint from its projected 2013-2025 fit population and validates it against this asset before scoring. A mismatch fails closed before the handoff CSV is written.

## Daily runtime implementation test

Formal test evidence:

- Issue `#977`
- run `34941126889`
- head SHA `72e73cb32ec2d5b74d9f638c86d85fda2bcd6175`
- Python `3.12.14`
- fixed numerical runtime equal to the frozen fingerprint
- workflow conclusion `success`

Test results:

- `test_training_edge_v0_2_core.py`: `6 passed`
- `test_fingerprint_training_edge_v0_2_runtime.py`: `2 passed`
- `test_score_training_edge_v0_2_daily.py`: `3 passed`
- total: `11 passed`

The daily scorer test covers:

- one-decimal `ROUND_HALF_UP` display behavior;
- exact five-column complete-runner output;
- ineligible runner blank behavior;
- fit max year 2025;
- target result not required;
- runtime fingerprint exact-match PASS;
- intentional fingerprint drift hard failure.

Issue `#976` was the first registration attempt and also ultimately returned PASS after delayed workflow registration. Issue `#977` is retained as the clean retry evidence used above.

## Handoff

Final PWA/Newspaper file:

`独自指数_YYYYMMDD.csv`

```csv
date,venue_code,race_no,horse_no,training_edge_index
```

Identity key:

`date + venue_code + race_no + horse_no`

The Newspaper side should perform identity join only and should not recompute, rescale, fill blanks, or re-round the value.

## First live forward run

The first real run must use a target day whose PACI exists while the target-day SED/result is still absent. The formal route must be launched before the result becomes available and its CSV/audit artifact retained immutably.

Until that happens:

- implementation readiness is confirmed;
- scientific v0.2 remains frozen;
- no live-forward result claim is made.


## PACI input location update — 2026-09-18

Daily Forward and replay 2026 PACI inventory is now the public Drive folder `1zFajenPU5jxInZCcmqZzkgiaYil3MD8r`. The former folder `12lmU6_NZF24ixrB7MMMzzvcBNzbhQTr0` is retired for this route. The daily workflow must use the new folder; SED location is unchanged.
