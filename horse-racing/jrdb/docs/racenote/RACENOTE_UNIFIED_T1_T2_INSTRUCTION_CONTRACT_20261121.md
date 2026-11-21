# RaceNote — T1 / T2 単一指示オーケストレーション契約

更新: 2026-11-21。対象は v0.5.6 BTDAY / FORWARD、および既存 v0.5.5 r6 BTDAY 互換。
**意図はユーザー入力の簡素化であり、Prediction・Confidenceの機械化や受入基準緩和ではない。**
未受入の実行を完成・正式昇格として扱わない。

## ユーザー側の入口

利用者は原則 **「T1」** または **「T2」** だけ指示する。直近の会話・進行中セッションに
BACKTEST / FORWARD、日付、BTDAY、契約世代が定義されていればそれをそのまま維持する。
「11/22 T1」のように日付だけ更新された場合、FORWARDモードを維持する。
モードを黙って変更・拡大しない。判定に必要な文脈が本当に欠ける場合のみ確認する。
内部のDrive ID、SHA、producer evidence path、Issue本文を利用者に要求しない。

標準のプラン生成:
`python horse-racing/jrdb/src/racenote_t1_t2_command.py T1 --mode BACKTEST --version v056`
`python horse-racing/jrdb/src/racenote_t1_t2_command.py T1 --mode FORWARD --target-date 2026-11-22`
`python horse-racing/jrdb/src/racenote_t1_t2_command.py T2 --mode BACKTEST --selection-id BTDAY-XXXX`
`python horse-racing/jrdb/src/racenote_t1_t2_command.py T2 --mode FORWARD --target-date 2026-11-22`

これらは **実行計画と再開段階を返す制御モジュール** であり、実行完了を偽装しない。
ChatGPT/Work側が接続済みGitHub/Drive・必要時Actionsを操作し、実行結果を読み戻す。
GitHub ActionsにChatGPTの人間比較判断を代替させない。

## T1 / BACKTEST

- v056: `racenote_v056_t1_orchestrator.yml` への一意なNEXT/EXISTING requestを
  `backtests/requests/orchestrator-v056/` に1件だけ保存する。
  既存の進行中/READYがあれば二重発行せず再開/再配布する。
- v055-r6指定時だけ、旧 `racenote_v055_r6_t1_orchestrator.yml` と
  `backtests/requests/orchestrator/` を保持する。暗黙にv056へ移行しない。
- 自動Picker・canonical source判定・共有T1・ZIP配布の実ジョブと、
  `selection.json`、`operation_handoff.json`、全RのReader ZIP index/SHAを検証する。
- 過去レースの日付を推測してPoolと異なる日付へ差し替えない。結果・当日市場をT2以前に開かない。

## T1 / FORWARD

- ChatGPT側で認証済みDriveコネクタから canonical PACIフォルダ
  `1zFajenPU5jxInZCcmqZzkgiaYil3MD8r` を走査し、対象日の
  `PACIyyMMdd.zip` を **親フォルダ・正確な名前・日付** で確認する。
  対象日も省略された場合は会話の開催日とDriveの未来PACIを照合し、複数あれば安全に停止。
  GitHub Actionsが公開Driveの一覧を推測したり、JRDBからPACIを取り直すことは禁止。
- `[RACENOTE_FORWARD_T1] YYYYMMDD` を **一度だけ** 起票する。
  Issue JSONは `target_date` / 検証済み `paci_drive_file_id` / 判明した場合のみ
  `paci_drive_sha256`。利用者への追加作業指示は禁止。
- `racenote_v056_forward_paci_t1.yml` が先に
  `racenote_forward_t1_bootstrap.py` を実行する。
  受入済みgeneration-setが適格なら再利用。
  新たな検証済みproducer evidenceがあれば `accept-producer` reusable jobで
  **consumed-field検証 → generation-set受入 → main commit** を自動実施してからT1へ進む。
  対象日binding、cutoff、PACI取得、CLEAN BLIND Reader、main不変出力を最後まで確認する。
- この自動準備によって別の `[RACENOTE_FORWARD_ACCEPTANCE]` Issueは通常不要。
  既存のproducer acceptance Issueは診断・手動再現経路として維持する。
- **producer evidenceもまだ存在しない場合**：ChatGPTが認証済みDrive/producerの
  CURRENT、完了日、独立producer受入参照、正確なfile ID/SHAを取得し、
  検証済み宣言をGitHubへ保存してから、同一T1依頼の準備を続行する。
  不明なID・SHAを推測して `VERIFIED` としない。必要なproducer更新が未完了なら
  `ORCHESTRATION_MISSING` で止め、専用producer業務へ進める。
  Actions側単独では非公開Drive一覧とモデルの確認判断を代替できない。
- 不一致なら `DATA_INVALID`。同cutoffの受入と新producer宣言が食い違う場合は
  明示的に止める。ZIPのmodified time/transport SHAだけでは不一致扱いしない。
  race開始後の遡及FORWARDや未来の結果混入は不可。

## T2 / BACKTEST・FORWARD共通

- `racenote_t1_t2_command.py T2` で現在の `v056` セッションを調べ、
  `AUTHOR_ALL_RACE_PREDICTIONS` /
  `SUBMIT_PREDICTION_FREEZE` /
  `AUTHOR_INDEPENDENT_CONFIDENCE` /
  `SUBMIT_CONFIDENCE_FREEZE` /
  `ALREADY_COMPLETE` に区別して再開する。
  v055-r6を明示した場合のみ旧root・旧Freeze workflowへ分岐する。
- T1 Reader/authoring bundleの全レース・全馬をLLMが比較・著述する。
  **PredictionにConfidenceを混ぜない。**
  `incoming/llm_decisions.json` をrootに保存し、既存Prediction Freeze Actionsの
  実成功・mainの `frozen/day_handoff.json` / SHAを確認する。
- **凍結済み◎** を固定した状態で独立にA/B/C/Zと敗北シナリオ等を著述する。
  `incoming/llm_confidence.json` 保存後にConfidence Freeze Actionsを実行し、
  mainの `confidence_frozen/day_handoff.json` と `turn2_summary.json` を確認する。
- 前段で作成済みのdraftやFreezeは上書きせず再利用・検証する。矛盾する半端な
  freeze・複数候補セッション・結果混入はfail-closed。ChatGPTが単一セッションの
  一意な文脈を確定できないときは勝手に最新レースを選ばない。
- T2指示は両Freezeまで実施する指示であり、二段階目を利用者に再依頼しない。
  r6の `PIPELINE` 指定時のみ既存運用に従い次BTDAYの先行T1も動かす。
  v056通常T2は無断で次BTDAYを予約しない。
- 無人Actionsだけで全レースLLM著述を生成する設計ではない。**このチャット/Workの
  LLM実行をT2の著述主体**とし、既存Actionsは検証・凍結・監査主体とする。

## 運用上の成功判定

T1: accepted producer lineage/実PACI → Actions success → mainのREADYとmanifest →
artifact/readbackをすべて確認して `T1_READY`。
T2: Prediction Freeze success/readback → Confidence Freeze success/readback →
`turn2_summary.status=TURN2_COMPLETE`。
dispatchやCI PASSだけを実行完了と呼ばない。
失敗時は `DATA_INVALID` / `ORCHESTRATION_MISSING` /
それ以外のrunner障害を別々に報告し、旧resultを再利用しない。

関連:
- `horse-racing/jrdb/.gpt/WORKFLOW.md`
- `horse-racing/jrdb/forward-acceptance/README.md`
- `RACENOTE_V056_BTDAY_PREDICTION_THREAD_HANDOFF_20261030.md`
- `RACENOTE_V055_R6_PIPELINE_CURRENT_RUNBOOK_20261030.md`
