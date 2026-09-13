# RaceNote legacy prediction assets

Status: HISTORICAL / REPRODUCIBILITY
Last reviewed: 2026-09-13

## 1. Purpose

この文書は、RaceNoteで過去に構築した**決定論的な印決定・Edge連携予想系**を、現行のRaceNote Forecast Gen0と混同しないための境界を定義する。

旧資産は削除しない。

過去予想の再現、TRUE_FORWARD監査、比較研究、provenance確認に必要だからである。

ただし、旧ロジックを現行のGPT Forecastへ暗黙に適用しない。

## 2. Legacy scope

少なくとも次をlegacy prediction logicとして扱う。

- RaceNote prediction control baseline v0.2
- v1.1-P gated policy (`1.1-P-gated-0.1`)
- `src/racenote_edge_prediction_policy.py`
- `src/run_racenote_v11p_true_forward_day.py`
- `.github/workflows/racenote_v11p_true_forward_issue.yml`
- v1.1-P TRUE_FORWARD freeze artifacts / manifests
- v1.1-Pでfreezeされた印を入力とするprediction presentation
- 過去のv1.1-P operational issues / run records / daily freezes

関連するpresentation moduleやcontractは、別consumerがまだ利用している可能性があるため、単純削除・移動はしない。

## 3. Historical v1.1-P decision rule

v1.1-Pでは、概ね次のgateで軸変更を決定していた。

- base ranking上位5頭のみ候補
- baseline ◎とのGood差が `<= 0.04`
- candidateにmatched Edgeがある
- candidateのEdge polarityがbaseline axisよりstrictly stronger
- 条件を満たす場合のみ◎を変更
- ◎は必ず1頭
- 軸変更以外の相対順位を原則維持
- confidenceを変更しない

これは過去predictionを再現するための重要な仕様である。

一方、現行Gen0ではこのgateを予想決定規則として使わない。

## 4. Why it is legacy

v1.1-Pは、再現性・監査性・TRUE_FORWARD運用を確立するうえで価値があった。

しかしRaceNoteの原点は、authoritative facts / evidenceをGPTへ渡し、GPT prediction layerがレース全体を比較して予想することにある。

v1.1-Pのような固定gateを中心に据えると、GPTがRaceNote全体を読む研究よりも、事前に決めたルールのexecutionが中心になる。

そのため、今後は:

```text
legacy deterministic policy
  -> historical reproducibility / benchmark

GPT Forecast Gen0
  -> current prediction research
```

と分離する。

## 5. Assets that remain reusable

legacyだからといってすべてを捨てるわけではない。

次はcurrent系でも再利用可能な研究インフラである。

- result leakage guard
- target-date / as-of validation
- source identity validation
- Edge publication validation
- provenance capture
- input / output SHA
- immutable pre-result freeze
- manifest
- result取得前後のstage separation
- prediction / presentation immutable-field check
- daily batch execution pattern

再利用時は、旧prediction ruleとインフラを分けて扱う。

## 6. Physical file policy

現時点ではlegacy資産を物理移動しない。

理由:

- import pathを壊す可能性がある
- workflow / historical run再現性を壊す可能性がある
- artifact / issue / docsから既存pathが参照されている
- presentation / downstream consumerが一部moduleを利用している可能性がある

従って当面は**documentation上の論理分離**を採用する。

将来物理移動する場合は:

1. import / workflow / docs referenceを全検索
2. historical reproducibilityへの影響を確認
3. compatibility shimまたはfrozen tagを用意
4. current consumerが旧moduleを参照していないことを確認
5. migration commitでまとめて移動

の順で実施する。

## 7. Historical result handling

旧v1.1-Pの成績はbenchmarkとして残してよい。

ただし:

- 新方式より一時的に良かったからという理由だけで旧方式へ戻さない
- 1R単位の勝敗でGen0を旧gateへ寄せない
- 比較条件、対象期間、input availabilityを揃えずに優劣を断定しない

旧方式は**履歴比較対象**であって、current defaultではない。

## 8. 2026-09-13 operational note

2026-09-13のv1.1-P TRUE_FORWARD predictionは、当時の契約に従ったimmutable historical freezeとして扱う。

そのfreezeを後からGen0形式へ書き換えない。

新しいGen0検証を同日・過去日で行う場合は、旧freezeとは別record / versionとして保存し、result leakageを避けたblinded inputを用いる。

## 9. Current references

現行方針:

- `../README.md`
- `../FORECAST_GEN0_PLAN.md`

historical/origin reference:

- `../../RaceNote_Prediction_Handoff_v0_1.md`
- `../../RaceNote_Presentation_Comment_Contract_v0_2.md`
- v1.1-P source modules / workflow / immutable run artifacts

current truthの判定では、古いIssue番号やrun IDではなくlatest mainのsource / current docsを優先する。
