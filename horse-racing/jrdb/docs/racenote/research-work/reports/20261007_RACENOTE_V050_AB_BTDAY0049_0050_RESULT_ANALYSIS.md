# RaceNote v0.5.0 A/B — BTDAY-0049 / 0050 Result Analysis

Status: **POST-FREEZE RESULT ANALYSIS — 2 DAYS / 72 RACES**  
Date: 2026-10-07

## Scope

Compare the frozen clean-blind forecasts:

- Lane A: `RaceNote-Human-Context-Reader-0.4.6-candidate`
- Lane B: `RaceNote-Human-Context-Reader-0.5.0-candidate`

Days:

- BTDAY-0049: 2026-03-22, 36 races
- BTDAY-0050: 2026-09-05, 36 races

Both days passed `BOTH_LANES_FROZEN_CLEAN_BLIND` before result opening.

## Result source

Canonical 2026 JRDB Raw on Google Drive was used.

BTDAY-0049:

- SED: `SED260322.zip`, Drive id `1u6b7PiFJfLaieqRWAU_Oc7Dm9uF4-zOI`
- HJC: `HJC260322.zip`, Drive id `1MkajtgcG3g945vi_CbgP891p5TsjZ6fK`

BTDAY-0050:

- SED: `SED260905.zip`, Drive id `1_SO1RlmVCcbLceA_ol_BIQG0GvjTE25R`
- HJC: `HJC260905.zip`, Drive id `1ZGeq1st5CbFV6pMJMFu9NNz3aJsjx3f1`

SED produced 36 races on each day. HJC produced 36 races on each day. SED win/place payouts matched HJC on all 72 races; cross-validation mismatch count = 0.

## Core prediction metrics

| Scope | Lane | ◎ win | ◎ top2 | ◎ top3 | ▲ win | ▲ top3 | winner in 5 marks | avg actual top3 captured |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| BTDAY-0049 | v0.4.6 | 9/36 (25.0%) | 16/36 (44.4%) | 21/36 (58.3%) | 2/36 (5.6%) | 16/36 (44.4%) | 27/36 (75.0%) | 2.139 |
| BTDAY-0049 | v0.5.0 | 8/36 (22.2%) | 15/36 (41.7%) | 22/36 (61.1%) | 1/36 (2.8%) | 12/36 (33.3%) | 26/36 (72.2%) | 2.056 |
| BTDAY-0050 | v0.4.6 | 9/36 (25.0%) | 15/36 (41.7%) | 24/36 (66.7%) | 2/36 (5.6%) | 12/36 (33.3%) | 27/36 (75.0%) | 2.222 |
| BTDAY-0050 | v0.5.0 | 7/36 (19.4%) | 13/36 (36.1%) | 23/36 (63.9%) | 4/36 (11.1%) | 11/36 (30.6%) | 25/36 (69.4%) | 2.194 |
| **Combined** | **v0.4.6** | **18/72 (25.0%)** | **31/72 (43.1%)** | **45/72 (62.5%)** | **4/72 (5.6%)** | **28/72 (38.9%)** | **54/72 (75.0%)** | **2.181** |
| **Combined** | **v0.5.0** | **15/72 (20.8%)** | **28/72 (38.9%)** | **45/72 (62.5%)** | **5/72 (6.9%)** | **23/72 (31.9%)** | **51/72 (70.8%)** | **2.125** |

Winner mark distribution across 72 races:

| Lane | ◎ | ○ | ▲ | △1 | △2 | unmarked |
|---|---:|---:|---:|---:|---:|---:|
| v0.4.6 | 18 | 16 | 4 | 5 | 11 | 18 |
| v0.5.0 | 15 | 14 | 5 | 11 | 6 | 21 |

## Paired interpretation

The two Reader designs produced the same ◎ in 58/72 races. On the 14 races where ◎ changed:

- v0.5.0 ◎ finished better: 6
- v0.5.0 ◎ finished worse: 8

At the binary ◎-win level, only five races were discordant:

- v0.4.6 only won: 4
- v0.5.0 only won: 1
- exact paired-binomial p = 0.375

◎ top3 was exactly tied overall at 45/72. Discordant top3 races were 5 vs 5.

Five-mark winner capture:

- v0.4.6 only captured winner: 8 races
- v0.5.0 only captured winner: 5 races
- paired-binomial p = 0.581

These samples therefore do **not** support a statistically reliable difference yet.

## ▲ behavior

v0.5.0 materially changed the character of ▲.

Across the 72 forecasts, post-result market inspection shows:

| Lane | ▲ median final popularity | ▲ mean final popularity | ▲ median win odds | ▲ mean win odds |
|---|---:|---:|---:|---:|
| v0.4.6 | 4th | 4.28 | 8.3 | 12.18 |
| v0.5.0 | 6th | 6.29 | 18.95 | 36.30 |

Thus v0.5.0's ▲ was much more longshot-oriented. Its top3 frequency fell from 28/72 to 23/72, but wins increased from 4 to 5.

This is consistent with a more asymmetric ▲ interpretation, but 72 races are too few to claim that the Reader change caused the effect.

## Mark-only betting economics — separate from prediction accuracy

For diagnostic purposes only, each mark was treated as one independent 100-yen win/place bet in every race. This is **not** the primary A/B criterion.

Win ROI:

| Mark | v0.4.6 | v0.5.0 |
|---|---:|---:|
| ◎ | 60.7% | 44.3% |
| ○ | 99.4% | 88.2% |
| ▲ | 32.6% | 55.0% |
| △1 | 34.6% | 142.5% |
| △2 | 331.1% | 75.8% |

Place ROI:

| Mark | v0.4.6 | v0.5.0 |
|---|---:|---:|
| ◎ | 80.6% | 80.0% |
| ○ | 78.1% | 65.8% |
| ▲ | 93.1% | 111.7% |
| △1 | 85.0% | 93.2% |
| △2 | 85.6% | 85.3% |

The large v0.4.6 △2 win ROI and v0.5.0 △1 win ROI are driven by sparse longshot wins and must not be interpreted as stable profitability.

## Day-level changes

BTDAY-0049:

- same ◎: 29/36
- same ▲: 12/36
- exact five-horse set: 8/36
- v0.5.0 gained two winners that v0.4.6 omitted, but lost three winners that v0.4.6 included
- changed ◎ finished better in 3 races and worse in 4

BTDAY-0050:

- same ◎: 29/36
- same ▲: 9/36
- exact five-horse set: 6/36
- v0.5.0 gained three winners that v0.4.6 omitted, but lost five winners that v0.4.6 included
- changed ◎ finished better in 3 races and worse in 4

The strongest positive v0.5.0 change in BTDAY-0050 was 阪神4R, where v0.5.0's changed ▲ included the winner while v0.4.6 did not.

## Current judgment

After two clean-blind days / 72 races:

1. v0.5.0 has **not demonstrated an overall accuracy improvement** over v0.4.6.
2. ◎ top3 performance is exactly tied, while v0.5.0 trails in ◎ wins, ◎ top2, winner-in-five capture and total top3 capture.
3. v0.5.0 appears to move ▲ toward a genuinely more asymmetric / higher-price role.
4. The observed accuracy differences are small relative to sample size; paired tests do not indicate a reliable difference.
5. The correct next action is to continue prospective same-BTDAY A/B sampling rather than promote or reject v0.5.0 from these two days alone.

BTDAY-0049 v0.4.6 has weaker qualitative Decision Trace quality than BTDAY-0050, so mark-level numerical comparison is valid, but detailed causal prose attribution for that lane/day should be treated cautiously.
