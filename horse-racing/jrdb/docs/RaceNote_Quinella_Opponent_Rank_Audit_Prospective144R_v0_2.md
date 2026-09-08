# RaceNote Quinella Opponent Rank Audit — Prospective 144R / v0.2

## Scope

This audit uses only the preregistered prospective blind blocks already frozen before HJC:

- 2025-03-01 / 2025-03-02 — 72R
- 2025-06-28 / 2025-06-29 — 72R
- total: 144R

The prediction marks are not changed. This is a post-settlement audit of the frozen order below ◎:

- ○
- ▲
- △1
- △2

Current quinella baseline buys only:

- ◎-○
- ◎-▲

The audit asks whether useful counterpart horses were already inside the five marks but ranked below the current quinella cut line.

## 1. v0.2 — four individual quinella tickets

Each ticket is treated as 100 yen in every race.

| Ticket | Investment | Hits | Payout | Return | Avg payout / hit |
|---|---:|---:|---:|---:|---:|
| ◎-○ | 14,400 | 22 | 12,190 | **84.65%** | 554 |
| ◎-▲ | 14,400 | 8 | 6,480 | **45.00%** | 810 |
| ◎-△1 | 14,400 | 8 | 10,910 | **75.76%** | 1,364 |
| ◎-△2 | 14,400 | 11 | 13,860 | **96.25%** | 1,260 |

The observed hit order is therefore:

```text
○ 22 > △2 11 > ▲ 8 = △1 8
```

This is not the monotonic order expected from a clean prediction ranking (`○ > ▲ > △1 > △2`).

In particular, △2 produced more winning quinella counterparts than both ▲ and △1 in this 144R sample.

## 2. Current two-ticket baseline vs four-ticket flow

### Current baseline — ◎-○ / ◎-▲

- investment: 28,800
- payout: 18,670
- hit races: 30 / 144
- return: **64.83%**

### Four-ticket — ◎ to all four marks

- investment: 57,600
- payout: 43,440
- hit races: 49 / 144
- return: **75.42%**

Adding △1 / △2 therefore adds:

- +19 hit races
- +24,770 payout
- +28,800 investment
- incremental return of the two additional tickets: **86.01%**

Thus simply buying all four improves observed return from 64.83% to 75.42%, but still does not reach break-even. This is evidence for an opponent-ranking / selection issue, not evidence to promote a four-ticket production policy.

## 3. Where was the actual quinella counterpart when ◎ finished top2?

v0.2 ◎ was in the winning quinella in **74 / 144 races**.

The counterpart position inside the frozen marks was:

| Counterpart location | Races | Share of ◎-top2 races |
|---|---:|---:|
| ○ | 22 | 29.7% |
| ▲ | 8 | 10.8% |
| △1 | 8 | 10.8% |
| △2 | 11 | 14.9% |
| outside the other four marks | 25 | 33.8% |
| **Total** | **74** | **100%** |

Among the 49 races where the counterpart was already inside the five-mark set:

- current ○/▲ tickets captured 30
- △1/△2 contained the counterpart in **19**

Therefore **19 / 49 = 38.8%** of the in-set winning counterparts were missed only because the opponent was ranked below the current quinella cut line.

Relative to all 74 races where ◎ reached top2, these are **19 / 74 = 25.7%** of axis-correct races missed by the ○/▲ cutoff despite the counterpart already being selected inside the five marks.

There is also a separate candidate-set issue: in **25 / 74 = 33.8%** of ◎-top2 races, the actual counterpart was outside all four opponent marks.

So two different problems exist:

1. **opponent ordering / cut-line problem** — counterpart was in △1/△2;
2. **opponent recall problem** — counterpart was outside the five marks entirely.

## 4. Comparison with v0.1 control

### Individual roles

| Ticket | v0.1 return | v0.2 return |
|---|---:|---:|
| ◎-○ | 59.86% | **84.65%** |
| ◎-▲ | **80.14%** | 45.00% |
| ◎-△1 | **77.99%** | 75.76% |
| ◎-△2 | 70.28% | **96.25%** |
| four-ticket total | 72.07% | **75.42%** |

For v0.1, the winning counterpart counts were:

```text
○ 17 > ▲ 15 > △1 9 > △2 7
```

That order was substantially more monotonic than v0.2.

v0.2 improved the ◎ axis, but the lower-order ranking became less orderly: ○ strengthened, ▲ weakened sharply, and △2 captured many useful counterparts.

This supports reviewing the **opponent-ranking stage separately from the ◎ selection stage**.

## 5. Block stability

v0.2 returns by independent 72R block:

| Ticket | Mar 2025 | Jun 2025 |
|---|---:|---:|
| ◎-○ | 126.53% | 42.78% |
| ◎-▲ | 49.86% | 40.14% |
| ◎-△1 | 129.03% | 22.50% |
| ◎-△2 | 54.72% | 137.78% |
| four-ticket total | 90.03% | 60.80% |
| current ○/▲ two-ticket | 88.19% | 41.46% |

The role-level economics are highly unstable across blocks. In particular, △2 changed from weak in March to very strong in June.

Therefore no role swap should be promoted from the same 144R sample.

## 6. Post-hoc two-opponent combinations — diagnostic only

If two roles were selected mechanically from the same already-observed 144R results, v0.2 would have produced:

| Two roles | Return |
|---|---:|
| ○ + ▲ (current) | 64.83% |
| ○ + △1 | 80.21% |
| ○ + △2 | **90.45%** |
| ▲ + △1 | 60.38% |
| ▲ + △2 | 70.63% |
| △1 + △2 | 86.01% |

This is **not** a valid production-selection result because it is post-hoc. It is useful only as evidence that the current `○ + ▲` cut is not obviously aligned with the strongest observed quinella counterpart roles under v0.2.

## 7. Interpretation

### What the 144R supports

1. The user's concern is real: good counterpart horses are often already selected but placed in △ rather than ○/▲.
2. The current five-mark ranking is not sufficiently monotonic below ◎ under v0.2.
3. The problem should not be solved simply by buying four tickets; the incremental △ tickets returned 86.01%, still below break-even.
4. v0.2's axis improvement and opponent-ranking issue should be treated as separate model components.
5. A dedicated **opponent ranking / paired-top2 layer** is justified for prospective testing.

### What the 144R does not support

1. Do not replace ▲ with △2 based on this sample.
2. Do not buy all four as the new production baseline.
3. Do not optimize the next rule to `○ + △2`; that is a post-hoc winner on this sample.
4. Do not treat △2 as a permanent longshot/value slot.

## 8. Recommended next candidate

Keep the current v0.2 ◎ selection unchanged.

After ◎ is frozen, separately rank the remaining candidates for **paired top2 suitability with ◎**, rather than reusing exactly the same win-oriented order used for ○▲△.

Candidate inputs may include:

- sufficient base ability / IDM / total level;
- stable expected position and trip;
- pace/style compatibility for finishing top2 rather than necessarily winning;
- distance / surface suitability;
- current condition;
- complementary race-shape relationship to ◎;
- uncertainty / failure-mode penalty.

Market/value should remain separate from this probability ranking.

Prospective test should compare, before HJC:

- Baseline Q2: ◎-○ / ◎-▲
- Candidate Q2: ◎ to two opponent-specific ranked horses
- Diagnostic Q4: ◎ to all four frozen marks

This will directly test whether the issue is **ordering** rather than simply insufficient ticket count.
