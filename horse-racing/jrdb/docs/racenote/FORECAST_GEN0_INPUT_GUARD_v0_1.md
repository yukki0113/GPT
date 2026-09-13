# RaceNote Forecast Gen0 Input Guard v0.1

Status: CURRENT
Last reviewed: 2026-09-13

## Purpose

GPT Forecast Gen0の自由な予想判断には介入せず、研究入力の完全性だけをfail-closedで保証する。

予想ロジックと混同しない。

```text
RaceNote source runners
  + GPT frozen forecast
  -> input completeness guard
     -> PASS
        -> Google Sheets pre-result transaction
```

## Guard checks

`src/racenote_forecast_gen0_guard.py` は次のみを確認する。

1. frozen forecast自体のhash auditがPASS
2. RaceNote sourceに存在した全馬とforecast `horses` が完全一致
3. sourceに存在しない馬をforecastへ追加していない
4. horse-scope factor usageがsource runnerだけを参照している
5. `(factor_code, scope, horse_no)` のfactor usage identityが重複していない

以下は行わない。

- 印の妥当性判定
- factor weightの指定
- 上位候補の絞り込み
- JRDB指数の再計算
- Edgeによる軸変更

## Operational use

Freeze後、Google Sheetsへ記帳する直前に `to_guarded_ledger_rows()` を使用する。

この関数は通常のpre-result row projectionへ次の監査項目を追加する。

- `source_runner_count`
- `forecast_runner_count`
- `factor_usage_count`
- `runner_coverage_match`
- `factor_usage_identity_unique`

これらは `Freeze監査` tabへ保存する。

## Source identity

`source_horses` は、forecastの `source_semantic_sha256` が指す同一RaceNote / Reader Viewから抽出したrunner identityでなければならない。

別version、別race、結果取得後に組み直したrunner listを渡してはならない。

## Relationship to prediction contract

Prediction Contractの「全馬を読む」はGPTへの予想者方針であり、このGuardはその最低限の機械的完全性を監査する。

GuardがPASSしても予想内容の質が高いことは保証しない。

逆に、Guardを強化するためにGPTの自由なfactor weightingや結論を固定してはならない。
