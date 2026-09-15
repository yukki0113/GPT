# Training Edge v0.2 — 2026 OOT Evidence

Date: 2026-09-15

## Status

- `2026_OOT_STATUS = OPENED_AND_CONSUMED`
- `FORWARD_EVIDENCE = POSITIVE`
- `V0_2_POST_OOT_RETUNING = PROHIBITED`
- `PRODUCTION_DEPLOYMENT = NOT_AUTOMATICALLY_AUTHORIZED`
- `FORMAL_PROMOTION_DECISION = NOT_DEFINED_BY_FREEZE`

This document records the first successful authorized 2026 OOT evaluation of frozen Training Edge v0.2.
It is evidence, not a tuning set.

The pre-OOT scientific contract remains the immutable source of the target, eligibility, feature blocks,
preprocessing, Ridge parameters, Training Edge definition, calibration, and reporting contract:

- `horse-racing/jrdb/docs/Training_Edge_v0_2_Freeze_20260915.md`
- Freeze commit: `1ae1b424597d391fdca57c8fe826d99df123221b`

No feature, target, eligibility rule, alpha, calibration knot, threshold, or category interpretation may be
changed in response to the results below while continuing to call the changed model Training Edge v0.2.

## 1. Execution provenance

Authorized Issue:

- Issue `#961`
- title: `[JRDB_TRAINING_V02_2026_OOT] 20260915-frozen-v02-drive2026-a1`

Successful Actions run:

- run ID: `34925686309`
- execution SHA: `a6818c0eb4986d23a277f098eaab7d1953113946`
- workflow: `.github/workflows/jrdb_training_edge_v02_2026_oot_issue.yml`
- artifact: `jrdb-training-v02-2026-oot-34925686309`
- artifact ID: `10380054377`
- artifact digest: `sha256:7a800f51dea478aba2c4a24d7adf87c89371f6c6ead41654bd8b33f21f02861d`

All execution gates completed successfully:

- `ANNUAL_FETCH = 0`
- `DRIVE = 0`
- `BUNDLE = 0`
- `INDEX = 0`
- `RUNPERF = 0`
- `PROJECT = 0`
- `EVALUATE = 0`

The earlier Issue `#857` / run `34565399143` did not open the 2026 metric because it failed before
projection/evaluation and recorded `evaluation={}`.

## 2. Input boundary and source integrity

Historical reconstruction:

- 2010–2025 authenticated annual JRDB Raw
- the annual acquisition path had already completed successfully in the pre-open failed run `#857`

2026 target-period input:

- public Drive PACI/SED route validated by Issue `#952`
- cutoff: `2026-09-13`
- PACI dates: 76
- SED dates: 76
- common dates: 76
- PACI-only dates: 0
- SED-only dates: 0
- latest common date: `2026-09-13`

The 2026 annual-compatible archive hashes matched the preflight contract exactly:

| kind | SHA-256 | members |
|---|---|---:|
| BAC | `f495cf3036cb4f129ea07bb805668c2ff276e8c695800d3e109e6771e224f9f8` | 76 |
| KYI | `7ca1a1eeea1835d0148cf20b409ebc7fcd7c7ba0c1a115d1f71a9fea9431c462` | 76 |
| SED | `07e231282e6b5d86d9085a83dcc9de1e836a0ea6bff1af47732bdc45af83ebed` | 76 |
| UKC | `c5f09d979d34db816723cf63f44afaf34243f95b94085a776de1f77371871413` | 76 |
| CHA | `164804bf36930e94399fbee384259270e8d309bbf54f6bb7b86d7c82f442ca29` | 76 |
| CYB | `e15ea92e4dcb4faffcb094a261d9d49d8d28185e06e62ecf26a8766247b19fd2` | 76 |

Projected Training Edge input:

- rows: `815,595`
- 2026 rows: `34,434`
- duplicate business keys: `0`
- future training rows: `0`
- SQLite integrity: `ok`
- projected DB SHA-256: `0221cbaf9977406b502ea86c942aaa434d6619e30c940c1f5302d257e2790902`

## 3. Frozen OOT population

- training period: `2013–2025`
- test year: `2026`
- training eligible n: `256,701`
- test eligible n: `15,276`
- test minimum date: `2026-01-04`
- test maximum date: `2026-09-13`

Leakage / holdout guards:

- `fit_max_year = 2025`
- `test_min_year = 2026`
- `test_max_year = 2026`
- `test_rows_in_fit = 0`
- `v0_1_2024_2025_holdout_reused_as_unopened = false`

All frozen chronology guards therefore passed.

## 4. Primary C vs C+A+B result

### C baseline

- Spearman vs PerformanceDelta: `0.1202404003`
- RMSE: `0.0953096803`
- top-decile minus bottom-decile mean target spread: `+0.0301836196`
- median target spread: `+0.0277447354`
- positive-rate spread: `+18.3901 pt`

### C+A+B frozen model

- Spearman vs PerformanceDelta: `0.1736779346`
- RMSE: `0.0947102417`
- top-decile minus bottom-decile mean target spread: `+0.0480924387`
- median target spread: `+0.0423218102`
- positive-rate spread: `+26.8979 pt`

### Frozen increment

- Spearman increment: `+0.0534375343`
- RMSE change: `-0.0005994386`
- mean top-bottom spread increment: `+0.0179088192`
- positive-rate top-bottom spread increment: `+8.5079 pt`

The primary forward result is therefore positive on both frozen headline metrics:
rank correlation improves materially and RMSE improves rather than trading accuracy for ranking.

## 5. Training Edge residual evidence

Frozen raw Training Edge is:

`training_edge_raw = CAB_hat - C_hat`

2026 OOT:

- raw Edge vs C residual Spearman: `0.1323600139`
- raw Edge vs target Spearman: `0.1286290358`
- raw mean: `-0.0014684020`
- raw sample SD: `0.0113412725`
- raw zero-or-positive rate: `47.3553%`
- negative: `8,042`
- neutral: `0`
- positive: `7,234`

Raw-Edge deciles evaluated against C residual show:

- bottom decile mean residual target: `-0.0231130024`
- top decile mean residual target: `+0.0134014560`
- top-bottom mean residual spread: `+0.0365144583`
- bottom decile positive rate: `47.7749%`
- top decile positive rate: `64.1361%`
- top-bottom positive-rate spread: `+16.3613 pt`

The middle deciles contain small local inversions, but the broad ordering is strongly directional and the
extreme spread is positive. This is evidence that the frozen A+B augmentation contains information beyond
the C baseline rather than merely reproducing the baseline ranking.

The development-derived percentile transform is monotonic, so its decile ordering reproduces the same
2026 residual-decile table. The 2026 outcomes were not used to recompute percentile knots.

## 6. Relation to development evidence

Stage2b development had selected the simple generic-pattern M1-style structure because it captured nearly
all of the more complex M4 gain without trainer-specific complexity.

Development M1 Spearman increment over M0 was approximately `+0.01752` with RMSE improvement.
The frozen 2026 OOT Spearman increment is `+0.05344`, about 3.05 times that development increment, and the
RMSE improvement is also larger in magnitude.

This comparison is descriptive only. It is not a basis for changing the model, calibration, or threshold.

## 7. Interpretation discipline

The allowed conclusion from this run is:

**Frozen Training Edge v0.2 receives positive forward evidence on 2026-01-04 through 2026-09-13.**

The run supports all of the following factual statements:

1. C+A+B outperformed C alone in frozen OOT Spearman.
2. C+A+B also improved frozen OOT RMSE.
3. C+A+B increased top-bottom target separation.
4. raw Training Edge correlated positively with the C residual.
5. extreme raw-Edge residual deciles separated in the intended direction.
6. no 2026 test row entered the fit.

The Freeze did not preregister a numerical promotion threshold or a production-deployment decision rule.
Therefore this document does **not** retroactively create one and does not label production deployment as
automatically approved.

Any production consumer decision should be versioned separately from this scientific confirmation record.

## 8. Irreversible post-open rules

From this run onward:

- 2026 may never again be described as an unopened Training Edge v0.2 holdout;
- v0.2 may not be retuned against these 2026 outcomes and then reuse 2026 as fresh evidence;
- any changed feature set, coefficient policy, model family, calibration, threshold, or semantics is a new
  version/candidate;
- the v0.2 Freeze and this evidence document remain immutable historical evidence;
- trainer-specific patterns remain auxiliary unless a separately preregistered future experiment changes
  that policy using genuinely new evidence.

## 9. Canonical result source

Canonical machine-readable evidence remains the successful Issue `#961` result and Actions artifact:

- `training_edge_v0_2_2026_oot.json`
- `workflow_result.json`
- run `34925686309`

This Markdown document is the human-readable evidence summary and must not replace the machine-readable
artifact for exact audit/reproduction.
