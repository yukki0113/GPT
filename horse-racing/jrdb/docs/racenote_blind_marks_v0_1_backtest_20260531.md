# RaceNote Blind Marks v0.1 Backtest — 2026-05-31

Target day: 2026-05-31
Races: 24
Venues: 京都 / 東京
G1: 東京11R 東京優駿

## Blind contract

The target day was frozen before result lookup.

- RaceNote source: run 36385114530
- Blind Marks pipeline: run 36385184728
- 24/24 PASS
- result visibility: HIDDEN
- market visibility: HIDDEN
- RL index: hidden
- EdgeDB match: hidden
- Training Edge: hidden
- JRDB condition signal: corroboration only

Versions:
- General Evidence v0.2
- Semantic Pairwise v0.3
- Semantic Author v0.4
- Mark Policy v0.1

## Day-level results

Axis:
- ◎ wins: 2 / 24 = 8.3%
- ◎ top2: 3 / 24 = 12.5%
- ◎ top3: 7 / 24 = 29.2%

Compact Quinella:

### ◎-○▲ 2 points
- stake: 4,800 JPY
- return: 0 JPY
- hits: 0 / 24
- ROI: 0%

### ◎-○▲△ 3 points
- stake: 7,200 JPY
- return: 2,570 JPY
- hits: 1 / 24
- ROI: 35.7%

The only added hit from △ was:
- 京都11R 白百合ステークス
- ◎1 - △7
- payout 2,570 JPY

Therefore:
- △ incremental stake: 2,400 JPY
- △ incremental return: 2,570 JPY
- △ incremental ROI: 107.1%

On this single day, the third point added value, unlike 2026-06-14 where it added none.

## Mark-role diagnostics

Among the 3 races where ◎ finished top2:
- ○ captured the other top2 horse: 0
- ▲ captured the other top2 horse: 0
- △ captured the other top2 horse: 1

The other two correct partners were outside the selected mark roles.

This is another weak day for the current ○ Stability Partner implementation.

## G1 — 東京優駿

Frozen semantic order:

1. #11 リアライズシリウス
2. #5 バステール
3. #16 グリーンエナジー
4. #15 フォルテアンジェロ
5. #18 エムズビギン
6. #14 ゴーイントゥスカイ

Marks:
- ◎ #11 リアライズシリウス
- ○ #5 バステール
- ▲ #15 フォルテアンジェロ
- △ #16 グリーンエナジー

Actual:
1. #17 ロブチェン
2. #13 パントルナイーフ
3. #5 バステール

Quinella:
- #13-#17
- 1,460 JPY

The forecast missed both actual top2 horses entirely.
○ #5 did finish 3rd, but this was not enough for any axis Quinella.

This G1 miss is different from the 2026-06-14 宝塚記念:
- 宝塚記念: ◎ and ○ both in actual top3, but actual 2nd was outside the semantic top6.
- 東京優駿: only ○ reached the podium; ◎ and both actual top2 horses were outside the useful axis/partner structure.

## G1 interpretation

The current model can look reasonable in one high-class race and fail materially in another.

東京優駿 shows that:
1. semantic reordering alone cannot repair a candidate cluster that is already wrong;
2. high-class races can contain several strong Ability horses whose coarse Trend/RaceReview states do not separate them well;
3. current ○ selection did find the eventual 3rd horse, but the axis was not viable;
4. compact Quinella performance depends first on axis viability, then on partner roles.

No rule should be tuned from one G1 miss.

However, after 宝塚記念 and 東京優駿 together, high-class-race candidate coverage should remain a dedicated diagnostic.

## Two recent blind-day comparison

### 2026-06-14
- 2-point ROI: 66.8%
- 3-point ROI: 44.5%
- △ added no hit

### 2026-05-31
- 2-point ROI: 0%
- 3-point ROI: 35.7%
- △ added one hit

Thus △ is not consistently useless or consistently necessary.

The question remains empirical:
- does the third point improve aggregate ROI over a larger blind sample?

## Decision

Do not change Semantic v0.4 or Mark Policy v0.1 from this single day.

Next research priorities:
1. aggregate 2-point vs 3-point performance across all new-policy blind days;
2. inspect why ○ captured zero top2 partners again;
3. track actual top2-partner location inside/outside semantic top6;
4. split diagnostics for G1/high-class races versus ordinary races;
5. only after several such races consider whether high-class races need a wider semantic candidate pool.
