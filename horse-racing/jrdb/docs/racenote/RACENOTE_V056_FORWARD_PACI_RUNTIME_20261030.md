# RaceNote v0.5.6 FORWARD — PACI → RaceNote → 二段階Freeze

更新: 2026-10-30。対象は日次PACI由来の**開催前**Reader生成と、既存v0.5.6二段階Freezeへの接続。新聞短評清書とPWA送信JSON生成は別工程として切り離す。

## 実行口

1. GitHub Actions **RaceNote v0.5.6 Forward PACI T1** (`.github/workflows/racenote_v056_forward_paci_t1.yml`) をmainで手動実行。
2. `target_date`（例 `2026-10-31`）、**Drive正本に存在する対象日PACIの`paci_drive_file_id`**、必要に応じ既知の`paci_drive_sha256`、`race_lap_expected_period_to`、承認済み `analysis_artifact_id` / `analysis_generation_id` / `course_fit_artifact_id` / `race_lap_artifact_id` を指定。不明なファイルID・Generationを推測して起動しない。
3. **PACIはGoogle Driveの既存正本から取得する。JRDBへの再取得は禁止。** 接続済みDriveでcanonical PACIフォルダ（[Drive/PACI](https://drive.google.com/drive/folders/1zFajenPU5jxInZCcmqZzkgiaYil3MD8r)）を直接確認し、`PACIyyMMdd.zip` の完全一致・親フォルダ・ファイルIDを確認する。Driveの検索0件を不存在と判定しない。GitHub Actionsの `racenote_v056_forward_drive_paci.py` が指定されたDrive IDを取得し、CRC/KYI日付/SHAを検証して取得証跡を作成。直接JRDBへfallbackせず、Drive取得不能時は停止する。RRDB CURRENTは従来どおり専用 `racenote_fetch_rrdb_current.py` を使用し、Analysis/Course Fit/RaceLapは指定された受入済みArtifactsから取得する。
4. 既存 `racenote_v053_from_paci.py --prep-only` → `racenote_v054_kyi_bundle.build_bundle` → `racenote_v056_single_day.init_session` → `racenote_v056_authoring_bundle.build` の順。バージョン違いのLegacy Sessionを生成しない。
5. ワークフローが `operation_handoff`、`session.json`、Reader/authoring Bundleの件数・Session ID・CLEAN BLINDを検査した後、mainへT1コミット。Artifact `racenote-v056-forward-YYYY-MM-DD-authoring` を発行する。
6. LLMは各レースReaderの全頭を判断し、`v056/incoming/llm_decisions.json` を提出。既存 `racenote_v056_llm_prediction_freeze.yml` のSUCCESS・main上の `frozen/day_handoff.json` を照合。
7. 凍結◎だけを参照して独立Confidenceを著述し、`v056/incoming/llm_confidence.json` を提出。既存 `racenote_v056_llm_confidence_freeze.yml` のSUCCESS・main上の `confidence_frozen/day_handoff.json` / `turn2_summary.json` を照合。
8. FORWARDの結果・当日市場・確定オッズは両Freeze前に開かない。両Freeze後に別工程として `forward_newspaper_comment` の清書/PWA JSONを出力できる（現Workflowには含めない）。

## 生成物

`horse-racing/jrdb/daily/YYYYMMDD/v056_day/`

- `day_prep/RaceNote_YYYYMMDD/` — PACI由来のRaceNote日次入力（既存日次ビルダーの正本）。
- `forecast_prep/` — Market-blind Readerとソースハンドオフ。
- `v054_inputs/kyi_bundle.json` — Allowlist KYI evidence。
- `v056/session.json` — v056 Session Seal。
- `v056/reader_manifest.json` / `v056/reader/*.json` — 予想入力Reader。
- `v056/authoring_bundle/manifest.json` / `v056/authoring_bundle/<venue>.json` — LLM全頭比較のためのロスレスBundle。
- `operation_handoff.json` — `READY_FOR_V056_AUTHORING` / `execution_mode=FORWARD`、T1 SHAに加え `paci_source`（`GOOGLE_DRIVE_CANONICAL_PACI`、Drive ID・ファイル名・サイズ・内容SHA・直接JRDB取得=false）を保存。
- T2後のみ: `v056/frozen/`、`v056/confidence_frozen/`、`v056/turn2_summary.json`。

## Fail-closed 境界

- Drive正本PACIのIDを指定できない、同名別日付、CRC/KYI日付不正、取得証跡欠落、ダウンロード後SHA不一致、Rootの衝突、選択ID不一致は停止。対象日は実行日のJSTから7日以内。`fetch_jrdb_paci.py` とJRDB認証情報はこのforward T1で使用しない。Drive側のPACI未配置／非公開／取得障害でもJRDBへ自動fallbackしない。
- RaceLap は現在承認済みの `CURRENT` で、指定 `expected_period_to` と一致し、対象日より前でなければ停止。T1では自動的に不明なSEDや未来データを補完しない。
- バンドルのReader件数とSession件数が一致しなければ停止。
- AnalysisとRRDBの鮮度管理は従来どおり専用運用責務。Workflowの `Analysis artifact ID` は受入済みのGenerationを指定すること（存在するだけでは最新版とみなさない）。
- 本モジュールは印・予想・Confidenceを**一切生成しない**。これらは予想スレッドのLLM判断。
- `v055` の既存Root/Freeze/workflowは変更しない。

## ローカル実行

Driveから正規の `PACIyyMMdd.zip` を取得し `racenote_v056_forward_drive_paci.py` が `drive_source_receipt.json` を作成済みで、Analysis・Course Fit・RRDB・RaceLap CURRENTを用意している場合、リポジトリrootから次を実行する。出力Rootが存在する場合は実行禁止。**未確認のPACI IDをコードや運用指示に固定しないこと。**

```bash
PYTHONPATH=horse-racing/jrdb/src python horse-racing/jrdb/src/racenote_v056_forward_turn1.py \
  --date 2026-10-31 \
  --paci /tmp/paci/PACI261031.zip \
  --paci-source-receipt /tmp/paci/drive_source_receipt.json \
  --main-sha "$(git rev-parse HEAD)" \
  --analysis-root /tmp/analysis \
  --course-fit-root /tmp/fit \
  --racereview-root /tmp/rrdb/postrace_review/v0_1 \
  --race-lap-current-bundle /tmp/racelap/current \
  --race-lap-expected-period-to 2026-10-25 \
  --output-root horse-racing/jrdb/daily/20261031/v056_day
```

**注意:** 上記の日付とカットオフは記載例。実際の開催日・完了済み期間に置き換える。RaceLapのカットオフは前日の日付ではなく、実際に確定済みの直近開催日を承認済みCURRENTのmanifestで確認する。RaceLap CURRENTが古ければ既存の `RACELAP_FORWARD_REFRESH` 手順で事前更新する。

## Drive正本の選定・監査ルール

- 正本はDriveの `PACI` フォルダに既存保存された対象日PACI。PACIに限ってはこのDrive資産を優先し、JRDB会員サイトから新規ダウンロードし直さない。
- ファイル名は対象日から機械的に `PACIyyMMdd.zip` を導出する。フォルダを直接確認してファイルIDを特定し、複数候補はサイズ・更新時刻・既知SHAで判定する。
- GitHub Actionsは指定されたDriveファイルIDを使用し、`source_receipt.json` のSHAと `operation_handoff.json.paci.sha256` が一致するまで受入しない。
- ZIPがDriveから読めなければ、**未取得／未接続として停止**。JRDB直接取得や外部Web検索で勝手に代替しない。

## 受入判定

現行CIは構文・契約・入口のテストを実施する。**初回PACI実データの日次T1と二段階Freezeの実行をもってFORWARDの実運用受入を判定する**。その成功前にPWA送信完了・FORWARD全工程完走とは報告しない。
