# RaceNote v0.6a Pair-Compatibility Replication-2 Result — 2025-10-04 / 10-13 / 10-25

## Status

**SECOND UNTOUCHED v0.6a BLIND BLOCK / 84 RACES — RETIRE v0.6a**

- v0.6 original design commit: `c6c424f5c681222a797b01fd3ad49099d5901398`
- v0.6a pre-result correction commit: `93c18411eb16a30c4947b64884dc099e7b97bae0`
- pre-HJC freeze commit: `7b694fcaecb779db733a8d720f38f50c70f5e999`
- prediction payload SHA-256: `7870da627187d1a5c4b79377843e355dc08587ac08e5943acb25fbf00eec3fab`
- v0.6a activation before HJC: **0/84 = 0.0%**
- no threshold/model calibration was performed in this replication block
- target HJC was acquired only after the freeze commit

HJC source SHA-256:

- 2025-10-04: `99fad801bc6b6868935ba684ca2b3626be2ad1daff7dd61f817aef1af46c5933`
- 2025-10-13: `a14c0937abdfba3c26d0b19de50d83cc2d954aec18db91a9d5e948add2298341`
- 2025-10-25: `0cea1d12d4e13620599c2ab6035adfdd72d9ae576f0479aaea0a9c29da697e5f`

All three HJC workflow runs used head SHA `7b694fcaecb779db733a8d720f38f50c70f5e999`, the authoritative pre-result freeze.

## 1. Pre-result activation result

The unchanged v0.6a selector promoted **zero** P4 horses into ▲ across all 84 races.

Therefore:

- v0.2 pure P3 marks and v0.6a marks are identical in all 84 races;
- changed-role comparison is empty;
- any second-block betting difference between v0.2 and v0.6a is mathematically impossible.

This zero-activation result is itself important negative evidence. The first block activated 2/72 races; the two blocks combined activate only **2/156 = 1.28%**.

## 2. Axis — 84R

v0.2/v0.6a share the same ◎ and ○ axis.

- ◎ win: 17/84 = **20.24%**
- ◎ top2: 32/84 = **38.10%**
- ◎ top3: 40/84 = **47.62%**
- ◎ win return: 8,400 -> 4,670 = **55.60%**

This was a difficult block for the reconstructed v0.2 axis. It does not create a selector comparison because v0.6a does not change the axis.

## 3. Q2 — 84R

Q2 = `◎-○ / ◎-▲`, 100円 each.

| selector | investment | payout | hit races | return |
|---|---:|---:|---:|---:|
| v0.2 pure P3 | 16,800 | 5,350 | 9 | **31.85%** |
| v0.6a | 16,800 | 5,350 | 9 | **31.85%** |

The equality is mechanical because v0.6a made no role changes.

## 4. Other policies — 84R

- `◎-pure P3` wide: 8,400 -> 4,280, 12 hits = **50.95%**
- Q4: 33,600 -> 21,050, 24 hit races = **62.65%**
- Trio A6: 50,400 -> 18,990, 14 hit races = **37.68%**
- Trio B5: 42,000 -> 18,990, 14 hit races = **45.21%**

Because top-five membership and all role labels are unchanged, these are identical for v0.2 and v0.6a in this block.

## 5. Confidence — 84R

| confidence | N | ◎ win | ◎ top2 | ◎ top3 | ◎ win return | Q2 return |
|---|---:|---:|---:|---:|---:|---:|
| A | 18 | 22.22% | **50.00%** | **55.56%** | 44.44% | 40.00% |
| B | 51 | 17.65% | 31.37% | 43.14% | 41.76% | 7.84% |
| C | 15 | **26.67%** | 46.67% | 53.33% | **116.00%** | **103.67%** |

Confidence again does not order cleanly enough to become an automatic purchase filter. Retain it as an explanatory aid only.

## 6. v0.6a two-block evidence — 156R

First block: 2025-09-15 / 09-21 / 09-27, 72R.
Second block: 2025-10-04 / 10-13 / 10-25, 84R.

### Activation

- first block: 2/72 = 2.8%
- second block: 0/84 = 0.0%
- combined: **2/156 = 1.28%**

### Q2

| selector | investment | payout | return |
|---|---:|---:|---:|
| v0.2 pure P3 | 31,200 | **15,250** | **48.88%** |
| v0.6a | 31,200 | 14,950 | 47.92% |

All incremental difference comes from the first block because the second block had zero promotions.

### Actual v0.6a promotions across both blocks

Only the two first-block promotions exist:

- pure P3 quinella: 200 -> **300**, 1 hit
- v0.6a promoted ▲ quinella: 200 -> 0, 0 hits
- pure P3 wide: 200 -> **730**, 2 hits
- v0.6a promoted ▲ wide: 200 -> 630, 1 hit

There is no replicated positive changed-role evidence.

### Combined axis reference

Across these two reconstructed-runtime blocks:

- ◎ win: 39/156 = **25.00%**
- ◎ top2: 69/156 = **44.23%**
- ◎ top3: 87/156 = **55.77%**
- ◎ win return: 15,600 -> 10,340 = **66.28%**

Do not merge this mechanically with the earliest original-runtime prospective blocks as one homogeneous sample; the known reconstruction limitation remains.

## 7. Decision

### v0.6a

**DO NOT PROMOTE. RETIRE THIS HEURISTIC SELECTOR. DO NOT RETUNE ITS THRESHOLDS.**

Reasons:

1. first untouched block: only 2 promotions and no quinella gain;
2. second untouched block: 0 promotions across 84 races;
3. combined activation 1.28% is below the original engineering-feasibility boundary;
4. the only two actual promotions produced worse quinella and wide payout than pure P3;
5. further loosening the same gates would become repeated threshold search rather than a clean new hypothesis.

### Production/default

Keep **v0.2 pure P3 as ▲** for now:

`◎=P1 / ○=P2 / ▲=P3 / △1=P4 / △2=P5`

The conceptual idea that ▲ can eventually become a value/opponent role is not rejected. What is rejected is the current hand-built P3-vs-P4 heuristic implementation.

## 8. Recommended next research direction

Stop creating `v0.6b` by manually changing gates.

The next candidate should be a separately preregistered **probabilistic opponent / pair model** with explicit development and untouched holdout periods. Its target should directly estimate something close to:

- `P(candidate finishes top2 | pre-race features)`; and/or
- `P(◎ and candidate form the quinella pair | pre-race features)`.

Use only pre-race information. Market/value should remain a final ticket-role layer, not the outcome target itself.

The development period, feature set, model family, calibration method, candidate selection rule and holdout period must all be frozen before viewing holdout HJC.

## 9. Result cache

Normalized HJC payouts for all 84 races are stored separately as:

`horse-racing/jrdb/result_cache/RaceNote_Prospective_20251004_13_25_HJC_Payouts.csv`

These October races are settled and must not be reused as fresh blind targets.
