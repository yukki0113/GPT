# RaceNote Blind Historical Backtest Settlement — 2025-05-04 v0.1

## Status

**SETTLED AFTER 36-RACE PREDICTION FREEZE**

This block targets the day containing 京都11R 天皇賞（春） G1 and uses JRDB/RaceNote metadata only for target confirmation.

Sequence:

```text
JRDB/RaceNote metadata target confirmation (no Web)
 -> RaceNote acquisition
 -> Reader View v0.1 round-trip 36/36 PASS
 -> prediction freeze commit a3acd9233946086da4986fdd3bed1949777edf5f
 -> HJC acquisition
 -> deterministic settlement
```

Prediction logic remained `provisional_handoff_v0.1_unweighted`.
Settlement remained `RaceNote_Backtest_Settlement_Protocol_v0_1.md`.

## Source audit

- target date: 2025-05-04
- venues: 東京 / 京都 / 新潟
- metadata-confirmed notable races:
  - 京都11R 天皇賞（春） / G1 / 芝3200m
  - 東京10R ブリリアントステークス / L
  - 東京11R プリンシパルステークス / L
- RaceNote: Issue #500 / run `34193765696` / artifact `10043120284` / backend `racenote_archive`
- prediction freeze: `prediction_runs/20250504_racenote_prediction_blind_batch_v0_1.md`
- freeze commit: `a3acd9233946086da4986fdd3bed1949777edf5f`
- HJC: Issue #501 / run `34193978112` / artifact `10043184927`
- `HJC250504.zip` SHA-256: `d35046fb6b4c02e63ba39794f584d4183dec2d9d2de259b91a11a408e7c410a0`
- `HJC250504.txt` SHA-256: `d58799c818959c9617c4f7db3397ce5bbfae4fedde58f7f7ab79f530b5f86119`
- HJC race records: 36
- no target-date HJC/result/final-odds/Web result was read before prediction freeze

## 36-race summary

| Pattern | Investment | Payout | Hit races | Hit rate | Return rate |
|---|---:|---:|---:|---:|---:|
| 1 | 3,600円 | 2,440円 | 9/36 | 25.00% | 67.78% |
| 2 | 7,200円 | 8,880円 | 9/36 | 25.00% | 123.33% |
| 3 | 21,600円 | 16,900円 | 12/36 | 33.33% | 78.24% |
| 1+2 | 10,800円 | 11,320円 | 14/36 | 38.89% | 104.81% |
| 1+3 | 25,200円 | 19,340円 | 16/36 | 44.44% | 76.75% |
| 1+2+3 | 32,400円 | 28,220円 | 19/36 | 52.78% | 87.10% |

## Venue split

| Venue | Races | ① | ② | ③ | ①+② | ①+③ | ①+②+③ |
|---|---:|---:|---:|---:|---:|---:|---:|
| 東京 | 12 | 31.67% | 102.08% | 49.03% | 78.61% | 46.55% | 58.89% |
| 京都 | 12 | 90.83% | 55.83% | 120.42% | 67.50% | 116.19% | 102.78% |
| 新潟 | 12 | 80.83% | 212.08% | 65.28% | 168.33% | 67.50% | 99.63% |

京都12Rだけでは③と①+③、全買いが100%を超えたが、12R単独なのでルール化しない。

## Confidence split

| Confidence | Races | ① | ② | ③ | ①+②+③ |
|---|---:|---:|---:|---:|---:|
| A | 12 | 58.33% | 129.58% | 120.00% | 115.28% |
| B | 24 | 72.50% | 120.21% | 57.36% | 73.01% |

## 天皇賞（春） G1 settlement

Frozen marks:

```text
◎ 6 ヘデントール
○ 5 サンライズアース
▲ 13 ジャスティンパレス
△1 15 ハヤテノフクノスケ
△2 11 マイネルエンペラー
confidence A
```

HJC winning combinations:

```text
単勝   6       310円
馬連   6-14    1,810円
3連複  6-8-14  5,500円
```

Settlement:

- ① ◎単勝: **310円 hit**
- ② ◎-○ / ◎-▲ 馬連: 0円
- ③ ◎1頭軸3連複6点: 0円

The axis horse was correct, while the required opponent horses 14 and 8 were outside the frozen opponent set.

## 京都G1 tiny reference

The blind sample now contains two 京都G1 races:

- 2025-11-16 エリザベス女王杯: frozen ◎7 レガレイラ -> 単勝230円 hit
- 2025-05-04 天皇賞（春）: frozen ◎6 ヘデントール -> 単勝310円 hit

Therefore 京都G1の◎単勝は現時点で **2/2 hit / 200円投資 / 540円払戻 / 270.00%**。
This is interesting but only two races and must not be treated as a Kyoto-G1 rule.

## 京都 pooled reference — 60 races

Prior blind blocks supplied 48 京都 races; adding 2025-05-04 gives 60.

| Pattern | Investment | Payout | Return rate |
|---|---:|---:|---:|
| 1 | 6,000円 | 5,970円 | 99.50% |
| 2 | 12,000円 | 10,240円 | 85.33% |
| 3 | 36,000円 | 31,650円 | 87.92% |
| 1+2 | 18,000円 | 16,210円 | 90.06% |
| 1+3 | 42,000円 | 37,620円 | 89.57% |
| 1+2+3 | 54,000円 | 47,860円 | 88.63% |

京都 is no longer above 100% after pooling 60 races. The earlier local strength is therefore not stable enough to use as a filter.

## Pooled reference — 219 races

The prior blind reference contained 183 races. Adding this 36-race block gives **219 total races**.

| Pattern | Investment | Payout | Hit races | Hit rate | Return rate |
|---|---:|---:|---:|---:|---:|
| 1 | 21,900円 | 16,440円 | 60/219 | 27.40% | 75.07% |
| 2 | 43,800円 | 35,230円 | 46/219 | 21.00% | 80.43% |
| 3 | 131,400円 | 105,720円 | 61/219 | 27.85% | 80.46% |
| 1+2 | 65,700円 | 51,670円 | 79/219 | 36.07% | 78.65% |
| 1+3 | 153,300円 | 122,160円 | 99/219 | 45.21% | 79.69% |
| 1+2+3 | 197,100円 | 157,390円 | 104/219 | 47.49% | 79.85% |

Change from the 183-race snapshot:

- ①: 76.50% -> **75.07%**
- ②: 71.99% -> **80.43%**
- ③: 80.89% -> **80.46%**
- ①+③: 80.27% -> **79.69%**
- ①+②+③: 78.43% -> **79.85%**

No frozen pattern is above break-even at 219 races.

## Distance-fit diagnostic prompted by the Oaks miss

This is a **model-design observation**, not a retroactive result-driven change.

The current `provisional_handoff_v0.1_unweighted` selector ranks eight equally treated evidence dimensions:

1. total_index
2. IDM
3. recent-run IDM
4. historical_profile.same_distance
5. historical_profile.same_venue
6. training/condition metric
7. forecast finish order
8. base win rank

It does **not** directly use `ability.distance_fit`.

In the frozen 2025-05-25 優駿牝馬 bundle:

- ◎9 エンブロイダリー had `distance_fit = マイル`
- the race distance was 2400m
- `historical_profile.same_distance.starts = 0`
- several leading rivals also had zero same-distance starts

Therefore the same-distance dimension often supplied no ranking information, while high total_index / IDM / market rank could still dominate. This makes an explicit distance-fit / distance-extension treatment a legitimate candidate for a future prediction revision.

Do not rewrite the 219-race v0.1 history. A clean next experiment would preregister a **distance-aware candidate** and compare it prospectively on a new untouched blind block alongside unchanged v0.1.

## Interpretation

- The 2025-05-04 block was relatively strong in 馬連: ② **123.33%**, ①+② **104.81%**.
- 京都12R was strong in trio patterns, but pooled 京都60R remains below 100% for every frozen pattern.
- 天皇賞（春）は◎ヘデントールが勝利し、京都G1のblind ◎は2戦2勝になった。
- The opponent-ranking layer did not capture the full G1 combinations in either Kyoto G1, so the G1 observation currently supports the axis more than the multi-horse ticket structure.
- Overall 219-race returns remain around 75-80%; the next meaningful development step is not to chase venue/day effects, but to preregister a targeted model change such as distance-fit handling and test it on untouched races.
