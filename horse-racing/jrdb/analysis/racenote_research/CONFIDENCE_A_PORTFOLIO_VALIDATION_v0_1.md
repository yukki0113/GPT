# RaceNote Confidence A — Portfolio Validation v0.1

Status: **RESEARCH / NON-NORMATIVE**  
Scope: RaceNote v0.5.5 Confidence `A` races only  
Purpose: evaluate how Confidence A behaves under a simplified real-world betting portfolio without changing Prediction or Confidence semantics.

## 1. Separation of concerns

This research layer is downstream of frozen Prediction and Confidence.

It must not:
- change ◎○▲△△;
- change A/B/C/Z after result unlock;
- rewrite frozen artifacts;
- use target results to re-grade historical A races.

Confidence A continues to mean:

> ◎を勝ち馬・単勝軸として積極的に支持できる。

The portfolio model is only a post-freeze evaluation model for how A may be used in practice.

## 2. Outcome KPIs for Confidence A

For each A race, classify the race outcome using frozen marks:

- **DOUBLE HIT** — ◎ wins and either ○ or ▲ finishes second.
- **SINGLE HIT** — ◎ wins, but neither ○ nor ▲ finishes second.
- **COVER HIT** — ◎ does not win, but the quinella ◎-○ or ◎-▲ hits.
- **MISS** — neither ◎ win nor ◎-○ / ◎-▲ quinella hits.

Primary A-quality KPIs:

- A race count;
- ◎ win rate;
- ◎ top-3 rate;
- DOUBLE HIT rate;
- SINGLE HIT rate;
- COVER HIT rate;
- combined HIT rate = DOUBLE + SINGLE + COVER;
- MISS rate;
- defeat rescue rate = COVER HIT / races where ◎ did not win.

These outcome KPIs are independent of stake sizing.

## 3. Portfolio bankroll

Per-race bankroll cap:

```text
5,000 JPY
```

This is a maximum risk budget, not an obligation to force every yen into a ticket.

Stake unit:

```text
100 JPY
```

The portfolio uses final market odds only after Prediction and Confidence are frozen.

## 4. Market-regime purchase logic

The portfolio changes by final ◎ win odds.

### Regime L — ◎ win odds < 2.0

The win ticket is omitted because the payout is too compressed for the intended portfolio.

Purchase order:

1. Fund quinella ◎-○ toward a 7,000 JPY gross-return target.
2. Fund quinella ◎-▲ toward a 7,000 JPY gross-return target.
3. Split the remaining bankroll equally between:
   - exacta ◎→○;
   - exacta ◎→▲.

This regime intentionally converts a strong-market-favorite A into a pair-structure bet.

### Regime M — ◎ win odds 2.0–5.9

Purchase order:

1. Fund quinella ◎-○ toward a 7,000 JPY gross-return target.
2. Fund quinella ◎-▲ toward a 7,000 JPY gross-return target.
3. Put the remaining bankroll on ◎ win.

The intended profit engine is mainly ◎ win, while quinella provides cover and DOUBLE-HIT upside.

### Regime H1 — ◎ win odds 6.0–7.9

Purchase order:

1. Fund quinella ◎-○ toward an 8,000 JPY gross-return target.
2. Fund quinella ◎-▲ toward an 8,000 JPY gross-return target.
3. Put the remaining bankroll on ◎ win.

### Regime H2 — ◎ win odds 8.0–11.9

Purchase order:

1. Fund quinella ◎-○ toward a 10,000 JPY gross-return target.
2. Fund quinella ◎-▲ toward a 10,000 JPY gross-return target.
3. Put the remaining bankroll on ◎ win.

### Regime H3 — ◎ win odds >= 12.0

Purchase order:

1. Fund quinella ◎-○ toward a 12,000 JPY gross-return target.
2. Fund quinella ◎-▲ toward a 12,000 JPY gross-return target.
3. Put the remaining bankroll on ◎ win.

The high-odds regimes deliberately shift more expected profit toward quinella because the market is signaling greater uncertainty around ◎ even when RaceNote Confidence is A.

## 5. Stake calculation

For each quinella ticket:

```text
raw_stake = target_gross_return / quinella_odds
stake = ceil(raw_stake to next 100 JPY)
```

Example:

```text
target 10,000 JPY
quinella odds 30.0
raw stake 333.3
stake 400 JPY
```

### Budget-binding fallback

If the two calculated quinella stakes together exceed the 5,000 JPY bankroll cap:

- preserve both quinella legs;
- scale the two stakes down proportionally in 100 JPY units to fit the 5,000 JPY cap;
- no win/exacta residual is then assumed;
- log `BUDGET_BOUND=true`.

This is a deterministic research fallback, not a claim that a human bettor would always make the same choice.

For Regime L, after quinella funding:
- split the residual as evenly as possible between ◎→○ and ◎→▲ exacta;
- any unsplittable final 100 JPY may remain uninvested.

For Regime M/H1/H2/H3:
- all residual bankroll is assigned to ◎ win.

## 6. Portfolio performance metrics

For each A race persist:

- market regime;
- final ◎ win odds;
- final ◎-○ quinella odds;
- final ◎-▲ quinella odds;
- exacta odds for Regime L;
- stake by ticket;
- total stake;
- gross payout;
- net profit;
- ROI;
- `BUDGET_BOUND`;
- outcome class: DOUBLE / SINGLE / COVER / MISS.

Aggregate at minimum:

- total A portfolio ROI;
- ROI by market regime;
- average and median payout;
- profit rate;
- rate of bankroll >= 10,000 JPY after settlement;
- rate of bankroll >= 20,000 JPY after settlement;
- DOUBLE-HIT average payout;
- MISS rate.

## 7. Interpretation rule

Do not optimize Confidence A directly for historical ROI alone.

The preferred research direction is:

> improve A so that DOUBLE HIT and overall HIT increase, COVER remains useful, and MISS decreases, while checking whether portfolio ROI improves out of sample.

A rule change should not be adopted merely because it improves one retrospective bankroll simulation.

Prediction quality, Confidence quality, and stake-allocation quality remain separate research questions.

## 8. Promotion-A diagnostic

The current research has identified a possible weakness in A races where ◎ is explicitly being promoted across a class boundary.

Track these races separately:

```text
promotion_A = true / false
```

Do not automatically demote promotion races yet.

Compare:
- ◎ win rate;
- DOUBLE/COVER/SINGLE/MISS;
- portfolio ROI;
- by-day replication.

This remains a diagnostic until prospective evidence is sufficient.

## 9. Initial pilot cohort

The first practical pilot for this framework is:

- BTDAY-0116
- BTDAY-0117
- BTDAY-0118
- BTDAY-0119

The pilot is explicitly exploratory because the framework was specified after those results were already known.

It may be used to test whether the metrics and purchase logic behave sensibly, but not as blind proof of profitability.

Future BTDAYs should evaluate this specification without changing thresholds after seeing their results.

## 10. Change control

Any later change to:
- odds regime boundaries;
- quinella gross-return targets;
- bankroll cap;
- exacta fallback;
- KPI definitions;

must create a new documented revision.

Do not silently rewrite v0.1 after additional results are known.
