# RaceNote Forecast Gen0 plan

Status: CURRENT RESEARCH PLAN
Last reviewed: 2026-09-13

## 1. Goal

RaceNote Forecast Gen0の目的は、固定ルールで印を機械生成することではなく、**RaceNoteの開催前evidenceをGPTが読み、比較し、予想し、その読み方を結果から改善する研究サイクル**を成立させることである。

評価対象は単なる的中率だけではない。

- どのevidenceを重く読んだか
- どのevidenceを読み落としたか
- 過大評価 / 過小評価は何だったか
- 相手比較で何を誤ったか
- 不確実性を適切に表現できたか
- Reader View / RaceNoteに不足情報があったか

をprediction時点の記録とpost-race結果から検証する。

## 2. One-race lifecycle

1Rについて必ず次の順序を守る。

```text
pre-race source resolve
  -> RaceNote validation
  -> GPT evidence reading
  -> horse-to-horse comparison
  -> prediction draft
  -> pre-result self-audit
  -> immutable freeze
  -> result acquisition
  -> post-race evaluation
```

結果取得をprediction freezeより前へ置かない。

## 3. Prediction inputs

基本入力はRaceNote authoritative bundle / validated Reader Viewとする。

`docs/RaceNote_Prediction_Handoff_v0_1.md` のreading orderを基準に、最低限以下を確認する。

### Race level

- surface / distance
- course layout / turn
- class / grade / race conditions
- field size
- weight rule
- race trends
- pace structure

### Horse level

- basic / ability
- IDM / total index等のJRDB事前評価
- surface / distance / track fit
- running style / forecast position
- pace-related indices
- training / condition
- recent detailed runs
- historical profile / older runs
- same course / same distance / same surface
- jockey / sire / frame等のcontext statistics
- JRDB事前market情報
- coverage / missing / contradictory evidence

単一index、単一Edge、単一コメントだけで結論を固定しない。

## 4. Forecast record

各予想は結果取得前に、少なくとも次を記録する。

### Identification

- target date
- venue
- race_no
- race_key
- source version / semantic hash
- forecast generation version (`RaceNote Forecast Gen0`)

### Race reading

- race shape summary
- expected pace / position picture
- important condition factors

### Horse comparison

各主要候補について:

- horse_no / horse_name
- strengths
- risks
- evidence used
- evidence conflicts
- comparison against nearby rivals

### Final prediction

- ◎ / ○ / ▲ / △等の相対順位
- axis horse
- confidence A / B / C
- concise reason for the axis
- alternatives / upset candidates where appropriate

confidenceは的中確率ではなく、**入力coverageとevidence整合性に対する予想時点の確信度**とする。

## 5. Pre-result self-audit

freeze前にGPT自身が予想を監査する。

最低限、次を確認する。

- レース条件を先に読んだか
- 単一indexへ引っ張られていないか
- 能力と展開を分けて評価したか
- 調教を過剰に上書き材料へしていないか
- 小母数実績を100%だからという理由で強く評価していないか
- missingをnegative signalへ変換していないか
- contradictory evidenceを消していないか
- 人気 / base oddsだけで順位を決めていないか
- 各馬を独立採点しただけでなく横比較したか
- target result / final odds / post-race情報を見ていないか

監査によって予想を修正した場合、修正理由もfreeze前記録へ残す。

## 6. Freeze

prediction freezeはresult acquisitionより先に完了させる。

freezeでは最低限:

- prediction body
- input identity / semantic hash
- generation version
- created_at
- pre-race guard status
- prediction hash

を固定する。

既存TRUE_FORWARD資産のhash / provenance / immutable recordの考え方は再利用してよい。

ただし、旧v1.1-Pの印決定ロジック自体をGen0へ持ち込まない。

## 7. Post-race evaluation

結果取得後は「当たった / 外れた」だけで終わらせない。

### Outcome

- ◎着順
- ○▲△着順
- winnerをどこまで評価できていたか
- 上位候補の順位整合性
- 必要に応じて馬券評価。ただしprediction evaluationとは分ける

### Reading audit

- ability reading
- condition reading
- pace / position reading
- suitability reading
- recent-run interpretation
- long-history interpretation
- context-stat interpretation
- uncertainty handling

について、予想時点の根拠と結果後の事実を比較する。

結果を知った後の後付け説明でprediction recordを書き換えない。

## 8. Improvement unit

原則として**約50Rを1改善単位**とする。

1Rごとの結果で即座にweight・ルール・reading orderを変更しない。

50R程度のまとまりで、少なくとも次を集計する。

- ◎成績
- 印別成績
- confidence別成績
- favorite / mid-price / longshot等の市場帯別傾向
- surface / distance / class別傾向
- reading-error category件数
- recurring overvaluation / undervaluation
- missing-data起因の失敗
- Reader View不足項目

50Rは絶対値ではなく、過学習を避けてまとまった傾向を見るための初期運用単位である。

## 9. Change discipline

改善案は次の3種類へ分ける。

### A. Reading guidance change

GPTが既存情報をどう読むかの改善。

例:

- pace interpretationの順番
- small sampleの扱い
- contradictory evidenceの残し方

### B. Input / RaceNote change

必要なevidence自体が不足している場合のdata contract改善。

RaceNote authoritative factsを変える場合は、prediction都合だけで意味を捏造せずsource / provenanceを明確にする。

### C. Model / rule experiment

固定weight、score、gate等を導入する実験。

これはGen0の自然言語比較とは分け、独立version・blind test・forward testで評価する。

## 10. Relationship with EdgeDB

EdgeDBは有用なhistorical evidence sourceになり得るが、Gen0では旧v1.1-PのようにEdge polarityだけで機械的に軸を入れ替えない。

Edgeを使う場合も:

- Performance / Valueを区別する
- CONFIRMED / SUGGESTIVEを区別する
- overlapを安易に加算しない
- sample / applicability / current-matchを確認する
- 他のRaceNote evidenceと横比較する

という既存EdgeDB contractを守る。

## 11. Relationship with external sources

Eval、keibailuka、その他外部sourceはRaceNote単独Gen0へ暗黙に混ぜない。

併用研究を行う場合はsource別に記録し、RaceNote-only predictionとの比較が可能な状態を保つ。

## 12. Initial acceptance target

Gen0初期段階の成功条件は「高い的中率を宣言できること」ではない。

まず次を安定して満たすことを優先する。

- pre-race onlyを守れる
- 同じRaceNote evidenceから一貫した比較理由を残せる
- predictionとpost-race解説を混同しない
- 予想根拠を後から監査できる
- 一定R単位で失敗パターンを集約できる
- 改善前後のversion差を追跡できる

この基盤が成立してから、accuracy / ranking quality / betting valueの改善へ進む。
