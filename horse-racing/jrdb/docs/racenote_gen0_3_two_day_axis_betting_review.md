# RaceNote Gen0.3 two-day axis and betting review

Date: 2026-09-25
Sample: 2026-07-25 and 2026-07-26
Races: 72
Forecast profile: DayRehearsal-v0.1

## 1. Purpose

Horse-racing forecast quality must not be evaluated only by whether the ◎ horse wins.

This review separates:
1. axis quality — how often ◎ remains in the top three;
2. mark quality — how often ○ / ▲ and the marked candidate set contain placings;
3. betting quality — equal-stake return for common mark-based tickets.

All tickets below use 100 JPY per combination.
No odds threshold, bet skipping, Kelly sizing, confidence filtering, or value filtering is applied.

Therefore these are raw mark-quality diagnostics, not a recommended betting strategy.

## 2. Axis quality

Across 72 races:

- ◎ win: 11 / 72 = 15.3%
- ◎ top2: 17 / 72 = 23.6%
- ◎ top3: 29 / 72 = 40.3%

By day:

2026-07-25:
- ◎ win: 22.2%
- ◎ top3: 47.2%

2026-07-26:
- ◎ win: 8.3%
- ◎ top3: 33.3%

The win rate is unstable by day, while top-three performance is a more useful axis diagnostic.

Note:
actual top-three rate and 複勝 ticket hit rate are not identical in small fields because Japanese 複勝 can pay only top two when the field is sufficiently small.

## 3. Individual top-mark placement quality

Across 72 races:

- ◎ top3: 40.3%
- ○ top3: 40.3%
- ▲ top3: 23.6%

Actual first-two horses both inside ◎○▲:
- 6 / 72 = 8.3%

Actual first-two horses both inside all six marks ◎○▲△△△:
- 26 / 72 = 36.1%

Actual podium all inside ◎○▲:
- 2 / 72 = 2.8%

Actual podium all inside all six marks:
- 17 / 72 = 23.6%

This suggests the current marks behave more like a broad candidate set than a compact exact-order ticket generator.

## 4. Raw equal-stake betting returns

### Single-horse axis

| strategy | stake | return | hits | ROI |
|---|---:|---:|---:|---:|
| ◎ win | 7,200 | 3,590 | 11 | 49.9% |
| ◎ place | 7,200 | 5,310 | 28 | 73.8% |

The place-ticket hit count is 28 rather than the 29 top-three finishes because place payout rules depend on field size.

### ◎ with ○ / ▲

| strategy | stake | return | hits | ROI |
|---|---:|---:|---:|---:|
| Quinella ◎-○ | 7,200 | 2,270 | 4 | 31.5% |
| Quinella ◎-▲ | 7,200 | 220 | 1 | 3.1% |
| Quinella ◎-○▲, 2 points/race | 14,400 | 2,490 | 5 | 17.3% |
| Wide ◎-○ | 7,200 | 2,290 | 7 | 31.8% |
| Wide ◎-▲ | 7,200 | 2,230 | 5 | 31.0% |
| Wide ◎-○▲, 2 points/race | 14,400 | 4,520 | 10 | 31.4% |

### ◎○▲ compact box

| strategy | stake | return | hits | ROI |
|---|---:|---:|---:|---:|
| Quinella box ◎○▲, 3 points/race | 21,600 | 3,930 | 6 | 18.2% |
| Wide box ◎○▲, 3 points/race | 21,600 | 8,710 | 13 | 40.3% |
| Trio ◎○▲ | 7,200 | 880 | 2 | 12.2% |

### Including △ marks

| strategy | stake | return | hits | ROI |
|---|---:|---:|---:|---:|
| Quinella ◎-○▲△△△, 5 points/race | 36,000 | 3,910 | 7 | 10.9% |
| Wide ◎-○▲△△△, 5 points/race | 36,000 | 17,670 | 21 | 49.1% |
| Trio ◎ one-axis to ○▲△△△, 10 points/race | 72,000 | 28,530 | 9 | 39.6% |

## 5. Day split

The raw returns are also unstable by day.

### ◎ place
- 2026-07-25 ROI: 91.1%
- 2026-07-26 ROI: 56.4%

### Quinella ◎-○▲
- 2026-07-25 ROI: 16.5%
- 2026-07-26 ROI: 18.1%

### Wide ◎-○▲
- 2026-07-25 ROI: 44.3%
- 2026-07-26 ROI: 18.5%

### Wide box ◎○▲
- 2026-07-25 ROI: 66.0%
- 2026-07-26 ROI: 14.6%

No raw ticket family reached 100% ROI across the 72-race sample.

## 6. Interpretation

The 72-race rehearsal currently shows:

```text
◎ win selection
  weaker and day-volatile

◎ top-three axis quality
  materially better than win rate, but still not profitable by itself

◎○▲ compact ticket structure
  insufficient for raw equal-stake betting

six-mark candidate set
  captures more relevant runners,
  but blindly expanding combinations destroys ROI
```

This is an important distinction.

The current system has some candidate-selection information, but the marks are not yet calibrated as a betting portfolio.

Adding more combinations is not the solution:
more coverage increases hit count but also increases stake faster than return.

## 7. Required standard metrics going forward

Every blind day rehearsal should record at least:

Axis:
- ◎ win rate
- ◎ top2 rate
- ◎ top3 rate
- ◎ place-bet hit rate and ROI

Mark placement:
- ○ top3 rate
- ▲ top3 rate
- actual top2 coverage by ◎○▲
- actual top2 coverage by all marks
- actual top3 coverage by all marks

Betting:
- ◎ win / place ROI
- Quinella ◎-○
- Quinella ◎-▲
- Quinella ◎-○▲
- Wide ◎-○▲
- Quinella box ◎○▲
- Wide box ◎○▲
- Trio ◎○▲
- Quinella ◎-○▲△△△
- Wide ◎-○▲△△△
- Trio one-axis ◎ to ○▲△△△

All raw ROI metrics should be calculated under fixed 100-JPY equal stakes before any later value/odds filtering.

## 8. Next research question

The next goal should not be simply to increase the number of ◎ winners.

It should separate:

1. axis selection quality:
   can rank 1 remain in the top three reliably?

2. companion-mark quality:
   when ◎ is in the race, are ○ / ▲ the correct partners?

3. ticket efficiency:
   which marks add enough hit probability to justify their extra combinations?

4. value selection:
   after mark quality is stable, can market/value information identify which races and ticket families should actually be purchased?

The current 72-race raw betting result does not justify live betting from DayRehearsal-v0.1 alone.
