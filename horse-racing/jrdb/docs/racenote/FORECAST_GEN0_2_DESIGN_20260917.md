# RaceNote Forecast Gen0.2 Design Draft

Status: PROPOSED / NOT YET CURRENT
Date: 2026-09-17

## 0. Purpose

Gen0-G000 / RaceNote-Forecast-Gen0.1 の50R検証を受け、RaceNoteがJRDBの今回レース用派生評価や市場コンセンサスをなぞる構造を弱め、独立した予測・確率・妙味・馬券研究へ進むためのGen0.2設計案を定義する。

この文書は設計案であり、現行 `FORECAST_GEN0_PREDICTION_CONTRACT_v0_1.md`、Gen0-G000のFreeze済み予想、既存hashを変更しない。

次generationを開始する場合の想定:

- generation_id: `Gen0-G001`
- forecast_version: `RaceNote-Forecast-Gen0.2`
- factor_set_version: `FSET-Gen0.2`

## 1. Gen0-G000からの主要観測

50R評価では以下が観測された。

- ◎勝利 12/50 = 24.0%
- 正常に走った49Rのうち、◎敗戦37R
- ◎敗戦37Rのうち勝馬印内 27R
- ◎敗戦37Rのうち勝馬無印 10R
- ◎敗戦時、◎の方が勝馬より最終人気上位 33/37R
- 勝馬印内率 40/50 = 80.0%

したがって主要課題は「候補を全く発見できない」ことより、候補内序列、人気側への回帰、今回JRDB派生評価への依存を含む可能性が高い。

Gen0.1の◎理由では、今回IDMまたは総合指数が46/50R、両方が41/50Rで明示的に使われていた。Gen0.2では、今回レース用JRDB派生評価を独立予測から分離する。

## 2. Core principle

Gen0.2の最重要境界:

```text
RaceNote Independent evidence
  -> independent all-runner comparison
  -> base probabilities / base rank
  -> EdgeDB performance adjustment
  -> RaceNote final probabilities / marks
  -> immutable RaceNote Forecast Freeze
  -> JRDB consensus comparison (no forecast mutation)
  -> market snapshot / value analysis
  -> betting plan freeze
  -> optional consumer display: Training Edge
  -> result acquisition
  -> prediction / value / betting evaluation
```

### Hard rules

1. RaceNote最終印は、今回JRDB印、今回IDM、今回総合指数、JRDB予測ゴール順位、市場人気を見て決めない。
2. EdgeDBはRaceNote内部の独自補正シグナルとして利用する。
3. EdgeDBの `performance_signal` と `value_signal` を分離する。
4. RaceNote予想へ効かせるのは `performance_signal` のみ。
5. EdgeDB `value_signal` は必要ならmarket/value layerだけで利用し、印を変更しない。
6. Training Edge (TE) はRaceNote予想へ入力しない。
7. TEは新聞/PWAでRaceNote印と並列表示し、実購入時の人間判断材料とする。
8. RaceNote検証とTEを混ぜない。TE併用購入を検証する場合は別consumer/購入記録として扱う。
9. result / final odds / final popularity / payoutはforecastおよびbet-plan freeze前に見ない。

## 3. Input partition / firewall

Reader View v0.1はlosslessであるため、Gen0.2ではGPTへ渡す情報を用途別に物理分離する。

### A. Independent prediction view — forecast前に閲覧可

主対象:

- race conditions
  - surface / distance / turn / course layout
  - class / grade / race type
  - field size / weight rule / carried weight
  - known pre-race track/condition facts
- horse identity / basic facts
- past race facts
  - finish / abnormality
  - prior race condition
  - time / sectionals / corner position
  - carried weight / body weight
  - jockey
  - running pattern / trip facts
  - comments / equipment / known traits where source exists
- prior-run derived performance indices
  - past IDM等は「過去走要約」として補助利用可
  - raw factsと同じ過去走を多重加点しない
- current raw workout / preparation facts
  - course / clock / furlongs / effort / pair work等
- rotation / rest facts
- historical_profile
  - career / same surface / same distance / distance range / same venue
- as-of-safe sire / jockey / frame stats
- history coverage / missing / warnings

### B. JRDB consensus view — RaceNote Forecast Freeze後にのみ閲覧可

独立予測から遮断する今回レース用JRDB派生評価の例:

- current-entry IDM
- current total / 総合指数
- JRDB各種印
- jrdb_ratings / 情報系評価
- current distance / surface / heavy-track fitのJRDB結論値
- current training_index / condition_index / training_arrow / stable evaluation等のprocessed rating
- current pace indices / pace ranks
- JRDB forecast pace / forecast positions / forecast finish order
- current JRDB class / current-entry composite predictions

役割:

- RaceNoteとJRDBの一致 / 不一致を記録する
- disagreement研究に使う
- Gen0.2のRaceNote final probabilities / marksは変更しない

### C. Market view — RaceNote Forecast Freeze後にのみ閲覧可

- JRDB base odds / rank
- TRUE_FORWARDで別途取得するlive odds snapshot

役割:

- fair oddsとの比較
- value判定
- betting plan

市場情報を能力推定へ戻さない。

### D. Forbidden until result phase

- target finish
- target final odds / popularity
- payout
- target date以降のhistory
- target resultを含むweb/search/article

## 4. Factor model v0.2

### Core prediction factors

- F01: 過去パフォーマンス / 基礎能力
- F02: 今回条件適性
- F03: 独立展開・位置取り
- F04: 調教・状態のraw evidence
- F05: 近走内容 / trip quality
- F06: 長期履歴・条件実績
- F07: 騎手・厩舎
- F08: 血統
- F09: 枠・条件統計
- E01: EdgeDB performance signal

### Prediction factorから外すもの

旧F10事前市場情報はprediction factorから外す。

次を別namespaceとする。

- C01: JRDB consensus — forecast後の比較専用
- M01: market price — value/betting専用
- M02: EdgeDB value signal — value/betting専用
- T01: Training Edge — newspaper/consumer display専用

### Factor contribution record

各horse × factorに最低限:

- direction: POSITIVE / NEGATIVE / MIXED / NEUTRAL
- impact: STRONG / MEDIUM / WEAK / NOT_USED
- evidence_quality: GOOD / MIXED / POOR / MISSING
- evidence_ref
- short judgment

を保存する。

impactは加算スコアではない。最初のGen0.2で固定weightを導入しない。

## 5. Independent Pass

### 5.1 Race structure

現在JRDBの予測ペース・予測着順を見ず、過去の脚質・corner position・race contextからレース構造を組み立てる。

### 5.2 All-runner comparison

全馬について:

- strengths
- risks
- condition fit
- pace fit
- uncertainty
- nearby rivalsとの比較

を保存する。

### 5.3 Base probability estimate

印より先に確率を作る。

各馬について:

- `p_win_base`
- `p_top2_base`
- `p_top3_base`

を保存する。

整合条件:

- 0 <= p_win <= p_top2 <= p_top3 <= 1
- Σ p_win = 1
- 通常完走を前提とした確率系では Σ p_top2 ≈ 2、Σ p_top3 ≈ 3
- 取消・除外等の事前既知異常は別処理

初期Gen0.2の確率は未calibratedなmodel estimateとして明示する。精度を装わない。

確率は結果後にBrier / Log Loss / calibrationで評価し、将来versionで補正する。

### 5.4 Base snapshot

EdgeDBを見る前の:

- base rank
- base probabilities
- base reason

を保存し、EdgeDBの増分効果を後から評価可能にする。

## 6. EdgeDB integration

### 6.1 Role

EdgeDBはRaceNoteの「隠し味」。base ability modelを置き換えず、独立予測後の補正evidenceとする。

### 6.2 Allowed signal

RaceNote predictionで利用可:

- ACTIVE / applicableなEdge
- `performance_signal`
- family
- confidence / evidence status
- review_due等のcanonical caution metadata

predictionで利用不可:

- `value_signal` を能力/印へ流入させること
- target result由来情報
- target時点でas-of-safeでないEdge evidence

### 6.3 Family overlap

同一family内の複数Edgeを単純加算しない。

- family単位で重複をまとめる
- supporting / opposing signalを両方保持
- overlapを理由に票数を水増ししない

### 6.4 No legacy gate

以下をGen0.2へ復活させない。

- `edge_adjustment = 0.02 * tier`
- Good差 `<= 0.04`
- Edge polarityによる機械的軸昇格
- Top5だけへのEdge適用

Edgeは全馬に対してevidenceとして確認可能とする。

### 6.5 Audit fields

各馬に:

- base_rank
- final_rank
- p_win_base
- p_win_final
- p_top2_base / final
- p_top3_base / final
- matched_edge_ids
- edge_families
- performance_signal summary
- edge_adjustment_direction
- edge_adjustment_reason
- axis_changed_due_to_edge

を保存する。

## 7. RaceNote final forecast

EdgeDB performance evidenceを読んだ後、全馬probabilityを再調整し、整合条件を再確認する。

Primary output:

- `p_win_final`
- `p_top2_final`
- `p_top3_final`
- final rank
- ◎○▲△
- evidence uncertainty
- race shape

marksはpresentationであり、betting decisionの直接ruleではない。

◎は原則 `p_win_final` 最大馬とする。

○▲△はfinal rank / probability clusterを表現するが、馬券は「印だから買う」方式にしない。

## 8. Uncertainty

旧A/B/Cだけを確率と誤解しない。

Gen0.2では最低限:

- `evidence_uncertainty`: LOW / MEDIUM / HIGH
- `uncertainty_reasons`: coverage / newcomer / condition change / pace dependence / conflicting evidence等
- `probability_entropy`: final p_win分布からdeterministic計算

を分離する。

A/B/C表示を互換上残す場合も、的中確率を意味しない。

## 9. JRDB consensus comparison

RaceNote Forecast Freeze完了後にconsensus viewを開く。

保存候補:

- RaceNote rank
- JRDB current IDM rank
- JRDB total/composite rank
- JRDB mark
- JRDB forecast finish rank
- agreement / disagreement
- disagreement magnitude

この工程でRaceNote forecastを修正しない。

目的:

- RaceNoteがJRDBの再掲になっていないか監査
- 独立一致が強いケースを識別
- 独立不一致ケースの精度 / 妙味を研究

## 10. Market / fair odds / value

RaceNote Forecast Freeze後にmarket snapshotを取得する。

Win fair odds:

`fair_win_odds = 1 / p_win_final`

raw value:

`win_ev_raw = p_win_final * market_win_odds - 1`

PlaceはJRA払戻対象着順に応じ、事前place oddsが利用可能な場合に別計算する。

重要:

- final oddsをbet-plan inputへ使わない
- BLINDED_HISTORICALでは当時取得可能と証明できるpre-race marketだけを使用する
- TRUE_FORWARDではmarket snapshot timestamp / sourceを保存する
- calibration未確認の間は小さな正EVを過信せず、raw値を研究記録する

## 11. Betting construction

### 11.1 Separation

`prediction quality` と `betting policy` を別versionで持つ。

- prediction: `RaceNote-Forecast-Gen0.2`
- betting policy: `RaceNote-Bet-Gen0.2-exp1` 等

### 11.2 Win / Place

p_win / p_top2 / p_top3からfair priceを作り、marketとの比較を保存できる。

### 11.3 Quinella / Trio etc.

単馬のmarginal probabilityだけから正確な組合せ確率を捏造しない。

Gen0.2初期では:

- 組合せ候補は保存可能
- 的中率 / ROIは検証可能
- coherent joint-probability modelが未導入なら `EV_NOT_MODELED` と明示

将来Plackett-Luce等のjoint ranking modelを導入する場合は別version / calibration / forward testとする。

### 11.4 Bet plan freeze

market snapshot後・result取得前に:

- bet_plan_id
- betting_policy_version
- snapshot_at / odds source
- bet_type
- combination
- stake
- model probability where valid
- market odds where valid
- raw EV where valid
- rationale
- plan hash
- frozen_at

を固定する。

## 12. Training Edge

Training Edge v0.2はRaceNote予想へ入力しない。

- RaceNote p/rank/markを変えない
- EdgeDB補正と混ぜない
- betting policyの自動入力にもしない

新聞/PWAではRaceNote印 / JRDB印 / TE指数を並列表示する。

実購入時、人間がTEを参考に購入を変更してよい。その場合はRaceNote自動bet planとは別にactual purchase / human overlayとして記録し、RaceNote predictionの成績へ混ぜない。

## 13. New ledger data model proposal

既存Freeze recordは変更しない。Gen0.2用に以下を追加候補とする。

### `確率評価`

1 forecast × 1 horse:

- p_win_base / final
- p_top2_base / final
- p_top3_base / final
- base_rank / final_rank
- evidence uncertainty
- entropy component / notes

### `EdgeDB補正`

1 forecast × horse × Edge/family:

- edge snapshot identity / hash
- edge_id / family / status
- performance signal
- value signal (predictionには不使用)
- confidence / review_due / applicability
- used_in_prediction
- adjustment direction / reason

### `JRDB照合`

forecast freeze後にwrite:

- current IDM / total/composite / marks / forecast ranks
- RaceNoteとのrank差
- forecast mutation prohibited flag

### `市場Snapshot`

forecast freeze後・result前:

- snapshot timestamp
- source
- win/place odds and rank
- market identity/hash

### `馬券Plan`

bet-plan freeze:

- ticket / stake / odds / model probability / EV status
- bet plan hash

TEはRaceNote core ledgerに必須化しない。

## 14. Freeze / hash boundaries

最低3境界を分離する。

1. `base_snapshot_hash`
   - Independent Pass完了時
2. `prediction_hash`
   - EdgeDB performance反映後のRaceNote Forecast
3. `bet_plan_hash`
   - market snapshot後の馬券plan

JRDB consensus comparison / TE displayは `prediction_hash` を変更しない。

## 15. EdgeDB chronology / leakage guard

EdgeDBはhistorical research由来であるため、BLINDED_HISTORICALへ利用する場合はtarget raceがEdge発見・confidence・evidenceの生成に混入していないことを証明できなければならない。

最低限:

- edge catalog version / hashを固定
- evidence end date / source periodを記録
- target resultがEdge evidenceに含まれないことをguard

これを証明できないhistorical targetではEdgeDBをprediction inputにせず、`NOT_ASOF_SAFE` とする。

EdgeDBを含むGen0.2の最も強い検証は、現時点でcatalogをFreezeした後のTRUE_FORWARDである。

## 16. Evaluation

### Prediction primary

- multiclass Brier score
- winner log loss
- p_win calibration
- p_top2 / p_top3 calibration
- winner rank / reciprocal rank
- top1 / top3 / marked winner coverage
- ◎ win / top2 / top3 rate

### EdgeDB incremental

同一raceで base vs finalを比較:

- ΔBrier
- ΔLogLoss
- winner rank improved / worsened / unchanged
- axis changed and outcome
- p_win shift calibration
- family別 helpful / misleading

### JRDB comparison

- agreement rate
- rank correlation
- RaceNote独自1位 vs JRDB1位 cases
- 一致 / 不一致別performance

### Betting

- ticket count / stake / payout / ROI
- bet type別
- value band別
- market snapshot band別
- no-bet率

final oddsはpost-result evaluationにのみ利用できる。

### TE observational analysis

RaceNote mark × TE bandと結果は別分析可能だが、Gen0.2 RaceNote予測精度へ混ぜない。

## 17. Validation generation proposal

### Historical

新しいPRIMARY50 + RESERVE20を固定し、Gen0-G000の50Rは再利用しない。

ただしEdgeDBがas-of-safeでないhistorical targetでは、RaceNote Independentのみを正式評価し、EdgeDB込み結果をfresh blind claimにしない。

### TRUE_FORWARD

EdgeDB catalog/versionを事前Freezeしたうえで、実開催前に:

- Independent snapshot
- EdgeDB-adjusted forecast
- prediction freeze
- market snapshot
- bet plan freeze

まで完了し、開催後にのみresultを取得する。

EdgeDB込みGen0.2の正式性能確認はTRUE_FORWARDを重視する。

## 18. Acceptance / promotion criteria

Gen0.2の目的は「50RでROI100%を超えたら成功」のような単一条件にしない。

少なくとも:

- no result leakage
- JRDB current consensusがfinal marksを変更していない
- marketがp_winを変更していない
- EdgeDB incremental effectが監査可能
- probability calibrationを測定可能
- betting planがpredictionと別Freeze
- TEがRaceNote predictionへ混入していない

を必須とする。

性能判断は複数generation / TRUE_FORWARDを通して行う。

## 19. Implementation impact

実装時に新規/改修が必要な候補:

- partitioned prediction input view / guard
- forecast schema v0.2
- factor set v0.2
- base snapshot + final probability validation
- EdgeDB snapshot/join contract
- ledger v0.2 additional tabs/columns
- market snapshot contract
- bet-plan schema / freeze / hash
- post-result probability / betting evaluation
- newspaper consumer: RaceNote mark / JRDB mark / TE display separation

現行Gen0.1資産はimmutable historical recordとして維持する。
