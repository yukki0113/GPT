# RaceNote v0.5 Prospective Blind Result — 2025-09-13 / 09-14 / 09-28

## Status

**FIRST 72-RACE RESULT-BLIND CHECK OF v0.5 INTERACTION-VALUE ▲**

- random seed: `20260908`
- selected dates: 2025-09-14 / 2025-09-28 / 2025-09-13
- venues: 中山 / 阪神
- races: 72
- v0.5 design commit: `2cf5de5d97d8d85c788bdf775903e6087527b006`
- compact freeze commit: `7c3b4b1b64ceedb7999c50193f13f3c46973c25c`
- full prediction payload SHA-256: `a87e45aed1bd66b4356eb33f7a20b856a59f35af795470adb078115b32338490`
- v0.4a promotions before HJC: 8/72
- v0.5 promotions before HJC: 4/72 = 5.6%
- v0.5 preregistered pathological activation boundary: <2% or >35%; no pre-result calibration performed
- target HJC/results were acquired only after the freeze commit

HJC SHA-256:

- 2025-09-14: `b0ab913bd0c7fdbb0477d5210582cb6f37d9a819a473e05e413008acd9e7389b`
- 2025-09-28: `58f48236c62d0b91db70a4037cf1a18b9d6c5584a77ea91809f4c843aab98c63`
- 2025-09-13: `3fd1835605507f5118639babab239c79d546afe3fad22699f270c4b54412a3e9`

## 1. Axis — 72R

v0.2 / v0.4a / v0.5 share the same ◎ / ○ axis.

- ◎ win: 27/72 = **37.50%**
- ◎ top2: 38/72 = **52.78%**
- ◎ top3: 47/72 = **65.28%**
- ◎ win return: 7,200 -> 6,700 = **93.06%**

This block uses the same documented-spec-compatible v0.2 reconstruction used in the immediately previous 108R block. It is internally valid for selector comparison, but it is not perfectly identical to the original one-off historical runtime used in the earliest prospective blocks.

## 2. Quinella Q2 — all 72R

Q2 = `◎-○ / ◎-▲`, 100 yen each.

| Selector | Investment | Payout | Hit races | Return |
|---|---:|---:|---:|---:|
| v0.2 pure P3 | 14,400 | 12,700 | 21 | **88.19%** |
| v0.4a | 14,400 | **13,270** | 21 | **92.15%** |
| v0.5 | 14,400 | 12,700 | 21 | **88.19%** |

v0.5 was identical to pure P3 in settlement because none of its four actual role changes produced a quinella hit for either old P3 or new ▲.

## 3. Clean v0.5 changed-role comparison — 4R

v0.5 promoted P4 into ▲ in exactly four races:

1. 2025-09-14 中山2R: P3 #13 -> P4 #16
2. 2025-09-28 阪神5R: P3 #17 -> P4 #11
3. 2025-09-13 中山10R: P3 #7 -> P4 #2
4. 2025-09-13 阪神7R: P3 #11 -> P4 #15

### Quinella `◎-▲`

- pure P3: 400 -> 0, 0 hits
- v0.5 promoted ▲: 400 -> 0, 0 hits
- v0.5-only gains: 0
- pure-P3-only losses: 0

This is neutral evidence, not positive evidence. The P3-defense structure avoided measurable quinella damage in this tiny block, but it also failed to create any new quinella value.

### Wide `◎-▲`

- pure P3: 400 -> **990**, 1 hit = **247.50%**
- v0.5 promoted ▲: 400 -> 660, 1 hit = **165.00%**

The two hits occurred in different races:

- 2025-09-28 阪神5R: pure P3 wide = 990円; promoted ▲ missed
- 2025-09-13 中山10R: promoted ▲ wide = 660円; pure P3 missed

Net changed-role wide payout favored pure P3 by 330円. Sample size is far too small to infer a stable difference.

## 4. v0.4a shadow in the same 72R

v0.4a changed ▲ in 8 races.

Changed-ticket quinella:

- pure P3: 800 -> 340, 1 hit
- v0.4a ▲: 800 -> **910**, 1 hit

The old P3 hit and v0.4a hit occurred in different races, so v0.4a exchanged one hit for another with a larger payout.

All-race Q2 therefore improved from 88.19% to 92.15%, but this is only a 570円 difference and remains payout-sensitive.

Across the previous 108R plus this 72R (180R continuity sample under the same reconstructed runtime):

- pure v0.2 Q2: 36,000 -> 30,520 = **84.78%**, 54 hit races
- v0.4a Q2: 36,000 -> 30,660 = **85.17%**, 53 hit races

The tiny payout edge does not compensate for the lack of replicated hit-rate improvement. v0.4a remains a research/shadow selector, not a production promotion.

## 5. Wide / Q4 / trio — 72R

### `◎-▲` wide, all races

- pure v0.2 ▲: **66.39%**, 15 hits
- v0.4a ▲: **69.03%**, 16 hits
- v0.5 ▲: **61.81%**, 15 hits

### Q4

Membership is unchanged, so all selectors are identical:

- 28,800 -> 19,620 = **68.13%**, 27 hit races

### Trio A6

- 43,200 -> 30,050 = **69.56%**, 18 hit races

### Trio B5

- v0.2: 36,000 -> 30,050 = **83.47%**, 18 hits
- v0.4a: 36,000 -> 29,500 = 81.94%, 17 hits
- v0.5: 36,000 -> 30,050 = **83.47%**, 18 hits

No betting policy is promoted from this block.

## 6. Confidence — 72R

| Confidence | N | ◎ win | ◎ top2 | ◎ top3 | ◎ win return | v0.2 Q2 return |
|---|---:|---:|---:|---:|---:|---:|
| A | 13 | 15.38% | 30.77% | 53.85% | 23.85% | 35.77% |
| B | 30 | 40.00% | 60.00% | 63.33% | 89.33% | **102.67%** |
| C | 29 | 44.83% | 55.17% | 72.41% | **127.93%** | 96.72% |

A did not calibrate well in this block. This reinforces the existing conclusion that confidence is not yet a stable automatic purchase filter; B/C ordering also remains inconsistent across blocks.

## 7. v0.5 interpretation

### Positive

- v0.5 reduced activation to a selective 4/72 without requiring any target-result calibration.
- all four promotions had an explicit P3 vulnerability plus two independent P4 advantages.
- unlike old v0.3, this block showed no direct quinella loss caused by replacing a successful P3.

### Negative

- 0/4 promoted ▲ quinella hits.
- no v0.5-only quinella gain.
- changed-role wide payout was lower than pure P3 (660 vs 990).
- four role changes are far too few for validation.

## 8. Decision

### Production/default

**KEEP v0.2 pure P3.**

### v0.4a

**KEEP as shadow/research only.** Its 180R reconstructed-runtime continuity sample is nearly flat versus pure P3 and has one fewer Q2 hit.

### v0.5

**CONTINUE UNCHANGED TO A SECOND UNTOUCHED BLOCK. DO NOT PROMOTE OR RETUNE.**

The first block is neutral-to-slightly-negative, but the changed-role sample is only four races. The design specifically required replication before promotion. The correct next action is another untouched block with the exact same v0.5 gates.

If the second block again produces no v0.5-only quinella gains, the next redesign should change the evidence model rather than loosen thresholds. In particular, consider replacing the simple hard market confirmation with an explicit estimate of P3/P4 pair-specific top2 probability or richer comparable-performance evidence, while preserving result-blind validation.

## 9. Result cache

Normalized HJC payouts for the 72 races are stored separately under:

`horse-racing/jrdb/result_cache/RaceNote_Prospective_20250913_14_28_HJC_Payouts.csv`

These races are settled and must never be reused as a fresh blind block.
