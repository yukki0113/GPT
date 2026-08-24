# Eval表活用

中央競馬のEval表取得・検証運用を支援するPythonツール群です。

## Source of truth

GitHub `yukki0113/GPT` の `main` ブランチ配下 `horse-racing/eval/` をPython・README・作業手順の正本とします。

画像、OCR途中成果物、Excel運用台帳、日次CSV、ログ等の運用成果物はGit管理対象外です。

## Current tools

- `src/master_eval_media_collector.py` — X上のEval表メディア収集
- `src/fetch_jra_daily_results.py` — JRA日次結果・払戻取得
- `src/validate_jra_results.py` — JRA結果CSVの機械検証

各ツールの詳細は `docs/` を参照してください。

## Eval表画像取得の標準実行経路

Chatからの依頼では `.github/workflows/eval_media_chat.yml` のGitHub Issue経路を標準とします。

Chat側で対象日の `@master_eval` 投稿を探索し、対象日と投稿IDの対応を確定したうえで、専用Issueを作成します。

- タイトル: `[EVAL_MEDIA_REQUEST] <request_id>`
- 本文: 対象日と投稿IDを記したJSON

Issue作成をトリガーにGitHub Actionsが起動し、Git正本の `src/master_eval_media_collector.py` を実行します。取得結果は `resolved_request.json`、`validation_report.json`、`run_status.txt`、投稿ID別の `metadata.json` と `media_XX.*` を含むartifactとして保存します。

完了時はActionsが同じIssueへ `EVAL_MEDIA_RESULT` 形式の機械可読コメントを返し、Issueを自動で閉じます。コメントには `run_id`、artifact名、collection/validation終了コード、対象日と投稿ID、検証結果が含まれます。

Actions側の検証は「各投稿でmetadataと1枚以上のmediaを取得できたか」までです。Eval表本体と注意事項・説明画像の内容判定は自動化せず、Chatがartifact回収後に画像内容を確認して選別します。

最終成果物は従来どおり、Eval表画像だけを含む `eval_YYYYMMDD_YYYYMMDD_Eval表画像.zip` とします。

投稿ID探索自体は `master_eval_media_collector.py` の担当外です。標準運用ではChatがWeb検索等で投稿IDを確定してからIssueを作成します。

## JRA結果取得の標準実行経路

Chatからの依頼では `.github/workflows/jra_results_chat.yml` を標準経路とします。

Chatは専用Issueを作成します。

- タイトル: `[JRA_RESULTS_REQUEST] <request_id>`
- 本文: 日付条件等を記したJSON

Issue作成をトリガーにGitHub Actionsが起動し、Git正本のPythonと `horse-racing/eval/requirements.txt` を使って取得・検証します。

完了時はActionsが同じIssueへ `JRA_RESULTS_RESULT` 形式の機械可読コメントを返し、Issueを自動で閉じます。コメントには `run_id`、artifact名、fetch/validation終了コード、validator結果が含まれます。Chatはそのコメントを読み、必要に応じてartifactを回収します。

これにより、Chat側の外部HTTPS通信可否や `workflow_dispatch` 起動APIの有無に依存せず、Chatから定型取得を開始・追跡できます。

## 予備経路

- `.github/workflows/eval_media_manual.yml` — Eval画像取得を人間がGitHub UIから `workflow_dispatch` する場合の予備経路
- `.github/workflows/jra_results_manual.yml` — JRA結果取得を人間がGitHub UIから `workflow_dispatch` する場合の予備経路
- Chat/ローカルから各Pythonを直接実行 — デバッグ・緊急時の補助経路

日常運用ではChat専用Issue経路を優先します。

日次画像、CSV、検証レポート、実行ログ等はGitへcommitしません。
