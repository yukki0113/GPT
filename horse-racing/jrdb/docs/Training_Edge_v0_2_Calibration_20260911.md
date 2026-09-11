# Training Edge v0.2 — Development Calibration Evidence

Date: 2026-09-11
Status: **DEVELOPMENT CALIBRATION COMPLETE / NOT FORWARD-CONFIRMED**

## 1. Purpose

This document validates the proposed v0.2 Edge representation after the A/B/C research decision.

The key design is:

```text
C_hat   = prediction from JRDB processed training baseline C
CAB_hat = prediction from C + same-horse vertical A + generic rotation/training-process B
training_edge_raw = CAB_hat - C_hat
```

The goal is to verify that `CAB_hat - C_hat` behaves like genuine incremental information rather than merely restating C.

## 2. Data and chronology

Source: `jrdb_training_research_2010_2023_development_lite_v0_1.sqlite`

- Eligible 2013-2023 rows: `214,833`
- Annual OOT test period: 2018-2023
- OOT rows: `112,766`
- 2024-2025 selected: `0`

For each test year Y, models were fit only on 2013..Y-1.

## 3. Implementation used for calibration

To make the v0.2 implementation explicit and computationally reproducible, this calibration uses:

- preprocessing family unchanged from prior work;
- `Ridge(alpha=1.0, solver='lsqr')`;
- C features only for the C model;
- C + A + B generic-process features for the CAB model;
- no trainer-history features;
- no explicit A×B interaction block.

The explicit `lsqr` solver is a v0.2 development implementation choice. Stage 2b used the default Ridge solver; the observed ranking results remain effectively the same while `lsqr` is materially faster and deterministic for repeated development scoring.

## 4. C / A / B decomposition

Mean annual Spearman across the six 2018-2023 OOT folds:

| Model | Mean Spearman | Mean increment vs C | Positive years vs C |
|---|---:|---:|---:|
| C | 0.167887 | — | — |
| C + A | 0.172358 | **+0.004471** | **6/6** |
| C + B | 0.213738 | **+0.045852** | **6/6** |
| C + A + B | **0.216640** | **+0.048753** | **6/6** |

The incremental gain from adding A on top of the B context is about `+0.002902` mean annual Spearman.

Interpretation:

- B is the larger incremental block.
- A remains independently positive and improves the B-enhanced model.
- A should therefore remain in the core rather than being dropped after B is added.

## 5. CAB vs C by year

| Year | C Spearman | C+A+B Spearman | Increment |
|---:|---:|---:|---:|
| 2018 | 0.181863 | 0.222227 | **+0.040364** |
| 2019 | 0.160738 | 0.202074 | **+0.041336** |
| 2020 | 0.159756 | 0.226115 | **+0.066360** |
| 2021 | 0.156632 | 0.203103 | **+0.046471** |
| 2022 | 0.177321 | 0.231953 | **+0.054632** |
| 2023 | 0.171010 | 0.214367 | **+0.043356** |

No OOT year reverses.

Pooled OOT:

- C Spearman: `0.167796`
- C+A+B Spearman: `0.216631`
- increment: **`+0.048835`**

## 6. Does the raw Edge predict what C misses?

Primary raw Edge:

```text
training_edge_raw = CAB_hat - C_hat
```

Observed pooled OOT properties:

- Spearman(`training_edge_raw`, actual Performance Delta): `0.135784`
- Spearman(`training_edge_raw`, actual Performance Delta - C_hat): **`0.143514`**

This is the important incremental test: the raw Edge ranks the residual that remains after the C prediction.

When `training_edge_raw` is split into deciles, using the C residual as the target:

- top-decile residual mean: `+0.013224`
- bottom-decile residual mean: `-0.025276`
- top-minus-bottom mean residual spread: **`+0.038500`**
- median residual spread: **`+0.030180`**
- `P(C residual > 0)` spread: **`+19.35 pt`**

## 7. Conditional independence check inside C strength bands

The OOT population was first split into 10 deciles by `C_hat`. Within each C decile, `training_edge_raw` was then split into quintiles and the top-vs-bottom C-residual spread was measured.

All 10 C bands were positive.

| C decile | Edge high-minus-low residual mean spread |
|---:|---:|
| 1 | +0.030998 |
| 2 | +0.035195 |
| 3 | +0.035029 |
| 4 | +0.033788 |
| 5 | +0.030300 |
| 6 | +0.033378 |
| 7 | +0.028792 |
| 8 | +0.027401 |
| 9 | +0.026311 |
| 10 | +0.026010 |

This supports the intended semantics: the A+B Edge continues to discriminate current-day over/under-performance even among horses receiving similar C baseline evaluations.

## 8. Raw Edge distribution

OOT `training_edge_raw` distribution:

- mean: `-0.001895`
- standard deviation: `0.011670`
- median: `-0.000960`
- raw zero empirical percentile: `53.586%`

Selected quantiles:

| Percentile | raw Edge |
|---:|---:|
| 1 | -0.034913 |
| 5 | -0.023053 |
| 10 | -0.016753 |
| 20 | -0.010667 |
| 25 | -0.008639 |
| 50 | -0.000960 |
| 75 | +0.006255 |
| 80 | +0.007956 |
| 90 | +0.012082 |
| 95 | +0.015120 |
| 99 | +0.020449 |

The full 0..100 percentile knot table is stored in:

`horse-racing/jrdb/config/training_edge_v0_2_calibration.json`

## 9. Index representation

The research/store layer must preserve:

```text
training_edge_raw
```

in Official RunPerf-delta units.

The display layer may additionally expose:

```text
training_edge_pct
```

computed by linear interpolation over the frozen empirical OOT percentile knots.

Important distinction:

- `training_edge_raw = 0` is mathematical neutrality versus C;
- `training_edge_pct = 50` is the historical median A+B increment.

Because the historical median is slightly negative, raw zero corresponds to about percentile `53.59`, not exactly 50.

Recommended public/API fields:

```text
training_edge_raw
training_edge_pct
training_edge_direction  # negative / neutral / positive from raw sign
```

Do not discard the raw value and do not force zero to percentile 50 by an arbitrary rescaling.

## 10. Controller conclusion

```text
A_CORE = CONFIRMED_AND_RETAIN
B_GENERIC_PROCESS_CORE = RETAIN
B_TRAINER_HISTORY = AUXILIARY_ONLY
B_EXPLICIT_INTERACTIONS = EXCLUDE_FROM_CORE
C = BASELINE_ONLY
TRAINING_EDGE_RAW = CAB_HAT_MINUS_C_HAT
TRAINING_EDGE_PERCENTILE_CALIBRATION = FROZEN_DEVELOPMENT_CALIBRATION
V0_2_FORWARD_CONFIRMATION = REQUIRED
PRODUCTION = NOT_YET_AUTHORIZED
```

The next step is implementation freeze of the v0.2 scorer followed by new temporal confirmation. 2024-2025 must not be relabeled as unopened v0.2 holdout.
