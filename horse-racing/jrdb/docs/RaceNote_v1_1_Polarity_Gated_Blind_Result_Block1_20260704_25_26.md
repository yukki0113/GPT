# RaceNote v1.1-P Polarity-Gated Blind Result — Block 1

## Status

**SETTLED / CONTINUE UNCHANGED TO SECOND UNTOUCHED BLOCK**

Settled: 2026-09-10

Target dates:

- 2026-07-04
- 2026-07-25
- 2026-07-26

This document is a compact research interpretation of the immutable settlement metrics. It does not replace the frozen prediction payload or settlement JSON.

## 1. Scientific provenance

PRE_HJC freeze:

- freeze commit: `4aef9a0749f74a35837063ac2805c9ed44f081b5`
- freeze manifest SHA-256: `6ec6dcedcd8b422395118b82af42e726d5c4bfbd11c9090298bc9dd4766089e1`
- combined canonical prediction SHA-256: `be90119c73ce557365b8db39f5194c7be6ecba6d160876798f1f99e96d3262c7`
- `result_data_used=false`

Settlement:

- Issue: `#767`
- run: `34420257178`
- settlement commit: `555cfbc21aea6a9fede971efdea55c4d5d0c7005`
- metrics SHA-256: `5f49d53ff7973b7f42cbf6d4b3840c28765519154efa43d4bf95999d9ba31061`
- manifest SHA-256: `4265f148f40e9be2fe4ce3294139df933c902fb3c4c5334579ab13b06be2e001`

The PRE_HJC freeze was committed before HJC/SED acquisition. Settlement used HJC as payout authority and SED for finish/order audit.

## 2. Primary result — v1.1-P vs v0.2

All 108 races:

| metric | v0.2 | v1.1-P | delta |
|---|---:|---:|---:|
| axis win | 34/108 (31.48%) | 34/108 (31.48%) | 0 |
| axis top2 | 50/108 (46.30%) | 50/108 (46.30%) | 0 |
| axis top3 | 65/108 (60.19%) | 69/108 (63.89%) | +4 races / +3.70pt |
| axis win ROI | 79.35% | 79.17% | -0.19pt |
| Q2 hit races | 23 | 23 | 0 |
| Q2 ROI | 59.54% | 63.84% | +4.31pt |
| Q4 ROI | 63.96% | 75.74% | +11.78pt |
| Trio A6 ROI | 55.42% | 67.95% | +12.53pt |
| Trio B5 ROI | 62.17% | 64.87% | +2.70pt |

v1.1-P changed the axis in 14/108 races (12.96%).

Changed-axis subset, 14 races:

| metric | v0.2 axis | v1.1-P axis |
|---|---:|---:|
| win | 2/14 | 2/14 |
| top2 | 5/14 | 5/14 |
| top3 | 6/14 | 10/14 |
| win ROI | 33.57% | 32.14% |
| Q2 ROI | 47.86% | 81.07% |
| Q4 ROI | 23.93% | 114.82% |
| Trio A6 ROI | 62.50% | 159.17% |
| Trio B5 ROI | 41.57% | 62.43% |

Direct finish comparison among the 14 changed-axis races:

- v0.2 axis finished better: 8
- v1.1-P axis finished better: 6

Interpretation: the candidate preserved win/top2 performance and increased top3 capture, but the 14-race direct finish comparison does not establish broad axis superiority. Ticket ROI improvements on this small changed-axis subset are secondary and payout-sensitive.

## 3. Comparison with frozen v1.0-R

All 108 races:

- v1.0-R axis: win 34, top2 49, top3 69
- v1.1-P axis: win 34, top2 50, top3 69
- v1.0-R Q2 ROI: 60.46%
- v1.1-P Q2 ROI: 63.84%

v1.1-P vs v1.0-R:

- changed axes: 8
- changed races in any mark position: 45
- lower-order changed positions: 95

On the eight changed-axis races, v1.1-P had the better direct finish in 5 and v1.0-R in 3. The sample is too small for promotion claims.

The redesign greatly reduced the relevance of lower-order Edge-driven rearrangement while preserving the same 69/108 top3 axis count seen in v1.0-R.

## 4. Performance Edge polarity diagnostics

All runners:

- NEGATIVE: n=306, win 6.86%, top3 20.26%
- NEUTRAL: n=517, win 7.54%, top3 22.24%
- POSITIVE: n=541, win 8.87%, top3 27.36%

Race-cluster bootstrap, POSITIVE minus NEGATIVE:

- win-rate difference: +2.01pt, 95% CI `[-1.42pt, +5.45pt]`
- top3-rate difference: +7.10pt, 95% CI `[+1.33pt, +12.65pt]`

Within the frozen v0.2 top five:

- NEGATIVE: n=104, win 15.38%, top3 36.54%
- NEUTRAL: n=194, win 17.01%, top3 45.88%
- POSITIVE: n=242, win 16.94%, top3 41.74%

Race-cluster bootstrap, POSITIVE minus NEGATIVE inside the top five:

- win-rate difference: +1.56pt, 95% CI `[-7.26pt, +9.72pt]`
- top3-rate difference: +5.20pt, 95% CI `[-7.01pt, +16.21pt]`

Interpretation: PerformanceEdgePolarity shows a useful ordered separation at the all-runner population level, particularly for top3 probability. That separation is not yet established with precision inside the v0.2 top-five decision region where v1.1-P actually operates.

PerformanceEdgeTier remains diagnostic only; Block 1 does not justify an ordinal `+2 > +1` rule.

## 5. Value Edge shadow

Value-role shadow would have changed `▲` in only 2/108 races.

It is not part of v1.1-P primary evaluation and provides no reason to activate Value Edge in the candidate. Continue shadow-only recording.

## 6. Decision

Under `RaceNote_v1_1_PolarityAxis_Backtest_Protocol.md`:

- one three-day block cannot promote v1.1-P;
- the candidate produced only 14 changed axes;
- changed-axis win/top2 were tied against v0.2;
- direct finish comparison was mixed;
- the top-five polarity bootstrap intervals still include zero.

Therefore the registered decision is:

> **CONTINUE_UNCHANGED_SECOND_BLOCK**

For the second untouched block:

- do not change `BaseGood - HorseGood <= 0.04`;
- do not change polarity aggregation;
- do not introduce PerformanceEdgeTier magnitude;
- do not activate Value Edge;
- do not alter v0.2 top-five membership;
- do not change tie-breaking or confidence rules;
- use the same settlement definitions and bootstrap method.

Any rule redesign must wait until after the unchanged second block is frozen and settled, and would become a new candidate/version requiring another untouched validation block.
