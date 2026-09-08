# RaceNote v0.2 vs v0.3 Prospective Blind Result — 2025-07-26 / 2025-07-27

## Status

**THIRD PROSPECTIVE BLOCK / FIRST BLIND TEST OF v0.3 VALUE-MARK ROLE**

- target: 2025-07-26 / 2025-07-27
- venues: 中京 / 新潟 / 札幌, 24 races each
- total: 72 races
- target selection: BAC/Analysis identity metadata only
- RaceNote Reader View round-trip: 72/72 PASS
- v0.2/v0.3 marks, confidence, comments and betting policies frozen before HJC
- 2025-07-26 freeze commit: `c4935450cdbba24813546216ff0dba5395c8f388`
- 2025-07-27 freeze commit: `1753190cb99652b2ce1139c76c96b77fafe27130`
- HJC 2025-07-26 acquired after freeze: SHA-256 `cb4d31083c0d6e38d5a1a05a8cd39fff0ac02b255e014b3358fe42aeebcaa208`
- HJC 2025-07-27 acquired after freeze: SHA-256 `126d70f121afc2919d99257e8cf32aca8b0881f83911b1e7af641cb3aef7fb0e`

## 1. v0.2 axis replication

v0.2 and v0.3 share the same ◎ and ○ in this experiment. The v0.2 axis remained strong in the new venue block.

| Metric | Result |
|---|---:|
| ◎ win | 29/72 = **40.28%** |
| ◎ top2 | 37/72 = **51.39%** |
| ◎ top3 | 50/72 = **69.44%** |
| ◎ win return | 7,200 -> 8,240 = **114.44%** |

The unusually high win rate in this block should not be extrapolated by itself. Across all three prospective blocks (216 races), the unchanged v0.2 axis is:

- ◎ win: 66/216 = **30.56%**
- ◎ top2: 111/216 = **51.39%**
- ◎ top3: 146/216 = **67.59%**
- ◎ win return: 21,600 -> 18,440 = **85.37%**

Thus the suitability-first axis improvement has now persisted through three independent 72-race blocks, while the pooled single-win economics remain below break-even.

## 2. v0.3 value-mark activity

The preregistered v0.3 rule reused the old ☆ disagreement eligibility but restricted it to pure ranks P3-P5.

- value-eligible ▲: 21/72 races
- already pure P3, so no role-order change: 5 races
- pure P4/P5 promoted into ▲: **16 races**

Therefore the meaningful v0.2-v0.3 comparison is concentrated in 16 races.

## 3. Quinella result

### All 72 races

| Policy | Investment | Payout | Hit races | Return |
|---|---:|---:|---:|---:|
| v0.2 Q2 = ◎-○ / ◎-pure▲ | 14,400 | 18,210 | 18 | **126.46%** |
| v0.3 Q2 = ◎-○ / ◎-value▲ | 14,400 | **23,310** | **20** | **161.88%** |
| Q4 = ◎ to all four top-five opponents | 28,800 | 31,030 | 27 | 107.74% |

Individual second ticket:

- ◎-○: 7,200 -> 3,460, 10 hits = 48.06%
- v0.2 ◎-pure▲: 7,200 -> 14,750, 8 hits = 204.86%
- v0.3 ◎-value▲: 7,200 -> **19,850**, 10 hits = **275.69%**

The headline return is high partly because this July block itself was favorable to the ▲ ticket. The cleaner causal comparison is the 16 races where v0.3 actually changed the role order.

### 16 changed-role races

| Policy | Investment | Payout | Hit races | Return |
|---|---:|---:|---:|---:|
| v0.2 Q2 | 3,200 | 1,050 | 2 | 32.81% |
| v0.3 Q2 | 3,200 | **6,150** | **4** | **192.19%** |

For the changed ▲ ticket alone:

- old pure P3 ▲: 1,600 -> **0**, 0 hits
- promoted value ▲: 1,600 -> **5,100**, 2 hits = 318.75%

There were **2 v0.3-only quinella gains and 0 v0.2-only losses** among the changed ▲ tickets.

The two gains were:

1. 2025-07-27 新潟8R: ◎9 ノットファウンド - ▲12 ダズリングダンス, quinella **2,180円**
2. 2025-07-27 新潟9R: ◎2 アールプロスト - ▲13 ブレードサクセス, quinella **2,920円**

In both cases the promoted ▲ had been pure rank 4 under v0.2 and was raised because pre-target market evaluation lagged the prediction/ability view while race-specific support remained sufficient.

This is strong first-block support for the user's proposed ▲ semantics, but the effective changed sample is only 16 races and must not be treated as final promotion evidence.

## 4. Trio interaction

The six-ticket trio Policy A uses every pair among the same four opponents, so v0.2 and v0.3 are identical.

- Policy A: 43,200 -> 49,540, 20 hits = **114.68%**

Policy B excludes only `◎△1△2`, so changing which horse is ▲ can change the omitted combination.

- v0.2 Policy B: 36,000 -> 25,230, 15 hits = 70.08%
- v0.3 Policy B: 36,000 -> **31,210**, 15 hits = **86.69%**

Only two races changed Policy-B payout:

- 2025-07-27 新潟8R: v0.2 0 -> v0.3 **7,810**
- 2025-07-27 札幌12R: v0.2 **1,830** -> v0.3 0

Net +5,980 favored v0.3 in this block, but this is payout-concentrated. Continue the 5-vs-6 ticket comparison rather than promoting a trio policy change.

Across all 216 prospective v0.2 races:

- trio Policy A: 129,600 -> 131,630 = **101.57%**
- trio Policy B: 108,000 -> 90,640 = 83.93%

Policy A is now barely above break-even pooled, but block returns remain unstable (Mar 106.78%, Jun 83.24%, Jul 114.68%).

## 5. Confidence validation

The July freeze contained:

- A: 17 races
- B: 37 races
- C: 18 races

July axis capture:

| Confidence | N | ◎ win | ◎ top2 | ◎ top3 |
|---|---:|---:|---:|---:|
| A | 17 | **58.82%** | **64.71%** | **88.24%** |
| B | 37 | 35.14% | 48.65% | 62.16% |
| C | 18 | 33.33% | 44.44% | 66.67% |

To reduce single-block noise, all prospectively frozen v0.2 confidence labels across 216 races were also pooled:

| Confidence | N | ◎ win | ◎ top2 | ◎ top3 | ◎ win return | Q2 return |
|---|---:|---:|---:|---:|---:|---:|
| A | 52 | **36.54%** | **59.62%** | **82.69%** | 76.54% | 75.77% |
| B | 106 | 28.30% | 49.06% | 64.15% | **92.83%** | **101.65%** |
| C | 58 | 29.31% | 48.28% | 60.34% | 79.66% | 64.22% |

Interpretation:

1. **A is meaningfully stronger as a hit-confidence label.**
2. B and C are only weakly separated; top3 is monotonic, but win/top2 are nearly tied.
3. Confidence is not expected value. B produced the best pooled win/Q2 economics despite lower hit confidence than A.

Therefore `自信度:A` is useful purchase-context information, but it should not yet be converted into an `A only = buy` rule.

## 6. Short-comment audit

The compact output was operationally usable, but two rendering issues were observed before any result-driven rewrite:

1. races with sparse running-style/pace data can render awkward text such as `前0頭・差し追込0頭`;
2. obstacle/new-horse races can produce `不明想定` language that should be rendered more naturally as `展開材料が少なく読みづらい`.

These are presentation-only defects. They do not change the frozen model ranking or the value-role test.

The main comment contract worked as intended:

- ◎: translated raw indices into `能力は上位圏` and exposed race-specific support/risk;
- ○: attempted to state why ◎ was preferred and a reversal condition;
- ▲: explicitly distinguished `妙味込み` from `純粋な3番手評価`;
- △: remained compact and order-preserving.

## 7. Decision

### v0.2

Keep as the provisional standard axis. Three independent prospective blocks support the suitability-first re-ranking direction.

### v0.3 ▲ semantics

**Promising, continue unchanged for another untouched block; do not promote yet.**

Reason:

- effective role changes: only 16 races
- v0.3-only quinella gains: 2
- v0.2-only quinella losses: 0
- changed-role Q2 return improved from 32.81% to 192.19%
- no top-five/axis degradation is possible by construction
- one favorable block is still too small to establish stable value selection

The next block should use the exact same value eligibility thresholds with no tuning from these July results.

### Confidence

Keep A/B/C in the output. Treat A as a meaningful high-confidence signal, while continuing to audit whether B/C need recalibration.

### Betting

Do not change the permanent betting contract yet. Continue blind comparison of:

- v0.2 Q2
- v0.3 Q2
- Q4 diagnostic
- trio A6
- trio B5

## 8. Result-cache boundary

The July HJC payouts are normalized separately under `result_cache/` so future post-hoc questions about wide, exacta, trifecta, alternate formations, or payout concentration can be answered without re-reading RaceNote or mixing results into prediction generation.

The same July races are now settled and must never be reused as a fresh blind prediction block.
