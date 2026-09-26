# RaceNote Semantic Author v0.3 — first out-of-sample blind validation

Date: 2026-09-26
Validation day: 2026-08-01
Races: 36
Venues: 中京 / 新潟 / 札幌

## 1. Validation status

This is the first clean out-of-sample validation day for Semantic Author v0.3.

v0.3 was designed after reviewing the 2026-07-25 and 2026-07-26 72-race sample.
Therefore those 72 races are development data for v0.3 and must not be used as proof of generalization.

The 2026-08-01 sequence was:

```text
RaceNote daily source
→ Gen0.3 Day Prepare
→ DayRehearsal-v0.1 baseline Freeze
→ Semantic Pairwise Packet v0.2
→ Semantic Author v0.3
──────── result firewall boundary ────────
→ result open
→ baseline / v0.3 comparison
```

All semantic authoring was completed with:
`result_visibility_status = HIDDEN`

before the 2026-08-01 result file was opened.

### Runs

RaceNote:
- run 36198385140
- artifact `racenote-gen03-semantic-validation-20260801-v01-36198385140`

Prepare:
- run 36247510611
- 36/36 PASS
- artifact `racenote-gen0-3-day-prepare-36247510611`

Baseline:
- profile `DayRehearsal-v0.1`
- run 36247552650
- 36/36 Freeze PASS
- artifact `racenote-gen0-3-day-author-36247552650`

Semantic Packet:
- `RaceNote-Semantic-Pairwise-Research-v0.2`
- run 36247582685
- 36/36 PASS

Semantic Author:
- `RaceNote-Semantic-Author-Research-v0.3`
- run 36247614175
- 36/36 PASS
- axis changed in 1 / 36 races

## 2. Why v0.3 is stricter than v0.2

v0.2 changed the axis in 36 / 72 development races.

Post-analysis showed that 34 of those changes were driven by RaceReview-only decisions.
That was too permissive.

v0.3 therefore applies:

```text
RaceReview alone
    cannot dethrone the existing axis.

RaceReview + Trend agreement
or
RaceReview + Ability corroboration
    may support a reversal.
```

The design goal is not to suppress RaceReview.

The goal is to use RaceReview as semantic context and corroboration rather than a scalar horse rating.

## 3. Axis result

Only one race changed axis:

### 中京9R

Baseline top5:
`[9, 2, 3, 6, 11]`

Semantic v0.3 top5:
`[2, 9, 3, 11, 6]`

Actual podium:
`[7, 8, 2]`

Therefore:
- baseline ◎ #9: outside podium
- v0.3 ◎ #2: 3rd

The only axis change on the first out-of-sample day improved axis top-three status.

It did not produce a win.

## 4. Forecast-quality comparison

| metric | DayRehearsal-v0.1 | Semantic v0.3 |
|---|---:|---:|
| ◎ wins | 4 / 36 = 11.1% | 4 / 36 = 11.1% |
| ◎ top2 | 9 / 36 = 25.0% | 9 / 36 = 25.0% |
| ◎ top3 | 11 / 36 = 30.6% | 12 / 36 = 33.3% |
| winner mean forecast rank | 5.08 | 5.08 |
| winner median forecast rank | 5 | 5 |
| winner in forecast top3 | 14 / 36 = 38.9% | 15 / 36 = 41.7% |
| winner in forecast top5 | 19 / 36 = 52.8% | 19 / 36 = 52.8% |
| mean top3 overlap | 1.06 / 3 | 1.14 / 3 |
| mean actual podium in forecast top5 | 1.56 / 3 | 1.56 / 3 |

Interpretation:

v0.3 did not change candidate-set coverage.
It changed the internal ordering of that candidate set.

That is exactly the intended target:
`candidate cluster → better semantic ordering`

The observed improvement is small and only one validation day.
It is encouraging but not sufficient for promotion.

## 5. Raw axis-bet comparison

100 JPY equal stake per race.

| strategy | baseline ROI | v0.3 ROI |
|---|---:|---:|
| ◎ win | 36.4% | 36.4% |
| ◎ place | 50.0% | 54.2% |

The place improvement is entirely explained by 中京9R:
v0.3 promoted #2, which returned 150 JPY place.

No claim of profitability is justified.

## 6. Provisional top-three mark diagnostic

Semantic Author v0.3 is **not** Mark Policy.

However, as a diagnostic only, if its top three order is provisionally mapped to:

```text
rank 1 → ◎
rank 2 → ○
rank 3 → ▲
```

the following raw 100-JPY equal-stake results occur.

### Baseline

| strategy | return / stake | ROI | race hits |
|---|---:|---:|---:|
| 馬連 ◎-○ | 6,510 / 3,600 | 180.8% | 2 |
| 馬連 ◎-▲ | 2,500 / 3,600 | 69.4% | 1 |
| 馬連 ◎-○▲ 2点 | 9,010 / 7,200 | 125.1% | 3 |
| 馬連 ◎○▲ BOX 3点 | 10,580 / 10,800 | 98.0% | 4 |
| ワイド ◎-○ | 2,890 / 3,600 | 80.3% | 5 |
| ワイド ◎-▲ | 1,800 / 3,600 | 50.0% | 2 |
| ワイド ◎-○▲ 2点 | 4,690 / 7,200 | 65.1% | 7 |
| ワイド ◎○▲ BOX 3点 | 6,430 / 10,800 | 59.5% | 11 |

### Semantic v0.3 provisional ranking marks

| strategy | return / stake | ROI | race hits |
|---|---:|---:|---:|
| 馬連 ◎-○ | 8,490 / 3,600 | 235.8% | 3 |
| 馬連 ◎-▲ | 3,540 / 3,600 | 98.3% | 2 |
| 馬連 ◎-○▲ 2点 | 12,030 / 7,200 | 167.1% | 5 |
| 馬連 ◎○▲ BOX 3点 | 13,600 / 10,800 | 125.9% | 6 |
| ワイド ◎-○ | 3,670 / 3,600 | 101.9% | 6 |
| ワイド ◎-▲ | 2,190 / 3,600 | 60.8% | 3 |
| ワイド ◎-○▲ 2点 | 5,860 / 7,200 | 81.4% | 8 |
| ワイド ◎○▲ BOX 3点 | 8,340 / 10,800 | 77.2% | 12 |

Important:

These are **not Mark Policy results**.

The semantic author was designed to improve ordering, not to optimize ○ or ▲ roles.

Still, this is a useful observation because the user's preferred compact ticket family is:

`◎単勝 + ◎-○▲ 馬連2点`

and on the first out-of-sample day, the provisional semantic top-three ordering improved the raw two-point Quinella ROI from 125.1% to 167.1%.

This is one day only.
A few large payouts can dominate 36-race ROI.
Do not optimize v0.3 from this result.

## 7. Main conclusion

The first clean out-of-sample result supports continuing the semantic-reading direction.

It does **not** support declaring v0.3 production-ready.

The useful pattern is:

```text
candidate set
  unchanged

semantic internal ordering
  modestly improved

axis changes
  highly selective

RaceReview-only reversals
  suppressed
```

This is much closer to the intended forecasting philosophy than v0.2.

## 8. Next step

Do not tune v0.3 from 2026-08-01.

Run at least one more untouched blind day with exactly the same:
- Semantic Packet v0.2
- Semantic Author v0.3

Then compare:
- ◎ win / top2 / top3
- winner top3 / top5
- top3 overlap
- provisional compact ticket results

Only after another unchanged blind day should the project decide whether to:
1. promote semantic v0.3 into the core Pairwise research path; and
2. begin a separate `Mark Policy v0.1` for ○ Stability Partner and ▲ Upside Partner.

The Mark Policy should remain separate from forecast ranking.
