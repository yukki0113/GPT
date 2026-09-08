# RaceNote Quinella Opponent Rank Audit — Prospective 144R / v0.1 vs v0.2

## Scope

This audit uses only the two preregistered prospective blind blocks:

- 2025-03-01 / 2025-03-02 — 72R
- 2025-06-28 / 2025-06-29 — 72R
- total 144R

The marks remain frozen. Every ticket below is a post-settlement diagnostic using 100 yen per race.

## 1. Individual quinella tickets

| Ticket | v0.1 hits | v0.1 payout | v0.1 return | v0.2 hits | v0.2 payout | v0.2 return |
|---|---:|---:|---:|---:|---:|---:|
| ◎-○ | 17 | 8,620 | 59.86% | **22** | **12,190** | **84.65%** |
| ◎-▲ | **15** | **11,540** | **80.14%** | 8 | 6,480 | 45.00% |
| ◎-△1 | **9** | **11,230** | **77.99%** | 8 | 10,910 | 75.76% |
| ◎-△2 | 7 | 10,120 | 70.28% | **11** | **13,860** | **96.25%** |

Hit-count ordering:

```text
v0.1: ○17 > ▲15 > △1 9 > △2 7
v0.2: ○22 > △2 11 > ▲8 = △1 8
```

v0.1 is substantially more monotonic below ◎. v0.2 strengthens the ◎ axis and ○, but the ordering from ▲ through △2 is not monotonic.

## 2. Two-ticket baseline vs four-ticket flow

| Policy | v0.1 hits | v0.1 payout / investment | v0.1 return | v0.2 hits | v0.2 payout / investment | v0.2 return |
|---|---:|---:|---:|---:|---:|---:|
| Current Q2 = ◎-○ / ◎-▲ | **32** | 20,160 / 28,800 | **70.00%** | 30 | 18,670 / 28,800 | 64.83% |
| Q4 = ◎ to ○▲△1△2 | 48 | 41,510 / 57,600 | 72.07% | **49** | **43,440 / 57,600** | **75.42%** |
| Incremental △1+△2 only | 16 | 21,350 / 28,800 | 74.13% | **19** | **24,770 / 28,800** | **86.01%** |

The candidate v0.2 has a better axis, yet the existing Q2 captures fewer races than v0.1 (30 vs 32). Expanding to all four opponents restores one extra hit beyond v0.1 (49 vs 48), but neither model reaches break-even with Q4.

## 3. Where was the actual quinella counterpart when ◎ finished top2?

### v0.1

v0.1 ◎ finished in the winning quinella in **69 / 144** races.

| Counterpart location | Races | Share of ◎-top2 races |
|---|---:|---:|
| ○ | 17 | 24.6% |
| ▲ | 15 | 21.7% |
| △1 | 9 | 13.0% |
| △2 | 7 | 10.1% |
| outside the other four marks | 21 | 30.4% |
| **Total** | **69** | **100%** |

- counterpart already inside the five marks: 48 races
- captured by current ○/▲ cutoff: 32
- counterpart in △1/△2 and therefore missed by cutoff: **16**
- cutoff miss among in-set counterparts: **16 / 48 = 33.3%**
- cutoff miss among all axis-correct races: **16 / 69 = 23.2%**
- counterpart outside five marks: **21 / 69 = 30.4%**

### v0.2

v0.2 ◎ finished in the winning quinella in **74 / 144** races.

| Counterpart location | Races | Share of ◎-top2 races |
|---|---:|---:|
| ○ | 22 | 29.7% |
| ▲ | 8 | 10.8% |
| △1 | 8 | 10.8% |
| △2 | 11 | 14.9% |
| outside the other four marks | 25 | 33.8% |
| **Total** | **74** | **100%** |

- counterpart already inside the five marks: 49 races
- captured by current ○/▲ cutoff: 30
- counterpart in △1/△2 and therefore missed by cutoff: **19**
- cutoff miss among in-set counterparts: **19 / 49 = 38.8%**
- cutoff miss among all axis-correct races: **19 / 74 = 25.7%**
- counterpart outside five marks: **25 / 74 = 33.8%**

## 4. Direct interpretation

The comparison supports three separate conclusions.

### 4.1 v0.2 improved the axis

- ◎ top2: v0.1 69/144 -> v0.2 74/144

This is consistent with the earlier suitability-first axis findings.

### 4.2 v0.2 did not improve opponent recall

When the axis was correct, the actual counterpart was inside the remaining four marks:

- v0.1: 48/69 = **69.6%**
- v0.2: 49/74 = **66.2%**

So v0.2's gain is not from broadly finding more counterpart horses.

### 4.3 v0.2 worsened the current ○/▲ cut-line efficiency

Among in-set counterparts, the current Q2 captured:

- v0.1: 32/48 = **66.7%**
- v0.2: 30/49 = **61.2%**

And the lower-mark miss rate increased:

- v0.1: 33.3%
- v0.2: **38.8%**

Therefore the user's concern is supported in both versions, but it is **more pronounced in v0.2**: the candidate improved ◎ while making the lower-order ranking less suitable for the fixed `◎-○ / ◎-▲` quinella rule.

## 5. What not to conclude

Do not promote any post-hoc role combination from this 144R sample.

In particular:

- do not replace ▲ with △2 merely because v0.2 `◎-△2` returned 96.25%;
- do not make Q4 the production rule merely because it improves observed return;
- do not change prediction marks to optimize quinella tickets.

## 6. Next prospective candidate

Keep v0.2 ◎ selection unchanged.

After ◎ is fixed, create a separate **quinella-opponent ranking** among the remaining candidates, optimized conceptually for paired top2 suitability with ◎ rather than for independent win rank.

Future blind settlement should freeze and compare:

1. `Q2_baseline`: ◎-○ / ◎-▲
2. `Q2_opponent`: ◎ to the two dedicated opponent-ranked horses
3. `Q4_diagnostic`: ◎ to all four prediction marks

This cleanly separates:

- axis selection;
- opponent recall;
- opponent ordering;
- ticket economics.
