# RaceNote 前向き検証 運用指示書 v0.1

## 目的
実開催前に生成した RaceNote Forecast を結果閲覧前に Freeze し、後日ロジックや研究軸が変わっても再分析できる前向き検証証跡を残す。

BTDAY（過去日 blind backtest）とは別系統で扱う。

## 基本方針
- Git を正本とする。
- Google Drive への追加保存は原則不要。JRDB Raw は既存の `00_raw` を参照する。
- xlsx / zip / parquet / Raw 複製などの重量資産を Git に置かない。
- 1日ごとの Forecast は 36個の個別ファイルへ分割せず、原則 `forecast_all.json` 1本へ集約する。
- 結果を見てから Forecast を修正しない。修正が必要なら新しい generation / version として別記録にする。
- Race Selector、自信度、波乱度など将来の研究レイヤーは Forecast 本体と分離して Freeze する。

## 保存先

### 予想 Freeze
`horse-racing/jrdb/prediction_runs/forward/YYYYMMDD/`

最低限:
- `manifest.json`
- `forecast_all.json`
- `audit.json`

任意:
- `selector_snapshot.json`  
  Race Selector を運用開始した後のみ。Forecast 本体へ混在させない。

### 結果・精算
`horse-racing/jrdb/settlement_runs/forward/YYYYMMDD/`

最低限:
- `result.json`
- `settlement.json`

### 研究台帳
`horse-racing/jrdb/analysis/forward_validation/ledger.jsonl`

巨大表を作らず、原則1レース1行の JSONL とする。派生集計は必要時に生成し、Gitへ恒久保存しない。

## 開催日前 / 当日の Forecast 手順
1. 通常の RaceNote 入力を準備する。
2. target-day market 情報を Forecast 入力から除外する。
3. 現行ロジックで全レースを予想する。
4. `forecast_all.json` に、各レースについて少なくとも以下を残す。
   - identity（日付、場、R、条件）
   - ◎○▲△1△2
   - reader-facing reason
   - decision_trace
   - mainline_cases
   - single_shot_case と `selected_independently_from_mainline`
   - RRDB evidence / matched_signal_ids
   - logic_version
   - RRDB recommendation contract
   - RaceNote input semantic hash
   - main_sha_at_forecast
   - prediction hash
5. `audit.json` で以下を確認する。
   - result_opened = false
   - market blind guard = PASS
   - five-mark role guard = PASS
   - mainline / single-shot guard = PASS
   - RRDB contract guard = PASS
   - prediction hash が全レースで確定
6. Freeze 後は結果判明まで Forecast を上書きしない。

## 結果判明後
1. `jrdb_result_query_runner.py` を標準入口として JRDB Raw の SED/HJC を取得・照合する。
2. Web を JRDB Raw の代替にしない。
3. `result.json` に公式結果・払戻・最終単勝人気/オッズを保存する。
4. `settlement.json` に Forecast と結果を JOIN した精算結果を保存する。
5. `ledger.jsonl` に研究用の最小行を追記する。

## ledger の最低限フィールド
- date
- venue
- race_no
- logic_version
- main_sha_at_forecast
- prediction_hash
- freeze_status
- result_status
- main / second / single_shot / other_1 / other_2
- main_finish
- winner_mark
- winner_in_five
- all_top3_in_five
- 各研究対象馬券の investment / payout
- selector_version（存在する場合のみ）
- selector_snapshot_hash（存在する場合のみ）

## Race Selector / 研究注釈
◎信頼度、波乱度、5頭収束度、▲妙味度などを導入する場合は、
結果閲覧前に `selector_snapshot.json` として独立 Freeze する。

後日結果を見て付けた分析ラベルは `posthoc_analysis` として別資産にし、事前 Freeze 値と混同しない。

## Git 容量ルール
Git に置いてよい:
- JSON
- JSONL
- Markdown
- 小さな CSV（必要時のみ）

Git に置かない:
- xlsx
- zip
- parquet
- JRDB Raw の複製
- DAY_PREP の巨大スナップショット
- 一時集計ファイル
- 同一内容の個別R複製

1日の Forward Forecast が不自然に肥大化した場合は、保存前に原因を確認する。Raw や入力全文の埋め込みはしない。

## BTDAYとの境界
- `backtests/BTDAY-xxxx`: 過去日を使った blind research
- `prediction_runs/forward/YYYYMMDD`: 実開催前に Freeze した prospective evidence
- 両者は集計時に区別できるよう source_mode を保持する。

## 予想スレッドへの短縮指示
「本日は RaceNote 前向き検証として実行してください。FORECAST_HUMAN_CONTEXT_READER の現行正本と FORWARD_VALIDATION_RUNBOOK_v0_1 に従い、結果・target-day market を見ずに全レースを予想し、prediction_runs/forward/YYYYMMDD に forecast_all.json / manifest.json / audit.json を Freeze してください。重い資産や xlsx は作成しないでください。結果判明後の精算は別工程です。」
