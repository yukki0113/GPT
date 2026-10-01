# RaceReviewDB 展開逆行（Pace Opposition）研究設計 v0.1

Status: RESEARCH_DESIGN_READY  
Date: 2026-10-01  
Repository: yukki0113/GPT  
Component: RaceReviewDB / Next-Watch

## 1. 目的

RaceReviewDB の Next-Watch 研究において、従来の POSITION_RECOVERY
（レース中に通過順位を押し上げた）とは別に、

- 厳しい前傾ペースを前方で受けた
- 後傾・スローペースで後方に置かれた

という「展開そのものに対する不利」を、再現可能な数値特徴として研究する。

狙いは「動いた馬」を評価することではなく、

> 不利な展開位置にいたにもかかわらず、着順以上の内容を残した馬

を抽出できるか検証することである。

この研究は現行 HV01-HV13 / S/A ルールを直ちに変更しない。
まず独立した研究特徴として評価し、Discovery / Historical OOS / forward validation
を経てから昇格を判断する。

## 2. 現行RRDBで利用可能な材料

### レース単位

fact_race_context / fact_race_review には以下が存在する。

- first3f_reference_sec
- last3f_reference_sec
- pace_balance_sec
  - 定義: last3f - first3f
  - 正が大きいほど前半が速い（front-loaded）
- pace_balance_percentile
  - 同 venue/surface/distance を優先した過去レース分布に対する as-of percentile
- pace_shape
  - VERY_BACK_LOADED: percentile <= 10
  - BACK_LOADED: <= 30
  - BALANCED: 30-70
  - FRONT_LOADED: 70-90
  - VERY_FRONT_LOADED: >= 90
- pace_sample_count
- pace_scope_level

### 馬単位

fact_horse_performance には以下が存在する。

- corner1_frontness
- corner2_frontness
- corner3_frontness
- corner4_frontness
- early_position_gain
- middle_position_gain
- late_position_gain
- overall_position_gain
- last3f_speed_percentile
- closing_gain_sec
- performance_signal
  - -horse_adjusted_delta_per_1000m
  - 高いほどタイム内容が良い
- winner_gap_sec
- finish
- race_running_style_code
- JRDB trouble fields

## 3. POSITION_RECOVERYとの分離

現行 HV07 の POSITION_RECOVERY は、

- 通過順位が前へ動いた
- かつ上がり条件を満たした

という「レース内の位置変化」を主に見る。

これは展開逆行とは別概念とする。

例:

4角12番手 -> 6着

でも、

- ハイペースで前崩れなら差し有利だった可能性がある
- 超スロー前残りなら強い逆風を受けていた可能性がある

したがって position_gain 単独を「位置取り不利」とは呼ばない。

今後は名称も分離する。

- POSITION_RECOVERY = 通過順位の押し上げ
- PACE_OPPOSITION = ペースと位置取りの不整合による展開逆風

## 4. 研究する2つの主要仮説

### PO-F: 前傾を前受けした馬

仮説:

> 前傾度が高いレースで前方に位置しながら、
> タイム内容や着順を維持した馬は、
> 見た目の着順以上に評価できる。

Exposure（不利を受けた度合い）候補:

- pace_balance_percentile
- pace_shape
- corner1_frontness / corner2_frontness / corner4_frontness

Outcome-quality（その不利下で残した内容）候補:

- performance_signal
- finish
- winner_gap_sec
- late_position_gain
- last3f_speed_percentile

### PO-R: 後傾・スローで後方に置かれた馬

仮説:

> 後傾度が高く前が止まりにくいレースで後方に位置しながら、
> 上がりやタイム内容を残した馬は、
> 着順以上に評価できる。

Exposure候補:

- low pace_balance_percentile
- BACK_LOADED / VERY_BACK_LOADED
- low corner4_frontness

Outcome-quality候補:

- last3f_speed_percentile
- closing_gain_sec
- performance_signal
- winner_gap_sec
- finish

## 5. 最初に作る閾値なし研究特徴

閾値を先に最適化しない。

### 5.1 前傾逆風 exposure

front_pace_strength:
- pace_balance_percentile / 100

front_position_strength:
- corner4_frontness
- 補助として corner1_frontness / corner2_frontness

front_pace_opposition_raw:
- front_pace_strength * corner4_frontness

これは「前傾ほど強く、前にいるほど高い」連続値。

### 5.2 後傾逆風 exposure

back_pace_strength:
- (100 - pace_balance_percentile) / 100

rear_position_strength:
- 1 - corner4_frontness

rear_pace_opposition_raw:
- back_pace_strength * rear_position_strength

これは「後傾ほど強く、後ろにいるほど高い」連続値。

### 5.3 Exposure と Performance は混ぜずに保持

重要:

最初から

exposure × performance_signal

のような単一スコアに潰さない。

まず別列で保持する。

- front_pace_opposition_raw
- rear_pace_opposition_raw
- performance_signal
- last3f_speed_percentile
- closing_gain_sec

理由:

「展開逆風そのものに予測力があるのか」
「逆風＋好内容で初めて予測力が出るのか」
を分離して検証するため。

## 6. 安定bucketによる一次スクリーニング

Discoveryでは arbitrary threshold search をしない。

### pace percentile

- 0-10
- 10-30
- 30-70
- 70-90
- 90-100

### corner4_frontness

- 0.00-0.20
- 0.20-0.40
- 0.40-0.60
- 0.60-0.80
- 0.80-1.00

### performance_signal

まず既存と整合する quantile:

- bottom 50%
- 50-80%
- 80-90%
- top 10%

または既存HVとの比較用に top20 / top10 を併記。

### last3f

- < 50
- 50-80
- 80-90
- >= 90

## 7. 最初に検証する解釈可能な組み合わせ

### PO-F1

FRONT_LOADED以上
+
corner4_frontness 上位帯

目的:
純粋な「前傾を前受け」の exposure 効果。

### PO-F2

PO-F1
+
performance_signal 上位20%

目的:
前傾を前受けしながらタイム内容も良かった馬。

### PO-F3

VERY_FRONT_LOADED
+
corner4_frontness >= 0.8
+
performance_signal 上位20%

高逆風・高内容の狭い subtype。
Discovery N が小さければ昇格禁止。

### PO-R1

BACK_LOADED以下
+
corner4_frontness 下位帯

目的:
純粋な「後傾で後方」の exposure 効果。

### PO-R2

PO-R1
+
last3f_speed_percentile >= 80

目的:
前残り型の流れを後方から伸びた馬。

### PO-R3

PO-R1
+
performance_signal 上位20%

目的:
後傾で位置取り不利でも全体タイム内容が良かった馬。

### PO-R4

PO-R1
+
last3f_speed_percentile >= 90
+
closing_gain_sec > 0

目的:
単に上がり順位が高いだけでなく、
実際に終盤で先頭との差を縮めた馬。

## 8. 「残した」「差した」の評価

単純な最終着順だけに依存しない。

### 前傾前受け

候補指標:

- performance_signal
- winner_gap_sec
- corner4_frontness -> finish の late_position_gain
- finish band

「前で受けて4着」のような結果だけでなく、
9着でもタイム内容が良いケースを残す。

### 後傾後方

候補指標:

- last3f_speed_percentile
- closing_gain_sec
- performance_signal
- winner_gap_sec

上がり順位だけでは
「ただ後ろで脚を余した馬」を過大評価する可能性があるため、
closing_gain_sec と performance_signal を併用して検証する。

## 9. トラックバイアスとの分離

PACE_OPPOSITION はまずレース内のペース×位置取りを扱う。

別研究軸として DAY_TRACK_OPPOSITION を持つ。

例:

- 当日「前有利」の傾向に対して後方から好走
- 当日「外有利」に対して内を通って好走
- 当日「差し有利」に対して前受けして好走

RaceReviewDB には fact_track_bias の基礎が存在するが、
同一レースの馬自身がその日のbias推定に寄与すると循環評価になる。

研究用 day-bias feature は、

- source race を除外した leave-one-race-out
  または
- source race以前だけを使う as-of-day

で作る。

Next-Watchはレース後に使うため同日全レース利用自体は可能だが、
因果的な「逆風」研究では source race 自己寄与を避ける。

## 10. 必須リーク対策

target next-start outcome は特徴量生成に使わない。

source race の PACE_OPPOSITION は source race 時点で確定する情報のみ使用。

pace_balance_percentile は既存RRDBと同じく、
source race date より前の historical pace peers を使う。

自身過去比較を追加する場合も source race より前のみ。

day track bias を使う場合は source race 自己寄与を除く。

## 11. 評価指標

Phase A: 能力予測

- N
- next top3
- next top5
- average / median next finish
- matched baseline lift
- finish improvement

baselineは最低でも:

- source finish band
- turf/dirt
- distance category
- class group

Phase B: 市場価値

- next popularity
- next win odds
- next place hit
- next place payout
- 100円均等 place ROI
- odds band別 ROI
- 高配当的中数

能力予測と市場価値は分離する。

## 12. 比較対象

必ず以下と比較する。

1. 全eligible
2. finish-matched baseline
3. performance_signal単独
4. last3f単独
5. POSITION_RECOVERY
6. PACE_OPPOSITION単独
7. performance_signal + PACE_OPPOSITION
8. last3f + PACE_OPPOSITION

これにより、

「展開逆行が独立した情報を足しているのか」
「結局performance_signalだけで十分なのか」

を判定する。

## 13. 研究順序

### Stage 1

9月全出走馬ベース研究台帳を作る。

1行 = target entrant + immediately previous completed JRA start。

必要列:

- target identifiers
- source identifiers
- source finish
- performance_signal
- pace_balance_percentile
- pace_shape
- corner1-4_frontness
- position_gain fields
- last3f_speed_percentile
- closing_gain_sec
- winner_gap_sec
- next/target result and market fields

### Stage 2

単一signal screening:

- performance_signal
- pace opposition exposure
- last3f
- position recovery

### Stage 3

解釈可能な2条件 combination。

### Stage 4

必要な場合のみ限定的3条件。

### Stage 5

2024-2025 Historical OOSで閾値固定検証。

## 14. 成功判定

PACE_OPPOSITIONを新しいHV系統へ昇格する条件:

- 単なる source finish baseline を上回る
- performance_signal / last3f 単独に対して追加情報がある
- DiscoveryだけでなくHistorical OOSでも方向が維持
- 十分なN
- 一部の高配当1頭だけに依存しないことを確認
- 人間が説明可能な条件

満たさない場合は研究特徴のまま保持し、
S/Aへ組み込まない。

## 15. 今回の設計上の重要判断

POSITION_RECOVERY を「位置取り不利」と呼ばない。

今後は:

- POSITION_RECOVERY:
  レース中に順位を押し上げた事実

- PACE_OPPOSITION_FRONT:
  前傾ペースを前方で受けた展開逆風

- PACE_OPPOSITION_REAR:
  後傾ペースで後方に置かれた展開逆風

- DAY_TRACK_OPPOSITION:
  当日コース傾向に逆らった走り

を別特徴として管理する。

特に PACE_OPPOSITION は
「不利を受けた exposure」と
「その中で示した performance」を分離保持する。
