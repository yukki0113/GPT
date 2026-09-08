# RaceNote Blind Historical Backtest Settlement — 2025-05-24 / 2025-05-25 v0.1

## Status

**SETTLED AFTER 72-RACE PREDICTION FREEZE**

This block deliberately shifts season from the earlier August/November samples and uses only JRDB/RaceNote metadata for target selection.

Sequence:

```text
JRDB/RaceNote metadata target selection (no Web)
 -> RaceNote acquisition
 -> Reader View v0.1 round-trip 72/72 PASS
 -> prediction freeze commit 2450e9c1027ba313cab3ed171c37dca5d8dcf9c4
 -> HJC acquisition
 -> settlement
```

Target design:

- 2025-05-24: 東京 / 京都 / 新潟, 36 races
- 2025-05-25: 東京 / 京都 / 新潟, 36 races
- graded/listed metadata identified internally: 京都11R 平安S G3 (5/24), 東京11R 優駿牝馬 G1 (5/25), 京都11R 都大路S L (5/25)
- no JRA official site, search engine, or other Web result was used to determine the target dates/venues/classes/grades
- prediction logic: `provisional_handoff_v0.1_unweighted`
- settlement policy unchanged: ① ◎単勝1点 / ② ◎-○・◎-▲馬連2点 / ③ ◎1頭軸3連複6点 / 100円均等

## Source audit

- RaceNote 2025-05-24: Issue #496 / run `34192692341` / artifact `10042764072` / `racenote_archive`
- RaceNote 2025-05-25: Issue #497 / run `34192699358` / artifact `10042766965` / `racenote_archive`
- prediction freeze: `prediction_runs/20250524_20250525_racenote_prediction_blind_batch_v0_1.md` / commit `2450e9c1027ba313cab3ed171c37dca5d8dcf9c4`
- HJC 2025-05-24: Issue #498 / run `34193178124` / `HJC250524.zip` SHA-256 `d426eed02e045af9cb139dc570284a7813cb4b491a078c5ed653457348d4684d` / member SHA-256 `f7d8d15c0ba9374863e48fac0451d3e7dd851cbd4f61b651e0e2c60d5f902e63`
- HJC 2025-05-25: Issue #499 / run `34193188307` / `HJC250525.zip` SHA-256 `74b46ad3f92f63bc8739b4ba6066b16a229824631c4156bd26bae7fbc474e66c` / member SHA-256 `37bebddb878a7c9a52e16e485a5595807775d9d647cdc19bff36b6ddecd14f5f`

## 72-race summary

| Pattern | Investment | Payout | Hit races | Hit rate | Return rate |
|---|---:|---:|---:|---:|---:|
| 1 | 7,200円 | 4,690円 | 18/72 | 25.00% | 65.14% |
| 2 | 14,400円 | 9,720円 | 14/72 | 19.44% | 67.50% |
| 3 | 43,200円 | 32,240円 | 21/72 | 29.17% | 74.63% |
| 1+2 | 21,600円 | 14,410円 | 23/72 | 31.94% | 66.71% |
| 1+3 | 50,400円 | 36,930円 | 30/72 | 41.67% | 73.27% |
| 1+2+3 | 64,800円 | 46,650円 | 30/72 | 41.67% | 71.99% |

## Date split

| Date | Races | ① | ② | ③ | ①+② | ①+③ | ①+②+③ |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2025-05-24 | 36 | 83.61% | 63.75% | 72.04% | 70.37% | 73.69% | 71.48% |
| 2025-05-25 | 36 | 46.67% | 71.25% | 77.22% | 63.06% | 72.86% | 72.50% |

## Venue split

| Venue | Races | ① | ② | ③ | ①+② | ①+③ | ①+②+③ |
|---|---:|---:|---:|---:|---:|---:|---:|
| 京都 | 24 | 102.08% | 63.75% | 109.58% | 76.53% | 108.51% | 98.56% |
| 新潟 | 24 | 55.83% | 80.83% | 57.78% | 72.50% | 57.50% | 62.69% |
| 東京 | 24 | 37.50% | 57.92% | 56.53% | 51.11% | 53.81% | 54.72% |

## Class split

| Class | Races | ① | ② | ③ | ①+②+③ |
|---|---:|---:|---:|---:|---:|
| 未勝利 | 32 | 58.44% | 82.03% | 75.94% | 75.35% |
| 1勝クラス | 21 | 62.38% | 64.05% | 115.08% | 97.88% |
| 2勝クラス | 9 | 78.89% | 51.67% | 32.96% | 49.88% |
| オープン | 6 | 31.67% | 5.00% | 18.33% | 15.00% |
| 3勝クラス | 4 | 92.50% | 36.25% | 30.00% | 44.44% |

The class split is descriptive only. In particular, the apparent 1勝クラス strength comes from only 21 races and must not be promoted to a filter yet.

## Confidence split

| Confidence | Races | ① | ② | ③ | ①+②+③ |
|---|---:|---:|---:|---:|---:|
| A | 14 | 37.86% | 114.64% | 199.05% | 162.38% |
| B | 58 | 71.72% | 56.12% | 44.60% | 50.17% |

The A split is strongly positive in ②/③ but contains only 14 races and is influenced by several multi-thousand-yen trio hits. Treat it as noise until replicated.

## G1 / graded settlement

### 2025-05-24 京都11R 平安ステークス (G3)

- frozen ◎: 8 ブライアンセンス
- ① payout: 0円
- ② payout: 0円
- ③ payout: 0円
- HJC win: 7 / 600円
- HJC quinella: 6-7 / 1,570円
- HJC trio: 6-7-12 / 20,600円

### 2025-05-25 東京11R 優駿牝馬 (G1)

- frozen ◎: 9 エンブロイダリー
- ① payout: 0円
- ② payout: 0円
- ③ payout: 0円
- HJC win: 15 / 1,430円
- HJC quinella: 1-15 / 2,470円
- HJC trio: 1-13-15 / 21,380円

Both graded races missed all three frozen groups in this block. This is two races only and is not a graded-race conclusion.

## Pooled reference — 183 races

The previous blind reference was 111 races. Adding this 72-race spring block gives **183 total races**.

| Pattern | Investment | Payout | Hit races | Hit rate | Return rate |
|---|---:|---:|---:|---:|---:|
| 1 | 18,300円 | 14,000円 | 51/183 | 27.87% | 76.50% |
| 2 | 36,600円 | 26,350円 | 37/183 | 20.22% | 71.99% |
| 3 | 109,800円 | 88,820円 | 49/183 | 26.78% | 80.89% |
| 1+2 | 54,900円 | 40,350円 | 65/183 | 35.52% | 73.50% |
| 1+3 | 128,100円 | 102,820円 | 83/183 | 45.36% | 80.27% |
| 1+2+3 | 164,700円 | 129,170円 | 85/183 | 46.45% | 78.43% |

Change from the 111-race snapshot:

- ①: 83.87% -> **76.50%**
- ②: 74.91% -> **71.99%**
- ③: 84.95% -> **80.89%**
- ①+③: 84.80% -> **80.27%**
- ①+②+③: 82.60% -> **78.43%**

## Interpretation / next step

- The early 39-race >100% effects have not returned after expanding to 183 races.
- ③ remains the best single frozen pattern in the pooled sample at 80.89%, but is still below break-even.
- Venue, class, confidence, and date splits continue to move materially between blocks; no filter should be adopted from one block.
- The pipeline now covers summer, autumn, and spring; venues include 札幌/新潟/中京/東京/京都/福島 and G1 races from different seasons.
- Keep `provisional_handoff_v0.1_unweighted` unchanged for another independent block before deciding whether to tune the prediction layer.
- Future target selection should follow `RaceNote_Blind_Target_Selection_Raw_Metadata_v0_1.md` and use BAC/RaceNote metadata instead of Web calendar lookup.
