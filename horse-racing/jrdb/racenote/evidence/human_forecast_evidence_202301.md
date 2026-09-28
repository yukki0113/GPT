# RaceNote Human Forecast Evidence

Purpose: preserve examples of the user's manually authored horse-racing forecasts as evidence for RaceNote design.

These examples are not model-generated labels or post-hoc rewrites. They are source material for studying how the user actually chose ◎/○/▲/△/☆ and justified "the horse I most want to buy" in context.

## 2023-01-08 Nakayama 11R — Polux Stakes (OP) Dirt 1800m

### Forecast
- ◎ 1 ウィリアムバローズ
- ○ 9 ニューモニュメント
- ▲ 10 ルコルセール
- △ 3 アシャカトブ
- ☆ 6 メイショウムラクモ

### View (aggregated from past 9 runnings)

#### Popularity
- 1st favorite: (4-1-2-2)
- 2nd favorite: (0-2-0-7)
- 3rd favorite: (1-2-1-5)
- 4th favorite: (0-2-0-7)
- 5th-9th: (3-1-2-33)
- 10th or lower: (1-0-3-46)

#### Draw
- Frame 1: (1-2-1-11)
- Frame 2: (1-0-1-14)
- Frame 3: (4-2-0-11)
- Frame 4: (0-1-0-17)
- Frame 5: (2-0-1-15)
- Frame 6 or outer: (1-4-6-43)

#### Running style
- Front: (2-1-1-5)
- Forward: (2-1-2-29)
- Stalker: (3-3-0-32)
- Closer: (2-4-6-45)

#### Sires
- King Kamehameha: (0-2-1-12)
- Lord Kanaloa: (2-0-0-0)
- Heart's Cry: (1-1-0-7)

### User-authored reasoning
- The historical tendency showed a high level of trust in the race favorite.
- ウィリアムバローズ had stable results over the same course and with the same jockey, so the user trusted him despite the innermost draw being a concern.
- Although the race tendency suggested considering outsiders, ニューモニュメント was rated highly because he had beaten Champions Cup winner ジュンライトボルト two starts earlier and finished second over the same course last time.
- ルコルセール was rated as a supporting candidate because of a jockey with good course results and pedigree matching the race trend.
- メイショウムラクモ was considered as an outsider capable of revival because of a compatible jockey and course despite returning from a layoff.

## 2023-01-09 Nakayama 11R — Fairy Stakes (GIII) Turf 1600m

### Forecast
- ◎ 7 ディナトセレーネ
- ○ 5 ヒップホップソウル
- ▲ 8 イコノスタシス
- △ 6 ミシシッピテソーロ
- ☆ 11 ディヴァージオン

### View (aggregated from past 10 runnings)

#### Popularity
- 1st favorite: (1-2-0-7)
- 2nd favorite: (1-0-1-8)
- 3rd favorite: (4-0-1-4)
- 4th favorite: (0-1-1-8)
- 5th favorite: (1-1-2-6)
- 6th-9th: (0-4-5-31)
- 10th favorite: (2-2-0-6)
- 11th or lower: (1-0-0-59)

#### Draw
- Frame 1: (2-0-3-15)
- Frame 2: (1-3-1-15)
- Frame 3: (1-0-2-17)
- Frame 4: (3-2-1-14)
- Frame 5: (2-0-1-15)
- Frame 6: (0-1-0-19)
- Frame 7: (1-0-3-16)
- Frame 8: (1-3-0-16)

#### Running style
- Front: (4-0-1-8)
- Forward: (0-4-3-30)
- Stalker: (6-5-4-45)
- Closer: (0-1-2-47)

### User-authored reasoning
- The user considered the tendency for horses coming from G1-G3 races to underperform, along with a pattern of outsider wire-to-wire wins or races decided by stalkers/closers.
- No horse looked clearly optimal as a strong axis, so the betting construction was designed to cover both normal and upset outcomes.
- The user specifically expected a potential M. Demuro upset in a Nakayama fillies graded stakes context.

### Bets
Frame quinella:
- Red-Blue 1,400 JPY
- Red-Green 300 JPY
- Blue-Green 300 JPY

Trio box:
- 5,6,7,8,11
- 10 combinations x 300 JPY

## Design notes for RaceNote

These examples support the following observations for future research:

1. ◎ is not "the horse with the highest generic score" or necessarily "the most likely winner".
   - It is the horse the user most wants to buy in this specific race under the user's own reasoning.
2. Race-level context comes first.
   - The user decides what kind of race this is before deciding which evidence should matter most.
3. The evidence hierarchy is flexible.
   - Popularity, local race history, course fit, jockey, pedigree, recent opponent strength, class level, and current context can become more or less important depending on the race.
4. Concerns do not automatically disqualify ◎.
   - Example: ウィリアムバローズ retained ◎ despite the innermost draw concern.
5. There can be an ◎ even when no strong "axis horse" exists.
   - Example: Fairy Stakes, where the user explicitly stated there was no optimal axis and constructed the bet for a wider outcome range.
6. Recent form should be read contextually, not reduced only to a rolling average.
   - Opponent strength, race class, same-course performance, and the meaning of a loss or win can matter.
7. These examples should be treated as human-forecast evidence, not as deterministic rules to reproduce literally.
