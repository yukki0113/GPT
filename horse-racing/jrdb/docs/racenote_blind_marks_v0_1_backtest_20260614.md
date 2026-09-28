# RaceNote Blind Marks v0.1 Backtest — 2026-06-14

Date of evaluation: 2026-09-28
Target day: 2026-06-14
Races: 36
Venues: 函館 / 東京 / 阪神

## 1. Blind contract

The target day was frozen before result lookup.

Pipeline:

```text
RaceNote source
→ General Evidence v0.2
→ DayRehearsal baseline Freeze
→ Semantic Pairwise v0.3
→ Semantic Author v0.4
→ Mark Policy v0.1
→ ◎○▲△ Freeze
──────── result firewall boundary ────────
→ result/payoff open
→ evaluation
```

Blind pipeline:
- Issue #1560
- run 36381627575
- 36/36 PASS
- artifact `racenote-gen03-blind-marks-v01-36381627575`
- frozen_at `2026-09-28T14:23:00+09:00`
- result visibility: HIDDEN
- market visibility: HIDDEN
- RL index: hidden
- EdgeDB match: hidden
- Training Edge: hidden
- JRDB condition signal: visible as corroboration only

Versions:
- General Evidence: `RaceNote-General-Evidence-0.2`
- logic: `TrendFirst-RR-AbilityAnchor-ConditionCorroboration-v0.2`
- Pairwise: `RaceNote-Semantic-Pairwise-Research-v0.3`
- Semantic Author: `RaceNote-Semantic-Author-Research-v0.4`
- Mark Policy: `RaceNote-Mark-Policy-Research-v0.1`

## 2. Day-level axis metrics

- ◎ wins: 4 / 36 = 11.1%
- ◎ top2: 8 / 36 = 22.2%
- ◎ top3: 12 / 36 = 33.3%
- ◎ win stake: 3,600 JPY
- ◎ win return: 1,190 JPY
- ◎ win ROI: 33.1%

This day was not strong for axis win selection.

## 3. Main compact Quinella test

### Two points: ◎-○▲

- stake: 7,200 JPY
- return: 4,810 JPY
- hits: 2 / 36
- hit rate: 5.6%
- ROI: 66.8%

Hit races:
- 函館4R: ◎12 - ▲6, payout 4,270 JPY
- 東京7R: ◎8 - ▲7, payout 540 JPY

### Three points: ◎-○▲△

- stake: 10,800 JPY
- return: 4,810 JPY
- hits: 2 / 36
- hit rate: 5.6%
- ROI: 44.5%

The △ ticket added:
- additional stake: 3,600 JPY
- additional hits: 0
- additional return: 0 JPY
- incremental ROI: 0%

On this day, the third point was clearly unnecessary.

This is one blind day only; it is not evidence that △ should be removed globally.

## 4. Mark-role diagnostics

Among the 8 races where ◎ finished in the actual top2:

- ○ captured the other top2 horse: 0 / 8
- ▲ captured the other top2 horse: 2 / 8
- △ captured the other top2 horse: 0 / 8

The actual partner's position inside the six-horse semantic candidate order was:

- semantic rank2: 1 race
- semantic rank3: 1 race
- semantic rank4: 1 race
- semantic rank5: 1 race
- semantic rank6: 1 race
- outside semantic top6: 3 races

This is the most important day-level finding.

The system's weak point on this day was not only role assignment.
In 3 / 8 axis-top2 races, the correct partner was not inside the six-horse Mark Policy candidate cluster at all.

The first Mark Policy day therefore does not justify tuning ○ versus ▲ in isolation.

Candidate-cluster coverage and role selection must both remain visible diagnostics.

## 5. G1 — 宝塚記念

### Frozen forecast

Semantic candidate order:

```text
1  #1  ダノンデサイル
2  #16 メイショウタバル
3  #6  ビザンチンドリーム
4  #11 シンエンペラー
5  #9  コスモキュランダ
6  #7  ファミリータイム
```

Marks:

```text
◎ #1  ダノンデサイル
○ #16 メイショウタバル
▲ #9  コスモキュランダ
△ #6  ビザンチンドリーム
```

Primary tickets:
- ◎1 - ○16
- ◎1 - ▲9

Expanded third ticket:
- ◎1 - △6

### Actual podium

```text
1st #16 メイショウタバル
2nd #5  クロワデュノール
3rd #1  ダノンデサイル
```

Quinella:
- #5-#16
- payout 620 JPY

### Interpretation

The G1 forecast had two actual podium horses in the semantic top2:

- ○ #16 won
- ◎ #1 finished 3rd

So the leading forecast interpretation was not far from the podium structure.

However, the actual second horse #5 クロワデュノール was baseline rank7:

```text
baseline:
1, 16, 11, 7, 6, 9, 5, ...
```

Semantic Pairwise v0.3 only reorders the baseline top6.
Therefore #5 never entered the semantic comparison / Mark Policy pool.

This means the G1 miss is structurally different from a simple ○/▲ role-selection miss.

The chain was:

```text
#5 baseline rank7
→ outside six-horse semantic candidate cluster
→ cannot become ○ / ▲ / △
→ actual 2nd unavailable to the compact tickets
```

### Why #5 is notable

Before the race, #5 had:
- Data Trend: MIXED
- RaceReview: MIXED
- Ability typical: 75
- Ability latest: 76
- Ability peak: 76
- MAD: 1
- JRDB condition signal: SUPPORTIVE
- training arrow: 上昇

By contrast, the baseline ordering strongly protected horses with coarse Data Trend = SUPPORTIVE.

The G1 therefore exposes a known compression boundary:

`coarse Data Trend state can still push a very strong Ability + improving-condition horse outside the semantic comparison pool.`

This does not justify moving #5 upward retrospectively.

It does justify keeping candidate-pool coverage as a first-class diagnostic in future blind days, especially for high-class races where many runners have strong absolute Ability.

## 6. G1-specific impression

The first G1 sample is mixed but useful.

Positive:
- ◎ and ○ both finished in the actual top3.
- ○ selected the actual winner.
- the new JRDB condition signal correctly showed ○ #16 as SUPPORTIVE and helped ○ stability selection.
- the race was not an obvious total-ranking collapse.

Negative:
- ◎ was 3rd rather than top2, so any ◎-partner Quinella strategy could not hit.
- actual 2nd #5 was outside the six-horse semantic candidate pool.
- compact-ticket logic therefore had no route to the winning pair.

For a G1 test, this is more encouraging for the forecast-reading layer than for the betting layer.

## 7. Decision after this test

Do not change the production/research logic from this single date.

Keep:
- Semantic Author v0.4 unchanged
- Mark Policy v0.1 unchanged
- two-point ◎-○▲ as the primary compact ticket
- three-point ◎-○▲△ as the comparison strategy

Continue tracking:
1. 2-point hit rate / ROI
2. 3-point hit rate / ROI
3. △ incremental return
4. ○ capture rate when ◎ is top2
5. ▲ rescue contribution
6. actual winning-partner semantic candidate rank
7. number of top2 partners outside semantic top6

If future G1 / high-class blind races repeatedly place the correct partner at semantic rank7+,
then candidate-cluster width should be reviewed separately from Mark Policy.
