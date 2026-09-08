# RaceNote v0.2 vs v0.3 Prospective Blind Result — 2025-08-02/03/09/10

## Status

**FOUR-DAY / 144-RACE FOLLOW-UP BLIND BLOCK FOR v0.3 VALUE-MARK SEMANTICS**

- dates: 2025-08-02, 2025-08-03, 2025-08-09, 2025-08-10
- venues: 中京 / 新潟 / 札幌
- races: 144
- target selection: BAC/Analysis identity metadata only
- Reader View round-trip: 144/144 PASS
- complete prediction payload SHA-256 frozen before HJC: `e3e484707a7027c9c6b74fb24c452aa92c7f14213314603ef8f6947f23a34158`
- freeze commit: `5248d6384638b5ef65f2cbe121e56e6a1040d5d2`
- v0.2/v0.3 logic, confidence, comments, Q2/Q4 and trio A/B policies: unchanged from the July blind block
- no target HJC/result/final target odds-popularity/Web result was consulted before freeze

HJC acquired only after freeze:

- 2025-08-02: `HJC250802.zip`, SHA-256 `2cfca192b3b55258e5de31559b77ea845a2819aefd9a2298b73084440f7ccf9e`
- 2025-08-03: `HJC250803.zip`, SHA-256 `5fa30533e0715a63875f008422c2e994710503b5fd183aac2f16b8f02da0053b`
- 2025-08-09: `HJC250809.zip`, SHA-256 `cb3e5c940771b581f047f5b247546b861a3ead912bc820c30d3c74490ac55072`
- 2025-08-10: `HJC250810.zip`, SHA-256 `a8b0ba23e5479e869b22af30d60a73f501c5b95c7b70702c86336859a68deb59`

## 1. v0.2 axis — August 144R

v0.2 and v0.3 share the same ◎ / ○ axis in this experiment.

| Metric | Result |
|---|---:|
| ◎ win | 43/144 = **29.86%** |
| ◎ top2 | 66/144 = **45.83%** |
| ◎ top3 | 87/144 = **60.42%** |
| ◎ win return | 14,400 -> 11,750 = **81.60%** |

The axis remains useful, but August was weaker than the July 72R block and again demonstrates that one favorable block must not be extrapolated.

## 2. v0.3 value-role activity

The exact July rule was reused with no tuning:

- value-role eligible: 63/144 races
- actual role-order changes (pure P4/P5 promoted into ▲): **45/144 races**
- confidence distribution: A 30 / B 70 / C 44

## 3. Quinella — August 144R

### All races

| Policy | Investment | Payout | Hit races | Return |
|---|---:|---:|---:|---:|
| v0.2 Q2 = ◎-○ / ◎-pure▲ | 28,800 | **21,150** | **31** | **73.44%** |
| v0.3 Q2 = ◎-○ / ◎-value▲ | 28,800 | 18,400 | 28 | 63.89% |
| Q4 = ◎ to all four top-five opponents | 57,600 | 40,980 | 47 | 71.15% |

Individual v0.2 roles:

- ◎-○: 14,400 -> 9,770, 19 hits = 67.85%
- ◎-pure▲: 14,400 -> 11,380, 12 hits = 79.03%
- ◎-△1: 14,400 -> 12,620, 9 hits = 87.64%
- ◎-△2: 14,400 -> 7,210, 7 hits = 50.07%

v0.3 value ▲:

- ◎-value▲: 14,400 -> 8,630, 9 hits = **59.93%**

Thus the July advantage of the value-role rule did **not** replicate in this larger August block.

## 4. Clean causal comparison — 45 changed-role races

Only these races actually test whether replacing pure P3 with the value-oriented ▲ helped.

| Policy | Investment | Payout | Hit races | Return |
|---|---:|---:|---:|---:|
| v0.2 Q2 | 9,000 | **7,150** | **6** | **79.44%** |
| v0.3 Q2 | 9,000 | 4,400 | 3 | 48.89% |

Changed ▲ ticket head-to-head:

- v0.3-only gain: **1 race**
- v0.2-only loss caused by replacing pure▲: **4 races**
- both hit: 0
- both miss: 40

The one v0.3-only gain was:

- 2025-08-02 中京12R: promoted ▲ returned quinella **3,000円**

The four v0.2-only lost quinellas were:

- 2025-08-02 札幌3R: **1,230円**
- 2025-08-03 中京4R: **1,650円**
- 2025-08-03 札幌12R: **600円**
- 2025-08-10 札幌7R: **2,270円**

This is the opposite direction from July (2 v0.3-only gains / 0 v0.2-only losses).

## 5. Four-day stability

| Date | Role changes | v0.2 Q2 | v0.3 Q2 |
|---|---:|---:|---:|
| 2025-08-02 | 9 | 66.25% | **90.83%** |
| 2025-08-03 | 11 | **82.50%** | 51.25% |
| 2025-08-09 | 13 | 73.89% | 73.89% |
| 2025-08-10 | 12 | **71.11%** | 39.58% |

The value-role candidate won one day, tied one day, and lost two days.

## 6. v0.3 cumulative prospective sample — July + August = 216R

The valid v0.3 prospective sample is now 216 races (2025-07-26/27 + 2025-08-02/03/09/10).

### All races

| Policy | Investment | Payout | Hits | Return |
|---|---:|---:|---:|---:|
| v0.2 Q2 | 43,200 | 39,360 | **49** | 91.11% |
| v0.3 Q2 | 43,200 | **41,710** | 48 | **96.55%** |

### Changed-role races only

There are 61 actual role changes across the 216R sample.

| Policy | Investment | Payout | Hits | Return |
|---|---:|---:|---:|---:|
| v0.2 Q2 | 12,200 | 8,200 | **8** | 67.21% |
| v0.3 Q2 | 12,200 | **10,550** | 7 | **86.48%** |

The pooled return still favors v0.3 because the July gains were larger payouts, but v0.3 now has **fewer hits** and the August block moved strongly against it. The pooled advantage is therefore payout-concentrated and not stable enough for promotion.

## 7. Trio interaction

### August 144R

- Trio Policy A6 (same candidate set, order-insensitive): 86,400 -> 46,630 = **53.97%**
- v0.2 Policy B5: 72,000 -> 41,590 = **57.76%**
- v0.3 Policy B5: 72,000 -> 31,780 = **44.14%**

The value-role reordering materially hurt the five-ticket omission rule in August.

### July + August v0.3 prospective 216R

- Trio Policy A6: 129,600 -> 96,170 = **74.21%**
- v0.2 Policy B5: 108,000 -> 66,820 = **61.87%**
- v0.3 Policy B5: 108,000 -> 62,990 = **58.32%**

No trio policy is promoted from these figures.

## 8. v0.2 axis cumulative prospective sample — 360R

Across all five independent prospective blocks used so far (Mar 72 + Jun 72 + Jul 72 + Aug 144):

- ◎ win: 109/360 = **30.28%**
- ◎ top2: 177/360 = **49.17%**
- ◎ top3: 233/360 = **64.72%**
- ◎ win return: 36,000 -> 30,190 = **83.86%**

Betting diagnostics using pure v0.2 marks across the same 360R:

- Q2 ◎-○/▲: **80.60%**
- Q4 ◎ to four opponents: **80.17%**
- trio A6: **82.53%**
- trio B5: **73.46%**

The prediction axis remains useful, but no fixed betting policy has demonstrated pooled break-even economics.

## 9. Confidence — cumulative 360R

| Confidence | N | ◎ win | ◎ top2 | ◎ top3 | ◎ win return | v0.2 Q2 return |
|---|---:|---:|---:|---:|---:|---:|
| A | 82 | **37.80%** | **57.32%** | **79.27%** | 79.02% | 65.49% |
| B | 176 | 28.41% | 47.16% | 61.36% | **90.57%** | **94.94%** |
| C | 102 | 27.45% | 46.08% | 58.82% | 76.18% | 67.99% |

Interpretation:

- A remains clearly separated as a **hit-confidence / evidence-confidence** label.
- B and C remain much closer to each other.
- A is not a value signal; B has better pooled betting economics.

Therefore keep `自信度:A/B/C` in the user-facing output, but do not convert it directly into an automatic buy/no-buy rule.

## 10. Decision

### v0.2 axis

**KEEP as provisional standard.**

The 360R sample continues to support the suitability-first ◎ selection direction.

### v0.3 `▲ = 妙味役` semantic idea

**KEEP THE SEMANTIC IDEA AS A RESEARCH DIRECTION, BUT DO NOT PROMOTE THE CURRENT SELECTION RULE.**

The user's intended structure remains coherent:

- ◎ = main win candidate
- ○ = strongest orthodox opponent
- ▲ = value-oriented opponent when justified
- △1 = pure next-ranked contender retained for multi-horse bets
- △2 = next contender

However, the current mechanical value eligibility inherited from the old ☆ rule is not stable enough:

- July: favorable
- August: unfavorable
- cumulative 216R: return advantage remains, but hit rate is lower and payout concentration is high

The correct next development target is not to abandon the ▲ meaning; it is to improve **how a horse earns the ▲ value role**, and validate that new rule on another untouched block.

No threshold or feature should be tuned directly to maximize these settled August payouts.

## 11. Result-cache boundary

All August HJC payouts are normalized separately under `result_cache/` for future post-hoc ticket questions. These races are now settled and must never be reused as a fresh blind prediction block.