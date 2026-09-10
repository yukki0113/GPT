# JRDB Training Research — Stage 1b / Stage 2 / Stage 3

Date: 2026-09-10

## Status

- Stage 1b: **WEAK_BUT_REPRODUCIBLE**
- Stage 2: **EXPLORATORY CANDIDATES FOUND / NO EDGE PROMOTION YET**
- Stage 3: **SELF-VERTICAL SIGNAL IS INCREMENTAL BUT WEAKER THAN KYI TRAINING SCORE**
- 2024-2025 predictive holdout: **NOT INSPECTED**

This report uses `jrdb_training_research_2010_2023_development_lite_v0_1.sqlite` only. The Lite DB physically contains 2010-2023 rows and therefore cannot expose 2024-2025 predictive outcomes.

## 1. Stage 1b — same-horse vertical workout comparison with Official RunPerf

### 1.1 Frozen feature

Current workout feature:

- CHA selected main workout `final_segment_sec`.

Comparable history:

```text
same horse_id
+ same CHA course_code
+ same furlong_count
+ strictly earlier race_date
```

Self percentile:

```text
final_self_pct =
  (count(prior final_sec > current final_sec)
   + 0.5 * count(prior final_sec == current final_sec))
  / prior comparable count
```

Higher = faster/better relative to the horse's own past comparable workouts.

Outcome:

```text
performance_delta =
  current official_runperf_raw
  - median(strictly-prior official_runperf_raw for same horse)
```

Primary development period: 2013-2023.
Minimum prior RunPerf count: 3.

### 1.2 Primary result, minimum comparable workouts >=3

Eligible rows: **214,833**
Eligible horses: **30,579**
Spearman(final_self_pct, performance_delta): **0.02997**

Fixed self-percentile bands:

| self percentile | n | mean Performance Delta | median Performance Delta | P(delta > 0) |
|---|---:|---:|---:|---:|
| 0-20% slow | 44,974 | -0.025632 | -0.014769 | 40.47% |
| 20-40% | 37,183 | -0.024434 | -0.013195 | 41.11% |
| 40-60% | 32,897 | -0.023128 | -0.013317 | 41.06% |
| 60-80% | 40,097 | -0.021081 | -0.011234 | 42.38% |
| 80-100% fast | 59,682 | -0.019050 | -0.009549 | 43.66% |

Fast 20% minus slow 20%:

- mean Performance Delta spread: **+0.006291**
- median spread: **+0.004893**
- positive-delta rate spread: **+2.967 pt**

### 1.3 History-count sensitivity

| minimum prior comparable workouts | n | Spearman | fast20-slow20 mean spread | median spread | positive-rate spread |
|---:|---:|---:|---:|---:|---:|
| 2 | 251,950 | 0.02792 | +0.005924 | +0.004392 | +2.661 pt |
| 3 | 214,833 | 0.02997 | +0.006291 | +0.004893 | +2.967 pt |
| 4 | 177,422 | 0.03324 | +0.006935 | +0.005132 | +3.243 pt |
| 5 | 148,961 | 0.03438 | +0.006888 | +0.005282 | +3.307 pt |
| 6 | 126,615 | 0.03531 | +0.007066 | +0.005738 | +3.578 pt |
| 8 | 93,559 | 0.03282 | +0.006509 | +0.005133 | +3.294 pt |
| 10 | 70,444 | 0.03450 | +0.006402 | +0.004928 | +3.205 pt |

The signal does not disappear as history increases. It modestly strengthens until roughly 6 prior comparable workouts and remains positive afterward.

### 1.4 Year stability

For minimum comparable workouts >=3, fast20-slow20 mean Performance Delta was positive in **all 11 development years, 2013-2023**.

Approximate yearly spreads:

- 2013 +0.00654
- 2014 +0.00804
- 2015 +0.00529
- 2016 +0.00495
- 2017 +0.00620
- 2018 +0.00525
- 2019 +0.00781
- 2020 +0.00764
- 2021 +0.00521
- 2022 +0.00585
- 2023 +0.00799

### 1.5 Within-horse paired comparison

Horses that experienced both fast20 and slow20 states: **14,417**.

Mean of horse-level `(fast-state mean delta - slow-state mean delta)`:

**+0.004784**

Median horse-level difference:

**+0.003471**

This supports a small within-horse state signal rather than only a cross-sectional horse-quality effect.

### Stage 1b disposition

`WEAK_BUT_REPRODUCIBLE`

The effect is too small for a stand-alone production Edge, but sufficiently stable to keep as a candidate component.

---

## 2. Stage 2 — trainer / rest / training-pattern exploration

This stage is exploratory. No discovered trainer pattern is promoted to EdgeDB in this report.

Because rest interval itself has a strong association with the within-horse RunPerf delta, trainer-pattern exploration first removes the broad rest-bucket mean from `performance_delta`.

### 2.1 Rest interval baseline

| rest days | n | mean Performance Delta | median | P(delta > 0) |
|---|---:|---:|---:|---:|
| <=20 | 63,395 | -0.011802 | -0.003116 | 47.94% |
| 21-34 | 90,942 | -0.015225 | -0.006284 | 45.78% |
| 35-62 | 59,766 | -0.023455 | -0.013520 | 41.19% |
| 63-119 | 55,634 | -0.027792 | -0.016203 | 39.52% |
| 120+ | 24,408 | -0.047516 | -0.032592 | 31.12% |

Therefore raw trainer/course comparisons without rest adjustment are not acceptable for Edge discovery.

### 2.2 Trainer x main-workout course candidates

Screening conditions:

- pattern n >=150
- observed years >=6
- comparison against same trainer's overall rest-adjusted residual
- year-level sign stability recorded

Notable positive exploratory candidates include:

| trainer | course | n | years | within-trainer residual effect | positive-year share |
|---|---|---:|---:|---:|---:|
| 福島信晴 | CW (12) | 200 | 6 | +0.01214 | 83.3% |
| 松永幹夫 | CW (12) | 393 | 11 | +0.01002 | 90.9% |
| 勢司和浩 | 南ポリ (10) | 297 | 11 | +0.00989 | 81.8% |
| 堀井雅広 | 美浦坂路 (01) | 174 | 10 | +0.00985 | 80.0% |
| 加用正 | CW (12) | 504 | 11 | +0.00914 | 81.8% |
| 新開幸一 | 南ポリ (10) | 202 | 8 | +0.00886 | 100.0% |
| 杉山晴紀 | CW (12) | 252 | 8 | +0.00827 | 87.5% |

These are discovery candidates only. Multiple-comparison risk remains substantial and the patterns need shrinkage / out-of-time confirmation before any EdgeDB registration.

### 2.3 Long-rest x polytrack check

A common heuristic that long-rest horses prepared mainly on polytrack may be underfinished was checked descriptively.

For rest >=120 days:

- CYB `only_polytrack` approximation: n=186, mean spread vs others **-0.00566**, positive-rate spread **-7.52 pt**.
- CHA main workout on polytrack (course 10 or 17): n=739, mean spread vs others **-0.00418**, positive-rate spread **-4.46 pt**.

However yearly signs are not stable. This is **not confirmed** as a robust rule.

### Stage 2 disposition

- Rest interval is a major confounder and must be controlled.
- Several trainer x course candidates deserve targeted confirmation.
- No trainer legend / heuristic is promoted yet.

---

## 3. Stage 3 — comparison with JRDB processed workout signals

Primary common population remains the Stage 1b population with minimum comparable workout history >=3.

### 3.1 Rank association with within-horse RunPerf delta

| signal | n | Spearman with Performance Delta | top20-bottom20 mean spread | positive-rate spread |
|---|---:|---:|---:|---:|
| self raw final-time percentile | 214,833 | **0.02997** | **+0.00629** | **+2.97 pt** |
| JRDB final-segment index | 214,833 | 0.01213 | +0.00420 | +0.77 pt |
| JRDB CHA workout index | 214,822 | -0.00595 | +0.00014 | -1.26 pt |
| CYB finish index | 214,833 | 0.02543 | +0.00752 | +2.37 pt |
| KYI training score | 214,307 | **0.16957** | **+0.03282** | **+19.68 pt** |
| week-ago workout index | 156,425 | -0.02431 | -0.00368 | -3.59 pt |

The KYI training score is materially stronger than the individual raw/JRDB workout-clock features for this target.

### 3.2 KYI training arrow

JRDB code definition:

- 1 = デキ抜群
- 2 = 上昇
- 3 = 平行線
- 4 = やや下降気味
- 5 = デキ落ち

Observed RunPerf-delta progression:

| arrow | n | mean delta | P(delta > 0) |
|---|---:|---:|---:|
| 1 | 4,891 | -0.00536 | 51.93% |
| 2 | 37,813 | -0.00997 | 49.67% |
| 3 | 165,759 | -0.02506 | 40.11% |
| 4 | 6,339 | -0.03871 | 35.27% |
| 5 | 31 | -0.06325 | 29.03% |

The monotonic ordering is strong, though category 5 is very sparse.

### 3.3 Is self vertical comparison redundant with KYI training score?

No.

Within each year-relative KYI-training-score decile, fast20-vs-slow20 self-workout comparison remained positive in all 10 deciles in this screen.

Weighted mean incremental self spread after KYI-score decile stratification:

- mean Performance Delta: **+0.00520**
- positive-rate spread: **+2.36 pt**

The incremental effect is larger in the lower/middle KYI-score bands and smaller at the highest bands.

A simple complete-case linear comparison also retains a positive coefficient for the self-percentile after including KYI training score, finish index, JRDB final-segment index and JRDB workout index. This is descriptive only, not a selected predictive model.

### Stage 3 disposition

- `KYI training score` is currently the strongest single processed training signal for the chosen within-horse RunPerf target.
- `final_self_pct` is much weaker but appears to carry additional information not fully contained in KYI training score.
- JRDB aggregate workout index alone is not superior to the simple same-horse final-time vertical feature for this target.
- A future Training Edge should probably be composite rather than replace KYI information with raw self-comparison.

---

## 4. Controller recommendation

Do not freeze a production Training Edge formula yet.

Recommended next research step:

1. keep `final_self_pct` as a candidate base feature;
2. perform targeted Stage 2 confirmation on a restricted, predeclared set of trainer/course and trainer/rest interactions;
3. test whether the self-vertical signal adds value to KYI training score / arrow in out-of-time development folds;
4. only after the development protocol is frozen, open 2024-2025 holdout once for final confirmation.

No odds, popularity or payout information was used in these stages.
