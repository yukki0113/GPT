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

## JRA結果取得の標準実行経路

Chatからの依頼では `.github/workflows/jra_results_chat.yml` を標準経路とします。

Chatは専用Issueを作成します。

- タイトル: `[JRA_RESULTS_REQUEST] <request_id>`
- 本文: 日付条件等を記したJSON

Issue作成をトリガーにGitHub Actionsが起動し、Git正本のPythonと `horse-racing/eval/requirements.txt` を使って取得・検証します。

完了時はActionsが同じIssueへ `JRA_RESULTS_RESULT` 形式の機械可読コメントを返し、Issueを自動で閉じます。コメントには `run_id`、artifact名、fetch/validation終了コード、validator結果が含まれます。Chatはそのコメントを読み、必要に応じてartifactを回収します。

これにより、Chat側の外部HTTPS通信可否や `workflow_dispatch` 起動APIの有無に依存せず、Chatから定型取得を開始・追跡できます。

## 予備経路

- `.github/workflows/jra_results_manual.yml` — 人間がGitHub UIから `workflow_dispatch` する場合の予備経路
- Chat/ローカルから `fetch_jra_daily_results.py` を直接実行 — デバッグ・緊急時の補助経路

日常運用ではChat専用Issue経路を優先します。

取得後は `validate_jra_results.py` で検証します。CSV・検証レポート・実行状態はartifact化し、日次成果物はGitへcommitしません。
