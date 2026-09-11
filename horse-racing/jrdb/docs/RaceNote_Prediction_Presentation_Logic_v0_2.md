# RaceNote Prediction Presentation Logic v0.2

Status: **ACTIVE / EDGE-AWARE PRESENTATION EXTENSION**

## 1. Purpose

v0.1 の「決定論的な根拠抽出 -> 自然文rendering」という責務分離を維持したまま、
`v1.1-P-gated-0.1` が Edge polarity 比較によって ◎ を変更した場合、その**印決定理由**を
presentation briefへ明示する。

v0.2は予想ロジックではない。次を変更しない。

- v0.2 Good
- v1.1-P axis selection
- ◎ / ○ / ▲ / △
- prediction rank
- confidence
- Edge Matcher / Registry semantics

## 2. Why v0.2 is needed

2026-09-05 のpresentation調整では、主に能力・展開・調教・状態の横比較を改善対象とした。
一方、2026-09-12 TRUE_FORWARDでは v1.1-P によるaxis changeが実際に発生した。

axis change raceでは、選ばれた◎が v0.2 Good 1位とは限らない。
そのためv0.1 briefだけで自然文を生成すると、

- 「能力・総合評価で最上位だから◎」と誤読させる
- base axisとselected axisの違いを説明できない

という問題がある。

## 3. Added structured evidence

実装:

`src/racenote_prediction_presentation_v0_2.py`

VERSION:

`racenote-presentation-evidence-0.2`

v0.1 briefをそのまま生成した後、already-frozen prediction recordから次を付与する。

### 3.1 Race-level `axis_decision`

- `axis_changed`
- `base_axis_horse_no`
- `selected_axis_horse_no`
- `axis_good_guard`
- `base_axis_polarity`
- `selected_axis_polarity`

### 3.2 Horse-level `edge_context`

- `mark_decision_role`
- `performance_edge_polarity`
- `family_vote_sum`
- `performance_family_votes`
- `axis_eligible`
- `good_gap_from_base_axis`
- `active_unexpired_match_count`
- supporting / opposing Edge ID（監査用）

`mark_decision_role` は少なくとも次を区別する。

- `edge_promoted_to_axis`
- `base_axis_displaced_by_edge_comparison`
- `relative_order_preserved_after_axis_change`
- `base_order_preserved`

## 4. Rendering rule

### axis change = false

従来v0.1と同様、能力・条件適性・展開・調教状態・riskを中心に説明する。
Edgeが印差の主要理由でない場合、無理にEdgeへ言及しない。

### axis change = true

◎短評は、selected axisが**固定済みv1.1-P Edge polarity比較で昇格した**ことを意味として含める。

例:

```text
基礎評価では○が上だが、Good差はguard内。条件Edgeがプラスに働き、◎へ繰り上げた。
```

○がdisplaced base axisの場合は、base評価の強さを隠さない。

例:

```text
基礎Goodは最上位。ただしEdge polarityで◎に譲った形で、地力評価は高い。
```

完成文を固定する必要はない。重要なのは、

- Edgeによるaxis changeを別の能力理由へすり替えない
- selected axisを「Good 1位」と偽らない
- raw Edge IDを通常の読者向け短評へ羅列しない

ことである。

## 5. Leakage / separation

v0.2 presentationはprediction freeze後に実行してよいが、入力はpre-race情報とalready-frozen predictionだけとする。

禁止:

- HJC / SED
- target finish
- payout
- final odds / final popularity
- later-dated history
- presentation文言を用いたmark再計算

`result_data_used = false` を維持する。

## 6. Version relationship

```text
prediction model:       1.1-P-gated-0.1
presentation evidence:  racenote-presentation-evidence-0.2
```

2026-09-05のpresentation v0.1成果物は再解釈しない。
v0.2はEdge-aware predictionを新聞PWAへ説明するための追加versionとする。
