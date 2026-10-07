# RaceNote v0.5.0 A/B — BTDAY-0051 / 0052 Result Analysis

Status: **POST-FREEZE RESULT ANALYSIS — 2 DAYS / 48 RACES**  
Date: 2026-10-07

## Scope

Compare the frozen clean-blind forecasts:

- Lane A: `RaceNote-Human-Context-Reader-0.4.6-candidate`
- Lane B: `RaceNote-Human-Context-Reader-0.5.0-candidate`

Days:

- BTDAY-0051: 2026-04-04, 24 races
- BTDAY-0052: 2026-01-10, 24 races

Both days passed `BOTH_LANES_FROZEN_CLEAN_BLIND` before result opening.

## Result source

Canonical 2026 JRDB Raw on Google Drive was used.

BTDAY-0051:

- SED: `SED260404.zip`
- HJC: `HJC260404.zip`

BTDAY-0052:

- SED: `SED260110.zip`
- HJC: `HJC260110.zip`

SED and HJC each produced 24 races on both days. SED win/place payouts matched
HJC on all 48 races; cross-validation mismatch count = 0.

## Core prediction metrics

| Scope | Lane | ◎ win | ◎ top2 | ◎ top3 | ▲ win | ▲ top3 | winner in 5 marks | avg actual top3 captured |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| BTDAY-0051 | v0.4.6 | 6/24 (25.0%) | 13/24 (54.2%) | 16/24 (66.7%) | 5/24 (20.8%) | 9/24 (37.5%) | 18/24 (75.0%) | 2.250 |
| BTDAY-0051 | v0.5.0 | 6/24 (25.0%) | 12/24 (50.0%) | 17/24 (70.8%) | 3/24 (12.5%) | 10/24 (41.7%) | 17/24 (70.8%) | 2.292 |
| BTDAY-0052 | v0.4.6 | 4/24 (16.7%) | 11/24 (45.8%) | 16/24 (66.7%) | 5/24 (20.8%) | 10/24 (41.7%) | 19/24 (79.2%) | 2.208 |
| BTDAY-0052 | v0.5.0 | 5/24 (20.8%) | 11/24 (45.8%) | 15/24 (62.5%) | 2/24 (8.3%) | 3/24 (12.5%) | 18/24 (75.0%) | 2.042 |
| **Combined** | **v0.4.6** | **10/48 (20.8%)** | **24/48 (50.0%)** | **32/48 (66.7%)** | **10/48 (20.8%)** | **19/48 (39.6%)** | **37/48 (77.1%)** | **2.229** |
| **Combined** | **v0.5.0** | **11/48 (22.9%)** | **23/48 (47.9%)** | **32/48 (66.7%)** | **5/48 (10.4%)** | **13/48 (27.1%)** | **35/48 (72.9%)** | **2.167** |

◎ was identical in 39/48 races. v0.5.0 changed ◎ in only nine races and the
changed ◎ finished better in six races and worse in three.

v0.5.0 continued to choose a materially more longshot-oriented ▲:

- v0.4.6 ▲ final popularity median: 4th; mean 4.31
- v0.5.0 ▲ final popularity median: 7th; mean 7.00
- v0.4.6 ▲ final win odds median: 8.75
- v0.5.0 ▲ final win odds median: 18.1
- v0.4.6 ▲ final win odds mean: 10.76
- v0.5.0 ▲ final win odds mean: 37.99

## Fixed-ticket settlement

All tickets are fixed at 100 yen.

### BTDAY-0051

| Formation | v0.4.6 ROI | v0.5.0 ROI |
|---|---:|---:|
| ◎ win | 55.0% | **63.7%** |
| ◎ place | 80.8% | **85.0%** |
| Quinella ◎-○ | **119.6%** | 109.2% |
| Quinella ◎-▲ | **61.7%** | 19.6% |
| Quinella ◎-○▲ | **90.6%** | 64.4% |
| Exacta ◎→○ | 42.9% | **77.5%** |
| Exacta ◎→▲ | 34.2% | 34.2% |
| Exacta ◎→○▲ | 38.5% | **55.8%** |
| Trio ◎ axis -> other 4 marks | 60.3% | **102.4%** |
| Trifecta ◎ 1st-fixed -> other 4 marks | 21.5% | **74.1%** |

### BTDAY-0052

| Formation | v0.4.6 ROI | v0.5.0 ROI |
|---|---:|---:|
| ◎ win | 28.3% | **48.3%** |
| ◎ place | **83.3%** | 74.6% |
| Quinella ◎-○ | 98.8% | **113.8%** |
| Quinella ◎-▲ | **66.2%** | 0.0% |
| Quinella ◎-○▲ | **82.5%** | 56.9% |
| Exacta ◎→○ | 25.8% | **54.2%** |
| Exacta ◎→▲ | **57.5%** | 0.0% |
| Exacta ◎→○▲ | **41.7%** | 27.1% |
| Trio ◎ axis -> other 4 marks | **71.0%** | 38.0% |
| Trifecta ◎ 1st-fixed -> other 4 marks | **25.0%** | 19.3% |

### Combined 48 races

| Formation | v0.4.6 hits | v0.4.6 ROI | v0.5.0 hits | v0.5.0 ROI |
|---|---:|---:|---:|---:|
| ◎ win | 10 | 41.7% | 11 | **56.0%** |
| ◎ place | 32 | **82.1%** | 32 | 79.8% |
| Quinella ◎-○ | 9 | 109.2% | 10 | **111.5%** |
| Quinella ◎-▲ | 6 | **64.0%** | 1 | 9.8% |
| Quinella ◎-○▲ | 15 | **86.6%** | 11 | 60.6% |
| Exacta ◎→○ | 3 | 34.4% | 5 | **65.8%** |
| Exacta ◎→▲ | 3 | **45.8%** | 1 | 17.1% |
| Exacta ◎→○▲ | 6 | 40.1% | 6 | **41.5%** |
| Trio flow | 15 | 65.7% | 13 | **70.2%** |
| Trifecta flow | 4 | 23.2% | 5 | **46.7%** |

Combined payout/stake:

- v0.4.6 quinella ◎-○▲: 8,310 / 9,600 yen
- v0.5.0 quinella ◎-○▲: 5,820 / 9,600 yen
- v0.4.6 exacta ◎→○▲: 3,850 / 9,600 yen
- v0.5.0 exacta ◎→○▲: 3,980 / 9,600 yen
- v0.4.6 trio: 18,910 / 28,800 yen
- v0.5.0 trio: 20,210 / 28,800 yen
- v0.4.6 trifecta: 13,390 / 57,600 yen
- v0.5.0 trifecta: 26,900 / 57,600 yen

## ▲ payout-boost check

The strong v0.5.0 ◎-▲ pair boost observed on BTDAY-0049 did not reproduce in
BTDAY-0051/0052.

BTDAY-0051 v0.5.0 had only one ◎-▲ quinella hit and one ◎→▲ exacta hit, both
from 阪神8R. BTDAY-0052 had no ◎-▲ quinella or exacta hit at all.

This is not because v0.5.0 never selected a winning ▲. On BTDAY-0052 its ▲ won
京都4R and 京都11R, but ◎ finished third in both races, so neither converted into
the direct ◎-▲ pair ticket.

The distinction is important: ▲ individual upset quality and ▲ contribution to
an ◎-anchored betting formation are different evaluation channels.

## Trio divergence

Across the 48 races:

- v0.4.6 trio hits: 15
- v0.5.0 trio hits: 13
- common hits: 12
- v0.4.6-only hits: 3
- v0.5.0-only hits: 1

Only four races changed the trio hit outcome.

| BTDAY | Race | Winner lane | Trio payout | Structural difference |
|---|---|---|---:|---|
| 0051 | 中山2R | v0.5.0 | 6,840 | new ▲11 completed the actual top3 |
| 0051 | 阪神9R | v0.4.6 | 790 | new v0.5.0 ▲5 displaced old △1=3, which finished 3rd |
| 0052 | 中山2R | v0.4.6 | 1,810 | new v0.5.0 ▲1 displaced old △2=8, which finished 3rd |
| 0052 | 中山11R | v0.4.6 | 2,940 | new v0.5.0 ▲10 displaced old △2=2, which finished 3rd |

v0.5.0 lost three trio hits through an aggressive new ▲ replacing a lower-support
horse, but the one new hit paid 6,840 yen. The three lost payouts total only 5,540
yen. Therefore v0.5.0 had fewer trio hits but a higher total trio payout by 1,300 yen.

This is a clearer example of the intended high-variance trade-off than BTDAY-0049/0050:
frequency decreased, but payout did not.

## Lower-support churn

Across these 48 races, horses from the v0.4.6 set were removed from the v0.5.0
five-horse set at the following rates:

- ◎: 0/48
- ○: 0/48
- ▲: 8/48
- △1: 9/48
- △2: **27/48**

New horses entering the v0.5.0 set most often entered as:

- ▲: 29
- △2: 10
- △1: 5

The fifth-horse boundary remains the most volatile membership position, while the
new ▲ is the main route by which outside horses enter the set.

## Four-day context — BTDAY-0049 through 0052

Across 120 clean-blind races:

Prediction accuracy:

- v0.4.6 ◎ wins: 28/120 (23.3%)
- v0.5.0 ◎ wins: 26/120 (21.7%)
- ◎ top3: both 77/120 (64.2%)
- winner in five marks: v0.4.6 91/120 (75.8%), v0.5.0 86/120 (71.7%)
- average actual top3 captured: v0.4.6 2.200, v0.5.0 2.142

Direct combined pair settlement, using exact accumulated payouts:

- quinella ◎-○▲:
  - v0.4.6: 14,820 / 24,000 = **61.8%**
  - v0.5.0: 21,390 / 24,000 = **89.1%**
- exacta ◎→○▲:
  - v0.4.6: 11,150 / 24,000 = **46.5%**
  - v0.5.0: 24,670 / 24,000 = **102.8%**
- trio flow:
  - v0.4.6: 75,150 / 72,000 = **104.4%**
  - v0.5.0: 52,700 / 72,000 = **73.2%**
- trifecta flow:
  - v0.4.6: 50,910 / 144,000 = **35.4%**
  - v0.5.0: 63,380 / 144,000 = **44.0%**

The four-day trio lead for v0.4.6 is still dominated by the 29,300-yen
BTDAY-0049 中山4R hit. Removing that single race from both lanes gives approximately:

- v0.4.6 trio ROI: 64.2%
- v0.5.0 trio ROI: 73.8%

So the evidence still does not support a stable structural trio advantage for
v0.4.6.

## Current judgment

After four clean-blind BTDAYs / 120 races:

1. v0.5.0 has not established superior raw prediction accuracy.
2. v0.5.0's ▲ remains materially more longshot-oriented, but its direct ◎-▲
   contribution is highly volatile and did not repeat on BTDAY-0051/0052.
3. Despite the failed direct pair boost in the latest 48 races, v0.5.0 still leads
   the cumulative 120-race ◎→○▲ exacta ROI, 102.8% vs 46.5%.
4. Trio hit frequency is slightly lower for v0.5.0, but current evidence suggests
   a high-variance trade-off rather than simple loss of stability.
5. △2 remains highly unstable under v0.5.0. The next research focus should continue
   separating independent ▲ quality from lower-support / fifth-horse coverage.
6. More clean-blind BTDAYs are required before promotion/rejection; current differences
   remain too sensitive to individual high-payout races.
