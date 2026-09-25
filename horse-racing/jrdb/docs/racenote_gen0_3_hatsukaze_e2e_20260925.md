# RaceNote Gen0.3 初風ステークス 実データE2E検証

Date: 2026-09-25  
Target: 2026-09-13 中山10R 初風ステークス  
Scope: POST_FREEZE_ONLY

## 1. 目的

RaceNote Gen0.3 の初回実データE2Eとして、以下を結果非参照のまま完了した後、
初めて実績を開いて設計上の違和感を確認した。

```text
General Evidence
-> All-Runner Synthesis
-> Pairwise
-> Scenario Robustness
-> Forecast Gen0.3
-> Decision Trace
-> Freeze
-> Freeze Audit
-> Post-Freeze Result Review
```

予想方針は以下を維持する。

```text
DATA / TRENDS > RACEREVIEW >= SIMPLE ABILITY
```

## 2. Freeze完了

Forecast ID:

```text
20260913_中山_10_Gen0-G001
```

Final order:

```text
1,4,10,3,8,2,9,5,6,7
```

Scenario:

```text
axis_horse_no = 1
axis_robustness = CONDITIONAL
risk_scenario_ids = [SLOW]
pairwise_recheck_recommended = false
```

Freeze:

```text
prediction_hash = c14daef2425c930059661db2592e0aaa06c959726f97e1deed43e6dbd585cc30
freeze_audit_status = PASS
run_id = 36110447876
```

## 3. Post-Freeze実績

実着順:

```text
2,8,9,6,10,4,5,3,7,1
```

上位3頭:

```text
1着 2 ドンレパルス
2着 8 ワンダラー
3着 9 アシャカトベ
```

実戦はHIGH pace。
2番ドンレパルスは過去位置取りprofileでは FRONT tendency だったが、
本番では7-6から差し切った。

予想順位と実着順:

| horse_no | forecast_rank | actual_rank |
|---:|---:|---:|
| 1 | 1 | 10 |
| 4 | 2 | 6 |
| 10 | 3 | 5 |
| 3 | 4 | 8 |
| 8 | 5 | 2 |
| 2 | 6 | 1 |
| 9 | 7 | 3 |
| 5 | 8 | 7 |
| 6 | 9 | 4 |
| 7 | 10 | 9 |

初回E2Eとして予想精度は不十分。
ただし、結果に合わせた順位ルール・係数調整は行わない。

## 4. 発見した設計上の違和感

Race Structure v0.1 は過去走corner historyから、

```text
FRONT
FORWARD
MID
BACK
UNKNOWN
```

の tendency と confidence を生成する。

しかし今回、

```text
1 パルデンス
BACK 3 / FORWARD 1 / MID 1
dominant share = 3/5

2 ドンレパルス
FRONT 3 / FORWARD 1 / MID 1
dominant share = 3/5
```

であり、どちらも単一位置帯へ固定された馬ではない。

旧出力は、

```text
tendency
confidence
band_counts
```

までは持っていたが、Scenario authorが
「傾向の強さ」と「位置取り可変性」を即座に判別できる明示フィールドが不足していた。

このため、

```text
historical tendency != today's committed position
```

という既存ポリシーを、データ構造上さらに明示する必要がある。

## 5. 局所修正

`racenote_general_evidence.py` の historical position profile に以下を追加した。

```text
dominant_band_count
dominant_share
distinct_band_count
variability_status
policy.historical_tendency_is_not_position_commitment
```

`variability_status` は恣意的な閾値を置かない。

```text
observed band が1種類のみ -> SINGLE_BAND
複数bandあり             -> MULTI_BAND
履歴なし                  -> UNAVAILABLE
```

既存の tendency / confidence / pace_pressure 判定は変更しない。

## 6. 実データSmoke

修正後mainで同じ初風Sの Gen0.3 prepare を再実行。

```text
Issue #1361
run_id = 36110783372
status = PASS
head_sha = 74f8d8a3de14448b2deab74c774ad43a62d3531c
runner_count = 10
```

代表出力:

```text
1 パルデンス
tendency = BACK
confidence = MEDIUM
dominant_band_count = 3
dominant_share = 0.6
distinct_band_count = 3
variability_status = MULTI_BAND

2 ドンレパルス
tendency = FRONT
confidence = MEDIUM
dominant_band_count = 3
dominant_share = 0.6
distinct_band_count = 3
variability_status = MULTI_BAND

4 スプランドゥール
tendency = BACK
confidence = HIGH
dominant_band_count = 4
dominant_share = 0.8
distinct_band_count = 2
variability_status = MULTI_BAND
```

## 7. 現時点の判断

採用:

- position variability の明示
- tendency を「今回位置の約束」と読ませないpolicyの明示
- 既存Scenario/Forecast境界は維持

未採用:

- 2番の勝利を根拠にFRONT馬をFASTで上げる/下げない等の後付けルール
- 1レースだけを根拠にScenario順位ロジックを変更
- Abilityや人気を上位に戻す固定重み
- Market/oddsをpre-Freeze予想へ混入

次段では複数レースのblind E2Eを重ね、
position variability とScenario感応度の関係が再現するか確認してから、
必要ならScenario contract側の局所修正を検討する。
