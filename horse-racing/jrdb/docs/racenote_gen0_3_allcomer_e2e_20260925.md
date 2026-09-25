# RaceNote Gen0.3 オールカマー Blind E2E検証

Date: 2026-09-25  
Target: 2026-09-20 中山11R 第72回産経賞オールカマー  
Scope: BLIND_TO_FREEZE -> POST_FREEZE_REVIEW

## 1. 目的

初風ステークスE2Eで追加した historical position variability を利用した状態で、
2レース目のblind E2Eを行う。

結果・人気・当日結果系JRDBを開く前に以下を完了する。

```text
General Evidence
-> All-Runner Synthesis
-> Pairwise
-> Scenario Robustness
-> Forecast Gen0.3
-> Decision Trace
-> Freeze
-> Freeze Audit
```

優先順位は維持する。

```text
DATA / TRENDS > RACEREVIEW >= SIMPLE ABILITY
```

ただし本レースではhorse-history Data Trendが全馬INSUFFICIENTだったため、
欠損をnegative evidenceとして扱わず、RaceReviewを主軸、Abilityを補助とした。

## 2. Prepare

position variability修正後mainで再Prepare。

```text
Issue #1366
run_id = 36111401252
status = PASS
runner_count = 13
```

Race Structure:

```text
pace_pressure = HIGH
front_or_forward_tendency_count = 9
known_position_profile_count = 12
runner_count = 13
```

代表的なhistorical position:

```text
7 レガレイラ
tendency = MID
dominant_share = 0.6
distinct_band_count = 3
variability_status = MULTI_BAND

9 コスモキュランダ
tendency = FRONT
dominant_share = 0.8
distinct_band_count = 2
variability_status = MULTI_BAND

8 メイショウゲキリン
tendency = UNKNOWN
dominant_share = 0.4
distinct_band_count > 1
variability_status = MULTI_BAND
```

historical tendencyは今回位置の約束として扱わない。

## 3. Synthesis

```text
Issue #1370
run_id = 36111893720
status = PASS
```

Draft order:

```text
7,9,8,6,3,2,13,4,12,1,10,11,5
```

全12境界をHIGH priorityとしてPairwiseへ渡した。

## 4. Pairwise

初回Issue #1371はcontract version文字列誤りでvalidation前にFAIL。
retryで文字列のみ修正し、予想判断は変更していない。

```text
Issue #1372
run_id = 36112177670
status = PASS
comparison_count = 16
```

Final Pairwise order:

```text
7,9,8,6,2,3,13,4,12,1,10,11,5
```

変更:

```text
2 ワイドエンペラー 6 -> 5
3 リビアングラス    5 -> 6
```

3はAbilityで2を上回ったが、
2のREPEATED_ABOVE_CLASS_PERFORMANCE /
REPEATED_RESULT_UNDERRATES_TIME を
優先度の高いRaceReviewとして採用した。

## 5. Scenario Robustness

```text
Issue #1373
run_id = 36112388912
status = PASS
axis_horse_no = 7
axis_robustness = CONDITIONAL
risk_scenario_ids = [SLOW]
pairwise_recheck_recommended = false
```

Scenario order:

```text
SLOW
9,7,8,6,2,3,13,4,12,1,10,11,5

MEDIUM
7,9,8,6,2,3,13,4,12,1,10,11,5

FAST
7,8,9,6,2,3,13,4,12,1,10,11,5
```

position variabilityは順位生成器にしない。
近接上位境界のみScenarioで変更した。

## 6. Forecast / Freeze

```text
Issue #1377
run_id = 36112625660
status = PASS
forecast_id = 20260920_中山_11_Gen0-G002
prediction_hash = 84f958093fe969bf82f9bc27989ba5d84a91f6810737a2588169acd3c9257780
freeze_audit_status = PASS
```

Final forecast:

```text
7,9,8,6,2,3,13,4,12,1,10,11,5
```

Edge performanceはNO_MATCH。
Market / current JRDB consensus / Edge value / target resultはFreeze前に開いていない。

## 7. Post-Freeze Result

JRA official result:
https://www.jra.go.jp/datafile/seiseki/replay/2026/087.html

Actual order:

```text
8,1,4,7,2,6,13,10,12,3,9,5,11
```

上位:

```text
1着 8 メイショウゲキリン
2着 1 キャントウェイト
3着 4 ヴーレヴー
4着 7 レガレイラ
5着 2 ワイドエンペラー
6着 6 パンジャ
7着 13 ジューンテイク
```

Forecast vs actual:

| horse_no | forecast_rank | actual_rank |
|---:|---:|---:|
| 7 | 1 | 4 |
| 9 | 2 | 11 |
| 8 | 3 | 1 |
| 6 | 4 | 6 |
| 2 | 5 | 5 |
| 3 | 6 | 10 |
| 13 | 7 | 7 |
| 4 | 8 | 3 |
| 12 | 9 | 9 |
| 1 | 10 | 2 |
| 10 | 11 | 8 |
| 11 | 12 | 13 |
| 5 | 13 | 12 |

Metrics:

```text
rank MAE = 2.923
Spearman rank correlation ~= 0.412
Top3 overlap = 1 / 3
Top5 overlap = 3 / 5
exact-rank matches = 2,13,12
```

初風Sより順位相関は改善したが、
1・4を大きく過小評価し、9を大きく過大評価した。

## 8. Post-Freezeで見えた別の不足

公式結果は雨・芝重。
8メイショウゲキリンが1-1-1-1で逃げ切り、
1キャントウェイトが2着、
4ヴーレヴーが3着。

レース回顧では1000m通過62.4秒。
歴史的位置取り由来Race StructureのHIGH pressureだけでは、
実際の当日レース条件を十分に表現できなかった。

一方、blind source bundleを再監査すると、

- prior runsには track_condition / weather が存在
- target race objectには weather / track_condition が存在しない
- target result ZEDからなら取得可能だがpre-Freezeでは使用禁止

であった。

従って、結果に合わせて脚質ルールを修正するのではなく、
独立pre-result race-day factsの取得経路が不足していると判断する。

## 9. Race-day Facts Contract

General Evidenceへ以下のoptional contractを追加した。

```text
race_data_context.race_day_facts
  status
  source_kind
  as_of
  weather
  track_condition
  policy
```

AVAILABLE条件:

```text
race.race_day_facts is object
AND result_independent == true
AND source_kind is present
AND weather or track_condition is present
```

それ以外はUNAVAILABLE。

policy:

```text
result_independent_required = true
may_auto_rank = false
missing_is_not_negative_evidence = true
```

これにより結果系ZED等からの事後情報を、
race-day factとして誤ってpre-Freeze利用する経路を作らない。

Commits:

```text
25f235b6a33749eba4cb047208a29f7f7e4fb147
  RaceNote: add pre-result race-day facts contract

0136112177fdf692ccf5385a20efabbb39d33b21
  Test RaceNote pre-result race-day facts contract

2c1d368836cd8fb5693c46353a5a147d861e2101
  Align RaceNote general evidence schema with new contexts
```

同時にposition variability追加後のschema driftも修正した。

最新main smoke:

```text
Issue #1379
run_id = 36113063008
status = PASS
head_sha = 2c1d368836cd8fb5693c46353a5a147d861e2101
runner_count = 13
```

現ソースにはtarget race-day factsが無いため、
このオールカマーを再Prepareしてもrace_day_facts.statusはUNAVAILABLEになる。
これは期待動作。

## 10. 判断

採用:

- position variabilityをcontextとして利用
- race-day factsの独立pre-result contract
- 結果由来race-day factsのfail-closed
- 現行Evidence優先順位とFirewallを維持

未採用:

- オールカマー結果だけを根拠にFRONT馬を上げるルール
- 8の逃げ切りを根拠にHIGH pressure判定の閾値を変更
- 1・4の好走に合わせたRaceReview係数の後付け
- target result ZEDから馬場状態をpre-Freezeへ逆流
- heavy_track_fitを対象馬場不明のまま順位根拠に利用

次段:

1. 独立pre-result sourceから weather / track_condition を取得するacquisition経路
2. race-day factsがAVAILABLEなblind raceを複数蓄積
3. track conditionを順位へ直結させず、まずScenario / Decision Trace contextとして検証
4. 十分な再現性が出た段階でData Trend laneへの昇格を検討

