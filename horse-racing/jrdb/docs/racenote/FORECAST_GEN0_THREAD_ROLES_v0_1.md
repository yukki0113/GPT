# RaceNote Forecast Gen0 Thread Roles v0.1

Status: **CURRENT**
Date: 2026-09-29

## 1. Purpose

RaceNote Forecast研究を、会話量と結果汚染を抑えながら継続するため、
ChatGPT上の役割を **Research thread** と **Forecast execution thread** に分離する。

この分離は会話上の便宜だけではなく、pre-result / post-result境界でもある。

## 2. Research thread

Research threadは本プロジェクトの司令塔。

Responsibilities:

- RaceNote仕様・抽出ロジックの研究 / 変更判断
- Forecast logicの仮説・version管理
- 現在採用するresearch baseline / candidateの指定
- day pool / contamination / eligibility方針
- Forecast execution threadから受領したFreeze済み成果物の監査
- **result open**
- objective metrics / qualitative review
- 予想時コメントと結果の突合
- recurring errorの抽出
- 次turnで変えるlogic themeの決定
- logic docs / config / handoffのGit更新
- TRUE_FORWARD移行判断

Research threadは、結果を見た後の知識を次のlogic versionへ反映してよい。

## 3. Forecast execution thread

Forecast execution threadは **pre-result prediction executor**。

Responsibilities:

- latest mainからcurrent research protocol / current logic versionを読む
- 指定またはPICKされたturn targetを確認
- 対象日のRaceNoteを構築 / 検証
- 1 race = 1 independent forecastとして全対象Rを予想
- common research recordへ保存
- immutable Freeze
- 1日1HTML forecastを生成
- turn handoff manifestを生成
- technical skip / missing evidenceを記録

Must NOT:

- target result / payout / final odds / final popularityを開く
- post-race evaluationを実施する
- turn途中でlogicを変更する
- current logic contractを自己判断で改訂する
- Gen0.3等の別candidateを暗黙に混ぜる
- 予想結果を見て印やコメントを書き換える
- Research threadの代わりに次versionを決める

実行中に気づいた「読みづらいEvidence」「曖昧な指示」等は
`execution_observations` として短く記録してよいが、
そのturnの予想判断ルールは変更しない。

## 4. Thread handoff boundary

Forecast execution threadの正常終了点:

```text
target days selected / confirmed
  -> RaceNote prepared
  -> every usable race forecast independently
  -> all usable predictions frozen
  -> daily HTML generated
  -> turn handoff manifest generated
  -> STOP
================ RESULT FIREWALL ================
  -> Research thread receives frozen package
  -> Research thread opens results
  -> evaluation / review
  -> logic adjustment
```

## 5. Required handoff package

Forecast execution threadからResearch threadへ最低限返す:

- `turn_handoff_<turn_id>.json`
- canonical prediction JSON / JSONL
- `forecast_YYYYMMDD.html` for each selected date
- target-day / PACI source identities
- logic_version
- race count / frozen count / technical skips
- prediction hashes
- execution_observations
- explicit `result_opened = false`

Schema:

`schema/racenote_forecast_turn_handoff_v0_1.json`

Research threadはこのpackageを受け取るまでtarget resultを開かない。

## 6. Current initial execution logic

Until changed by Research thread:

- logic version: `RaceNote-Baseline-Reader-0.1`
- contract: `docs/racenote/FORECAST_GEN0_BASELINE_READER_v0_1.md`
- config: `config/racenote_forecast_logic_baseline_v0_1.json`

Forecast execution threadは必ずlatest mainでcurrent logicを再確認する。
会話中の古いlogic説明をcurrent truthとして固定しない。

## 7. Relationship to TRUE_FORWARD

TRUE_FORWARDでも同じ役割分離を使う。

Forecast execution thread:
- pre-race prediction / Freeze / user-facing forecast delivery

Research thread:
- race終了後 result open / evaluation / logic research

前向き検証でも、予想スレッドへpost-race研究文脈を蓄積しすぎない。
