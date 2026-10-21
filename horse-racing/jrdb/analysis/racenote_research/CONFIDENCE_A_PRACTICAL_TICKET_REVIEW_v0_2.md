# RaceNote Confidence A — Practical Ticket Review v0.2

Status: **CURRENT / RESEARCH / NON-NORMATIVE**  
Scope: RaceNote v0.5.5 Confidence `A` races only  
Supersedes for current operation: `CONFIDENCE_A_PORTFOLIO_VALIDATION_v0_1.md`

## 1. Purpose

This layer evaluates whether frozen Confidence A marks produce a practically useful
betting structure without pretending that unavailable losing-ticket closing odds
can be reconstructed.

It is downstream of frozen Prediction and Confidence.

It must not:
- change ◎○▲△△;
- change A/B/C/Z after result unlock;
- rewrite frozen artifacts;
- use target results to re-grade the same historical A race;
- infer or synthesize odds for losing combinations;
- optimize stake allocation retrospectively.

Confidence A continues to mean:

> ◎を勝ち馬・単勝軸として積極的に支持できる。

This review asks a narrower practical question:

> If A is used with the simple ticket structure below, how often do the win and
> quinella ideas survive, and what can the realized payout odds tell us qualitatively
> about plausible practical allocation?

## 2. Standard ticket structure

For every Confidence A race, the research ticket structure is fixed to three ideas:

- **WIN**: ◎
- **QUINELLA 1**: ◎-○
- **QUINELLA 2**: ◎-▲

This document does **not** prescribe stake amounts.

There is no odds-dependent market regime, bankroll cap, target gross return,
stake-scaling formula, exacta fallback, or simulated ROI.

The ticket structure exists only so outcome classes are comparable across days.

## 3. Outcome classes

Classify every Confidence A race using frozen marks and the official result.

### DOUBLE HIT

Both of the following occur:

- ◎ wins; and
- either ◎-○ or ◎-▲ quinella hits.

This is two successful ticket ideas in the same race:

`WIN HIT + QUINELLA HIT`.

### WIN SINGLE HIT

- ◎ wins; and
- neither ◎-○ nor ◎-▲ quinella hits.

Only the WIN idea hits.

### QUINELLA SINGLE HIT

- ◎ does not win; and
- either ◎-○ or ◎-▲ quinella hits.

Only the QUINELLA idea hits.

This replaces the older `COVER HIT` terminology for current operation because
v0.2 does not assume a fixed stake allocation that must be "covered."

### MISS

- ◎ does not win; and
- neither ◎-○ nor ◎-▲ quinella hits.

## 4. Primary KPIs

Persist and aggregate at minimum:

- A race count;
- ◎ win count / win rate;
- ◎ top-3 count / rate;
- DOUBLE HIT count / rate;
- WIN SINGLE HIT count / rate;
- QUINELLA SINGLE HIT count / rate;
- combined any-HIT count / rate;
- MISS count / rate;
- quinella rescue rate = QUINELLA SINGLE HIT / races where ◎ did not win.

These are outcome-quality metrics, not bankroll metrics.

## 5. Odds use policy

JRDB HJC retains payout information for winning combinations but does not provide
closing odds for every losing quinella / exacta combination. Therefore v0.2 does
not attempt a complete odds-based stake simulation.

For a **ticket idea that actually hit**, finalized JRDB/JRA payout per 100 JPY may
be treated as its effective closing odds for practical discussion:

`effective odds = finalized payout / 100`

Small movements between the practical betting deadline and finalized payout are
accepted as immaterial for this research discussion.

For losing ticket ideas:

- do not infer an odds value;
- do not substitute a model estimate;
- do not search the public Web merely to fill historical losing-ticket odds;
- leave the unavailable price unobserved.

## 6. Practical review

After outcome classification, discuss realized hit odds only qualitatively.

Permitted examples include:

- both WIN and QUINELLA hit at useful prices, so a basic balanced allocation
  would likely have had enough payout room;
- both realized WIN and QUINELLA prices were short, so profitability would have
  depended heavily on allocation;
- QUINELLA SINGLE HIT, but ◎ itself was a mid-price / long-price selection and
  the realized quinella also paid well, so allocating meaningful capital to the
  pair ticket would have been plausible;
- a hit occurred at a compressed price, so "hit" and "practically profitable"
  should not be treated as equivalent.

Do not convert these observations into an invented retrospective stake plan.
The purpose is to understand the practical shape of A, not to maximize historical ROI.

## 7. What v0.2 intentionally does not report

Do not report as formal v0.2 metrics:

- simulated per-race stake;
- total stake;
- gross portfolio payout;
- net profit;
- portfolio ROI;
- ROI by odds regime;
- profit rate;
- bankroll thresholds;
- `BUDGET_BOUND`;
- exacta results;
- reconstructed losing-ticket odds.

A simple 100 JPY-per-ticket reference calculation may be shown only when explicitly
requested and must be labeled a **reference payout illustration**, not the Portfolio
strategy or a recommended allocation.

## 8. Interpretation rule

The preferred research direction is:

> improve A so that DOUBLE HIT and overall HIT increase and MISS decreases,
> while separately observing whether realized winning-ticket prices leave
> plausible room for practical profitability.

Do not change Prediction or Confidence because one retrospective allocation would
have made more money.

Prediction quality, Confidence quality, ticket-structure quality, and real stake
allocation remain separate questions.

## 9. promotion_A diagnostic

Continue to track explicit class-promotion A races separately:

`promotion_A = true / false`

Compare:

- ◎ win rate;
- DOUBLE / WIN SINGLE / QUINELLA SINGLE / MISS;
- realized payout odds for the ticket ideas that hit;
- by-day replication.

Do not automatically demote promotion_A from Confidence A without separate evidence.

## 10. Historical continuity

The earlier pilot cohort remains useful for outcome-structure continuity:

- BTDAY-0116
- BTDAY-0117
- BTDAY-0118
- BTDAY-0119

BTDAY-0120 and later fresh frozen days should use this v0.2 interpretation for
current discussion.

Where older notes use:

- `SINGLE HIT` for WIN-only, read as **WIN SINGLE HIT**;
- `COVER HIT` for quinella-only, read as **QUINELLA SINGLE HIT**.

Do not rewrite already frozen prediction or result artifacts solely to rename labels.

## 11. Change control

This revision deliberately removes the odds-regime and stake-allocation simulation
from v0.1 because complete losing-ticket historical odds are not available from the
verified JRDB source set.

Any later reintroduction of:

- stake sizing;
- bankroll simulation;
- odds-dependent purchase regimes;
- ROI as a formal KPI;
- exacta purchase logic;

requires a new documented revision and a verified price source that can reproduce
the required market inputs without synthesizing missing odds.
