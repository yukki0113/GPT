# RaceNote Forecast Gen0 plan

Status: CURRENT RESEARCH PLAN / GEN0.3 CONTRACT FINALIZED
Last reviewed: 2026-09-25

> Current next-generation contract: `RaceNote-Forecast-Gen0.3`.
> Planned first activation: `Gen0-G001`.
> Reading priority: `DATA / TRENDS > RACEREVIEW >= SIMPLE ABILITY`.
> Gen0.2 was implemented but never activated and is retained as reference only.

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
  -> deterministic validation / hash
  -> immutable freeze
  -> Google Sheets readback
  -> result acquisition
  -> post-race evaluation
```

結果取得をprediction freezeおよびledger readbackより前へ置かない。

## 3. Prediction inputs

Gen0.3 Independent Forecastの入力順は固定する。

```text
RaceNote INDEPENDENT view
  -> General Evidence
  -> Pairwise Comparison
  -> Scenario Robustness
  -> Base Forecast
  -> EdgeDB Performance-only overlay
  -> Final Forecast
  -> Freeze
```

### Pre-Freeze allowed

Race level:

- surface / distance / course layout / turn / class / grade / field size
- as-of-safe frame / running-style / other historical trends
- independent Race Structure reconstructed from prior corner positions

Horse level:

- same surface / same distance / same venue / distance-range history
- RaceReview historical running-content evidence
- prior-run IDM as Ability Anchor
- recent detailed runs / older history / coverage
- jockey / sire / frame context
- pre-race factual rotation / weight / raw workout evidence allowed by firewall
- EdgeDB Performance evidence after Base Forecast only

### Pre-Freeze forbidden

- current JRDB IDM / total composite / marks
- current JRDB forecast running style / forecast pace / forecast finish order
- current odds / popularity / market ranks
- EdgeDB Value channel
- RL / Value
- Training Edge
- target result / payout / final odds

Current JRDB consensus and market may be opened only after immutable Forecast
Freeze. They may evaluate the frozen prediction but must not mutate it.

## 4. Initial factor set

`FSET-Gen0.1` は Gen0-G000 の初期研究factor setとして保持する。

次世代のreading orderはfactor番号順ではなく、次のEvidence lane順とする。

General EvidenceからAll-Runner Synthesisへ入る直前に
`PredictionInterpretation-v0.1` を作る。
これはTrend / RR / Abilityのraw Evidenceを非加点で整理するpre-readであり、
順位・印・確率は決定しない。PairwiseはInterpretationを先に読み、
その後raw Evidence laneを再確認する。

その後 `All-Runner Synthesis v0.1` で全馬を一度に横比較し、
non-scoringのdraft orderと重点Pairwise境界を作る。
新規運用ではdraft orderをPairwiseへ直接手渡ししない。

```text
DATA_TREND
  -> RACEREVIEW
  -> ABILITY_ANCHOR
  -> relative comparison
```

したがってF01基礎能力を先頭だから最重要、と解釈してはならない。

2026-09-25時点で `General Evidence v0.1`、
`Pairwise Comparison v0.1`、`Scenario Robustness v0.1`、
`RaceNote-Forecast-Gen0.3` まで実装済み。
次世代では全馬独立採点だけで順位を作らず、直接比較と逆転条件を記録し、
SLOW / MEDIUM / FAST の3展開で軸の頑健性を確認したうえでBase Forecastを
作る。EdgeDBはその後にPerformance channelだけを補助Evidenceとして使う。

初期factor setは `FSET-Gen0.1` の10ファクター。

1. F01 基礎能力
2. F02 条件適性
3. F03 展開・位置取り
4. F04 調教・状態
5. F05 近走内容
6. F06 長期履歴・条件実績
7. F07 騎手・厩舎
8. F08 血統
9. F09 枠・条件統計
10. F10 事前市場情報

これは固定weightではない。

GPTはレースごとに重要度を変え、不要なfactorを軽視してよい。どのfactorを重視・軽視したかは予想内容とは別に研究メタデータとして記録する。

詳細は `FORECAST_GEN0_PREDICTION_CONTRACT_v0_1.md`。

## 5. Forecast record

各予想は結果取得前に、少なくとも次を記録する。

### Identification

- target date
- venue
- race_no
- race_key
- source version / semantic hash
- forecast generation version
- evaluation mode (`BLINDED_HISTORICAL / TRUE_FORWARD`)

### Race reading

- race shape summary
- expected pace / position picture
- important condition factors
- primary factor codes
- de-emphasized factor codes

### Horse comparison

全馬について:

- horse_no / horse_name
- GPT rank
- mark
- strengths
- risks
- evidence summary
- evidence conflicts
- comparison against nearby rivals
- factor codes

各馬を読むが、保存するのは監査用のreason summaryでありprivate chain-of-thoughtではない。

### Final prediction

- ◎ / ○ / ▲ / △等の相対順位
- axis horse
- confidence A / B / C
- concise reason for the axis
- alternatives / upset candidates where appropriate
- uncertainty summary

confidenceは的中確率ではなく、**入力coverageとevidence整合性に対する予想時点の確信度**とする。

## 6. Pre-result self-audit

freeze前にGPT自身が予想を監査する。

最低限、次を確認する。

- 全馬を見たか
- レース条件を先に読んだか
- 単一indexへ引っ張られていないか
- 能力と展開を分けて評価したか
- 調教を過剰に上書き材料へしていないか
- 小母数実績を100%だからという理由で強く評価していないか
- missingをnegative signalへ変換していないか
- contradictory evidenceを消していないか
- 人気 / base oddsだけで順位を決めていないか
- 各馬を独立採点しただけでなく横比較したか
- ◎の負け筋を確認したか
- target result / final odds / post-race情報を見ていないか

監査によって予想を修正した場合、Freezeするのは修正後の最終予想だけとする。

## 7. Freeze

prediction freezeはresult acquisitionより先に完了させる。

freezeでは最低限:

- prediction body
- input identity / semantic hash
- generation version
- factor set version
- created_at
- pre-race guard status
- result visibility status
- prediction hash
- frozen_at

を固定する。

`src/racenote_forecast_gen0_3.py` がGen0.3のsource-chain / probability / mark / Edge Performance / freeze境界をdeterministicに検証する。

禁止result field、pre-race guard不成立、結果visible、mark/axis内部不整合、hash不整合はfail closedとする。

既存TRUE_FORWARD資産のhash / provenance / immutable recordの考え方は再利用するが、旧v1.1-Pの印決定ロジック自体をGen0へ持ち込まない。

## 8. Google Sheets ledger

継続台帳はネイティブGoogle Sheet `RaceNote Forecast Gen0 検証台帳`。

正本config:

`config/racenote_forecast_gen0_ledger_v0_3.json`

Google SheetsはChatGPTのDrive / Sheets connectorから直接read / writeする。RaceNote sourceへGoogle API clientやcredentialを持ち込まない。

pre-resultでは:

- `予想Freeze`
- `馬別評価`
- `ファクター使用`
- `Freeze監査`

を同一transactionで記帳する。

post-resultでは:

- `結果_馬別`
- `振返り`
- `ファクター検証`
- `Freeze監査`

を更新する。

詳細は `FORECAST_GEN0_LEDGER_CONTRACT_v0_1.md`。

## 9. Post-race evaluation

結果取得後は「当たった / 外れた」だけで終わらせない。

`src/racenote_forecast_gen0_evaluation.py` は結果identity、freeze-before-resultを検証し、◎着順・winner mark・印内捕捉等の客観指標を作る。

### Outcome

- ◎着順
- ◎勝利
- winnerをどこまで評価できていたか
- 上位候補の順位整合性
- 印内の上位3着捕捉
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

### Factor audit

予想時に記録したfactor usageへ対し:

- HELPFUL
- NEUTRAL
- MISLEADING
- UNRESOLVED

および:

- OVER
- UNDER
- APPROPRIATE
- NA

を記録する。

結果を知った後の後付け説明でprediction recordを書き換えない。

## 10. Improvement unit

原則として**約50Rを1改善単位**とする。

初期generation:

- `Gen0-G000`
- `RaceNote-Forecast-Gen0.1`
- `FSET-Gen0.1`
- initial mode: `BLINDED_HISTORICAL`
- target: 50R

1Rごとの結果で即座にweight・ルール・reading orderを変更しない。

50R程度のまとまりで、少なくとも次を集計する。

- ◎成績
- 印別成績
- confidence別成績
- favorite / mid-price / longshot等の市場帯別傾向
- surface / distance / class別傾向
- factor別 `HELPFUL / MISLEADING`
- factor別 `OVER / UNDER`
- reading-error category件数
- recurring overvaluation / undervaluation
- missing-data起因の失敗
- Reader View不足項目

50Rは絶対値ではなく、過学習を避けてまとまった傾向を見るための初期運用単位である。

## 11. Change discipline

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

旧方式の成績が良かったことだけを理由にcurrent Gen0をv1.1-Pへ戻さない。

## 12. Relationship with EdgeDB

EdgeDBは有用なhistorical evidence sourceになり得るが、Gen0 core factor setでは旧v1.1-PのようにEdge polarityだけで機械的に軸を入れ替えない。

Edgeを使う別実験では:

- Performance / Valueを区別する
- CONFIRMED / SUGGESTIVEを区別する
- overlapを安易に加算しない
- sample / applicability / current-matchを確認する
- 他のRaceNote evidenceと横比較する

という既存EdgeDB contractを守る。

## 13. Relationship with external sources

Eval、keibailuka、その他外部sourceはRaceNote単独Gen0へ暗黙に混ぜない。

併用研究を行う場合はsource別に記録し、RaceNote-only predictionとの比較が可能な状態を保つ。

## 14. Initial acceptance target

Gen0初期段階の成功条件は「高い的中率を宣言できること」ではない。

まず次を安定して満たすことを優先する。

- pre-race onlyを守れる
- 同じRaceNote evidenceから一貫した比較理由を残せる
- predictionとpost-race解説を混同しない
- 予想根拠を後から監査できる
- Google Sheetsへtransaction単位で記帳できる
- factor usageとpost-race factor reviewをjoinできる
- 一定R単位で失敗パターンを集約できる
- 改善前後のversion差を追跡できる

この基盤が成立してから、accuracy / ranking quality / betting valueの改善へ進む。
