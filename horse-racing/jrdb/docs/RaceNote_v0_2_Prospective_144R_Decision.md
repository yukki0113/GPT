# RaceNote v0.2 Prospective 144R Decision

## Status

**DECISION: PROVISIONAL PROMOTION OF v0.2 PREDICTION RANKING / v0.1 RETAINED AS SHADOW CONTROL**

This memo combines the two independent untouched prospective blocks:

- 2025-03-01 / 03-02: 72R, 中山 / 阪神 / 小倉
- 2025-06-28 / 06-29: 72R, 函館 / 福島 / 小倉

Total: **144 new races**.

The earlier 219R v0.1 sample remains development/diagnostic data and is not counted as v0.2 validation.

No numerical v0.2 rule was changed between the two prospective blocks.

## 1. Primary prediction result

| Metric | v0.1 control | v0.2 candidate | Delta |
|---|---:|---:|---:|
| ◎ win | 29/144 = 20.14% | **37/144 = 25.69%** | **+5.56pt** |
| ◎ top2 | 69/144 = 47.92% | **74/144 = 51.39%** | +3.47pt |
| ◎ top3 | 94/144 = 65.28% | **96/144 = 66.67%** | +1.39pt |

The improvement is concentrated at the very top of the ranking, especially winner selection.

### Cross-block repeatability

March 72R:
- ◎ win: 20.83% -> **29.17%**
- ◎ top2: 50.00% -> **52.78%**

June 72R:
- ◎ win: 19.44% -> **22.22%**
- ◎ top2: 45.83% -> **50.00%**

The direction is favorable to v0.2 in both independent blocks.

## 2. Paired changed-axis test

v0.2 changed ◎ in **35/144 races**.

Within those 35:

| Capture | v0.1 | v0.2 |
|---|---:|---:|
| win | 4 | **12** |
| top2 | 11 | **16** |
| top3 | 16 | **18** |

Among races where exactly one changed axis won:

- v0.2-only winner: **12**
- v0.1-only winner: **4**

An exact sign/binomial view of the 16 winner-discordant races gives approximately:

- one-sided probability under equal direction: 0.038
- two-sided: 0.077

This is supportive, not definitive. The more important evidence for this engineering decision is that the favorable direction repeated across two independently selected blocks without tuning between them.

## 3. Broad five-horse recall

v0.2 does not materially improve the five-horse candidate set itself.

Across 144R:

- actual top3 horses captured inside the five marks, mean per race:
  - v0.1: **310 / 144 = 2.153**
  - v0.2: 307 / 144 = 2.132
- all actual top3 horses captured:
  - v0.1: 52 races
  - v0.2: **53 races**

Therefore the validated advantage is best described as **better ranking of plausible contenders**, not superior broad recall.

This is consistent with the intended suitability-first design: use ability to form a contender region, then decide which capable horse is most buyable today.

## 4. Prospective betting economics

### Pooled 144R

| Policy | v0.1 | v0.2 |
|---|---:|---:|
| ◎ win | 14,400 -> 7,250 = 50.35% | 14,400 -> 10,200 = **70.83%** |
| ◎-○ / ◎-▲ | 28,800 -> **20,160 = 70.00%** | 28,800 -> 18,670 = 64.83% |
| trio A 6 tickets | 86,400 -> 62,850 = 72.74% | 86,400 -> 82,090 = **95.01%** |
| trio B 5 tickets | 72,000 -> 57,390 = 79.71% | 72,000 -> 65,410 = **90.85%** |
| win + quinella + trio A | 129,600 -> 90,260 = 69.65% | 129,600 -> 110,960 = **85.62%** |

Interpretation:

- v0.2 improves win/trio/aggregate economics relative to v0.1;
- the fixed two-ticket quinella is **worse** under v0.2;
- v0.2 trio A is close to break-even prospectively but still below 100%;
- no claim of profitability is justified.

Prediction promotion is therefore based primarily on axis quality, not return.

## 5. Betting-layer decisions

### Quinella

**No change.**

Do not redefine ▲ as a longshot/value slot. The role contribution changes sharply by block and v0.2's better axis selection did not improve the fixed quinella overall.

The current two-ticket quinella remains a measurement baseline, not a validated production optimum.

### Trio A vs B

**No promotion of the five-ticket formation.**

Pooled v0.2 prospective:

- six-ticket: **95.01%**
- five-ticket: 90.85%

The historical 219R v0.1 diagnostic slightly favored five tickets, while prospective v0.2 currently favors six. Continue to measure both; do not change prediction marks to optimize either.

### ☆ value/disagreement

**Diagnostic only.**

Across the two prospective blocks:

- ☆ selections: 76 total
- winner: 6
- top2: 13
- top3: 19
- true opponent-star races: 70

Post-hoc `◎-☆`:

- March: 4,300 -> 6,990, 3 hits
- June: 2,700 -> 0, 0 hits
- pooled: 7,000 -> 6,990 = **99.86%**, only 3 hits

The apparent March value signal did not replicate. No ☆ ticket is promoted.

## 6. Promotion decision

The preregistered 108-144R decision point has been reached.

The following are now supported:

1. v0.2 materially changes the ranking often enough to matter (35/144 different ◎).
2. Changed-axis winner selection favors v0.2 by 12 vs 4.
3. ◎ win and top2 capture improve in both independent blocks.
4. The improvement occurs without materially improving broad five-horse recall, consistent with suitability-based re-ranking rather than result fishing.
5. The direction survives a major change in season/venue mix: spring 中山/阪神/小倉 and summer 函館/福島/小倉.

Therefore:

### Prediction layer

Promote the tested v0.2 ranking to **provisional preferred/default RaceNote prediction logic** for subsequent prediction work.

### Control

Retain v0.1 unchanged as a **shadow control for at least one additional 72R prospective block**. Do not delete or rewrite its history.

### Betting layer

No betting policy is promoted. Continue A/B measurement; no forced longshot ▲ and no ☆ ticket.

## 7. Important limitation: user-facing short comments

The ranking result and explanation quality are not the same thing.

The tested v0.2 implementation exposes relevant distance/pace/frame/state evidence, but its automatic short-comment renderer is not yet sufficient for the intended human betting workflow.

In the June 72R:

- distance evidence appeared in 68/72 ◎ comments;
- pace/style fit appeared in 24/72;
- frame evidence appeared in 14/72;
- **actual clock/time values appeared in 0/72**.

The tested TimeFit is also simpler than the user's normal handicapping method: it ranks the fastest observed exact same venue/surface/distance recent time when at least three horses are comparable, without numerical correction for going, class, carried weight, pace or date-specific track speed.

Therefore the next output-layer revision should make the reasoning more auditable:

- show the concrete comparable run used for distance/time judgment where meaningful;
- include time / last3F / position and the relevant context;
- explicitly say `時計比較不可` when direct/nearby evidence is not legitimately comparable;
- expose one concrete course/frame/style or pace-position reason rather than a generic fit phrase;
- state the most important failure condition.

This can be versioned as a **comment/output contract revision without altering the validated v0.2 ranking formula**.

Any numerical change to TimeFit, frame-style interaction, pace coefficients or other model factors is a future prediction model version and must be blind-tested separately.

## 8. Next development path

1. make v0.2 the provisional preferred prediction ranking;
2. preserve v0.1 shadow control;
3. create a v0.2.1 user-facing short-comment contract using the same ranking and evidence;
4. run one further untouched 72R block with v0.1 shadow + unchanged v0.2 ranking + v0.2.1 comments;
5. use that block primarily to confirm ranking stability and audit whether the comments are genuinely useful to a bettor;
6. after that, consider a separate v0.3 model candidate for richer comparable-clock normalization and true frame × running-style interaction.