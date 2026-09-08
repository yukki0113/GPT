# RaceNote Blind Historical Backtest Settlement — 2025-11-15 / 2025-11-16 v0.1

## Status

**SETTLED AFTER 72-RACE PREDICTION FREEZE**

This batch extends the earlier 39-race reference to **111 total races** while preserving the same prediction and settlement contracts.

Sequence:

```text
RaceNote acquisition
 -> Reader View v0.1 round-trip 72/72 PASS
 -> prediction freeze commit 3b56eef4827eecbbe050c7f6123ec631b775f5dd
 -> HJC acquisition
 -> deterministic settlement
```

Target design:

- 2025-11-15: 東京 / 京都 / 福島, 36 races
- 2025-11-16: 東京 / 京都 / 福島, 36 races
- includes **2025-11-16 京都11R エリザベス女王杯 (G1)**
- 2025-10-18 / 2025-10-19 were explicitly excluded because calendar verification exposed some target results before prediction freeze

Prediction logic remained `provisional_handoff_v0.1_unweighted`.
Settlement remained `RaceNote_Backtest_Settlement_Protocol_v0_1.md`.

## Source audit

RaceNote:

- 2025-11-15: Issue #491 / run `34191070352` / artifact `10042224799` / backend `racenote_archive`
- 2025-11-16: Issue #492 / run `34191075508` / artifact `10042227902` / backend `racenote_archive`

Prediction freeze:

- `prediction_runs/20251115_20251116_racenote_prediction_blind_batch_v0_1.md`
- commit `3b56eef4827eecbbe050c7f6123ec631b775f5dd`

HJC:

- 2025-11-15: Issue #494 / run `34191602120`
  - `HJC251115.zip`
  - SHA-256 `d744a61e573ad0d1d44b0338927320f8d24b8833a80c934d11e2c2c2a91bd0c0`
  - member `HJC251115.txt`
  - member SHA-256 `afaaef34cd5a0c422041c5ded00bcb51766f6fa48a6390f2ee01c5a17421663f`
  - records: 36
- 2025-11-16: Issue #495 / run `34191607477`
  - `HJC251116.zip`
  - SHA-256 `1a2c25d06effb64c0fa9e59d9921246ac0ac7be58a16bf214aaed729568ac25a`
  - member `HJC251116.txt`
  - member SHA-256 `07c1ee0e0ba30a919ec95435cb88b36fd5e272a305d1b20725f04588fc394e2e`
  - records: 36

No target-date HJC/result/final-odds source was read before the prediction freeze commit.

## Frozen betting policy

- ①: ◎単勝 1点
- ②: ◎-○ / ◎-▲ 馬連 2点
- ③: ◎1頭軸、○ / ▲ / △1 / △2への3連複6点
- 100円均等

## 72-race summary

| Pattern | Investment | Payout | Hit races | Hit rate | Return rate |
|---|---:|---:|---:|---:|---:|
| 1 | 7,200円 | 5,740円 | 22/72 | 30.56% | 79.72% |
| 2 | 14,400円 | 13,110円 | 17/72 | 23.61% | 91.04% |
| 3 | 43,200円 | 32,240円 | 17/72 | 23.61% | 74.63% |
| 1+2 | 21,600円 | 18,850円 | 29/72 | 40.28% | 87.27% |
| 1+3 | 50,400円 | 37,980円 | 34/72 | 47.22% | 75.36% |
| 1+2+3 | 64,800円 | 51,090円 | 36/72 | 50.00% | 78.84% |

## Date split

Return rate by date:

| Date | Races | ① | ② | ③ | ①+② | ①+③ | ①+②+③ |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2025-11-15 | 36 | 56.39% | 72.92% | 91.11% | 67.41% | 86.15% | 83.21% |
| 2025-11-16 | 36 | 103.06% | 109.17% | 58.15% | 107.13% | 64.56% | 74.48% |

The two dates behaved quite differently:

- 11/15: ③ was strongest at **91.11%**, while ① and ② were below 75%.
- 11/16: ① **103.06%**, ② **109.17%**, and ①+② **107.13%** exceeded 100%, while ③ fell to **58.15%**.
- This large day-to-day reversal is evidence against tuning the betting policy from one isolated day.

## Venue split

| Venue | Races | ① | ② | ③ | ①+② | ①+③ | ①+②+③ |
|---|---:|---:|---:|---:|---:|---:|---:|
| 東京 | 24 | 90.83% | 112.29% | 67.57% | 105.14% | 70.89% | 80.09% |
| 京都 | 24 | 101.25% | 121.67% | 50.00% | 114.86% | 57.32% | 71.62% |
| 福島 | 24 | 47.08% | 39.17% | 106.32% | 41.81% | 97.86% | 84.81% |

Descriptive observations only:

- 東京: ② **112.29%**, ①+② **105.14%**
- 京都: ① **101.25%**, ② **121.67%**, ①+② **114.86%**
- 福島: ③ **106.32%**, ①+③ **97.86%**
- each venue has only 24 races in this batch, so these are not stable venue rules.

## G1 settlement

2025-11-16 京都11R エリザベス女王杯:

Frozen marks:

```text
◎ 7 レガレイラ
○ 13 ココナッツブラウン
▲ 4 カナテープ
△1 11 フェアエールング
△2 1 パラディレーヌ
```

HJC winning combinations:

```text
単勝   7        230円
馬連   1-7      1,280円
3連複  1-7-12   8,920円
```

Settlement:

- ①: **230円 hit**
- ②: 0円
- ③: 0円

The G1 therefore confirms that the same RaceNote/prediction/settlement pipeline works without a special G1 rule. One race is not evidence for G1-specific performance.

## Confidence split

| Confidence | Races | ① | ② | ③ | ①+② | ①+③ | ①+②+③ |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 3 | 40.00% | 148.33% | 87.78% | 112.22% | 80.95% | 95.93% |
| B | 49 | 75.10% | 97.14% | 96.12% | 89.80% | 93.12% | 94.01% |
| C | 20 | 97.00% | 67.50% | 20.00% | 77.33% | 31.00% | 39.11% |

Counts:

- A: 3 races
- B: 49 races
- C: 20 races

B was comparatively stable across all three bet groups in this batch, while C had particularly weak trio performance. This remains descriptive; the confidence labels were not defined as calibrated hit probabilities and the sample is still too small for a confidence-based betting filter.

## Graded / listed note

Graded races (G1/G2/G3): 3 races.

| Pattern | Investment | Payout | Hit races | Hit rate | Return rate |
|---|---:|---:|---:|---:|---:|
| 1 | 300円 | 230円 | 1/3 | 33.33% | 76.67% |
| 2 | 600円 | 830円 | 1/3 | 33.33% | 138.33% |
| 3 | 1,800円 | 3,290円 | 1/3 | 33.33% | 182.78% |
| 1+2 | 900円 | 1,060円 | 2/3 | 66.67% | 117.78% |
| 1+3 | 2,100円 | 3,520円 | 2/3 | 66.67% | 167.62% |
| 1+2+3 | 2,700円 | 4,350円 | 2/3 | 66.67% | 161.11% |

Listed races: 3 races, with no payout under any frozen pattern in this batch.

The graded result is driven by only three races and must not be interpreted as evidence that graded races are easier.

## Pooled reference — 111 races

The earlier reference contained 39 races:
- 2025-08-23 full-day 36 races
- 2025-08-24 initial 3-race PoC

Adding the new 72 races gives **111 races**.

| Pattern | Investment | Payout | Hit races | Hit rate | Return rate |
|---|---:|---:|---:|---:|---:|
| 1 | 11,100円 | 9,310円 | 33/111 | 29.73% | 83.87% |
| 2 | 22,200円 | 16,630円 | 23/111 | 20.72% | 74.91% |
| 3 | 66,600円 | 56,580円 | 28/111 | 25.23% | 84.95% |
| 1+2 | 33,300円 | 25,940円 | 42/111 | 37.84% | 77.90% |
| 1+3 | 77,700円 | 65,890円 | 53/111 | 47.75% | 84.80% |
| 1+2+3 | 99,900円 | 82,520円 | 55/111 | 49.55% | 82.60% |

Key change from the 39-race snapshot:

- ③ was **104.02%** at 39 races, but is now **84.95%** at 111 races.
- ①+③ was **102.23%** at 39 races, but is now **84.80%**.
- No frozen pattern remains above 100% over the pooled 111 races.
- ①+②+③ is **82.60%** with 55/111 hit races.

This is exactly the kind of small-sample reversal the blind expansion was intended to detect.

## Interpretation / next step

- The RaceNote → Reader View → GPT prediction → HJC settlement path is now exercised over **111 blinded races**, including different venues and a G1 day.
- The prediction layer is not obviously nonfunctional: ◎ won 33/111 races, and combined patterns paid in roughly half the races.
- However, current return rates are below break-even across all six frozen patterns.
- The early apparent advantage of ③ / ①+③ did not survive sample expansion.
- Venue and date splits move sharply enough that no venue filter, confidence filter, or bet-type deletion should be introduced from this sample alone.
- Keep `provisional_handoff_v0.1_unweighted` and the v0.1 settlement policy frozen for at least one more materially different historical block before changing weights or betting rules.
- A useful next block would include another season/time of year and another G1 family rather than adjacent November dates.
