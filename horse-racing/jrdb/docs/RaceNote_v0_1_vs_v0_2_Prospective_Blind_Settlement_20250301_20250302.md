# RaceNote v0.1 vs v0.2 Prospective Blind Settlement — 2025-03-01 / 2025-03-02

## Status

**FIRST PREREGISTERED PROSPECTIVE BLIND COMPARISON — 72 RACES**

This settlement evaluates the first untouched block after the 219-race v0.1 development/diagnostic sample.

- control: `provisional_handoff_v0.1_unweighted`
- candidate: `RaceNote_Prediction_Handoff_v0_2_Candidate.md`
- target dates: 2025-03-01 / 2025-03-02
- venues: 中山 / 阪神 / 小倉, 24 races each
- target selection source: RaceNote Archive `expected_race_index.json` identity metadata only
- no target result/HJC/Web result lookup before prediction freeze
- RaceNote Reader View round-trip: 72/72 PASS

Prediction freezes:

- 2025-03-01: commit `d3354fd49bdd47202c99a6563b6465a41f60d37b`
  - `prediction_runs/20250301_racenote_v01_v02_blind_freeze.md`
- 2025-03-02: commit `5e7700b123287f55d304e4bddf9370f98b831bb1`
  - `prediction_runs/20250302_racenote_v01_v02_blind_freeze.md`

HJC was acquired only after both freezes:

- 2025-03-01: workflow run `34201797541`, `HJC250301.zip`, SHA-256 `3c0eec7516122a841ed76589da23b9fce6047e89b3f2d498eabc2b686c7fc754`
- 2025-03-02: workflow run `34201808349`, `HJC250302.zip`, SHA-256 `7197ea111880489e420e72d5b3b782992df18f02657bc270c1b2bcd6e47a33dc`

Betting policies were frozen before HJC:

- win: ◎ single
- quinella: ◎-○ / ◎-▲
- trio A: current six-ticket ◎ axis flow
- trio B: five-ticket formation excluding only ◎△1△2
- ☆: diagnostic only, no extra ticket in the preregistered primary settlement

## 1. Axis quality

| Metric | v0.1 | v0.2 | Delta |
|---|---:|---:|---:|
| ◎ win | 15/72 = 20.83% | **21/72 = 29.17%** | **+8.33pt** |
| ◎ top2 | 36/72 = 50.00% | **38/72 = 52.78%** | +2.78pt |
| ◎ top3 | 46/72 = 63.89% | **48/72 = 66.67%** | +2.78pt |

The main first-block improvement is therefore the **winner-axis ranking**, not a large increase in broad top3 coverage.

## 2. The 19 races where ◎ changed

v0.2 changed ◎ in **19/72 races**.

Within those 19:

| Capture | v0.1 | v0.2 |
|---|---:|---:|
| win | 1 | **7** |
| top2 | 7 | **9** |
| top3 | 8 | **10** |

Paired direction on winner selection:

- v0.2-only winner: **7 races**
- v0.1-only winner: **1 race**
- both cannot be winner because the axes differ

The seven v0.2-only winner changes were:

1. 2025-03-01 中山12R: 3 ソレルビュレット -> **10 ソーニーイシュー**, win 170
2. 2025-03-01 阪神2R: 16 リードプリンシパル -> **14 ホウショウマリス**, win 220
3. 2025-03-02 中山4R: 12 デルマアポロニア -> **6 シャンハイナイト**, win 680
4. 2025-03-02 中山8R: 8 ダンツティアラ -> **11 アースイオス**, win 520
5. 2025-03-02 阪神4R: 16 アスタールフナ -> **9 ヤマニンチェルキ**, win 340
6. 2025-03-02 阪神9R 淡路特別: 2 クルミナーレ -> **1 タガノデュード**, win 340
7. 2025-03-02 小倉1R: 10 トーケンサワー -> **9 タケルハーロック**, win 140

The single v0.1-only winner change was:

- 2025-03-01 中山7R: **8 ブラックルビー** -> 6 ノビリシマビジョン; v0.1 win 230, v0.2 axis still top3

Changed-axis win payout contribution:

- v0.1: 230円
- v0.2: **2,410円**

This is the strongest evidence in the first block that suitability-first re-ranking may improve the primary axis.

## 3. Five-horse set coverage

v0.2 is not simply finding many more correct horses.

- identical five-horse order: 5/72
- identical five-horse set, order may differ: 30/72
- five-horse membership changed: 42/72

Actual top3 horses captured inside the five marks:

- v0.1 mean: 2.097 / 3
- v0.2 mean: 2.083 / 3
- all three actual top3 horses captured: v0.1 25 races, v0.2 24 races
- v0.2 captured more top3 horses than v0.1: 7 races
- v0.1 captured more: 8 races

Thus the first-block advantage is **ranking within the candidate group**, especially ◎, rather than materially better five-horse recall.

## 4. Frozen betting settlement — six-ticket trio policy

### v0.1

| Pattern | Investment | Payout | Hit races | Return |
|---|---:|---:|---:|---:|
| ① ◎ win | 7,200 | 3,870 | 15 | 53.75% |
| ② ◎-○ / ◎-▲ quinella | 14,400 | 13,130 | 19 | 91.18% |
| ③ trio six-ticket | 43,200 | 34,100 | 21 | 78.94% |
| ①+② | 21,600 | 17,000 | 29 | 78.70% |
| ①+③ | 50,400 | 37,970 | 28 | 75.34% |
| ①+②+③ | 64,800 | 51,100 | 36 | 78.86% |

### v0.2

| Pattern | Investment | Payout | Hit races | Return |
|---|---:|---:|---:|---:|
| ① ◎ win | 7,200 | 6,050 | 21 | **84.03%** |
| ② ◎-○ / ◎-▲ quinella | 14,400 | 12,700 | 19 | 88.19% |
| ③ trio six-ticket | 43,200 | 46,130 | 22 | **106.78%** |
| ①+② | 21,600 | 18,750 | 29 | 86.81% |
| ①+③ | 50,400 | 52,180 | 32 | **103.53%** |
| ①+②+③ | 64,800 | 64,880 | 37 | **100.12%** |

The candidate clears 100% on trio A and the all-six-ticket aggregate in this one block, but **this must not be treated as promotion evidence by itself**.

A single 9,570-yen trio payout at 2025-03-02 中山3R contributes heavily. Removing only that payout would reduce v0.2 trio-A return from 106.78% to about 84.63%. The economically important signal is therefore the axis improvement above, not the headline 100%+ return alone.

## 5. Quinella role decomposition

### v0.1

- ◎-○: 7,200 -> 4,880, 10 hits, 67.78%
- ◎-▲: 7,200 -> 8,250, 9 hits, **114.58%**

### v0.2

- ◎-○: 7,200 -> 9,110, 16 hits, **126.53%**
- ◎-▲: 7,200 -> 3,590, 3 hits, 49.86%

This block reverses the earlier qualitative impression that ▲ naturally acts as the high-value economic leg. Under v0.2, ○ became the main quinella contributor while ▲ was weak.

Therefore **do not formalize `▲ = longshot/value slot`**. Keep prediction marks pure and retain ☆ as a separate value/disagreement concept.

## 6. Trio six-ticket vs five-ticket formation

### v0.1

- six-ticket: 43,200 -> 34,100 = 78.94%
- five-ticket: 36,000 -> 34,100 = **94.72%**
- `◎△△` sixth ticket: 7,200 -> 0 = 0%

For v0.1, the five-ticket formation clearly helped in this block.

### v0.2

- six-ticket: 43,200 -> 46,130 = **106.78%**
- five-ticket: 36,000 -> 35,770 = 99.36%
- `◎△△` sixth ticket: 7,200 -> 10,360 = **143.89%**, 2 hits

The two v0.2 `◎△△` hits were:

- 2025-03-02 中山3R: 9,570円
- 2025-03-02 小倉3R: 790円

This is a clear example of betting-policy interaction with prediction ranking. The 219R retrospective pooled result slightly favored five tickets, while this first prospective block gives opposite answers depending on model.

**No betting-policy promotion should be made yet. Continue A/B.**

## 7. v0.2 ☆ value/disagreement diagnostic

☆ was frozen in 46/72 races. Three were themselves ◎, so 43 were true opponent candidates.

Among all 46 ☆ selections:

- winner: 3
- top2: 9
- top3: 12
- median base market rank: 7
- mean base market rank: 7.83
- range: 4 to 15

The three ☆ winners were all opponent roles:

- 2025-03-01 阪神8R: 4 ピジョンブラッド, base market rank 10, role △1
- 2025-03-02 阪神6R: 2 セブンスストリート, base market rank 8, role ▲
- 2025-03-02 小倉5R: 7 ウインアクトゥール, base market rank 8, role △2

Post-hoc diagnostic only, not a preregistered betting policy:

- ◎-☆ among 43 valid opponent-star races: 4,300 investment -> 6,990 payout
- 3 hits
- 162.56% return

This is promising but extremely sparse and payout-concentrated. It must not be converted directly into a production ticket rule from this block.

## 8. Venue split

### v0.2

| Venue | ◎ win rate | Win return | Quinella | Trio A | All A |
|---|---:|---:|---:|---:|---:|
| 中山 24R | 33.33% | 117.50% | 51.04% | 136.81% | 115.60% |
| 阪神 24R | 29.17% | 77.50% | 113.75% | 66.88% | 78.47% |
| 小倉 24R | 25.00% | 57.08% | 99.79% | 116.67% | 106.30% |

Do not infer venue rules from n=24.

## 9. Major-race reference

Both models kept the same ◎ on the two G2 races in the block:

- 2025-03-02 中山11R 中山記念: ◎8 ソウルラッシュ — top3, did not win; frozen v0.2 reason emphasized ability plus pace/style fit and 1800m evidence.
- 2025-03-02 阪神11R チューリップ賞: ◎9 ビップデイジー — top3, did not win.

Thus the v0.2 improvement in this block came mainly from ordinary races where the suitability layer actively changed the axis, not from the two headline G2 races.

## 10. Interpretation

### Supported by this first prospective block

1. Explicit suitability-first re-ranking can materially change the axis without requiring new result-derived information.
2. The changed-axis subset is strongly favorable to v0.2 on winner selection: 7 gains vs 1 loss.
3. The improvement is mainly **ranking**, not five-horse recall.
4. A separate ☆ value flag is conceptually cleaner than forcing ▲ to be a longshot.
5. Trio policy A/B must remain model-aware and under prospective comparison.

### Not yet supported

1. v0.2 is not yet ready for production promotion from 72 races.
2. 100%+ headline return is not stable evidence; one large trio result materially affects it.
3. No venue-specific rule is justified.
4. No `▲ = value horse` rule is justified.
5. No `◎-☆` production ticket is justified from three hits.

## 11. Next action

Continue the preregistered prospective comparison to at least **108-144 total new races before any promotion decision**.

For the next block:

1. keep v0.1 unchanged as control;
2. keep v0.2 candidate procedure unchanged — no tuning from these 72 results;
3. freeze v0.1/v0.2 marks and v0.2 comments before HJC;
4. continue trio A/B in parallel;
5. continue ☆ as diagnostic only;
6. prioritize untouched venue/season coverage, with 函館 still not represented in either the 219R development sample or this 72R prospective block;
7. after 108-144 new races, evaluate promotion primarily on paired axis-quality improvement, then secondarily on betting return stability and comment usefulness.