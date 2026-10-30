# RaceNote v0.5.6 FORWARD — PACI → RaceNote → 二段階Freeze

更新: 2026-10-30。対象は日次PACI由来の**開催前**Reader生成と、既存v0.5.6二段階Freezeへの接続。新聞短評清書とPWA送信JSON生成は別工程として切り離す。

## 実行口

1. GitHub Actions **RaceNote v0.5.6 Forward PACI T1** (`.github/workflows/racenote_v056_forward_paci_t1.yml`) をmainで手動実行。
2. `target_date`（例 `2026-10-31`）、`race_lap_expected_period_to`、受入済みの `analysis_artifact_id` / `analysis_generation_id` / `course_fit_artifact_id` / `race_lap_artifact_id` を指定。Artifacts IDを知らない場合、使用すべきGenerationを確認するまで**推測して起動しない**。
3. JRDB認証済み `fetch_jrdb_paci.py` が対象PACIを取得する。RRDB CURRENTは既存 `racenote_fetch_rrdb_current.py` で取得する。Analysis/Course Fit/RaceLapは**指定された**既存GitHub Artifactsから取得する。
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
- `operation_handoff.json` — `READY_FOR_V056_AUTHORING` / `execution_mode=FORWARD`、T1 SHA受け渡し。
- T2後のみ: `v056/frozen/`、`v056/confidence_frozen/`、`v056/turn2_summary.json`。

## Fail-closed 境界

- 日付・PACIファイル名不一致、CRC不正、Rootの衝突、選択IDの不一致は停止。対象日は実行日のJSTから7日以内に限る。
- RaceLap は現在承認済みの `CURRENT` で、指定 `expected_period_to` と一致し、対象日より前でなければ停止。T1では自動的に不明なSEDや未来データを補完しない。
- バンドルのReader件数とSession件数が一致しなければ停止。
- AnalysisとRRDBの鮮度管理は従来どおり専用運用責務。Workflowの `Analysis artifact ID` は受入済みのGenerationを指定すること（存在するだけでは最新版とみなさない）。
- 本モジュールは印・予想・Confidenceを**一切生成しない**。これらは予想スレッドのLLM判断。
- `v055` の既存Root/Freeze/workflowは変更しない。

## ローカル実行

正規の `PACIyyMMdd.zip`・Analysis・Course Fit・RRDB・RaceLap CURRENTを既に用意している場合、リポジトリrootから次を実行する。出力Rootが存在する場合は実行禁止。

```bash
PYTHONPATH=horse-racing/jrdb/src python horse-racing/jrdb/src/racenote_v056_forward_turn1.py \
  --date 2026-10-31 \
  --paci /tmp/paci/PACI261031.zip \
  --main-sha "$(git rev-parse HEAD)" \
  --analysis-root /tmp/analysis \
  --course-fit-root /tmp/fit \
  --racereview-root /tmp/rrdb/postrace_review/v0_1 \
  --race-lap-current-bundle /tmp/racelap/current \
  --race-lap-expected-period-to 2026-10-30 \
  --output-root horse-racing/jrdb/daily/20261031/v056_day
```

**注意:** 上記の日付とカットオフは記載例。実際の開催日・完了済み期間に置き換える。RaceLap CURRENTが古ければ既存の `RACELAP_FORWARD_REFRESH` 手順で事前更新する。

## 受入判定

現行CIは構文・契約・入口のテストを実施する。**初回PACI実データの日次T1と二段階Freezeの実行をもってFORWARDの実運用受入を判定する**。その成功前にPWA送信完了・FORWARD全工程完走とは報告しない。
