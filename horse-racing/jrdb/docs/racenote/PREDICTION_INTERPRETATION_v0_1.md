# RaceNote Prediction Interpretation v0.1

Status: IMPLEMENTED RESEARCH INTERPRETATION LAYER  
Date: 2026-09-25

## 1. Purpose

RaceNote が保持する Evidence を、Pairwise Comparison の前に
「何が上げ材料か / 下げ材料か / どこまで再現性を期待できるか」
へ整理する。

この層は順位を決めない。

予想の標準読解順は次とする。

```text
条件・レース傾向
  -> 各馬の条件適合
  -> RaceReview の走った内容
  -> Ability Anchor
  -> positive / concern / contradiction を保持
  -> Pairwise Comparison
  -> Scenario Robustness
  -> Forecast
```

基本優先順位は変わらない。

```text
DATA / TRENDS > RACEREVIEW >= SIMPLE ABILITY
```

## 2. DATA_TREND の読み方

最初に馬自身の条件別履歴を見る。

- SAME_SURFACE
- SAME_DISTANCE
- DISTANCE_RANGE
- SAME_VENUE

各観測は以下を保持する。

- direction
- sample size band
- condition rate
- career baseline
- condition - career の rate delta
- redundancy group

方向は実測差を表すだけで因果を意味しない。

sample size は Evidence の方向を消さない。
小母数の positive は positive のまま残し、
Pairwise で confidence を落として読む。

### Redundancy

同距離と距離帯は同じ情報族を含みやすいため、
ともに `DISTANCE` redundancy group とする。

同様に:

- surface -> SURFACE
- venue -> VENUE

とする。

「positive が3個あるから3票」という解釈は禁止する。

## 3. Population context

次に race-level / population-level context を見る。

現在:

- frame
- sire
- jockey
- historical running-style trend

これらは馬自身の条件別履歴と異なり、
単体で positive / negative を決めない。

他馬との相対比較で使う context とする。

例:

- 2枠の成績が良い
- 同条件で先行型が優勢
- 当該種牡馬の同条件成績が高い
- 騎手の条件成績が高い

これらを単独で本命理由にはしない。

## 4. Race Structure

Independent Race Structure は、各馬の過去コーナー位置から作る。

- FRONT
- FORWARD
- MID
- BACK
- UNKNOWN

レース全体では:

- LOW
- MEDIUM
- HIGH
- UNKNOWN

の前受け圧力を保持する。

この情報を現在の JRDB 予測脚質へ変換しない。
また、

`FRONT = 今回逃げる`

とは扱わない。

Race Structure は Pairwise / Scenario の相対 context である。

## 5. RaceReview の読み方

RaceReview は着順では失われる「走った内容」を読む。

優先して確認する。

1. visible result と running content の乖離
2. direct performance
3. repeatability
4. pace / position context
5. concern / contradiction
6. target condition overlap

代表例:

- RESULT_UNDERRATES_TIME
- RESULT_OVERRATES_TIME
- PACE_POSITION_AGAINST_GOOD_RUN
- PACE_POSITION_AIDED_RESULT
- LOSS_WITH_FASTEST_LAST3F
- MOVE_THEN_FADE
- repeated variants

### Hidden strength

着順が悪くても内容が良い場合は
`HIDDEN_STRENGTH` candidate として残す。

これはまだ「穴馬」や「妙味馬」を意味しない。
市場は Freeze 後まで見ない。

### Fragile form

着順は良いが内容が弱い / 展開恩恵が大きい場合は
`FRAGILE_FORM` candidate として残す。

これも「人気馬だから消す」という意味ではない。

### Mixed

hidden strength と fragile form が共存する場合は
MIXED のまま残す。

一方を消して単純化しない。

## 6. RaceReview transferability

RaceReview の良い過去走が、今回にもそのまま再現するとは限らない。

v0.1 では採用された RR Evidence の元走について
明確に判定できる一致だけを残す。

- exact same surface
- exact same distance

状態:

- EXACT_SURFACE_DISTANCE_PRESENT
- PARTIAL_EXACT_MATCH_PRESENT
- NO_EXACT_TARGET_MATCH
- UNKNOWN

v0.1 では以下を勝手に導入しない。

- 「200m差なら同条件」等の距離許容幅
- venue code の推測変換による一致判定
- pace shape 一致を数値的な transfer score にすること

元走 pace shape は context として保持する。

## 7. Ability Anchor

Ability Anchor は過去 IDM から:

- latest
- peak
- typical median
- minimum
- MAD

を保持する。

用途は:

- 地力の上限 / 下限確認
- Trend / RR が薄い時の補助
- Trend / RR で拾った馬が能力的に大きく足りない可能性の確認
- 近い2頭の tie-break 補助

禁止:

- Ability だけで upgrade
- Ability だけで downgrade
- peak IDM 順をそのまま最終順位にする

Ability は `ANCHOR_ONLY` である。

## 8. Prediction Interpretation profile

General Evidence の各馬に:

`PredictionInterpretation-v0.1`

を付与する。

主な項目:

```text
data_trend
race_structure
racereview
ability_anchor
positive_case_components
concern_case_components
pairwise_reading_order
policy
```

例:

```text
data_trend:
  MIXED
  same_distance = positive / small
  same_venue    = negative / small

racereview:
  HIDDEN_STRENGTH
  exact same surface + distance source runあり
  repeated above-class performanceあり

ability_anchor:
  AVAILABLE_ANCHOR
  peak 60 / typical 58

positive_case:
  DATA_TREND_MIXED_SUPPORT
  RACEREVIEW_SUPPORT

concern_case:
  DATA_TREND_MIXED_CONCERN
```

これは Pairwise 前の整理であり、最終評価ではない。

## 9. Pairwise reading

Pairwise request は両馬の Prediction Interpretation を先に読む。

その後 raw Evidence lane を確認する。

```text
Interpretation profile
  -> raw DATA_TREND verification
  -> raw RACEREVIEW verification
  -> Ability Anchor verification
  -> A / B relation
```

Pairwise では必ず:

- なぜ A > B か
- higher-priority evidence と矛盾していないか
- 何なら逆転するか

を残す。

Ability が Trend / RR を覆す場合は override reason が必須。

## 10. Prediction case semantics

Interpretation は次の component を提示できる。

Positive examples:

- DATA_TREND_SUPPORT
- DATA_TREND_MIXED_SUPPORT
- RACEREVIEW_SUPPORT

Concern examples:

- DATA_TREND_OPPOSITION
- DATA_TREND_MIXED_CONCERN
- RACEREVIEW_CONCERN
- RACEREVIEW_MIXED_CONCERN

component の個数を score にしてはならない。

## 11. Short comment relationship

短評は将来、同じ Evidence から生成する。

例:

```text
同距離では安定。近2走も着順以上の内容で、
同じ芝1600で現級水準を上回る走りがある。
地力も足りるが、同競馬場実績はやや弱くそこは課題。
```

または:

```text
能力値自体は上位。ただ前走好走は展開利を含み、
同距離成績も強調しづらい。今回は一枚評価を下げる。
```

短評だけの別ロジックを作らない。

## 12. Market boundary

current popularity / odds は Interpretation に入れない。

人気傾向を使う場合も、現行方針では Freeze 後の市場評価として扱う。

したがって pre-Freeze では:

`hidden strength != value`

`fragile form != popular risk`

である。

## 13. Canonical implementation

- `src/racenote_horse_evidence_card.py`
- `src/racenote_general_evidence.py`
- `src/racenote_pairwise_comparison.py`
- `schema/racenote_horse_evidence_card_schema_v0_1.json`
- `schema/racenote_general_evidence_schema_v0_1.json`

Prediction Interpretation remains non-scoring and deterministic.
