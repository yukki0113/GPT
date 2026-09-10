# Eval project context

## Status

Active。Eval表の画像取得、OCR/検証、JRDB事前情報付与、結果取得、台帳更新を支援する領域です。

## Source of truth

Python、README、作業手順、依存関係、GitHub Actions WorkflowはGitHub `yukki0113/GPT` の `main` を正本とします。

Eval画像、OCR途中成果物、日次取得CSV、検証レポート、ログ、JRDB Raw等の運用成果物は通常Git外を正本とします。

継続台帳はネイティブGoogleスプレッドシート `Eval表集計・検証` を正本とします。

- Spreadsheet ID: `1XBOYZrtJFLfY0Q3EmLfImJvughyXdAvdsLnmix8hgo0`
- Chat / WorkではGoogle Drive / Google Sheetsのnative操作で直接参照・更新する。
- 旧Google Drive Excel版とGitHub `horse-racing/eval/ledger/Eval表集計・検証.xlsx` は移行前スナップショットであり、最新台帳として扱わない。

## GitHub execution routing — 2026-09-10

Issue駆動Actionsを一律の標準経路にはしない。処理開始時に次の4系統を判定する。

- A: Read / Audit — GitHubのfile/commit/issue/run/artifact/SHA/diff確認。Issue不要。
- B: Git Change — UTF-8テキストのsource/test/docs/config/workflow変更。最新main/current content確認後にdirect create/update/deleteでmainへcommitする。
- C: Pure Deterministic Execution — 入力が手元にありSecretsや特別なrunner、長時間/大容量、immutable auditが不要な既存ロジックをChat/ローカルで直接実行する。
- D: Actions-Native Execution — Secrets、artifact chain、長時間/大容量、runner固有依存、immutable freeze、監査run等が必要な処理。既存Issue/Actionsを維持する。

DでIssueを作る場合のみ、ルート `.gpt/ISSUE_REQUEST_CONTRACTS.md` のpreflight / retry規約を適用する。

## Eval表OCR

本体は `src/extract_eval_table.py` と `src/eval_ocr/`。通常出力CSVは `date,venue,race_no,horse_no,eval` の5列。

馬名セル画像は行存在判定に使用するが馬名文字列のOCRは行わない。会場名ヘッダーOCR、Eval数値OCR、色付き上位セル・同色tie・固定色順位とEval大小のvalidationを維持する。

正式馬名・レース属性・馬属性は後段のJRDB PACI enrichmentが `date + venue + race_no + horse_no` をキーに付与する。

ChatへユーザーがEval表画像を直接渡す通常運用では、OCRはC: Pure Deterministic Executionとし、GitHub mainの正本ロジックをChat/ローカルで実行する。OCR validationがerrorならPACI enrichmentへ進めない。

既存 `[EVAL_OCR_REQUEST]` / `.github/workflows/eval_ocr_chat.yml` は、GitHub内artifact chain、immutable OCR audit、多数画像、runner側Tesseract環境固定が必要な場合のD経路として残す。

## Chat画像 -> 完成CSV

通常の最終成果物は5列OCR CSVではなく、JRDB PACI事前情報まで付与した完成CSVとする。OCRのみを明示された場合だけ5列で停止してよい。

標準フロー:

```text
ユーザー画像
  -> C: Chat/ローカルでGitHub mainのOCRロジックを使用
  -> OCR validation PASS
  -> 5列OCR CSV
  -> D: [EVAL_PACI_ENRICH_REQUEST]
  -> Actions Secretsで対象日PACIを取得
  -> enrich_eval_csv_with_paci.py
  -> 完成CSV + audit artifact
  -> A: RESULT/run/artifactを直接確認・回収
```

直接アップロードされた画像はGitHubへ永続化しない。GitHubへ渡すのはOCR後の5列CSVを圧縮・Base64化したpayloadのみ。

PACI取得には `JRDB_USER` / `JRDB_PASSWORD` Secretsが必要なため、`.github/workflows/eval_paci_enrich_chat.yml` はD: Actions-Native Executionとして維持する。

通常成功条件は `joined_horses == input_rows`、`unmatched_horses == 0`、`duplicate_keys == 0`。`race_headcount_mismatches` は必ず監査する。

## Eval表画像取得

本体は `src/master_eval_media_collector.py`。

ユーザーが画像を直接添付済みなら画像取得工程は不要。

X投稿から新規に取得し、取得時点のmetadata/media/validationを同一runのartifactへ固定する運用では、`.github/workflows/eval_media_chat.yml` / `[EVAL_MEDIA_REQUEST]` をDとして維持する。これは外部投稿の取得物をimmutableな監査証跡として扱うため。

単発のRead確認で既に画像を直接取得できておりartifact固定が不要なら、追加Issueを作らない。

## JRA結果取得

本体は `src/fetch_jra_daily_results.py`、検証は `src/validate_jra_results.py`。

Secrets不要なのでActions専用ではない。外部アクセス可能な環境で通常規模・監査run不要ならCで直接実行できる。

Chat/ローカルから取得先へ到達できない、長期/大量取得、または取得run/artifactの固定が必要な場合は `.github/workflows/jra_results_chat.yml` / `[JRA_RESULTS_REQUEST]` をDとして使用する。

出走頭数は取消・競走除外前の枠順確定時頭数を維持する。

## Git changes / audits

GitHub上の確認作業はAとして直接read/search/fetchする。確認専用Issueは作らない。

Python、Markdown、JSON、YAML、tests、workflow等のUTF-8テキスト変更はBとしてdirect create/update/deleteでmainへ反映する。`[gpt-git-update]` は標準経路ではない。

変更後のcommit/SHA/CI確認はAで行う。
