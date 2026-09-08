# RaceNote v0.2 / v0.3 / v0.4a Random 3-Day Result-Blind Settlement — 2025-08-16 / 08-17 / 08-31

## Status

**RANDOM 3-DAY / 108-RACE RESULT-BLIND SETTLEMENT**

Targets were selected from unused August dates with fixed seed `20260908` after excluding 2025-08-23/24 because their results were already known:

- 2025-08-16
- 2025-08-17
- 2025-08-31
- venues: 中京 / 新潟 / 札幌
- total: 108 races

RaceNote inputs were acquired before target HJC/results.

### Important pre-result calibration note

The first v0.4 design activated in only **1/108 = 0.9%** of races. This was judged pathological relative to its preregistered engineering expectation before any HJC/result was opened. Using **activation rate only**, and no outcome/payout information, the threshold was relaxed once to v0.4a.

- v0.4a promotions before result acquisition: **11/108 = 10.2%**
- all 11 promotions were pure P4 -> ▲
- full canonical prediction payload SHA-256: `4c249aefc6011a60d0ed890950872eff515a5873d269b45948b4db62398782f3`
- freeze commit: `91c50a58e2c150cbdefe4ea52ecd9811490460c3`
- no threshold was changed after that freeze

This block is therefore result-blind, but v0.4a's activation rate was calibrated on the target **pre-race inputs**. Treat this as the first result-blind performance check of v0.4a, not as a fully external preregistration block.

### Reproducibility limitation

The exact one-off v0.2 runtime used in earlier prospective blocks was not retained. This block uses the documented-spec-compatible reconstruction frozen before results. Its pre-result comparison against the prior 2025-08-02/03/09/10 freezes was:

- exact ordered top five: 134/144 = 93.1%
- same top-five membership: 141/144 = 97.9%
- old v0.3 exact marks: 132/144 = 91.7%

Therefore within-block v0.2/v0.3/v0.4a role comparisons are useful, but pooling the axis mechanically with earlier exact-runtime blocks should be treated as a continuity diagnostic rather than a perfectly homogeneous model sample.

## 1. HJC acquisition after freeze

HJC was acquired only after commit `91c50a58e2c...`:

- 2025-08-16: SHA-256 `f176cadce9c6dad99c139d59ab5b09d7ded200b1e09736281113c9c951259e9b`
- 2025-08-17: SHA-256 `e81c9e87fa4b7e37388bb45788e62d9b80d2d5eea3c14e33b1d24d8d0a8b5764`
- 2025-08-31: SHA-256 `7fc85898dc93a9edec6f6c381ad7b2aa08d3af9c5cf1dfae547f99c6350e8e3f`

All payouts are also normalized separately under `result_cache/`.

## 2. Axis result — 108R

v0.2 / v0.3 / v0.4a share the same ◎ and ○ in this block.

| Metric | Result |
|---|---:|
| ◎ win | 37/108 = **34.26%** |
| ◎ top2 | 56/108 = **51.85%** |
| ◎ top3 | 65/108 = **60.19%** |
| ◎ win return | 10,800 -> 9,440 = **87.41%** |

The axis remained useful, but because of the reconstruction limitation above, this block should not be treated as a perfectly identical sixth replication of the prior exact v0.2 runtime.

## 3. Quinella Q2 — all 108 races

Q2 is `◎-○ / ◎-▲`, 100 yen each.

| Selector | Investment | Payout | Hit races | Return |
|---|---:|---:|---:|---:|
| v0.2 pure P3 | 21,600 | **17,820** | **33** | **82.50%** |
| old v0.3 value selector | 21,600 | 16,070 | 30 | 74.40% |
| v0.4a P3-defense | 21,600 | 17,390 | 32 | **80.51%** |

v0.4a recovered much of the damage produced by old v0.3, but did **not** beat the pure-P3 control in this block.

### Day-by-day Q2

| Date | v0.2 | v0.3 | v0.4a |
|---|---:|---:|---:|
| 2025-08-16 | **52.36% / 9 hits** | 28.06% / 6 | 46.39% / 8 |
| 2025-08-17 | 68.89% / 12 | 68.89% / 12 | 68.89% / 12 |
| 2025-08-31 | 126.25% / 12 | 126.25% / 12 | 126.25% / 12 |

Only 8/16 produced a net role-selection difference in quinella settlement.

## 4. Clean v0.4a changed-role comparison — 11 races

The 11 promotion races directly test whether replacing pure P3 with the promoted value ▲ helped.

### Changed ▲ ticket only

| Ticket | Investment | Payout | Hits | Return |
|---|---:|---:|---:|---:|
| ◎-pure P3 | 1,100 | **430** | **1** | 39.09% |
| ◎-v0.4a promoted ▲ | 1,100 | 0 | 0 | **0.00%** |

- v0.4a-only quinella gains: **0**
- v0.2-only losses caused by promotion: **1**
- both hit: 0
- both miss: 10

The lost pure-P3 quinella was:

- 2025-08-16 中京6R: pure P3 #7 -> quinella payout **430円**; promoted ▲ #10 did not hit

This is not enough evidence to reject the semantic idea, because 11 changed races are very small, but it provides **no positive quinella evidence** for v0.4a yet.

## 5. ◎-▲ wide diagnostic

### All 108 races

| Selector | Investment | Payout | Hits | Return |
|---|---:|---:|---:|---:|
| v0.2 pure ▲ | 10,800 | 5,660 | **21** | 52.41% |
| old v0.3 ▲ | 10,800 | 4,630 | 17 | 42.87% |
| v0.4a ▲ | 10,800 | **5,970** | 20 | **55.28%** |

### The 11 actual v0.4a promotion races only

- pure P3 wide: 1,100 -> 630, 2 hits = **57.27%**
- promoted value ▲ wide: 1,100 -> 940, 1 hit = **85.45%**

The promoted horse produced one wide hit:

- 2025-08-17 中京6R: ◎ #5 - promoted ▲ #14 -> wide **940円**

So this tiny subset improved payout via one larger wide, but reduced hit count 2 -> 1. It is far too small and payout-concentrated to treat as validation.

## 6. Old v0.3 shadow — direct failure in this block

Old v0.3 actually replaced pure P3 in 24 races.

Changed ▲ ticket only:

- pure P3 quinella: 2,400 -> 1,750, 3 hits = **72.92%**
- old v0.3 value ▲ quinella: 2,400 -> 0, 0 hits
- pure P3 wide: 2,400 -> 1,030, 4 hits = **42.92%**
- old v0.3 value ▲ wide: 2,400 -> 0, 0 hits

This is further evidence that the old v0.3 market-disagreement-heavy selector should not be revived as the production ▲ rule.

## 7. Q4 and trio

Because all selectors keep the same top-five membership, Q4 and trio Policy A6 are membership-invariant.

- Q4 `◎ to all four`: 43,200 -> 26,300, 41 hit races = **60.88%**
- Trio Policy A6: 64,800 -> 45,130, 28 hits = **69.65%**

Policy B5 can in principle change when ▲/△ roles move. In this particular block, all three selectors happened to settle identically:

- Trio Policy B5: 54,000 -> 29,800, 25 hits = **55.19%**

No betting-policy improvement is supported here.

## 8. Confidence — 108R

| Confidence | N | ◎ win | ◎ top2 | ◎ top3 | ◎ win return | v0.2 Q2 return |
|---|---:|---:|---:|---:|---:|---:|
| A | 24 | 41.67% | **62.50%** | **70.83%** | **108.75%** | 77.50% |
| B | 44 | 27.27% | 38.64% | 50.00% | 66.36% | 51.93% |
| C | 40 | 37.50% | 60.00% | 65.00% | 97.75% | **119.13%** |

A again produced the strongest top2/top3 reliability, but B/C are not well ordered in this block. C also produced the strongest Q2 return. This reinforces the existing interpretation:

- confidence is an evidence/hit-confidence aid;
- it is not a direct expected-value or automatic buy/no-buy signal;
- B/C calibration still needs work.

## 9. Historical continuity diagnostics

### v0.2 axis, prior 360R + this 108R = 468R

If this reconstructed block is appended only as a continuity diagnostic:

- ◎ win: 146/468 = **31.20%**
- ◎ top2: 233/468 = **49.79%**
- ◎ top3: 298/468 = **63.68%**
- ◎ win return: 46,800 -> 39,630 = **84.68%**

Again, because the exact old runtime was not retained, do not treat this as a perfectly homogeneous formal pooled sample.

### v0.3-valid Q2 sample, July/August 216R + this 108R = 324R

- pure v0.2 Q2: 64,800 -> 57,180, **82 hit races**, return **88.24%**
- old v0.3 Q2: 64,800 -> 57,780, **78 hit races**, return **89.17%**

The tiny pooled payout edge of old v0.3 remains entirely compatible with payout concentration: it has fewer hits, and both the prior 144R August follow-up and this new block moved against it.

## 10. Decision

### v0.2 pure P3

**KEEP as the current control/default mark assignment.**

### old v0.3

**RETIRE as an active promotion candidate.** Keep only as historical/shadow evidence. The market-disagreement-heavy selector has now repeatedly discarded useful P3 horses.

### v0.4a P3-defense selector

**DO NOT PROMOTE YET; CONTINUE UNCHANGED ON ANOTHER UNTOUCHED BLOCK.**

Positive:

- activation was reduced from old v0.3's 24/108 role changes to 11/108;
- all-race Q2 recovered from 74.40% (v0.3) to 80.51%, close to v0.2's 82.50%;
- promoted wide produced one larger payout.

Negative:

- 0 promoted quinella hits in 11 actual role changes;
- one pure-P3 quinella was lost;
- no evidence yet that v0.4a improves the intended `◎-▲` quinella role.

The next test should keep v0.4a **exactly unchanged**. Do not loosen it because this settled block produced no quinella gains. If another sufficiently sized untouched block again produces no benefit, redesign the promotion evidence/features rather than tuning the threshold toward settled payouts.

## 11. Result-cache boundary

Normalized payouts for all 108 races are stored separately as:

`horse-racing/jrdb/result_cache/RaceNote_Prospective_20250816_17_31_HJC_Payouts.csv`

These races are settled and must not be reused as a fresh blind block.
