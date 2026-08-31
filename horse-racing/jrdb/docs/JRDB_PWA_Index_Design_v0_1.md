# JRDB PWA 独自指数設計 v0.1

## 1. 目的

JRDB 2010-2025 の長期履歴を用いて、PWA 競馬新聞向けの独自指数を構築する。

本設計では、競走予測を次の3層へ分離する。

1. **Ability** — 今回条件で平常ならどの程度の能力を発揮できるか
2. **Edge** — Ability に対して今回どちらへ上振れ / 下振れしそうか
3. **Value** — 独自予測と市場オッズの差。Ability / Edge には人気・オッズを入れない

Value は後段とし、v0 ではまず競走予測としての Ability / Edge を完成させる。

---

## 2. 基本原則

### 2.1 JRDB の使い方

JRDB はデータ供給源として最大限利用するが、JRDB 独自判断は無検証で採用しない。

- Raw / 観測値: 積極利用
- 標準化済み・前処理済み指標: 独自再計算との比較対象
- 判断系指標: 独自 Core 完成後の Addition Test
- 完成予想系指標: 原則 benchmark

### 2.2 時系列厳守

全特徴量は `as_of_exclusive = target_date` を原則とし、対象レース結果・対象日以降の情報を予測入力へ混入させない。

血統統計、騎手・厩舎統計、ExpectedTime、適性、調教履歴等もすべて対象日時点までで構築する。

### 2.3 Published snapshot

PWA 新聞に掲載する Ability / Edge は新聞出力時点で一度確定する。

保存対象:

- `published_ability_raw`
- `published_ability_score`
- `published_ability_rank`
- `published_edge_raw`
- `published_edge_rank`
- `published_forecast_raw`
- `confidence_score`
- `confidence_band`
- `published_at`
- `ability_model_version`
- `edge_model_version`
- `source_snapshot`

馬体重・当日馬場傾向等の当日情報による補正は published 値を書き換えず、別レイヤーで保持する。

---

## 3. 検証期間

2010-2025 を同一用途では使わない。

- 2010-2012: warm-up / 基礎統計形成
- 2013-2023: development walk-forward
- 2024-2025: locked holdout

Development では年単位 walk-forward を基本とする。

例:

```text
2013 test <- 2010-2012
2014 test <- 2010-2013
...
2023 test <- 2010-2022
```

2024-2025 を見た後に仕様変更した場合、その変更は次世代モデルとして扱い、2024-2025 を再び未見 holdout とはみなさない。

---

## 4. 検証データ単位

基本粒度は **1行 = 1レース × 1頭**。

主キー相当:

```text
race_date
race_key
horse_no
blood_registration_no
```

論理層:

1. Race / Runner Fact
2. Race Baseline
3. Run Performance
4. Pre-race Feature Snapshot
5. Target / Evaluation

取消・除外・競走中止等は消去せず `calculation_status` 等で別管理する。

---

## 5. RunPerf

### 5.1 定義

RunPerf は「その1走で実際に発揮した競走能力」を表す教師値。

前走不利や出遅れによる「もっと走れたはず」は RunPerf に最初から補正せず、Edge の Hidden Performance へ分離する。

### 5.2 ExpectedTime

v0 の基本形:

```text
ExpectedTime = CourseBaseTime + ClassAdjustment
```

- CourseBaseTime: 競馬場 × 芝ダ × 距離の race representative time
- RaceRepresentativeTime: 上位3頭走破時計中央値を初期候補
- ClassAdjustment: CourseBaseTime との差をクラス別に推定
- rolling 2 / 3 / 5年、expanding を development で比較

### 5.3 DayTrackBias

```text
RaceBias = RaceRepresentativeTime - ExpectedTime
DayTrackBias = shrink(median(RaceBias | date, venue, surface))
AdjustedTime = ActualTime - DayTrackBias
TimeResidual = ExpectedTime - AdjustedTime
```

同日の過去走 RunPerf を将来レースの履歴として評価する目的では、開催終了後に確定した当日 bias を使用可とする。

### 5.4 RunPerf 比較モデル

- B0: 着順 percentile
- B1: 着差系
- T0: TimeResidual
- T1: TimeResidual + margin
- T2: TimeResidual + weight
- T3: TimeResidual + margin + weight
- J0: JRDB 素点 benchmark
- J1: JRDB IDM benchmark

次走 RunPerf、次走順位、勝率 / 複勝率、レース内順位相関等で比較し正式版を選ぶ。

---

## 6. Ability

### 6.1 定義

Ability は「今回条件で平常なら期待される RunPerf」。

```text
Ability = f(historical RunPerf, aptitude, jockey, weight, ...)
```

クラスは RunPerf の ExpectedTime で正規化するため、Ability へクラス点を二重加算しない。

### 6.2 Ability v0 Core

- `recent_performance`
- `peak_performance`
- `peak_gap`
- `performance_stability`
- `surface_fit`
- `distance_fit`
- `course_fit`
- `going_fit`
- `jockey_general_effect`
- `jockey_surface_effect`
- `weight_relative`
- 各 feature の sample count / effective sample size / missing flag

初期仕様:

- recent / peak: 直近5走を中心
- recent decay: 0.70 / 0.80 / 0.90 / 1.00 比較
- aptitude history: 最大12走候補
- 適性は少数標本縮約
- 未経験を 0 評価としない。NULL + missing flag を保持

### 6.3 比較モデル

- A0: 説明可能な手組みモデル
- A1: Ridge / Elastic Net
- A2: 非線形 challenger

小さな性能差しかない場合は単純モデルを優先する。

---

## 7. 血統 Prior

血統は固定加点ではなく **本人実績が少ないほど重要な Prior** とする。

既走馬では履歴増加とともに本人 RunPerf へ主役を譲る。

主要候補:

- sire ability / debut ability
- damsire ability / debut ability
- sire surface / distance fit
- damsire surface / distance fit
- sire line / damsire line
- dam offspring performance（識別精度確認後）
- sire × damsire line interaction（強縮約）

血統統計は time-aware + leave-one-horse-out で作成する。

---

## 8. 新馬 Ability

新馬も Ability を算出し、既走馬と同じ RunPerf 尺度へ変換する。

```text
DebutAbility = f(Pedigree, Workout, Jockey, Trainer, ...)
```

新馬は血統だけでなく、追切・仕上・騎手・厩舎等の事前情報を積極利用する。

Core 候補:

- sire / damsire debut RunPerf
- sire / damsire 条件適性
- sire / damsire line prior
- debut workout index / finish index
- effort efficiency
- pair workout strength
- training volume / pattern / course type
- jockey debut effect
- trainer debut effect

履歴ゼロでも数値は出すが Confidence を低く表示する。

---

## 9. 調教

詳細定義は `JRDB_Training_Index_Definitions.md` を正本参照とする。

調教は4層へ分離する。

1. T-Raw: CHA 本追切の時計・強さ・コース・併せ等
2. T-Prepared: JRDB 追切指数等の標準化済み素材
3. T-Preparation: 仕上指数・調教量・調教タイプ
4. T-Human Judgment: 調教指数・調教矢印等の専門家判断

既走馬では絶対水準より自己比変化を重視する。

```text
workout_delta_prev
workout_delta_baseline
finish_index_delta
training_volume_change
training_pattern_change
```

新馬では自己履歴がないため cohort 内絶対水準を Ability に使う。

---

## 10. 騎手・厩舎

単純勝率ではなく、馬質を除いた residual を基本とする。

```text
JockeyEffect = ActualRunPerf - ExpectedRunPerfWithoutJockey
TrainerEffect = ActualRunPerf - ExpectedRunPerfWithoutTrainer
```

候補:

- jockey general / surface / course
- trainer general / debut / first-up / second-up
- jockey × running style
- jockey × trainer pair
- jockey × horse pair（低優先）

騎手×厩舎の「黄金タッグ」は、騎手効果・厩舎効果を差し引いた追加 residual として検証し、強く shrink する。

---

## 11. Edge

### 11.1 定義

```text
Residual = ActualRunPerf - PublishedAbility
Edge = E[Residual | current changes / condition / training / pace / hidden performance]
```

Edge は人気・オッズから独立させる。

内部値は予測 residual の RunPerf 点として保持し、`+4.2` / `-3.1` のような符号付き値を基本とする。

### 11.2 Edge v0 Core

#### 条件変化
- `distance_fit_gain`
- `surface_fit_gain`
- `course_fit_gain`
- `going_fit_gain`
- `class_change`
- `class_gap`

#### 休養・状態
- `rest_days`
- `rest_deviation`
- `stable_cycle`

#### 調教
- `workout_delta_prev`
- `workout_delta_baseline`
- `finish_index_delta`
- `training_volume_change`
- `training_pattern`

#### 展開
- `early_position_propensity`
- `race_pace_pressure`
- `leader_gap`
- `front_runner_count`
- `pace_fit`

#### Hidden Performance
- `finish_runperf_gap`
- `margin_residual`
- `late_strength_residual`
- `early_load`
- `start_position_shock`

#### その他
- `jockey_change_delta`
- `weight_delta`
- `bodyweight_delta`

### 11.3 Edge 比較モデル

- E0: Ridge + 明示交互作用
- E1: GAM 相当の滑らかな非線形
- E2: Gradient Boosting challenger

Ability 帯固定後でも Edge 高低で実績差が出ることを必須評価とする。

---

## 12. Hidden Performance

「前走不利だから買い」ではなく、前走着順と実走内容の乖離として測る。

主要候補:

- RunPerf順位 vs 着順 percentile gap
- 着順に対する僅差度
- 上がり / 位置取り residual
- high pace 下での先行負荷
- 普段の位置取りに対する start shock

JRDB SED の出遅・位置取り・不利・前中後不利は独自 Core へ追加した際の incremental value を検証する。

---

## 13. 展開 / Pace Fit

脚質を4分類だけで固定せず、過去走位置から連続値を作る。

- early position propensity
- mid position propensity
- late performance
- front / last 3F relative

今回全馬から:

- race pace pressure
- leader gap
- front runner count

を算出し、`horse style × race pace pressure` から PaceFit を学習する。

JRDB 脚質・予想テン・予想位置・展開予想は独自 PaceFit 完成後の Addition Test。

---

## 14. 身体・制度系ファクタ

馬体重・斤量・年齢・性別は主力単独ファクタではなく、条件付き補助層を基本とする。

Core 寄り:

- `weight_relative`
- `weight_delta`
- `bodyweight_delta`

候補:

- age curve / age in months
- sex × season
- weight × handicap race
- weight × distance
- bodyweight × surface
- bodyweight delta × rest days

「夏は牝馬」「ハンデ戦軽斤量」等は俗説として固定採用せず、development 内で residual 効果を検証する。

---

## 15. JRDB Addition Layer

独自 Core 完成後、JRDB 加工・判断項目を1つずつ追加する。

候補:

- 上昇度
- 調教矢印 / 調教指数
- 追切指数 / 仕上指数
- 調教量 / 調教タイプ
- 厩舎評価
- 距離適性
- 重適性
- 出遅 / 位置取り / 不利
- JRDB 展開予想

判定は常に:

```text
Own Core
vs
Own Core + JRDB feature
```

追加性能がなければ採用しない。

---

## 16. Confidence

Ability の強さと不確実性を分離する。

候補材料:

- career count
- recent run count
- aptitude effective sample size
- pedigree sample size
- workout history count
- model prediction uncertainty

新馬でも Ability は出すが、履歴馬より Confidence を低くする。

---

## 17. 表示スケール

Ability:

- 内部: expected RunPerf
- 表示: 平均50 / SD10相当を初期候補
- 絶対点 + レース内順位 + top gap を保持

Edge:

- 内部 / 表示とも符号付き residual 点を第一候補

Forecast:

```text
PerformanceForecast = Ability + Edge
```

総合値は内部保持するが、PWA 初期表示では Ability / Edge の意味を潰さないよう主役にしすぎない。

---

## 18. Feature 採否ルール

Feature status:

- CANDIDATE
- PROVISIONAL
- CORE
- PLUS
- REJECT

主な判定:

- 単体効果より incremental value を優先
- p値だけでなく effect size を見る
- 年別方向一貫性
- 芝ダ / 距離 / class 等の頑健性
- Ability は RunPerf予測改善
- Edge は Ability帯固定後の residual / 好走率改善
- 2024-2025 locked holdout で再現
- 微小改善なら単純モデルを選択

回収率は Ability / Edge の feature 採用主条件にしない。市場との比較は Value 層で扱う。

---

## 19. 実装順

### Phase A: 基礎データ
1. 2010-2025 longitudinal runner dataset
2. race context / historical links
3. UKC 血統
4. CHA / CYB 調教
5. availability / as-of 管理

### Phase B: RunPerf
6. ExpectedTime
7. DayTrackBias
8. B0-T3 / IDM benchmark
9. RunPerf正式決定

### Phase C: Ability
10. recent / peak / stability
11. aptitude
12. jockey / trainer
13. pedigree prior
14. A0 / A1 / A2比較

### Phase D: Edge
15. condition gain
16. rest
17. workout delta
18. pace fit
19. hidden performance
20. E0 / E1 / E2比較

### Phase E: 新馬
21. pedigree model
22. debut workout model
23. jockey / trainer debut effect
24. debut Ability / Edge

### Phase F: JRDB Addition
25. 各JRDB加工・判断値を個別追加検証

### Phase G: Holdout
26. 2024
27. 2025
28. v0 採否固定

---

## 20. 関連文書

- `JRDB_PWA_Index_Feature_Registry_v0_1.md`
- `JRDB_Training_Index_Definitions.md`
- `JRDB_PWA_Legacy_Feature_Inventory.md`
- `JRDB_PWA_Fact_Lite_v0_2_Plan.md`
- `整理版_JRDB_固定長データ定義` 相当の仕様資料
- `整理版_JRDB_マスタコード定義` 相当のコード資料

本設計は v0.1。係数・閾値・減衰率・縮約強度等は development walk-forward で選定し、設計思想とデータ駆動パラメータを分離する。
