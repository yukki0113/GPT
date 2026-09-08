# RaceNote v0.6a Pair-Compatibility Blind Result — 2025-09-15 / 09-21 / 09-27

## Status

**FIRST UNTOUCHED v0.6a BLIND BLOCK / 72 RACES**

- v0.6 original design commit: `c6c424f5c681222a797b01fd3ad49099d5901398`
- v0.6a pre-result correction commit: `93c18411eb16a30c4947b64884dc099e7b97bae0`
- pre-HJC freeze commit: `f547f6e3c243ade2b8cf3e1f150aaba0540c2143`
- prediction payload SHA-256: `d35c6bf4504b154622b0f4537b2ffa10641b4bd0705c0c72fd4aa65f3463801e`
- initial v0.6 activation 0/72 triggered preregistered engineering stop; no result was opened before v0.6a correction
- v0.6a activation: **2/72 = 2.8%**; no further calibration
- HJC acquired only after freeze commit

HJC SHA-256:

- 2025-09-15: `12dd44b5c623ec1cc906201794e752a7b015aa0ede79a99a81263617751bd01f`
- 2025-09-21: `4f765555095dae25ec7a57f0771ed83c107a01d1fdc01d4a1110b1c5257ff12d`
- 2025-09-27: `c3babeb7c4cc5bb8a777a5c93feeced63fe4ce7eb43b23c77932d5abb605df1f`

## 1. Axis — 72R

- ◎ win: 22/72 = **30.56%**
- ◎ top2: 37/72 = **51.39%**
- ◎ top3: 47/72 = **65.28%**
- ◎ win return: 7,200 -> 5,670 = **78.75%**

v0.2 and v0.6a share the same ◎/○ axis.

## 2. Q2 — all 72R

Q2 = `◎-○ / ◎-▲`, 100円 each.

| selector | investment | payout | hit races | return |
|---|---:|---:|---:|---:|
| v0.2 pure P3 | 14,400 | **9,900** | **18** | **68.75%** |
| v0.6a | 14,400 | 9,600 | 17 | 66.67% |

v0.6a did not improve Q2 in the first blind block.

## 3. Changed-role comparison — 2 races

### Quinella `◎-▲`

- pure P3: 200 -> **300**, 1 hit = **150.0%**
- v0.6a ▲: 200 -> 0, 0 hits = **0.0%**
- v0.6a-only gains: 0
- pure-P3-only losses: 1

### Wide `◎-▲`

- pure P3: 200 -> **730**, 2 hits = **365.0%**
- v0.6a ▲: 200 -> 630, 1 hit = **315.0%**

Concrete cases:

- 2025-09-21 中山7R — value promotion: pure P3 #10 -> P4 #8. Quinella old/new = **300 / 0**; wide = 190 / **630**.
- 2025-09-21 阪神9R — pair override: pure P3 #3 -> P4 #10. Quinella old/new = 0 / 0; wide = **540 / 0**.

The value path found a higher wide payout but lost a small quinella. The pair-override path lost a pure-P3 wide and added no hit. With only two promotions, this is negative but far too small for a stable conclusion.

## 4. Other policies

- Q4: 28,800 -> 19,850 = **68.92%**
- Trio A6: 43,200 -> 30,870 = **71.46%**
- Trio B5: 36,000 -> 30,870 = **85.75%**

Top-five membership is unchanged, so Q4 and Trio A6 are identical across selectors. Trio B5 also happened to settle identically in this block.

## 5. Confidence — 72R

| confidence | N | ◎ win | ◎ top2 | ◎ top3 | ◎ win return | v0.2 Q2 return |
|---|---:|---:|---:|---:|---:|---:|
| A | 14 | 35.71% | 42.86% | 64.29% | 63.57% | 27.14% |
| B | 34 | 29.41% | 47.06% | 61.76% | 76.76% | 38.53% |
| C | 24 | 29.17% | **62.50%** | **70.83%** | **90.42%** | **135.83%** |

Confidence again does not order cleanly in this block. Keep it as an explanatory confidence label, not an automatic buy filter.

## 6. Decision

### Production/default

**KEEP v0.2 pure P3.**

### v0.6a

**CONTINUE UNCHANGED TO A SECOND UNTOUCHED BLOCK; DO NOT PROMOTE OR RETUNE.**

The new pair-compatibility information target is conceptually distinct from v0.5, but the first block produced no quinella gain and one direct quinella loss. The changed-role sample is only two races, so the preregistered replication requirement still governs.

If the second untouched block again fails to produce incremental value, stop threshold work on this heuristic pair model and consider a learned/calibrated top2 pair model using a strictly separated development period rather than additional hand-gate tuning.

## 7. Result cache

Normalized payouts for all 72 races are stored separately as:

`horse-racing/jrdb/result_cache/RaceNote_Prospective_20250915_21_27_HJC_Payouts.csv`

These races are settled and must not be reused as fresh blind targets.
