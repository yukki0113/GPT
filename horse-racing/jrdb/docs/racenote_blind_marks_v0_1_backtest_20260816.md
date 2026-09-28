# RaceNote Blind Marks v0.1 Backtest — 2026-08-16

Target day: 2026-08-16
Races: 36
Venues: 中京 / 新潟 / 札幌

## Blind contract

Prediction was frozen before result retrieval.

- RaceNote source: run 36386044201
- Blind Marks pipeline: run 36386110580
- 36/36 PASS
- result visibility: HIDDEN
- market visibility: HIDDEN
- RL index: hidden
- EdgeDB match: hidden
- Training Edge: hidden
- JRDB condition signal: corroboration only

Result retrieval was executed only after freeze:
- JRA results run 36386283995
- 36/36 validation PASS

Versions:
- General Evidence v0.2
- Semantic Pairwise v0.3
- Semantic Author v0.4
- Mark Policy v0.1

## Day-level axis metrics

- ◎ wins: 4 / 36 = 11.1%
- ◎ top2: 11 / 36 = 30.6%
- ◎ top3: 14 / 36 = 38.9%

◎ win:
- stake 3,600 JPY
- return 1,400 JPY
- ROI 38.9%

## Compact Quinella

### ◎-○▲ 2 points
- stake: 7,200 JPY
- return: 5,320 JPY
- hits: 3 / 36
- hit rate: 8.3%
- ROI: 73.9%

All three hits were ◎-○:
- 新潟5R: 10-12, 2,270 JPY
- 新潟9R: 4-5, 2,380 JPY
- 新潟12R: 11-13, 670 JPY

▲ produced no Quinella hit on this day.

### ◎-○▲△ 3 points
- stake: 10,800 JPY
- return: 8,750 JPY
- hits: 4 / 36
- hit rate: 11.1%
- ROI: 81.0%

Additional △ hit:
- 新潟1R: 1-4, 3,430 JPY

△ incremental:
- extra stake: 3,600 JPY
- extra return: 3,430 JPY
- extra hits: 1
- incremental ROI: 95.3%

The third point nearly paid for itself but did not exceed 100% incremental ROI.

## Mark-role diagnostics

Among 11 races where ◎ finished actual top2:

- ○ captured the other top2 horse: 3 / 11
- ▲ captured the other top2 horse: 0 / 11
- △ captured the other top2 horse: 1 / 11

Actual partner location in the semantic six-horse candidate set:
- rank2: 1
- rank3: 1
- rank4: 2
- rank5: 1
- rank6: 1
- outside top6: 5

This is the first of the new-policy blind days where ○ clearly behaved like a Stability Partner.

However, five of eleven correct partners were outside the semantic top6, so candidate coverage remains a material limitation.

## 札幌記念 GII

Frozen semantic order:
1. #6 ローシャムパーク
2. #12 ゼンダンハヤブサ
3. #8 サクラファレル
4. #2 イガッチ
5. #10
6. #1

Marks:
- ◎ #6 ローシャムパーク
- ○ #8 サクラファレル
- ▲ #12 ゼンダンハヤブサ
- △ #2 イガッチ

Actual podium:
1. #15 シェイクユアハート
2. #8 サクラファレル
3. #14 レディネス

Quinella:
- 8-15
- 3,020 JPY

Interpretation:
- ○ #8 finished 2nd.
- ◎ #6 finished outside top3.
- actual winner #15 and third #14 were outside the semantic top6.

This is therefore a candidate-cluster miss rather than a simple mark-role miss.

## Three new-policy blind days

### 2026-05-31
- 24 races
- 2-point: 0 / 4,800 JPY = 0%
- 3-point: 2,570 / 7,200 JPY = 35.7%
- △ incremental: 2,570 / 2,400 = 107.1%

### 2026-06-14
- 36 races
- 2-point: 4,810 / 7,200 JPY = 66.8%
- 3-point: 4,810 / 10,800 JPY = 44.5%
- △ incremental: 0 / 3,600 = 0%

### 2026-08-16
- 36 races
- 2-point: 5,320 / 7,200 JPY = 73.9%
- 3-point: 8,750 / 10,800 JPY = 81.0%
- △ incremental: 3,430 / 3,600 = 95.3%

### Aggregate — 96 races

2-point ◎-○▲:
- stake: 19,200 JPY
- return: 10,130 JPY
- ROI: 52.8%

3-point ◎-○▲△:
- stake: 28,800 JPY
- return: 16,130 JPY
- ROI: 56.0%

△ incremental across 96 races:
- stake: 9,600 JPY
- return: 6,000 JPY
- ROI: 62.5%

At this point △ has improved aggregate return and aggregate total ROI slightly, but its own incremental ROI is below break-even.

Therefore the current evidence does not support saying the third point is economically necessary.

## Axis aggregate — 96 races

- ◎ wins: 10 / 96 = 10.4%
- ◎ top2: 22 / 96 = 22.9%
- ◎ top3: 33 / 96 = 34.4%

This remains the largest strategic weakness for an axis-based Quinella strategy.

## Mark-role aggregate

Among 22 races across the three days where ◎ finished actual top2:

- ○ correct partner: 3 / 22 = 13.6%
- ▲ correct partner: 2 / 22 = 9.1%
- △ correct partner: 2 / 22 = 9.1%

The remaining correct partners were either another semantic candidate or outside semantic top6.

8/16 is a positive ○ day, but the aggregate Stability Partner capture rate is still low.

## Decision

Do not change the logic yet from 8/16 alone.

The next adjustment, when enough blind data exists, should distinguish two failure classes:

1. Candidate coverage failure
   - actual partner outside semantic top6
2. Mark-role failure
   - actual partner inside top6 but ○▲△ assignment misses it

Only class 2 should be used to tune Mark Policy.

Class 1 belongs to Semantic candidate-cluster research and should not be disguised as a mark-selection problem.
