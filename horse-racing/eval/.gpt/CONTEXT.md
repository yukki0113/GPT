# Eval project context

## Status

Active。Eval表の画像取得、結果取得、OCR/検証・台帳更新を支援する領域です。

## Source of truth

Python、README、作業手順、依存関係、GitHub Actions WorkflowはGitHub `yukki0113/GPT` の `main` を正本とします。

Eval画像、OCR途中成果物、日次取得CSV、検証レポート、ログ等の運用成果物はGit外を正本とします。

継続台帳 `Eval表集計・検証.xlsx` はGoogle Drive `GPT/ledger/Eval表集計・検証.xlsx` を正本とします。GitHub `horse-racing/eval/ledger/Eval表集計・検証.xlsx` に残る同名ファイルはDrive移行前の旧スナップショットであり、最新台帳として扱いません。

## Eval表画像取得

本体は `src/master_eval_media_collector.py`。このPythonはX/Twitterの投稿IDを受け取り、添付メディアを取得します。日付から投稿IDを探索する機能と、Eval表本体・注意事項画像の内容分類機能は持ちません。

Chatからの定型取得は `.github/workflows/eval_media_chat.yml` のIssue経路を標準とします。Chatが対象日の `@master_eval` 投稿を探索して投稿IDを確定し、タイトル `[EVAL_MEDIA_REQUEST] <request_id>` のGitHub Issueを作成します。Issue本文JSONには対象日と投稿IDの対応を記載します。

ActionsはIssue作成をトリガーにGit正本の `src/master_eval_media_collector.py` を実行し、投稿ID別のmetadataとmedia、`resolved_request.json`、`validation_report.json`、`run_status.txt` をartifact化します。

完了後、同じIssueへ `EVAL_MEDIA_RESULT` コメントとして `run_id`、artifact名、fetch/validation終了コード、対象日・投稿ID、検証結果を返し、Issueを自動クローズします。Chatはこのコメントを完了通知として利用し、artifactを回収します。

Actions側の検証は各投稿でmetadataと1枚以上のmediaが取得できたかまでです。Eval表本体と注意事項・説明画像の分類はChatがartifact回収後に画像内容を見て行い、Eval表のみを `eval_YYYYMMDD_YYYYMMDD_Eval表画像.zip` にまとめます。

`.github/workflows/eval_media_manual.yml` の `workflow_dispatch` は人間操作用の予備経路です。直接Python実行はデバッグ・緊急時の補助経路とします。

## Eval表OCR

本体は `src/extract_eval_table.py` と `src/eval_ocr/` です。通常出力CSVの契約は `date,venue,race_no,horse_no,eval` の5列です。

馬名セル画像は行存在判定には使用しますが、馬名文字列のTesseract OCRは通常処理では行いません。会場名ヘッダーOCR、Eval数値OCR、色付き上位セル・同色tieを含む色検証は維持します。

正式馬名・レース属性・馬属性は後段のJRDB PACI enrichmentが `date + venue + race_no + horse_no` をキーに付与します。Eval OCRは識別キーとEval値の取得に責務を限定します。

Chatから取得済みartifactをOCRする場合は `.github/workflows/eval_ocr_chat.yml` の `[EVAL_OCR_REQUEST]` Issue経路を使用します。日常開催でユーザーがEval表画像を直接渡す運用では、画像取得工程は不要で、OCR/CSV化から開始します。

## Chat画像 -> 完成CSV

ChatへユーザーがEval表画像または画像ZIPを直接渡しCSV化を依頼した場合、通常の最終成果物は5列OCR CSVではなく **JRDB PACI事前情報まで付与した完成CSV** とします。OCRのみを明示された場合だけ5列で停止します。

標準フロー:

```text
ユーザー画像
  -> Chat実行環境でGitHub mainのOCRロジックを使用
  -> 5列OCR CSV
  -> gzip + Base64 payload
  -> [EVAL_PACI_ENRICH_REQUEST] Issue
  -> .github/workflows/eval_paci_enrich_chat.yml
  -> 対象日PACIyymmdd.zipをActions側で取得
  -> horse-racing/jrdb/src/enrich_eval_csv_with_paci.py
  -> JRDB事前情報付き完成CSV artifact
  -> Chatが回収してユーザーへ返却
```

直接アップロードされた画像自体はGitHubへ永続化しません。GitHubへ渡すのはOCR後の5列CSVを圧縮・Base64化したpayloadのみです。PACIはユーザーへ再添付を求めず、Actions側の `JRDB_USER` / `JRDB_PASSWORD` secretで取得します。

`[EVAL_PACI_ENRICH_REQUEST]` は複数日を受け付け、日付ごとにPACIを取得・結合して最終CSVを1本にまとめます。既定で `fail_on_unmatched=true` とし、`joined_horses == input_rows`、`unmatched_horses == 0`、`duplicate_keys == 0` を通常成功条件として確認します。`race_headcount_mismatches` は警告監査として必ず報告します。

## JRA結果取得

本体は `src/fetch_jra_daily_results.py`。取得後は `src/validate_jra_results.py` で検証します。

Chatからの定型取得は `.github/workflows/jra_results_chat.yml` を標準経路とします。Chatがタイトル `[JRA_RESULTS_REQUEST] <request_id>` のGitHub Issueを作成し、本文JSONに対象日を記載すると、Issue作成イベントでActionsが起動します。

ActionsはGit正本のPythonと `requirements.txt` を使用して取得・検証します。完了後、同じIssueへ `JRA_RESULTS_RESULT` コメントとして `run_id`、artifact名、fetch/validation終了コード、validator結果を返し、Issueを自動クローズします。Chatはこのコメントを完了通知として利用し、必要に応じてartifactを回収します。

このIssue経路を日常運用の第一選択とし、Chat実行環境からの直接HTTPS通信や `workflow_dispatch` 起動APIには依存しません。

`.github/workflows/jra_results_manual.yml` の `workflow_dispatch` は人間操作用の予備経路です。直接Python実行はデバッグ・緊急時の補助経路とします。

出走頭数は取消・競走除外前の枠順確定時の頭数を維持することが重要仕様です。

今後OCR・台帳取込等のモジュールが増えた場合も、このプロジェクト配下へ追加します。
