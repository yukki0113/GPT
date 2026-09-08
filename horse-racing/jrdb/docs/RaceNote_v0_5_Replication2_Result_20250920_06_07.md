# RaceNote v0.5 Replication-2 Blind Result — 2025-09-20 / 09-06 / 09-07

## Status

**SECOND UNTOUCHED BLIND BLOCK / 96 RACES**

- v0.5 design commit: `2cf5de5d97d8d85c788bdf775903e6087527b006`
- pre-HJC freeze commit: `4bfa62c85d61068b1403b071a084912d5a3e4505`
- prediction payload SHA-256: `34a0205a06703f804ea20c1df7aed021d788d2b71aec9ca1eabd22f952b98461`
- target HJC was acquired only after freeze.
- v0.5 activation: 5/96 = 5.2%; no threshold calibration.

HJC source SHA-256:

- 2025-09-20: `2b305dd551e4d9f30716876a29d1c7d347be4b82ac808c66124513e018e15a2e`
- 2025-09-06: `a83eadf3b45ec1b9449ba09c72a4e83ca6b545e54dff21f31dc0a044df22aa7b`
- 2025-09-07: `59d25e24a104a4ae49f95ec61531a8a504387a8e73198e677e16a69da3a210d5`

## 1. Q2 all 96 races

Q2 = `◎-○ / ◎-▲`, 100円 each.

| selector | investment | payout | hit races | return |
|---|---:|---:|---:|---:|
| v0.2 pure P3 | 19,200 | 14,130 | 24 | **73.59%** |
| v0.4a | 19,200 | 14,130 | 24 | **73.59%** |
| v0.5 | 19,200 | 13,070 | 24 | **68.07%** |

v0.5 did not improve Q2 in the second blind block.

## 2. Clean changed-role comparison — 5 races

| ticket | investment | payout | hits | return |
|---|---:|---:|---:|---:|
| ◎-pure P3 | 500 | **1,670** | 1 | **334.0%** |
| ◎-v0.5 promoted ▲ | 500 | 610 | 1 | 122.0% |

Head-to-head:

- v0.5-only gain: 1 race
- pure-P3-only loss: 1 race
- both hit: 0
- both miss: 3

Concrete cases:

- 2025-09-06 阪神9R: pure P3 #2 -> promoted ▲ #5; old 0 / new **610円**
- 2025-09-07 札幌9R: pure P3 #13 -> promoted ▲ #14; old **1,670円** / new 0

The new selector found one useful promotion, but the lost pure-P3 payout was materially larger.

## 3. ◎-▲ wide

All 96 races:

- v0.2: 9,600 -> 6,400, 19 hits = **66.67%**
- v0.5: 9,600 -> 5,770, 18 hits = **60.10%**

Changed 5 races only:

- pure P3: 500 -> 930, 2 hits = **186.0%**
- promoted ▲: 500 -> 300, 1 hit = **60.0%**

Again, promotion reduced both hit count and payout in this block.

## 4. Other policies

Membership is unchanged, so Q4 and Trio A6 are identical across selectors.

- Q4: 38,400 -> 28,160 = **73.33%**
- Trio A6: 57,600 -> 44,150 = **76.65%**
- Trio B5: 48,000 -> 39,260 = **81.79%** for all selectors in this block

## 5. v0.5 two-block combined evidence — 168 races

Combine first block (2025-09-13/14/28, 72R) and replication-2 (96R).

### Q2

| selector | investment | payout | hit races | return |
|---|---:|---:|---:|---:|
| v0.2 pure P3 | 33,600 | **26,830** | 45 | **79.85%** |
| v0.4a | 33,600 | **27,400** | 45 | **81.55%** |
| v0.5 | 33,600 | 25,770 | 45 | **76.70%** |

### v0.5 actual promotions only

Across the two blind blocks:

- promotions: **9 races**
- pure P3 quinella: 900 -> **1,670**, 1 hit
- promoted ▲ quinella: 900 -> **610**, 1 hit
- pure P3 wide: 900 -> **1,920**, 3 hits
- promoted ▲ wide: 900 -> **960**, 2 hits

Thus v0.5 reduced promotion frequency and avoided widespread P3 destruction, but it still failed to create positive incremental value.

## 6. Decision

### v0.5

**DO NOT PROMOTE. STOP THRESHOLD TUNING.**

Two untouched blocks now give no evidence that the current interaction-value gates improve `◎-▲` selection. The problem is no longer activation frequency. The feature concept itself is not separating useful P4 promotions from harmful ones reliably enough.

### Production/default

Keep **pure v0.2 P3** as the default ▲ assignment for now.

### v0.4a

v0.4a remains a historical conservative candidate. Its 168R combined Q2 is slightly higher than pure P3, but the changed-role sample is only 12 races and the edge is payout-concentrated. Do not promote it from this evidence alone.

## 7. Recommended next research direction

Do not make v0.5a by changing the same thresholds.

The next candidate should change the information used for opponent selection. Strong candidates are:

1. estimate **pair/quinella compatibility with ◎** rather than only P3-vs-P4 individual suitability;
2. use **P3 fragility probability** as a continuous diagnostic instead of hard vulnerability flags;
3. distinguish `win ability` from `top2 survival / second-place suitability` for opponent marks;
4. retain market/value only after a candidate has passed the pair-compatibility stage.

Any such change is a new model version and requires a new untouched blind block.

## 8. Result cache

Normalized HJC payouts for all 96 races are stored separately as:

`horse-racing/jrdb/result_cache/RaceNote_Prospective_20250920_06_07_HJC_Payouts.csv`

These races are settled and must not be reused as fresh blind targets.
