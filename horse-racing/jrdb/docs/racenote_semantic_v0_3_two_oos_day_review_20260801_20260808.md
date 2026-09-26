# RaceNote Semantic Author v0.3 — two out-of-sample day review

Date: 2026-09-26

Out-of-sample validation days:
- 2026-08-01
- 2026-08-08

Total: 72 races

Development sample used to design v0.3:
- 2026-07-25
- 2026-07-26

The development sample is excluded from the out-of-sample claims below.

## 1. Blind-validation contract

Both validation days were processed in this order:

```text
RaceNote source
→ Gen0.3 Day Prepare
→ DayRehearsal-v0.1 baseline Freeze
→ Semantic Pairwise Packet v0.2
→ Semantic Author v0.3
──────── result firewall boundary ────────
→ result open
→ comparison
```

No target-day result was opened before the semantic author output had been fixed.

### 2026-08-01
- Prepare: run 36247510611, 36/36 PASS
- baseline Freeze: run 36247552650, 36/36 PASS
- Semantic Packet: run 36247582685, 36/36 PASS
- Semantic v0.3: run 36247614175, 36/36 PASS
- axis changes: 1

### 2026-08-08
- Prepare: run 36247951088, 36/36 PASS
- baseline Freeze: run 36248005630, 36/36 PASS
- Semantic Packet: run 36248029949, 36/36 PASS
- Semantic v0.3: run 36248057250, 36/36 PASS
- axis changes: 3

## 2. Axis changes on the two OOS days

Across 72 out-of-sample races, v0.3 changed the baseline axis in only 4 races.

Observed outcomes:

- 2026-08-01 中京9R:
  old ◎ #9 outside podium
  → new ◎ #2 finished 3rd

- 2026-08-08 中京1R:
  old ◎ #2 outside podium
  → new ◎ #4 finished 3rd

- 2026-08-08 新潟6R:
  old ◎ #1 outside podium
  → new ◎ #2 finished 2nd

- 2026-08-08 札幌10R:
  old ◎ #6 outside podium
  → new ◎ #4 also outside podium

Thus:
- improved axis-top3 status: 3 / 4 changes
- neutral: 1 / 4
- worsened axis-top3 status: 0 / 4

This is a promising directional observation, but n=4 is too small for promotion by itself.

## 3. Forecast-quality comparison

### 2026-08-01

| metric | baseline | semantic v0.3 |
|---|---:|---:|
| ◎ win | 4 / 36 | 4 / 36 |
| ◎ top2 | 9 / 36 | 9 / 36 |
| ◎ top3 | 11 / 36 | 12 / 36 |
| winner top3 | 14 / 36 | 15 / 36 |
| winner top5 | 19 / 36 | 19 / 36 |
| mean top3 overlap | 1.06 | 1.14 |

### 2026-08-08

| metric | baseline | semantic v0.3 |
|---|---:|---:|
| ◎ win | 5 / 36 | 5 / 36 |
| ◎ top2 | 9 / 36 | 10 / 36 |
| ◎ top3 | 10 / 36 | 12 / 36 |
| winner mean rank | 5.61 | 5.50 |
| winner top3 | 14 / 36 | 15 / 36 |
| winner top5 | 24 / 36 | 24 / 36 |
| mean top3 overlap | 0.97 | 1.00 |

### 72-race OOS aggregate

| metric | baseline | semantic v0.3 |
|---|---:|---:|
| ◎ win | 9 / 72 = 12.5% | 9 / 72 = 12.5% |
| ◎ top2 | 18 / 72 = 25.0% | 19 / 72 = 26.4% |
| ◎ top3 | 21 / 72 = 29.2% | 24 / 72 = 33.3% |
| winner in top3 | 28 / 72 = 38.9% | 30 / 72 = 41.7% |
| winner in top5 | 43 / 72 = 59.7% | 43 / 72 = 59.7% |
| mean top3 overlap | 1.01 / 3 | 1.07 / 3 |

The most important structural result is:

```text
candidate-set coverage
    unchanged

internal ordering / axis placement
    modestly improved
```

This matches the intended purpose of semantic v0.3.

## 4. Compact betting diagnostic

These tests still map:
- semantic rank1 → ◎
- semantic rank2 → ○
- semantic rank3 → ▲

This is **not Mark Policy**.
It is only a provisional diagnostic of how reordering affects the user's preferred compact tickets.

100 JPY per combination.

### 2026-08-01

| strategy | baseline ROI | v0.3 ROI |
|---|---:|---:|
| ◎ win | 36.4% | 36.4% |
| 馬連 ◎-○ | 180.8% | 235.8% |
| 馬連 ◎-▲ | 69.4% | 98.3% |
| 馬連 ◎-○▲ 2点 | 125.1% | 167.1% |
| 馬連 ◎○▲ BOX 3点 | 98.0% | 125.9% |

### 2026-08-08

| strategy | baseline return / stake | baseline ROI | v0.3 return / stake | v0.3 ROI |
|---|---:|---:|---:|---:|
| ◎ win | 1,430 / 3,600 | 39.7% | 1,430 / 3,600 | 39.7% |
| 馬連 ◎-○ | 1,160 / 3,600 | 32.2% | 2,660 / 3,600 | 73.9% |
| 馬連 ◎-▲ | 3,040 / 3,600 | 84.4% | 610 / 3,600 | 16.9% |
| 馬連 ◎-○▲ 2点 | 4,200 / 7,200 | 58.3% | 3,270 / 7,200 | 45.4% |
| 馬連 ◎○▲ BOX 3点 | 5,830 / 10,800 | 54.0% | 4,730 / 10,800 | 43.8% |

The second day is important because it prevents over-reading the strong first-day betting result.

v0.3 improved axis/top3 ordering on 08-08 but did **not** improve the compact-ticket ROI that day.

This supports the separation:

```text
Forecast Best / ◎ selection
!=
○ Stability Partner selection
!=
▲ Upside Partner selection
```

### Two-day OOS aggregate — key compact tickets

For the user's preferred two-point Quinella:

Baseline:
- return: 9,010 + 4,200 = 13,210 JPY
- stake: 14,400 JPY
- ROI: 91.7%

Semantic rank-based marks:
- return: 12,030 + 3,270 = 15,300 JPY
- stake: 14,400 JPY
- ROI: 106.3%

For the three-point ◎○▲ Quinella box:

Baseline:
- return: 10,580 + 5,830 = 16,410 JPY
- stake: 21,600 JPY
- ROI: 76.0%

Semantic rank-based marks:
- return: 13,600 + 4,730 = 18,330 JPY
- stake: 21,600 JPY
- ROI: 84.9%

The two-point ROI above 100% is encouraging, but 72 races remain vulnerable to individual high-payout races.
It must not be treated as a stable expected return.

## 5. Interpretation

Two separate findings now coexist.

### Finding A — semantic v0.3 helps the forecast layer

Across the first 72 OOS races:
- candidate-set coverage did not change;
- ◎ top3 improved from 29.2% to 33.3%;
- winner-in-top3 improved from 38.9% to 41.7%;
- 3 of 4 axis reversals converted a non-podium old axis into a podium new axis;
- no axis reversal worsened podium status.

This supports continuing the semantic-content reading direction.

### Finding B — ranking alone is not sufficient Mark Policy

On 08-08:
- ○ performance improved in Quinella terms;
- ▲ performance worsened materially;
- combined ◎-○▲ two-point ROI fell despite better forecast ordering.

Therefore:
`rank2 = ○`
and
`rank3 = ▲`
should remain a control baseline only.

The user's proposed mark semantics are now justified as a separate research layer:

- ◎ = Forecast Best
- ○ = Stability Partner
- ▲ = Upside Partner

## 6. Engineering decision

Keep Semantic Author v0.3 unchanged.

Do not tune it from either OOS day.

It now has:
- two clean OOS days;
- 72 OOS races;
- four selective axis changes;
- modestly improved axis/top3 ordering.

This is sufficient to continue research, but not yet enough to replace production Pairwise automatically.

The next logical implementation is a **Mark Policy v0.1 research layer** placed *after* semantic forecast ordering.

The layer must:
1. preserve ◎ as Semantic Forecast Best;
2. choose ○ for stability/companion quality rather than rank2 by definition;
3. choose ▲ for upside/price-expansion evidence rather than rank3 by definition;
4. keep the conventional ◎○▲ presentation every race;
5. evaluate exactly the compact ticket families:
   - ◎ single win
   - ◎-○ Quinella
   - ◎-▲ Quinella
   - ◎-○▲ two-point Quinella
   - ◎○▲ three-point Quinella box.

No market/value filter should be used in the first Mark Policy evaluation.
That keeps mark-selection quality separate from odds-based bet selection.
