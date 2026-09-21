# RaceLift（RL）指数 研究・運用 引き継ぎ

更新日: 2026-09-22

## 0. この文書の目的

中央競馬予想プロジェクトにおける、JRDB由来の「今回どれだけ平常能力以上に走れそうか」を測る研究について、現時点の到達点・確定事項・凍結事項・未着手事項・次作業を、新しいスレッドへ引き継ぐための文書。

この文書は、旧称 Training Edge を含む研究全体を **RaceLift（RL）指数** の体系として整理した最新の引き継ぎ用正本候補である。

---

## 1. 研究コンセプト

RaceNote 等の Ability 系は、

> この馬は元々どれくらい強いか

を見る。

RaceLift（RL）は、

> この馬が今回、平常能力よりどれだけ上振れ／下振れしそうか

を見る。

市場情報（オッズ・人気）は RL には入れない。  
市場情報は後段の Value 判定でのみ利用する。

最終的な構想:

```text
Ability
  = その馬の地力

RaceLift
  = 今回、その地力からどれだけ上振れ／下振れしそうか
```

RL は複数の独立した切り口を研究し、各サブ指数を個別に検証した後に統合する。

---

## 2. RL の名称体系

全体名:

- **RL = RaceLift 指数**

現在の第一軸:

- **RL-T = Training Lift**
- 旧称: Training Edge v0.2
- 意味: 追い切り・調整過程から見た「今回の上振れ度」

第二軸として新規研究開始予定:

- **RL-R = Rebound Lift**
- 意味: 前走不利等で能力を出し切れなかった馬が、今回平常値へ戻る／上振れる余地

将来候補:

- **RL-S = Setup Lift**
  - 今回の展開適合
- **RL-C = Campaign Lift**
  - ローテ・休養・使われ方による走り頃
- **RL-F = Fit Lift**
  - 距離・コース・馬場・斤量等の今回条件への適合

体系イメージ:

```text
RL指数
├─ RL-T  Training Lift
│        今回の仕上がり
│
├─ RL-R  Rebound Lift
│        前走不利からの反発
│
├─ RL-S  Setup Lift
│        今回の展開適合
│
├─ RL-C  Campaign Lift
│        ローテ・使い頃
│
└─ RL-F  Fit Lift
         今回条件への適合
```

---

## 3. RL-T（Training Lift）の現在地

### 3.1 科学的定義

ターゲット:

```text
PerformanceDelta
= current Official RunPerf
- median(strictly-prior same-horse Official RunPerf)
```

意味:

- 今回の走りが、その馬自身の過去平常値よりどれだけ上／下だったか

RL-T は「能力そのもの」ではなく、「今回の調整・仕上がりによる増分」を測る。

### 3.2 Frozen v0.2

Training Edge v0.2 として科学仕様は凍結済み。

Frozenモデルは:

- C: JRDB processed training baseline
- A: same-horse comparable workout vertical
- B: generic preparation/process context

を使用し、

```text
training_edge_raw = CAB_hat - C_hat
```

として算出する。

現在は概念上これを **RL-T raw** と読み替える。

重要:

- モデルを変更してはいない
- 表示名・概念名だけ RaceLift体系へ整理している
- v0.2科学仕様のfreezeはそのまま有効

### 3.3 RL-T の主な frozen input

C:

- kyi_training_score
- finish_index
- jrdb_final_segment_index
- jrdb_workout_index_cha
- kyi_training_arrow_code

A:

- final_self_pct

B:

- days_before_race
- workout_count
- previous_days_since_last_run
- gap_log_change
- return_after_63d_break
- return_after_120d_break
- pair_work_present
- 各種course-use flags
- rest_bucket
- previous_rest_bucket
- course_code
- effort_code
- chase_state_code
- rider_type_code
- furlong category
- pair系
- training_type/course/distance/focus/volume
- week_ago_course
- interaction categories

### 3.4 RL-T 表示

外部CSVの値は 0–100 percentile。

表示契約:

```text
date,venue_code,race_no,horse_no,training_edge_index
```

ファイル名:

```text
独自指数_YYYYMMDD.csv
```

将来的には表示名をRL-TまたはRL指数へ変更可能だが、既存コード・契約を壊さない形で行うこと。

現状の意味:

- 高いほど今回の調教・調整由来の上振れ方向
- 低いほど下振れ方向
- 空欄 = 悪い馬ではなく、算出条件不足による判定不能

raw zero は development percentile 約53.59付近。

---

## 4. RL-T の実績・証拠

### 4.1 Stage1b

same horse + same CHA course + same furlong の strictly-prior 比較。

2013–2023 dev:

- n = 214,833
- Spearman 約 0.030
- fastest20 - slowest20 mean +0.006291
- positive-rate差 +2.967pt
- 年別mean spread 11/11で正方向
- same-horse paired mean +0.004784
- classification: WEAK_BUT_REPRODUCIBLE

### 4.2 v0.1 holdout

2024–2025 one-shot holdout は消費済み。

Full model は processed-only より改善:

- Spearman +0.036488
- RMSE改善
- spread +0.015932
- positive spread +8.4532pt

### 4.3 v0.2 2026 OOT

2026-09-13までの結果を one-shot OOT として開封済み・消費済み。

Fit:

- 2013–2025

Test:

- 2026

test eligible:

- 15,276

C baseline:

- rho 0.1202404
- RMSE 0.0953097
- mean spread +0.03018
- positive spread +18.39pt

CAB:

- rho 0.1736779
- RMSE 0.0947102
- mean spread +0.04809
- positive spread +26.90pt

increment:

- rho +0.0534375
- RMSE -0.0005994
- spread +0.0179088
- positive +8.5079pt

raw RL-T:

- raw vs C residual rho 0.13236
- raw vs target rho 0.12863

結論:

```text
2026_OOT_STATUS = OPENED_AND_CONSUMED
FORWARD_EVIDENCE = POSITIVE
POST_OOT_RETUNING = PROHIBITED
```

2026を未開封holdoutとして再利用しない。

---

## 5. RL-T 日次運用

日次経路は実装済み。

概念上:

```text
Frozen model/runtime bundle
+ prior-day historical state
+ today PACI
→ feature materialization
→ frozen RL-T scorer
→ CSV + audit
```

重要:

- target-day SED/resultはスコア時点で使わない
- target result required = false
- odds/popularity不使用
- scientific asset hash guard
- runtime fingerprint guard
- fail closed

### 5.1 0913 replay

2026-09-13 は retrospective operational validation として replay済み。

条件:

- PACI 0913あり
- SED 0913は scoring input から除外
- SEDは0912まで
- 0913 replay は live forward ではない
- 0913 replay は new OOT ではない

結果:

- 対象314頭
- 指数あり157
- 空欄157
- unique key 314/314
- CSV validation PASS

半分程度空欄なのは現行仕様どおり。

主因:

- prior Official RunPerf >= 3
- prior comparable workout >= 3
- final_self_pct nonmissing

の条件。

空欄は「悪い」ではなく「RL-Tでは判定不能」。

---

## 6. RL-T データ資産 / Parquet移行

対象資産:

```text
jrdb_training_research_2010_2023_development_lite_v0_1.zip
```

について、Parquet / DuckDB移行可否を監査済み。

結論:

```text
PARQUET_MIGRATION_TECHNICALLY_FEASIBLE = true
SQLITE_REQUIRED_FOR_LONG_TERM_ANALYTICAL_STORAGE = false
CURRENT_SOURCE_CODE_CHANGE_REQUIRED = true
RAW_COLLECTION_BLOCKER = false
IMMEDIATE_SQLITE_BUILDER_REMOVAL_REQUIRED = false
LEGACY_FROZEN_SQLITE_DELETE_RECOMMENDED = false
PARQUET_POC_RECOMMENDED = true
```

正本:

```text
horse-racing/jrdb/docs/移行判断_training_20260916.md
```

推奨:

- 既存SQLite builderは当面維持
- 完成SQLite → tools/data-storage → Parquet ZSTD
- consumerをDuckDB/Parquet化
- SQLite vs Parquet完全同値監査
- Frozen SQLite ZIPはhistorical evidenceとして保持

---

## 7. 第二軸 RL-R（Rebound Lift）設計

### 7.1 目的

前走に一過性の不利があり、本来の能力を発揮できなかった馬について、

> 今回、そのマイナス要因が消えることで平常能力へ戻る／上振れる余地

を測る。

単純な「前走負けた馬の巻き返し」ではなく、

> 同程度に前走走れなかった馬の中でも、不利が原因だった馬に追加の反発力があるか

を分離する。

### 7.2 ターゲット

RL-Tと統一する。

```text
PerformanceDelta
= current Official RunPerf
- median(strictly-prior same-horse Official RunPerf)
```

これにより将来RL-T / RL-Rを統合しやすくする。

### 7.3 基本モデル案

単純な不利有無→次走成績では、平均回帰を拾う危険がある。

そのため:

```text
R0 = 前走成績・前走PerformanceDelta等だけから予測する基準モデル

R1 = R0 + 前走不利情報

Rebound Lift raw
= R1_hat - R0_hat
```

とする。

これにより、

- 前走悪かったことによる通常のmean reversion
- 前走不利があったことによる追加のrebound

を分離する。

---

## 8. RL-R 候補材料

JRDB SED/ZED由来の前走情報を使用する想定。

主候補:

- 出遅
- 不利
- 前不利
- 中不利
- 後不利
- 位置取

補助候補:

- コース取り

原則RL-Rから外してRL-Sへ回す候補:

- レースペース
- 馬ペース

理由:

- RL-Rは偶発的・一過性的ロスに集中
- 展開適合はRL-Sとして独立研究する方が概念境界がきれい

### 8.1 接続経路

KYIには前走1～5の:

- result_key
- race_key

がある。

SED/ZEDは前走成績・不利情報を保持できる。

設計上は:

```text
current KYI
→ previous result key
→ previous SED/ZED
→ previous disadvantage fields
```

の接続を使う。

---

## 9. RL-R の重要な注意点

### 9.1 不利数値の意味を先に監査する

固定長定義上、各不利項目が数値フィールドであることは分かるが、

- 数値の方向
- 単位
- 0の意味
- 欠損の意味
- 大きいほど不利なのか
- 正負があるのか

を実データで確定してから使う。

したがって、最初から

```text
不利 + 前不利 + 中不利 + 後不利
```

のような合算はしない。

### 9.2 コース取りを自動で不利扱いしない

大外等はロスになり得るが、戦術の場合もある。

初期RL-Rは、まず明示的不利項目を中心にする。

### 9.3 Setupとの混同を避ける

ペース・脚質・展開予想・今回の位置取り適合はRL-Sへ分離する。

---

## 10. RL-R 研究ロードマップ

### Stage R0 — データ意味・分布監査

最初に実施する。

確認項目:

- KYI current → previous SED/ZED 接続率
- 対象年別接続率
- 不利各列の値域
- NULL率
- 0率
- 正負
- unique value
- percentile
- 年度別分布
- venue別差
- surface別差
- 相互相関
- 同一レース内分布
- 不利列と前走PerformanceDeltaの関係
- 不利列と次走PerformanceDeltaの粗関連

このStageでは採用・閾値最適化をしない。

### Stage R1 — 単独関連

各不利項目ごとに:

- 次走PerformanceDelta
- same-horse baselineとの差
- decile / bucket
- positive-rate
- Spearman
- 年度別安定性

を見る。

ただし単独関連だけで採用判断しない。

### Stage R2 — Mean Reversion制御

最重要。

前走PerformanceDeltaを同程度にそろえた中で、

- 不利あり
- 不利なし

の次走PerformanceDelta差を見る。

必要に応じて:

- previous PerformanceDelta bins
- previous finish percentile bins
- horse prior count
- race class/context

などを統制する。

### Stage R3 — R0 vs R1 モデル

```text
R0 = prior performance baseline
R1 = R0 + previous disadvantage features

RL-R raw = R1_hat - R0_hat
```

評価:

- Spearman vs target
- RMSE
- raw vs R0 residual Spearman
- top-bottom mean spread
- median spread
- positive-rate spread
- annual stability
- same-horse paired
- sample size / coverage

### Stage R4 — RL-Tとの独立性

Frozen RL-Tは変更しない。

確認:

- RL-T算出可能馬の中でRL-Rが追加情報を持つか
- RL-T high / low層でもRL-R効果が残るか
- RL-T + RL-Rでtarget説明力が増えるか
- correlationが高すぎないか

ここで「RL-RがRL-Tの別表現ではない」ことを確認する。

### Stage R5 — Freeze

RL-R仕様を凍結。

凍結対象:

- target
- eligibility
- feature list
- preprocessing
- model
- thresholds
- display calibration
- evaluation protocol

### Stage R6 — retrospective replication

2024–2026等を使用する場合は、

```text
RETROSPECTIVE_REPLICATION
```

として扱う。

2026はすでにプロジェクト上開封済みのため、fresh holdoutとは呼ばない。

結果を見てRL-R仕様を再調整しない。

### Stage R7 — prospective forward

Freeze後、未結果の開催から日次算出。

これを最終的なforward evidenceとする。

---

## 11. RL-R で最初に作るべきデータセット

暫定名:

```text
jrdb_rebound_research
```

最低限必要な1行単位:

```text
current race
+ current horse
+ current Official RunPerf
+ current PerformanceDelta

+ previous race key/result key
+ previous Official RunPerf
+ previous PerformanceDelta
+ previous finish percentile

+ previous:
    late_break / 出遅
    disadvantage / 不利
    front_disadvantage / 前不利
    middle_disadvantage / 中不利
    late_disadvantage / 後不利
    position_loss / 位置取
    course_path / コース取り

+ chronology / provenance
```

必須条件:

- current rowから未来情報を参照しない
- same-day leakageなし
- previousは必ずstrictly-prior
- market情報なし
- source member / record provenance保持

---

## 12. データ保存方針

プロジェクト全体がParquet/DuckDBへ移行中。

RL-Rの新規研究データセットは、可能なら最初から:

```text
Parquet ZSTD
+ DuckDB query
+ manifest/audit
```

を正本候補とする。

ただしsource materializationで既存SQLiteを使う必要がある場合は、一時中間物として許容する。

長期正本はParquet優先。

共通基盤:

```text
tools/data-storage
```

を利用し、JRDB専用の独自変換器を重複実装しない。

---

## 13. 現時点で未着手の作業

最優先:

1. RL-R Stage R0 を実データで実施
2. SED/ZED不利項目の実値監査
3. KYI→前走SED/ZED接続率監査
4. 不利各列のsemantic確認
5. RL-R research dataset schema設計
6. Parquet正本方針でmaterialization設計

その後:

7. Stage R1単独関連
8. Stage R2 mean-reversion制御
9. Stage R3モデル
10. RL-Tとの独立性検証
11. Freeze
12. retrospective replication
13. prospective forward

---

## 14. やってはいけないこと

- 2026を未開封holdoutとして扱わない
- RL-T v0.2を2026結果で再調整しない
- RL-R研究のためにRL-TのFrozen仕様を変更しない
- odds / popularity / payoutをRLへ入れない
- AbilityとRLを同一target/modelに混ぜない
- 不利数値の意味を未確認のまま合算しない
- SED target-day resultをpre-race predictorとして使わない
- RL-RとRL-Sを最初から混ぜない
- 既存Frozen evidenceを削除しない

---

## 15. 新スレッドで最初に行う作業

新スレッドの最初の依頼は以下でよい。

> RaceLift（RL）指数研究の引き継ぎとして、
> `horse-racing/jrdb/docs/RaceLift_RL_Research_Handoff_20260922.md`
> を確認してください。
>
> 次は RL-R（Rebound Lift）の Stage R0 から開始してください。
>
> まずコード実装やモデル作成には進まず、
> JRDBのKYI→前走SED/ZEDの接続構造と、
> 出遅・不利・前不利・中不利・後不利・位置取・コース取りの
> 実データ上の値域、欠損、年度安定性、接続率を監査してください。
>
> 数値意味が不明な項目は推測で意味付けせず、
> 原本定義・実データ・既存parserを突き合わせて確認してください。
>
> 監査結果を見てからRL-Rのfeature contractを凍結する方向で進めてください。

---

## 16. 関連正本

RL-T / Training Edge:

- `horse-racing/jrdb/docs/Training_Edge_v0_2_Freeze_20260915.md`
- `horse-racing/jrdb/docs/Training_Edge_v0_2_2026_OOT_Evidence_20260915.md`
- `horse-racing/jrdb/docs/Training_Edge_v0_2_Daily_Forward_Contract_20260915.md`
- `horse-racing/jrdb/docs/Training_Edge_v0_2_Daily_Forward_Implementation_20260915.md`
- `horse-racing/jrdb/docs/Training_Edge_v0_2_Work_Handoff_20260915.md`

Training Research:

- `horse-racing/jrdb/docs/Training_Research_Base_v0_1.md`
- `horse-racing/jrdb/docs/移行判断_training_20260916.md`

主要parser:

- `horse-racing/jrdb/src/jrdb_raw.py`

storage:

- `tools/data-storage/`

---

## 17. 現時点の要約

現在は、

> **RL-T（追い切り・調整由来の上振れ）を一つ目のRaceLiftとして実装・検証済み**

の段階。

次は、

> **RL-R（前走不利からの反発）を第二の独立したRaceLiftとして研究する**

段階。

RL-Rの最初の仕事はモデル作成ではなく、

> **JRDB不利データが何を意味し、どれだけ安定して取得でき、次走上振れ研究の入力として信用できるかを監査すること**

である。

ここを通過してから、mean reversionを制御したR0/R1差分モデルへ進む。
