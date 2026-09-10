# JRDB Training Research — Walk-forward continuation

Date: 2026-09-10

## Status

- 2024-2025 predictive holdout: **NOT INSPECTED**
- Stage 1b self-vertical signal: **RETAIN**
- Generic trainer-course score: **DO NOT PROMOTE**
- Rest interval: **RETAIN AS CORE CONTEXT**
- Trainer-pattern research: **CONTINUE ONLY WITH STRICT OOT CONFIRMATION**

This continuation uses only `jrdb_training_research_2010_2023_development_lite_v0_1.sqlite`.

## 1. Why this continuation was needed

The previous Stage 2 report listed trainer x workout-course candidates using the full 2013-2023 development period. Those are useful discoveries, but selecting and evaluating a pattern on the same entire period creates selection bias.

This continuation therefore imposes a stricter split:

- discovery: 2013-2017
- confirmation: 2018-2023

Rest interval is adjusted first because the previous stage showed a strong broad relationship between layoff length and within-horse Official RunPerf delta.

Outcome remains:

```text
performance_delta =
  current official_runperf_raw
  - median(strictly-prior official_runperf_raw for same horse)
```

## 2. Trainer x workout-course discovery and confirmation

Discovery screening requirements:

- 2013-2017 only
- n >= 100
- observed years >= 4
- positive within-trainer, rest-adjusted residual effect
- positive-year share >= 75%

This produced **75 discovery candidates**.

Confirmation requirements on 2018-2023:

- n >= 100
- observed years >= 4
- positive validation effect
- positive-year share >= 2/3

Only **17 / 75** discovery candidates satisfied the confirmation rule.

Examples that survived include:

| trainer | course | discovery n | discovery effect | validation n | validation effect | validation positive-year share |
|---|---|---:|---:|---:|---:|---:|
| 須貝尚介 | 25 | 128 | +0.02224 | 108 | +0.01207 | 66.7% |
| 松永幹夫 | CW (12) | 148 | +0.02162 | 304 | +0.00306 | 66.7% |
| 加藤和宏 | 美浦坂路 (01) | 176 | +0.01170 | 497 | +0.00137 | 66.7% |
| 加用正 | CW (12) | 305 | +0.00998 | 293 | +0.00559 | 83.3% |
| 中野栄治 | 南W (02) | 198 | +0.00748 | 362 | +0.00663 | 83.3% |
| 高木登 | 南W (02) | 262 | +0.00637 | 596 | +0.00297 | 83.3% |
| 藤原英昭 | CW (12) | 488 | +0.00452 | 418 | +0.00354 | 66.7% |
| 宗像義忠 | 南W (02) | 598 | +0.00334 | 592 | +0.00375 | 83.3% |
| 国枝栄 | 南W (02) | 704 | +0.00041 | 765 | +0.00313 | 83.3% |

Several plausible-looking discovery candidates reversed in confirmation. Therefore a trainer-course "legend" must not be accepted from pooled retrospective results alone.

## 3. Generic strictly-prior trainer-pattern scores

To avoid hard-coding named trainers, strictly prior-year pattern scores were also created. For every target year, only earlier development years were used to estimate a shrunk trainer interaction effect.

Dimensions screened:

- trainer x CHA course
- trainer x rest bucket
- trainer x CYB training type
- trainer x CHA course x rest bucket

2018-2023 mean Spearman association with `performance_delta`:

| strictly-prior pattern score | mean Spearman | positive years / 6 |
|---|---:|---:|
| trainer x CHA course | +0.0066 | 4/6 |
| trainer x rest bucket | ~0.0000 | 2/6 |
| trainer x CYB training type | +0.0097 | 6/6 |
| trainer x course x rest | +0.0064 | 4/6 |

The trainer x CYB training-type score is the most stable of these generic trainer interactions, but the effect is still very small.

Conclusion: generic trainer-pattern history does **not** currently justify a material standalone Edge component.

## 4. Walk-forward processed-training baseline and self-vertical increment

A fixed Ridge model was evaluated year-by-year. Each test year is predicted using only prior development years.

Processed JRDB baseline features:

- KYI training score
- KYI training arrow one-hot
- CYB finish index
- JRDB final-segment index
- JRDB CHA workout index

Self-vertical feature:

- `final_self_pct` from Stage 1b

Rest context:

- fixed rest-day buckets: <=20, 21-34, 35-62, 63-119, 120+, missing

### 4.1 Spearman by test year

| year | processed | + self vertical | + rest | + rest + self vertical |
|---:|---:|---:|---:|---:|
| 2018 | 0.18190 | 0.18607 | 0.20789 | 0.20973 |
| 2019 | 0.16109 | 0.16622 | 0.18218 | 0.18554 |
| 2020 | 0.15992 | 0.16836 | 0.19730 | 0.20339 |
| 2021 | 0.15664 | 0.15948 | 0.18129 | 0.18370 |
| 2022 | 0.17747 | 0.18069 | 0.20694 | 0.20913 |
| 2023 | 0.17092 | 0.17394 | 0.19910 | 0.20246 |

Mean Spearman:

- processed JRDB baseline: **0.16799**
- processed + self vertical: **0.17246**
- processed + rest: **0.19578**
- processed + rest + self vertical: **0.19899**

The self-vertical feature improves ranking in **all six 2018-2023 test years**, both before and after explicit rest adjustment.

Mean RMSE also changes in the expected direction:

- processed: 0.087006
- processed + self: 0.086965
- processed + rest: 0.086566
- processed + rest + self: 0.086523

The gain is small, but it is consistent.

## 5. Does generic trainer-course history add to the model?

No meaningful aggregate increment was found.

Adding the strictly-prior shrunk trainer x course score to `processed + self` leaves yearly Spearman essentially unchanged. Adding it on top of `processed + rest + self` also changes results only at the fourth decimal level.

Therefore:

- named trainer/course combinations may exist and some survive split confirmation;
- but a generic trainer-course historical score is currently too weak for automatic use;
- broad rest context is much more robust;
- same-horse workout vertical comparison retains a small incremental signal.

## 6. Updated controller interpretation

The evidence now supports a clearer hierarchy for a future Training Edge:

1. **JRDB processed training information, especially KYI training score / arrow** — strong base signal.
2. **Rest / rotation context** — large, highly stable contextual signal and necessary confounder control.
3. **Same-horse comparable-workout vertical feature (`final_self_pct`)** — weak but reproducible incremental signal.
4. **Trainer interaction patterns** — exploratory; use only individually confirmed or heavily regularized signals. Do not promote pooled retrospective legends.

A reasonable next development step is to build a compact candidate Training Edge from levels 1-3, evaluate it with strictly out-of-time 2018-2023 folds, and only then decide whether any Stage 2 trainer interactions deserve inclusion before freezing a protocol for the unopened 2024-2025 holdout.

No odds, popularity or payout data were used.
