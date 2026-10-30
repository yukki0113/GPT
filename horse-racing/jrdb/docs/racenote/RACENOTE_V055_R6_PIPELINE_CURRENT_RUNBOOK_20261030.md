# RaceNote r6 — 現行運用手順（T1 Orchestrator / T2 PIPELINE）2026-10-30

**この文書を新規 r6 BTDAY の第一参照先とする。** 対象は2025年 Historical Warehouse を利用する `v055-prediction-freeze-confidence-review-r6`。古い r4/r5・旧一括Freeze・PACI/forward専用手順は消さず再現用に保管し、新規 r6 の実行指示として混用しない。

## 0. 起動前に確認する

1. `main` の現在HEAD、選択済みBTDAYとその `selection.json`、オーケストレータ実行状況、T1 `operation_handoff.json`、ZIPのActions Artifactを確認する。IDの連番は見込みであり、**実際のPicker結果を正本とする**。
2. 現在BTDAYの `v055/session.json` がr6・CLEAN BLINDであること、ZIP `index.json` の `session_id` と36RのSHAが一致することを検証する。
3. 予想ロジック世代や読み込み契約の変更中なら `T2_ONLY` を選ぶ。開始したT1の基準SHA・contractを記録し、次回T2前に比較する。
4. T2本体（全頭比較、印、コメント、Confidence）は**LLMによる独立判断**であり、機械的な印や自信度を生成しない。結果・市場・配当は二段階Freezeと必要なコホート保護が終わるまで参照しない。

## 1. 初回／単独T1の実行

`RaceNote r6 T1 Orchestrator`：`.github/workflows/racenote_v055_r6_t1_orchestrator.yml`

- **NEXT**：2025年の未使用かつ適格な日をPickerで1日選び、選定保存→共通T1起動→検証→1R別ZIPを公開。
- **EXISTING + BTDAY-NNNN**：対象の既存T1がREADYなら再生成せずZIPを再配布。未着手なら新規T1。別経路で起動済みなら二重起動しない。
- **STATUS + BTDAY-NNNN**：T1正本の状態を確認（Artifactの存在は別途チェック）。
- **T2_ONLY**：T1を起動・選定しない。

GitHub connectorからは `main` に一意な新規リクエストファイル `horse-racing/jrdb/backtests/requests/orchestrator/<unique>.json` を1個作る。中身は `{"mode":"NEXT","selection_id":null}`。既存対象は `{"mode":"EXISTING","selection_id":"BTDAY-0138"}`。ファイル名の再利用や複数件の同時登録は避ける。

**成功判定はT1だけでは不十分**：オーケストレータrunの `reserve`、必要時の `t1`、`deliver` が成功し、`racenote-orchestrator-BTDAY-NNNN` Artifactを取得・ZIP内の `index.json` と各レースのSHAまで検証する。Artifactは7日保持。失効時は `EXISTING` で再配布する。

## 2. 通常の擬似1ターン PIPELINE

ユーザー指示例：`BTDAY-0138のT2をPIPELINEでお願いします`。

1. **T2冒頭**に、現在BTDAYのT1_READYとZIPを確認。最初に `NEXT` で**次**のBTDAYのT1 Orchestratorを起動する。起動を確認したら、T1完了を待たずに現在のT2へ進む。
2. LLMが現在BTDAYの36R全頭を独立比較し、1R単位のPredictionを検証・保存。既存のチェックポイントがあれば整合性確認後に再利用。全件がそろったら集約してsubmit gateを通す。
3. 現在BTDAYの `incoming/llm_decisions.json` **だけ**を `main` に保存し、`racenote_v055_llm_prediction_freeze.yml` の成功と `frozen/day_handoff.json` の**main永続化**を照合。Prediction Freeze前にConfidenceを判断・提出しない。
4. 凍結した◎に基づき、LLMが独立してA/B/C/Zと個別理由を判断。全件を集約し、`incoming/llm_confidence.json` **だけ**を提出。 `racenote_v055_llm_confidence_freeze.yml` の成功と `confidence_frozen/day_handoff.json`、`turn2_summary.json` のmain永続化を確認。
5. Batch Controllerをinspect/syncし `TURN2_COMPLETE` を確認。**その後**に冒頭で起動した次T1のworkflow runとArtifactの状態を照合する。T1が実行中・失敗ならそのまま報告し、現在BTDAYのT2は成功として扱う。GitHub Actions自体は別途実行を継続するが、ChatGPTが回答後に無監視の監視・追跡を続けるわけではない。
6. 報告は現在BTDAYのFrozen件数、二段階Freeze状態、Confidence件数、SHA、次BTDAYの選定ID・日付・T1/ZIP状態・run URL。全レース印の再掲は通常不要。

**T2_ONLY**：1のNEXT起動と5の次T1確認を省く。Prediction→Confidence→Batch Controllerの既存手順はそのまま実行する。ロジック世代更新時や前倒し準備を止めたい時に使う。

## 3. 失敗時・中断後

- 次T1が失敗しても、現在T2のPrediction/Confidence Freezeを巻き戻さない。T1失敗runと失敗ステップを特定し、**同一BTDAYを再利用**する。勝手に新しい日を取り直さない。
- すでにT1 READYの対象に `NEXT` を重ねず、次BTDAYが未選定か・進行中か・READYかを `selection.json` とActions runで確認する。
- Predictionの保存済みレースは、元Readerとの検証後に保持し、異なる内容で上書きしない。既に凍結したPredictionは変更しない。
- 不完全なT2を `TURN2_COMPLETE` と報告しない。Freeze workflowの起動だけでは成功ではなく、`main` の正本とSHAを確認する。
- `workflow_run`、GitHub botコミット起因のpush、明示的リクエストファイルなど起動方式を区別する。botコミットによるpushトリガー連鎖には依存しない。
- 2010–2024年のHistorical Warehouseや2026年PACIは、現行共通T1オーケストレータの対象外。別途検証・承認するまで `NEXT` の対象を拡大しない。

## 4. 関連する正本・詳細

- T1：`RACENOTE_V055_R6_T1_ORCHESTRATOR_OPERATION_20261029.md`
- 共通T1境界：`RACENOTE_V055_R6_SHARED_T1_v0_1.md`
- 1R ZIP：`RACENOTE_V055_R6_RACEZIP_EXECUTION_BRIDGE_v0_1.md`
- T2二段階：`RACENOTE_V055_TWO_PHASE_TURN2_OPERATION_v0_1.md`
- Prediction提出：`RACENOTE_V055_R6_T2_SUBMISSION_HANDOFF_v0_1.md`
- Confidence checkpoint：`RACENOTE_V055_R6_CONFIDENCE_CHECKPOINT_OPERATION_20261029.md`
- Batch Controller：`RACENOTE_V055_BATCH_CONTROLLER_v0_1.md`

## 5. バックアップと切り戻し

2026-10-30更新前の運用資料は `docs/racenote/operation-backups/20261030_pre_pipeline/` に元内容を保存している。切り戻し時は変更された**文書だけ**をバックアップから戻し、r6のT1/T2本体・BTDAY正本・Freezeを削除または巻き戻さない。元のSHA・対象ファイル一覧はバックアップの `MANIFEST.md` を参照する。
