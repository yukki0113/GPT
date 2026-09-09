# RaceNote v1.0 Edge Blind Settlement — 2026-08-09 / 08-15 / 08-22

Status: **SETTLED / PROSPECTIVE BLIND BLOCK**

## 1. Blind boundary

- Target: 2026-08-09 / 08-15 / 08-22, 3 venues × 12R = **108 races**.
- Prediction freeze payload SHA-256: `dab3ab1502d049d7bb1957991bf7ab7c16612d591318579f445a8fa4ba87863b`.
- Freeze manifest was committed to GitHub main as `01367a6e1a44d46d508ec318b852259aa4200dc5` before target HJC acquisition.
- Pre-result Edge matching used exact PACI / Analysis Lite / ACTIVE Registry inputs and source-equivalent canonical Matcher logic. It is `PRE_RESULT_RECONSTRUCTION` research evidence, not TRUE_FORWARD.
- No SED/HJC/result data was consulted while generating or freezing the marks.

## 2. Main result

| Policy | ◎ win | ◎ top2 | ◎ top3 | ◎ win ROI | Q2 hits | Q2 ROI | Q4 ROI | Trio A6 ROI | Trio B5 ROI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v0.2 reconstructed control | 40/108 (37.04%) | 56/108 (51.85%) | 70/108 (64.81%) | 103.80% | 31 | 98.75% | 88.84% | 100.60% | 102.17% |
| v1.0-R Edge ranking | 41/108 (37.96%) | 57/108 (52.78%) | 71/108 (65.74%) | 104.81% | 33 | 86.30% | 87.38% | 98.67% | 73.28% |
| v1.0-V value role | 41/108 (37.96%) | 57/108 (52.78%) | 71/108 (65.74%) | 104.81% | 33 | 86.30% | 87.38% | 98.67% | 73.28% |

### v1.0-R vs v0.2

- ◎勝率: **37.04% → 37.96%** (+1 win, +0.92pp)
- ◎連対率: **51.85% → 52.78%** (+1)
- ◎複勝圏率: **64.81% → 65.74%** (+1)
- ◎単勝回収率: **103.80% → 104.81%**
- Q2 hit races: **31 → 33**; Q2 ROI: **98.75% → 86.30%**

The Edge ranking slightly improved axis hit performance and single-win economics, but did not improve pooled ticket economics in this block.

## 3. Seven changed-axis races

| Date | Race | v0.2 ◎ | Tier | v1.0-R ◎ | Tier | v0.2 result | Edge result |
|---|---|---|---:|---|---:|---|---|
| 2026-08-09 | 札幌2R | 6 カッサンドラ | +0 | 5 スイーヴル | +1 | out | 1st / win 210 |
| 2026-08-15 | 新潟11R | 2 コンフィアンサ | -2 | 18 ラウンドヒル | +2 | out | top3 |
| 2026-08-15 | 札幌7R | 3 ミッキーテネシー | +0 | 1 メリザンド | +2 | out | out |
| 2026-08-15 | 札幌9R | 3 アヴィアトーレ | +0 | 8 デアグランツ | +1 | out | 1st / win 330 |
| 2026-08-22 | 中京3R | 3 アロマフェリス | +0 | 7 スノースケープ | +1 | top3 | out |
| 2026-08-22 | 中京11R | 4 イルミナジーティー | +0 | 3 セルヴァジオ | +1 | top3 | out |
| 2026-08-22 | 札幌10R | 9 アスミル | -1 | 10 ミキノバカラ | +1 | 1st / win 430 | top3 |

Changed-axis direct comparison: **new 2 wins vs old 1 win**, top2 **2 vs 1**, top3 **4 vs 3**. Single-win return on only these seven races was **61.43% → 77.14%**.

The effective sample is only seven races. This is directionally positive but far too small for promotion by itself.

## 4. Q2 decomposition

Q2 changed payout in six races. The Edge policy produced four newly hitting races and lost two old hits:

| Date | Race | v0.2 Q2 payout | v1.0-R Q2 payout | Delta |
|---|---|---:|---:|---:|
| 2026-08-09 | 新潟8R | 0 | 690 | +690 |
| 2026-08-09 | 札幌2R | 0 | 350 | +350 |
| 2026-08-15 | 札幌3R | 2,670 | 0 | -2,670 |
| 2026-08-15 | 札幌9R | 0 | 500 | +500 |
| 2026-08-22 | 新潟2R | 0 | 950 | +950 |
| 2026-08-22 | 札幌7R | 2,510 | 0 | -2,510 |

- Added hits: 690 + 350 + 500 + 950 = **2,490 yen**.
- Lost hits: 2,670 + 2,510 = **5,180 yen**.
- Net Q2 payout change: **-2,690 yen**.

This is an important separation: Performance Edge improved the number of Q2 hits, but the lost tickets were higher-paying. The Performance signal is not a value signal, so the result is coherent with the design rather than evidence that one signal should do both jobs.

## 5. PerformanceEdgeTier diagnostic

### All 1,459 runners

| Tier | N | Win | Top2 | Top3 | Win ROI |
|---:|---:|---:|---:|---:|---:|
| -2 | 139 | 4.32% | 10.79% | 15.83% | 56.40% |
| -1 | 225 | 5.78% | 12.00% | 16.00% | 73.69% |
| +0 | 503 | 7.95% | 16.50% | 23.66% | 55.47% |
| +1 | 330 | 9.09% | 16.06% | 25.76% | 53.18% |
| +2 | 262 | 7.25% | 14.50% | 23.66% | 177.48% |

### v0.2 top-five candidates only (540 runners)

| Tier | N | Win | Top2 | Top3 | Win ROI |
|---:|---:|---:|---:|---:|---:|
| -2 | 40 | 10.00% | 27.50% | 37.50% | 32.25% |
| -1 | 72 | 11.11% | 23.61% | 33.33% | 41.67% |
| +0 | 204 | 17.65% | 31.86% | 42.65% | 85.39% |
| +1 | 122 | 22.13% | 38.52% | 48.36% | 107.13% |
| +2 | 102 | 14.71% | 26.47% | 43.14% | 80.00% |

Positive (+1/+2) versus negative (-1/-2), race-cluster bootstrap (10,000 resamples):

- all runners: win **+3.06pp** (95% CI +0.05 to +5.98), top3 **+8.90pp** (+4.36 to +13.16)
- v0.2 top5 only: win **+8.04pp** (+0.63 to +15.13), top3 **+11.16pp** (+1.91 to +20.64)

This is the strongest positive finding in the block: **Edge polarity generalized out of sample**. Negative Edge horses underperformed positive Edge horses even after restricting to the pre-existing v0.2 top five.

However, the magnitude is not monotonic. Among v0.2 top-five candidates, +1 was strongest (win 22.13%, top3 48.36%), while +2 fell to win 14.71% / top3 43.14%. Therefore the current linear adjustment `0.02 × tier` is not validated as an ordinal strength scale. The evidence supports “positive vs negative” more clearly than “+2 > +1 > 0 > -1 > -2”.

## 6. Value-role v1.0-V

Only **2/108 races** changed ▲ under v1.0-V. Both changed ◎-▲ quinella and wide tickets missed, so pooled Q2/wide were exactly the same as v1.0-R.

| Date | Race | old ▲ | new ▲ | old/new top3 | quinella | wide |
|---|---|---|---|---|---:|---:|
| 2026-08-09 | 新潟1R | 11 シアルナーレ | 8 ラガリーガ | Y / Y | 0 / 0 | 0 / 0 |
| 2026-08-15 | 中京11R | 1 スマートティアナ | 4 イージーライダー | N / Y | 0 / 0 | 0 / 0 |

Two activations are not enough to evaluate Value Edge. It should remain shadow/research only.

## 7. Confidence

| Confidence | N | ◎ win | ◎ top2 | ◎ top3 | Win ROI |
|---|---:|---:|---:|---:|---:|
| A | 33 | 39.39% | 60.61% | 72.73% | 117.27% |
| B | 55 | 43.64% | 52.73% | 63.64% | 111.45% |
| C | 20 | 20.00% | 40.00% | 60.00% | 66.00% |

A remains stronger than C on top2/top3, but B had the highest win rate in this block. Keep confidence as evidence/robustness context, not a direct profitability filter.

## 8. Decision

### Performance Edge: **KEEP, but do not promote the current linear tier adjustment unchanged**

Evidence supporting retention:
- positive-vs-negative Edge separation generalized in an untouched 108-race block;
- v1.0-R improved ◎ win/top2/top3 by one race each;
- changed-axis head-to-head favored the Edge axis 2 wins to 1.

Reasons not to promote the exact current scoring rule:
- only seven axes changed;
- +2 did not consistently outperform +1;
- Q2 ROI fell from 98.75% to 86.30%;
- trio B5 was sensitive to lower-order reshuffling and fell from 102.17% to 73.28%.

The clean next hypothesis is to preserve **Edge polarity** while redesigning tier magnitude/role interaction. Any such redesign is post-hoc from this block and must be frozen before a new untouched block.

### Value Edge: **KEEP SHADOW ONLY**

Activation was only 2/108. No conclusion on profitability or role replacement is possible.

## 9. Settlement sources

- 2026-08-09 HJC SHA-256 `0c0a9679879deb5566e7e4d0be136950ef5139f04647af2de4fd130338b9e787`
- 2026-08-15 HJC SHA-256 `d454226ccd419e298a7cf9cb92aeda3bfc23583054526dcbd7f7090c7bc57a5f`
- 2026-08-22 HJC SHA-256 `d49d70be7c8776a1775c5166ebafd7607df8b0f430ee743af33bb404695b2e90`

Normalized payouts are stored separately in `result_cache` format for future ticket retrospectives. These 108 races are now settled and must not be reused as a fresh blind block.
