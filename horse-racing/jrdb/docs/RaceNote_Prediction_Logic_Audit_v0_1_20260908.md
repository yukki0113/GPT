# RaceNote Prediction Logic Audit — v0.1 / 2026-09-08

## Purpose

`provisional_handoff_v0.1_unweighted` の219R blind historyを変更せず、現在の予想がどのような馬を `◎ / ○ / ▲ / △1 / △2` に選びやすいかを構造診断する。

これは新ロジックではなく、現行v0.1の説明可能性を高めるためのauditである。

## Authoritative prediction contract

`RaceNote_Prediction_Handoff_v0_1.md` は最終比較軸として以下を要求する。

1. 基礎能力
2. 今回条件適性
3. 展開適合
4. 調教・状態
5. 近走内容
6. 履歴・条件実績
7. 騎手・種牡馬・枠等の補助統計
8. 不確実性 / coverage

固定weightは定義されていない。

Blind batch作成時の候補整理では、実務上次の8項目を強く参照した。

1. `ability.total_index`
2. `ability.idm`
3. recent-run IDM
4. `historical_profile.same_distance`
5. `historical_profile.same_venue`
6. training / condition metric
7. forecast finish order
8. `market.base_win_rank`

`ability.distance_fit` 等はReader View / Handoff上は読む対象だが、現行候補順位の独立ファクタとして固定されていない。

## Quantitative selection audit — 2025-08-23 36R

Result/payoutではなく、freeze済み36Rの印とRaceNote事前情報を突合した。

### Mark-level pre-race market profile

| Mark | n | base win rank mean | median | market top3 | market top5 | median base odds |
|---|---:|---:|---:|---:|---:|---:|
| ◎ | 36 | 1.50 | 1 | 35/36 | 36/36 | 3.2 |
| ○ | 36 | 2.47 | 2 | 31/36 | 35/36 | 4.15 |
| ▲ | 36 | 3.08 | 3 | 23/36 | 36/36 | 5.3 |
| △1 | 36 | 4.44 | 4 | 9/36 | 27/36 | 8.55 |
| △2 | 36 | 5.19 | 5 | 6/36 | 24/36 | 11.1 |

印の中央値は事前市場順位1→5位とほぼ一致する。

### Candidate-set concentration

5頭の印セットと事前市場上位5頭の重なり:

- exact same top5 set: 16/36
- 4 of market top5 selected: 18/36
- 3 of market top5 selected: 2/36
- therefore **34/36 races selected at least 4 of the market top5**
- all market top3 were included in the five marks in **32/36 races**

一方、印の順序までmarket 1→5位と完全一致したのは3/36だけであり、GPTは上位候補内の再順位付けは行っている。

5頭の印セットに含まれる各指標top5の平均頭数:

- `total_index` top5: 4.44 / 5
- market top5: 4.39 / 5
- IDM top5: 4.25 / 5
- forecast finish top5: 4.25 / 5

したがって現行v0.1は、候補集合自体が **能力・forecast・marketのconsensus上位へ強く集中**している。

## Why apparent longshots appeared in ▲/△

明示的な「相手は人気を散らす」ルールは存在しない。

低market rankでも能力指標が高い馬が、複数ファクタの不一致により上位5頭へ残る場合がある。

2025-08-23の例:

| Mark | Race | Horse | base win rank | base odds | IDM rank | total_index rank |
|---|---|---|---:|---:|---:|---:|
| △2 | 新潟2R | アイスリーディング | 12 | 25.5 | 2 | 3 |
| △2 | 中京7R | ダンツトラバース | 10 | 30.4 | 2 | 3 |
| △2 | 新潟4R | ソランチャン | 9 | 22.1 | 3 | 4 |
| △1 | 新潟7R | ブルバンビーナ | 8 | 18.3 | 4 | 4 |

これらは「穴馬だから選んだ」のではなく、**市場評価に比して能力評価が高いため残った disagreement horse** と解釈するのが正しい。

## Current mark semantics

現行v0.1の実態は概ね次である。

- ◎: consensus能力上位、marketもほぼ上位。軸として堅めになりやすい。
- ○: ◎に次ぐ総合上位。market上位が中心。
- ▲: 3番手総合評価。意図的なvalue枠ではない。
- △1 / △2: 4〜5番手総合評価。ここで初めてmarketとのdisagreement horseが入りやすくなる。

したがって、`◎は堅い軸 / ○は本線 / ▲は妙味 / △は穴・展開補完` のようなbetting-role設計にはまだなっていない。

## Structural issue

Prediction rankingとbet constructionが同一の5頭順位をそのまま共有している。

現在:

```text
総合的に強そうな5頭を順位付け
 -> ◎ ○ ▲ △1 △2
 -> その印から単勝 / 馬連 / 3連複を機械生成
```

そのため、相手候補に求めるべき

- marketに対する妙味
- ◎との組み合わせ適合
- pace/running-style complement
- 距離/コース特化
- 3着候補としての安定性

を、印の役割として明示的には最適化していない。

## Candidate direction for v0.2 (not adopted)

219R v0.1 historyは固定したまま、次の設計分離を候補とする。

### Layer A — Axis / win-probability ranking

◎候補は主に:

- ability
- condition fit
- distance/surface fit
- pace compatibility
- recent performance
- uncertainty

から「最も勝ち切る確率が高そうな馬」を選ぶ。

### Layer B — Opponent role ranking

○▲△は単なるoverall rank 2〜5位ではなく、役割を分ける候補がある。

- ○: 最も強い直接対抗、連対安定候補
- ▲: abilityに対してmarketが過小評価しているvalue challenger
- △1: pace / course / distanceで◎と異なる勝ち筋を持つ補完馬
- △2: 3着内への残存性・展開事故へのcoverageを持つ馬

ただし印そのものへbetting roleを埋め込むか、prediction marksとbetting candidatesを分離するかは別途設計判断とする。

## Recommended next step

1. 219R v0.1は変更しない。
2. 現行219Rについて、可能な範囲で mark × market rank / ability rank / distance fit / pace fit を診断する。
3. v0.2候補を事前登録する。
4. 新しいuntouched blind blockで v0.1 vs v0.2 を同時freezeする。
5. HJC取得後、軸精度と相手精度を分離して比較する。

特に今後は、headline returnだけでなく:

- ◎ win / top2 / top3 capture
- winning horseが○▲△内にいた率
- actual 2nd/3rd horseのopponent-set capture
- market rank別candidate capture
- axis correct but opponent miss

を診断metricとして持つ価値が高い。
