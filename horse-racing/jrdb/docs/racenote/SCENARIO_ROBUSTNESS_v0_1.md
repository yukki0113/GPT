# RaceNote Scenario Robustness v0.1

Status: IMPLEMENTED RESEARCH CONTRACT / NOT YET FORECAST-ACTIVE  
Date: 2026-09-25

## 1. Purpose

Pairwise Comparisonで得た順位を、1つの想定展開だけで確定しない。

最低3ケース:

- SLOW
- MEDIUM
- FAST

で全馬順を再評価し、Pairwiseの軸馬がどの程度シナリオ依存かを監査する。

Scenario Robustnessも予想スコアではない。

## 2. Pipeline position

    General Evidence
      -> Pairwise Comparison
      -> Scenario Robustness
      -> next-generation Forecast contract
      -> Independent Freeze
      -> post-Freeze market / value

Pairwise final orderはScenario入力時点のbase order。

Scenario orderはbase orderを自動上書きしない。
変化はrobustness evidenceとして次世代Forecastへ渡す。

## 3. Required scenarios

v0.1は3つを必須とする。

### SLOW

緩い流れ。

見るものの例:

- 前有利が強まるか
- 差し馬の位置取り要求が上がるか
- 瞬発力寄りになるか

### MEDIUM

中間的な流れ。

Pairwiseで想定した標準的な比較がどの程度維持されるかを見る。

### FAST

速い流れ。

見るものの例:

- 前受け馬が消耗するか
- RaceReviewの前傾耐性が効くか
- 差し/追込の条件傾向が強まるか

これらは固定的な「展開予言」ではない。
plausible scenario testである。

## 4. Scenario record

各scenarioで記録する:

- scenario_id / pace
- assumption_summary
- 全馬order
- Pairwise orderから変わったか
- scenario_summary
- key_reason_codes
- triggered_reversal_conditions

orderがPairwiseから変化した場合、少なくとも1つの
triggered_reversal_conditionを必須とする。

「なんとなく展開で逆転」は許可しない。

## 5. Axis robustness

Pairwise rank 1をaxis horseとする。

3シナリオ中のrank 1維持数から、説明用robustnessを導出する。

- 3/3: ROBUST
- 2/3: CONDITIONAL
- 0-1/3: FRAGILE

これは能力scoreではない。

「想定条件が変化してもPairwise首位を維持するか」の記述統計である。

FRAGILEではPairwise recheckを推奨する。

## 6. Horse sensitivity

全馬について:

- Pairwise rank
- SLOW rank
- MEDIUM rank
- FAST rank
- best rank
- worst rank
- rank span

を残す。

これにより「軸は変わらないが相手候補が展開で大きく入れ替わる」ケースも
Forecast側で扱える。

## 7. Evidence priority

Scenarioでも基本優先順位は変えない。

    DATA_TREND > RACEREVIEW >= ABILITY_ANCHOR

ScenarioはこのEvidenceの条件付き読み替えであり、別の点数体系ではない。

例:

    FAST
      running-style trend が差し寄り
      + RRで前傾戦の持続実績あり
      -> AをBより上へ

単純能力だけでScenario順位を機械生成しない。

## 8. Reversal conditions

Pairwise Comparisonで記録した「何なら逆転するか」を、
scenario側で実際にtriggerされた条件として明示する。

将来的にはPairwiseのreversal_conditionsとScenarioの
triggered_reversal_conditionsをIDで結びつける余地がある。

v0.1では文章＋reason codesで保持する。

## 9. Firewall

ScenarioはIndependent Forecast前。

禁止:

- current odds
- current popularity
- current JRDB consensus
- Training Edge
- target result

市場価値はFreeze後。

## 10. Short-comment relationship

Scenario evidenceがあると、短評は次の粒度まで上げられる。

    同距離傾向と近走内容から上位評価。
    流れが速くなると2番手に逆転余地はあるが、
    slow～mediumなら優位を維持。

あるいは:

    能力値は高いが展開依存が大きい。
    流れが締まると順位を落とす想定で、軸としては条件付き。

これもfuture rendererで生成し、Scenario validator自体は作文しない。

## 11. Implementation

- src/racenote_scenario_robustness.py
- schema/racenote_scenario_robustness_schema_v0_1.json
- tests/test_racenote_scenario_robustness.py

Successful validation emits:

    RaceNote-Scenario-Robustness-Audit-0.1

and:

    next_stage = FORECAST_NEXT_GENERATION_CONTRACT

downstream Forecast contractは `RaceNote-Forecast-Gen0.3` として実装済み。

- `src/racenote_forecast_gen0_3.py`
- `schema/racenote_forecast_gen0_schema_v0_3.json`
- `docs/racenote/FORECAST_GEN0_3_PREDICTION_CONTRACT_v0_3.md`

Scenario audit PASS後、Gen0.3 Base Forecastへ進む。
