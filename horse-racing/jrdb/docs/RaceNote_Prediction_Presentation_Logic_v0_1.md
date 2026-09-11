# RaceNote Prediction Presentation Logic v0.1

Status: **ACTIVE / PRESENTATION LAYER CONTRACT**

## 1. Purpose

RaceNote prediction の印・順位・confidence を変更せず、JRDB Newspaper / PWA に表示する
`race_short_comment` と `horse_short_comment` を、レース固有の根拠が分かる自然文として生成する。

従来の 2026-09-05 acceptance sample では、短評は軽量な固定文選択・定型句連結で生成した。
これは integration sample としては十分だったが、異なる馬・レースでも本文が同型になりやすく、
「なぜ ◎ と ○ が違うのか」「このレースで何を買いたいのか」を説明しきれない。

v0.1 presentation logic はこれを次の3層へ分離する。

```text
prediction
  v0.2 control / v1.1-P
  -> marks / ranks / confidence
       |
       v
deterministic evidence extraction
  -> race_comment_brief
  -> horse_comment_briefs (◎○▲)
       |
       v
natural-language rendering
  -> race_short_comment
  -> horse_short_comment
```

**自然文は prediction へ逆流させない。**

## 2. Separation of responsibilities

### 2.1 Prediction layer

prediction layer だけが次を決定する。

- 全馬順位
- ◎ / ○ / ▲ / △ / 無印
- confidence
- v1.1-P axis change

presentation の都合で順位や印を変更してはならない。

### 2.2 Evidence extraction layer

`src/racenote_prediction_presentation.py` が担当する。

入力:

- authoritative pre-race `race_bundle_*.json`
- already-frozen RaceNote prediction record

出力:

- `race_comment_brief`
- ◎○▲それぞれの `horse_comment_brief`

この処理は決定論的であり、結果データ、HJC、SED、払戻、最終オッズ、最終人気を読まない。

### 2.3 Natural-language rendering layer

GPT等のrendererが structured brief だけを自然文へ変換する。

renderer は新しい予想判断を行わない。briefに存在しない根拠を追加しない。
言い換え、文の組み立て、冗長性の除去のみを担当する。

## 3. Horse comment contract

`horse_short_comment` は ◎ / ○ / ▲ のみ生成する。

### 3.1 Common rule

単馬短評は最低限、次のうち2要素を含む。

1. その馬固有の主要な強み
2. 上位3頭内での相対差
3. material な弱みまたはrisk
4. その印に置いた理由

単に印ごとの末尾を

- `軸候補。`
- `相手筆頭。`
- `上位争いに警戒。`

へ差し替えただけの本文は不可。

### 3.2 ◎

目的:

**なぜこの馬を最上位にしたかを説明する。**

優先する比較:

- ○▲に対する能力差
- 展開・想定位置の優位
- 条件適性
- 調教・状態
- prediction score上の主要優位
- material risk

「全項目で優位」とは限らない。
たとえば能力で優位だが調教では○に劣る場合、その差を隠さない。

### 3.3 ○

目的:

**◎との差と、○自身が上回る材料を両方説明する。**

「◎と同じ本文 + 相手筆頭」は不可。

例となる構造:

```text
能力では◎に一歩譲る
+
調教・状態は◎より上
+
展開次第で逆転可能
```

### 3.4 ▲

目的:

**◎○より評価を落とした理由と、それでも上位候補に残す材料を説明する。**

単なる「3番手評価」ではなく、浮上条件または固有の強みを残す。

## 4. Race comment contract

`race_short_comment` は次を基本構造とする。

```text
展開読み
+
このレースで重視する選別軸
+
material なレース固有risk / 注意点（存在する場合）
```

### 4.1 展開読み

少なくとも以下を構造化してから文章化する。

- field の脚質構成
- forecast pace のfield内mode
- 逃げ+先行比率によるfront pressure
- 上位候補の脚質構成

固定された「ハイならこの1文」「スローならこの1文」だけで完成させない。

### 4.2 買いたい馬の選別法

上位3頭とfield全体を比較し、上位候補を分けている軸を抽出する。

現行 deterministic extractor の候補軸:

- `ability`
- `suitability`
- `pace_fit`
- `condition`
- `distance_fit`
- `forecast`

各軸について top3 mean と field mean の差を算出し、差が大きい順を
`selection_priorities` とする。

rendererはこの構造を使い、

- 基礎能力上位を優先
- 展開に乗れる馬を優先
- 調教・状態の良い馬を優先
- 距離適性を重視

など「このレースでは何を買いたいか」を説明する。

### 4.3 +α / race-specific risk

material な場合のみ触れる。

例:

- confidence C
- ◎と○のGood差が小さい
- 上位3頭が同一脚質
- 距離 contradiction を持つ上位馬がいる
- 上位比較が接戦で順位入替リスクが大きい

riskがない場合に無理に注意文を作らない。

## 5. Deterministic evidence payload

`racenote_prediction_presentation.py` は少なくとも次を保持する。

### 5.1 Horse brief

```json
{
  "mark": "○",
  "prediction_rank": 2,
  "horse_no": 13,
  "horse_name": "ナリタライズ",
  "observations": {
    "idm": 34.2,
    "total_index": 38.9,
    "running_style": "逃げ",
    "forecast_finish_order": 2,
    "training_index": 58,
    "condition_index": 56,
    "training_arrow": "上昇"
  },
  "relative": {
    "idm": {"rank_among_top3": 2},
    "training_index": {"rank_among_top3": 1},
    "condition_index": {"rank_among_top3": 1}
  },
  "strength_axes": ["training_condition"],
  "risk_axes": [],
  "rendering_role": "explain_difference_from_axis_and_upside"
}
```

### 5.2 Race brief

```json
{
  "pace": {
    "forecast_mode": "平均",
    "style_counts": {
      "逃げ": 1,
      "先行": 4,
      "差し": 5,
      "追込": 2
    },
    "front_pressure": "MEDIUM"
  },
  "selection_priorities": [
    {
      "axis": "ability",
      "top3_minus_field": 0.18
    }
  ],
  "risk_flags": [
    "axis_good_gap_small"
  ]
}
```

## 6. Rendering rules

### 6.1 Race short comment

目安は60–100字。

必須:

- 展開読み
- 選別法

任意:

- material risk

禁止:

- briefにない事実の追加
- 結果を知っている表現
- 最終オッズ・最終人気
- pace classだけで固定文を選んで終了
- 毎レース同一の結句を強制

同じ意味でも自然な言い換えは許可する。

### 6.2 Horse short comment

目安は35–70字/頭。

必須:

- 馬固有の根拠
- ◎○▲間の相対差が分かること

禁止:

- 3頭の本文を同一にして末尾だけ変更
- 調教を必ず入れる等、特定featureの機械的強制
- 数値を羅列するだけの短評
- predictionで使っていない新しい判断を文章側で追加

数値そのものを書くか、「能力上位」「状態面で優位」と要約するかはrendererに任せる。
ただし要約はstructured evidenceと矛盾してはならない。

## 7. Example: 2026-09-05 阪神6R

このレースで重要なのは、◎11と○13を同列の定型文にしないこと。

確認できる差の例:

- 11: IDM / total_index で13より上
- 11: forecast finish が上
- 13: training_index / condition_index で11より上
- 13: training arrow は上昇、11は平行線

したがってrendererが生成すべき意味は概ね:

```text
◎11:
能力・予測順位側の優位を軸に最上位。
状態面では○13に譲る材料も残す。

○13:
能力面では◎11に譲るが、調教・状態面はより強い。
その差を逆転余地として説明する。
```

ここで特定の完成文を固定しない。
重要なのは「同じ理由を別の印語尾で再利用しない」ことである。

## 8. Versioning

このv0.1は **presentation logic version** であり、
RaceNote prediction model versionとは独立して管理する。

例:

```text
prediction model:
  v1.1-P-gated-0.1

presentation evidence:
  racenote-presentation-evidence-0.1
```

presentation wordingを調整しても、印・順位・scoreが変わらない限り
prediction backtestのmodel versionを変更しない。

一方、evidence抽出項目・比較規則・risk判定を変更した場合は
presentation evidence versionを更新する。

## 9. PWA handoff

PWA CSV列契約は既存 `RaceNote_Newspaper_Output_Contract_v0_1.md` を維持する。

- `race_short_comment`: race briefを自然文化したもの
- `horse_short_comment`: ◎○▲ horse briefを自然文化したもの
- △ / 無印: `horse_short_comment` blank

CSV schema自体は変更しない。

2026-09-05の既存CSVはintegration acceptance sampleとして保持し、
このlogicで再生成する場合はpresentation revisionとして別生成物にする。
