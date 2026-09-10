# RaceNote v1.1-P Polarity-Gated Repeat Blind Result — 2026-07-05 / 07-11 / 07-12

Status: **SETTLED / KEEP_UNCHANGED / ADVANCE_TO_TRUE_FORWARD**

## Blind boundary

- target races: 108
- prediction freeze commit: `768428c0d92835119739b9507218f9ac3232a7b8`
- freeze manifest SHA-256: `5ff7358e5e20c18f296cf23fbb012bd5d3625ebf48ff1fee7bae188a90181d49`
- frozen combined canonical payload SHA-256: `8dec27b88774524302379be8266a2318bbb2827a1ef251bfd94731d2f9528c44`
- result data used at prediction freeze: `false`
- settlement run: `34424632511`
- settlement commit: `6532e47e316eea5619c18a8497f4a391c1265492`
- settlement manifest SHA-256: `4ed98dc27274d9ff6e19ccf0566a08d308376aafe278ebb0c34bbe315662b3e3`

Target HJC / SED were acquired only after the immutable PRE_HJC prediction freeze existed.

Metrics below were deterministically re-aggregated from the committed PRE_HJC freeze, settled 108-race outputs, SED finish cache and HJC payout cache. The primary metrics were independently cross-checked from frozen marks + SED + HJC and matched the settlement-derived aggregation exactly.

## Repeat block primary comparison

| Metric | v0.2 control | v1.1-P candidate |
|---|---:|---:|
| ◎ win | 36 | 38 |
| ◎ top2 | 45 | 51 |
| ◎ top3 | 57 | 60 |
| win ROI | 0.8815 | 0.9231 |
| Q2 hits | 26 | 30 |
| Q2 ROI | 0.8042 | 1.0421 |

The polarity gate changed the axis in **18 / 108 races (16.7%)**.

On those 18 changed-axis races:

- ◎ win: 4 -> 6
- ◎ top2: 5 -> 11
- ◎ top3: 9 -> 12
- win ROI: 0.6167 -> 0.8667
- Q2 hits: 1 -> 5
- Q2 ROI: 0.1028 -> 1.5306
- Q4 ROI: 0.2250 -> 1.6125
- Trio A6 ROI: 1.1722 -> 1.0519
- direct finish comparison: v0.2 better in 6 races, v1.1-P better in 12 races

The preregistered top-five polarity bootstrap remains inconclusive:

- positive-minus-negative win-rate difference: `0.0255`, 95% CI `[-0.0690, 0.1141]`
- positive-minus-negative top3-rate difference: `0.0130`, 95% CI `[-0.1140, 0.1371]`

Both intervals include zero.

## Two-block combined view — 216 races

The first untouched block was 2026-07-04 / 07-25 / 07-26. Combining only the same predeclared primary definitions across the two 108-race blocks gives:

| Metric | v0.2 control | v1.1-P candidate |
|---|---:|---:|
| ◎ win | 70 | 72 |
| ◎ top2 | 95 | 101 |
| ◎ top3 | 122 | 129 |
| win ROI | 0.8375 | 0.8574 |
| Q2 hits | 49 | 53 |
| Q2 ROI | 0.6998 | 0.8403 |

Across both blocks the axis changed in **32 / 216 races (14.8%)**.

On those 32 changed-axis races:

- ◎ win: 6 -> 8
- ◎ top2: 10 -> 16
- ◎ top3: 15 -> 22
- Q2 ROI: 0.2672 -> 1.2156
- direct finish comparison: v0.2 better in 14 races, v1.1-P better in 18 races

Block 1 improved top3 containment and Q2 economics but left wins/top2 unchanged and lost the direct finish comparison 8-6. The untouched repeat block improved wins, top2, top3 and Q2, and reversed the changed-axis direct comparison to 12-6 in favor of v1.1-P.

## Decision

**KEEP_UNCHANGED.**

Two untouched 108-race blocks now support retaining the polarity-gated axis rule. The repeat block addresses the main weaknesses of Block 1 and the combined 216-race primary metrics favor v1.1-P across win, top2, top3 and Q2.

This is not treated as proof that raw Edge polarity has a stable unconditional performance separation: the top-five race-cluster bootstrap again includes zero. The supported interpretation is narrower: **using polarity only as a gated axis selector inside the frozen top-five / Good-gap structure remains useful enough to keep and move to TRUE_FORWARD validation without parameter retuning.**

Therefore:

- keep `BaseGood - HorseGood <= 0.04` unchanged;
- keep family-vote aggregation and sign-only polarity collapse unchanged;
- do not tune on the settled 216 races;
- preserve the historical validation attribution boundary: fixed Phase1 ACTIVE Registry / ACTIVE-only evidence;
- do not retrofit EdgeDB v0.2 SUGGESTIVE evidence into these settled blocks;
- move the unchanged validated v1.1-P rule to TRUE_FORWARD/shadow operation for the next evidence stage;
- if EdgeDB v0.2 STANDARD is used operationally, keep SUGGESTIVE outside the validated v1.1-P mark-changing path until a separate consumer-policy validation authorizes it.
