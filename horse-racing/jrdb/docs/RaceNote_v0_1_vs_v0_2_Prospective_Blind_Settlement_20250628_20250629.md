# RaceNote v0.1 vs v0.2 Prospective Blind Settlement — 2025-06-28 / 2025-06-29

## Status

**SECOND PREREGISTERED PROSPECTIVE BLIND COMPARISON — 72 RACES**

This block extends the untouched prospective sample after the first 2025-03-01/02 block.

- control: `provisional_handoff_v0.1_unweighted`
- candidate: `RaceNote_Prediction_Handoff_v0_2_Candidate.md` **unchanged from the first prospective block**
- target dates: 2025-06-28 / 2025-06-29
- venues: 函館 / 福島 / 小倉, 24 races each
- target selection source: RaceNote Archive `expected_race_index.json` identity metadata only
- RaceNote Reader View round-trip: 72/72 PASS
- no target result/HJC/Web result lookup before prediction freeze

Prediction freeze manifests:

- 2025-06-28: commit `642c85ad746cbf75e7c3b21f5678b84bd1a45d7d`
- 2025-06-29: commit `e5ed7066296d98dc773c14b232245ae7ee23b741`
- complete pre-result prediction payload SHA-256: `5e857cfbb7f8fc6db5c736e7d7ca85fdd48eba98b36100f2db52bd3515886752`
- 2025-06-28 slice SHA-256: `77fbb0196b3b0b081ee722b2bce9f324d0aaea376c5c3dbfa2bfc6372ee9bf29`
- 2025-06-29 slice SHA-256: `369195b391ef5e1f8c6e29b18a433a8fc137222bb21e119b297af4ede2764e22`
- prediction-generation implementation SHA-256: `31a0000a88de3f8288f5c01535133dbe9104f274da8109815c22652e8d78bbd7`

HJC was requested only after those freeze commitments:

- 2025-06-28: Issue #514, run `34204139428`, `HJC250628.zip`, SHA-256 `1697db32ea28c840424b72037415696595c2c924e9b4f5e69f86119d58515fed`
- 2025-06-29: Issue #515, run `34204150411`, `HJC250629.zip`, SHA-256 `8eece67ee9dc0f3c0771a58104908c2d8b3bc979dcfcf5a49ff88fc9565f422c`

Frozen betting policies:

- win: ◎ single
- quinella: ◎-○ / ◎-▲
- trio A: six-ticket ◎ axis flow
- trio B: five-ticket formation excluding only ◎△1△2
- ☆: diagnostic only, no extra production ticket

## 1. Axis quality

| Metric | v0.1 | v0.2 | Delta |
|---|---:|---:|---:|
| ◎ win | 14/72 = 19.44% | **16/72 = 22.22%** | +2.78pt |
| ◎ top2 | 33/72 = 45.83% | **36/72 = 50.00%** | +4.17pt |
| ◎ top3 | 48/72 = 66.67% | 48/72 = 66.67% | 0.00pt |

The second block therefore repeats the first block's directional result: v0.2 improves the top of the ranking, while broad top3 axis capture is nearly unchanged.

## 2. The 16 races where ◎ changed

v0.2 changed ◎ in **16/72 races**.

Within those 16:

| Capture | v0.1 | v0.2 |
|---|---:|---:|
| win | 3 | **5** |
| top2 | 4 | **7** |
| top3 | 8 | 8 |

Paired winner direction:

- v0.2-only winner: **5 races**
- v0.1-only winner: **3 races**

v0.2-only winner changes:

1. 2025-06-28 福島5R: 7 ヘリテージブルーム -> **6 メーゼ**, win 290
2. 2025-06-28 小倉8R: 8 サンコンクエスト -> **16 レイナデアルシーラ**, win 360
3. 2025-06-29 函館6R: 12 コスモマガラニカ -> **8 サクラアドリア**, win 220
4. 2025-06-29 福島1R: 4 イザベルソレイユ -> **8 エウテルペ**, win 310
5. 2025-06-29 福島5R: 13 ジーネキング -> **9 ロスパレドネス**, win 220

v0.1-only winner changes:

1. 2025-06-28 函館4R: **4 アルマデオロ** -> 10 アスクデッドヒート, win 210
2. 2025-06-28 福島7R: **6 オストラヴァ** -> 7 プルミエソルティ, win 180
3. 2025-06-29 福島10R: **13 ジャスパーロブスト** -> 4 ハギノサステナブル, win 240

Changed-axis win payout contribution:

- v0.1: 630円
- v0.2: **1,400円**

This is less dominant than the first prospective block (7 gains vs 1 loss), but remains favorable to the suitability-first candidate.

## 3. Five-horse set coverage

Again, v0.2 is not winning by simply expanding broad recall.

- identical five-horse order: 4/72
- identical five-horse set, order may differ: 39/72
- five-horse membership changed: 33/72
- actual top3 captured per race: v0.1 **2.208/3**, v0.2 2.181/3
- all three actual top3 horses captured: v0.1 27 races, v0.2 **29 races**
- v0.2 captured more actual top3 horses: 5 races
- v0.1 captured more: 7 races

As in March, the useful signal is mainly **ranking near the top**, not a large recall gain from the five-horse candidate set.

## 4. Frozen betting settlement

### v0.1

| Pattern | Investment | Payout | Hit races | Return |
|---|---:|---:|---:|---:|
| ① ◎ win | 7,200 | 3,380 | 14 | 46.94% |
| ② ◎-○ / ◎-▲ | 14,400 | 7,030 | 13 | 48.82% |
| ③ trio six-ticket | 43,200 | 28,750 | 21 | 66.55% |
| ③ trio five-ticket | 36,000 | 23,290 | 18 | 64.69% |
| ①+②+③ six-ticket | 64,800 | 39,160 | 36 | 60.43% |

### v0.2

| Pattern | Investment | Payout | Hit races | Return |
|---|---:|---:|---:|---:|
| ① ◎ win | 7,200 | 4,150 | 16 | **57.64%** |
| ② ◎-○ / ◎-▲ | 14,400 | 5,970 | 11 | 41.46% |
| ③ trio six-ticket | 43,200 | 35,960 | 21 | **83.24%** |
| ③ trio five-ticket | 36,000 | 29,640 | 18 | **82.33%** |
| ①+②+③ six-ticket | 64,800 | 46,080 | 36 | **71.11%** |

v0.2 again improves win/trio/aggregate economics relative to v0.1, but **neither model is profitable in this block**. The quinella result is worse under v0.2.

Unlike March, no single 9,000-yen-class trio dominates the block; the largest v0.2 trio payout is 5,920円. This does not remove tail dependence, but makes the second-block directional improvement less attributable to one exceptional payout.

## 5. Quinella role decomposition

### v0.1

- ◎-○: 7,200 -> 3,740, 7 hits, 51.94%
- ◎-▲: 7,200 -> 3,290, 6 hits, 45.69%

### v0.2

- ◎-○: 7,200 -> 3,080, 6 hits, 42.78%
- ◎-▲: 7,200 -> 2,890, 5 hits, 40.14%

The March v0.2 result had ◎-○ at 126.53% and ◎-▲ at 49.86%; neither behavior repeats here. This reinforces the decision **not to define ▲ as a value/longshot slot** and also shows that improved ◎ winner selection does not automatically improve the fixed two-ticket quinella.

## 6. Trio six-ticket vs five-ticket

### v0.1

- six-ticket: 43,200 -> 28,750 = **66.55%**
- five-ticket: 36,000 -> 23,290 = 64.69%
- sixth `◎△1△2`: 7,200 -> 5,460 = 75.83%, 3 hits

### v0.2

- six-ticket: 43,200 -> 35,960 = **83.24%**
- five-ticket: 36,000 -> 29,640 = 82.33%
- sixth `◎△1△2`: 7,200 -> 6,320 = 87.78%, 3 hits

v0.2 trio role groups:

- `◎○▲`: 7,200 -> 4,690 = 65.14%
- `◎○△`: 14,400 -> 13,790 = **95.76%**
- `◎▲△`: 14,400 -> 11,160 = 77.50%
- `◎△△`: 7,200 -> 6,320 = 87.78%

There is still no stable basis for deleting the sixth ticket. Continue to treat A/B as a betting-layer comparison rather than prediction logic.

## 7. ☆ value/disagreement diagnostic

☆ was frozen in 30/72 races. Three were themselves ◎, leaving 27 true opponent-star races.

All 30 ☆ selections:

- winner: 3
- top2: 4
- top3: 7
- median base market rank: 7
- mean base market rank: 7.97
- range: 4 to 17

The three ☆ winners were:

- 2025-06-28 函館9R: 3 エルサトアナ, base market rank 4, role ○
- 2025-06-28 函館12R: 12 アレスグート, base market rank 10, role △1
- 2025-06-28 小倉8R: 16 レイナデアルシーラ, base market rank 5, role ◎

Post-hoc `◎-☆` diagnostic among the 27 true opponent-star races:

- investment 2,700円
- payout **0円**
- hits 0

This sharply fails to reproduce March's 162.56% `◎-☆` retrospective result. ☆ therefore remains **diagnostic only**. Do not promote a value ticket from the first block.

## 8. Venue split — v0.2

| Venue | ◎ win | Win return | Quinella | Trio A | All A |
|---|---:|---:|---:|---:|---:|
| 函館 24R | 3/24 = 12.50% | 29.17% | 14.79% | 97.15% | 71.30% |
| 福島 24R | 6/24 = 25.00% | 72.50% | 47.71% | 48.19% | 50.79% |
| 小倉 24R | 7/24 = 29.17% | 71.25% | 61.88% | **104.38%** | 91.25% |

These are only n=24 venue slices. No venue-specific selection rule is justified.

## 9. Major-race reference

### 2025-06-29 函館11R 函館記念 G3

- v0.1 ◎5 ボーンディスウェイ
- v0.2 ◎13 マコトヴェリーキー
- actual winner: 8
- actual quinella: 3-8
- actual trio: 3-8-12

Both axes missed top3. The suitability re-rank did not improve this race.

### 2025-06-29 福島11R ラジオNIKKEI賞 G3

- v0.1 ◎11 トレサフィール — outside top3
- v0.2 ◎5 センツブラッド — **top2**
- actual winner: 1
- actual quinella: 1-5
- actual trio: 1-5-7

v0.2 improved the axis from outside the top3 to the runner-up, but the actual winner was not inside the frozen top-five marks, so the fixed quinella still missed.

## 10. Interpretation

### Repeated from the first prospective block

1. Suitability-first v0.2 improves ◎ win/top2 capture relative to v0.1.
2. Improvement is mainly re-ranking, not broad five-horse recall.
3. v0.2 improves trio/aggregate settlement relative to v0.1, while fixed quinella does not improve.
4. `▲ = value horse` remains unsupported.
5. betting policy A/B remains unresolved.

### New negative evidence

1. ☆ `◎-☆` does **not** replicate economically; 0/27 in this block.
2. 函館 is difficult in this first 24-race sample and gives no basis for a venue rule.
3. Some suitability promotions still demote genuine v0.1 winners; the candidate is not uniformly superior.

## 11. Next step

The prospective sample has now reached the preregistered **144-race** decision point when combined with 2025-03-01/02.

Create a pooled 144R decision memo before changing any prediction or betting rule. Judge promotion primarily on paired axis quality and cross-block repeatability, not headline return.