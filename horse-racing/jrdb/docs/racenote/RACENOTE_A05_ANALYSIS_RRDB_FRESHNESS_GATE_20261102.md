# A05 — FORWARDのAnalysis／RRDB最新性preflight

更新日: 2026-11-02  
対象: `racenote_v056_forward_paci_t1.yml` と `racenote_v056_forward_turn1.py` のFORWARD運用のみ。更新・再生成は各DB専用運用の責務。

## 何が問題だったか

Analysisの受入済みartifact IDとgeneration ID、RRDBのZIP SHA/CRCが正しくても、
それらのデータが今回のFORWARD対象日に必要な**最後の確定済み開催日**まで反映済みとは限らない。
従来T1はこの確認をスキップして `forward_t1_checked=false` を記録するだけだった。

## 入力契約

通常実行とowner Issue起動のどちらも、新しい必須入力
`freshness_acceptance_json` (schema `racenote-forward-analysis-rrdb-acceptance-v1`) を受け取る。

これは**専用Analysis／RRDB運用で更新済み・検証済みという記録を取得した後に**
対象日ごとに用意する。単に前日の日付を入れてはいけない。
`required_completed_through` はJRDB結果取得の正常完了証跡から、
実際の対象日より前の最後の完了開催日を採用する。
このフィールドは日時ではなくレースデータの到達範囲を表す。

以下は**schemaの記入例であり、実運用で再利用してはいけない**。
SHAや世代・artifact IDは実物の受入結果に置き換えること。

```json
{
  "schema_version": "racenote-forward-analysis-rrdb-acceptance-v1",
  "status": "ACCEPTED",
  "target_date": "2026-10-31",
  "required_completed_through": "2026-10-25",
  "completion_evidence": {
    "source": "DEDICATED_JRDB_RESULT_OPERATION",
    "status": "PASS",
    "reference": "JRDB_RESULT_VERIFIED_RUN_OR_RECEIPT",
    "verified_at_utc": "2026-10-30T12:00:00Z"
  },
  "analysis": {
    "status": "ACCEPTED",
    "acceptance_reference": "ANALYSIS_ACCEPTED_RUN_OR_RECEIPT",
    "artifact_id": "12345678",
    "generation_id": "jrdb_analysis_approved_generation",
    "manifest_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "coverage_through": "2026-10-25"
  },
  "rrdb": {
    "status": "ACCEPTED",
    "acceptance_reference": "RRDB_ACCEPTED_RUN_OR_RECEIPT",
    "file_id": "1UwNfrupMTHRPhkzULPvClGre4MWz2TFg",
    "generation_id": "jrdb_race_review_v0_1_accepted_generation",
    "manifest_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "zip_sha256": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
    "coverage_through": "2026-10-25"
  }
}
```

- `completion_evidence.reference`: 結果取得のPASS記録へ辿れるID/URI。
- `analysis.acceptance_reference`: Analysis専用運用の受入Run/receipt、`artifact_id`、`generation_id`、そのgenerationのmanifest SHA。
- `rrdb.acceptance_reference`: RRDB専用運用の受入Run/receipt、Drive保存先、CURRENTのzip SHA、manifest SHA、generation ID。
- `coverage_through`: 実データの末尾開催日。単にupdate実行時刻やファイル更新日を使わない。

**注意**: このJSONはowner／専用運用から受け渡す証拠の**照合用**であり、T1自体は
IssueやRun IDの外部存在・成功を再照会しない。したがって入力を捏造すれば
真の「外部運用の成功」を証明することはできない。運用側で証跡を監査し、
承認した値だけを渡すこと。機械的に確認できるのは、実物のgeneration・SHA・到達日との一致である。

## ゲートの実行位置

```text
専用Analysis・RRDB更新／検証
    -> 更新証跡 + 最終確定済み開催日の結果照合
    -> owner Issue / workflow_dispatch (freshness_acceptance_json)
    -> PACI, Analysis受入artifact, RRDB CURRENTを既存ルートで取得
    -> A05 preflight (FAIL時はT1生成禁止)
       - Analysis current pointer→manifest→全必須asset SHA
       - Analysis実ParquetのMAX(race_date),COUNT(*)
       - RRDB取得receipt→ZIPサイズ/SHA→current/manifest
       - 各専用運用の受入世代/manifest SHA/coverage/保存先と完全一致
       - required_completed_through <= 各実データのcoverage < target_date
    -> v0.5.6日次T1 → 予想freeze
```

A05は結果取得や各DBの更新処理を実行しない。
単に`RaceLap expected_period_to`を各DBへ転用せず、
それぞれの専用更新証跡が要求するlast completed race dateを使う。
自然日としての前日や「ファイルが存在する」「artifactを取得できる」だけではPASSしない。

## CLI、出力

T1 wrapperの必須オプション:

```bash
PYTHONPATH=horse-racing/jrdb/src python horse-racing/jrdb/src/racenote_v056_forward_turn1.py \
  --date 2026-10-31 --paci /tmp/paci/PACI261031.zip \
  --paci-source-receipt /tmp/paci/source_receipt.json \
  --main-sha <40桁Git SHA> \
  --analysis-root /tmp/analysis --course-fit-root /tmp/fit \
  --racereview-root /tmp/rrdb/postrace_review/v0_1 \
  --race-lap-current-bundle /tmp/racelap/current \
  --race-lap-expected-period-to 2026-10-25 \
  --freshness-acceptance /tmp/a05/acceptance.json \
  --analysis-artifact-id 12345678 \
  --analysis-generation-id jrdb_analysis_approved_generation \
  --rrdb-zip /tmp/rrdb.zip --rrdb-receipt /tmp/rrdb_receipt.json \
  --output-root horse-racing/jrdb/daily/20261031/v056_day
```

成功後:

- `source_audit/forward_analysis_rrdb_freshness.json`: 入力承認SHA、双方のmanifest SHA、世代、coverage、実ZIP SHA、保存先、受入参照。
- `operation_handoff.analysis_freshness`／`rrdb_freshness`: `forward_t1_checked=true`・`status=PASS`、実世代・必要coverage・証跡参照。

すべての重要データは`main`のT1 commitへ記録する。失敗時はT1生成前に止まり、
過去のデータを「最新版」として使うfallbackを設けない。
受入日の後に別世代へ更新された場合、取得物と承認SHAが合わないので再承認が必要となる。

## 制約と安全境界

- 通常のPACI、RRDB CURRENT、Analysis artifact取得方法は変更しない。
- Drive REST API、サービスアカウント、Drive権限、共有`tools/`変更はしない。
- v0.5.5 r6／歴史BTDAYの固定baseline、PWA／Pages、評価ロジック変更はしない。
- 受入対象日ごとに専用運用の証拠が必要。未受入時は停止、勝手なデータ生成やWeb fallbackはしない。
- A06のRRDBファイルID追従契約は別作業。

## 判定

決定的回帰テストでは実Parquet/manifest/ZIPを使い、正しい結果のみPASS。
実運用の受入は、更新側が生成した**本物の**成功証跡を使った最初のFORWARD T1完走で判断する。
