# Eval project context

## Status

Active。Eval表の画像取得、結果取得、OCR/検証・台帳更新を支援する領域です。

## Source of truth

Python、README、作業手順、依存関係、GitHub Actions WorkflowはGitHub `yukki0113/GPT` の `main` を正本とします。

Eval画像、OCR途中成果物、Excel運用台帳、日次取得CSV、検証レポート、ログ等の運用成果物はGit外を正本とします。

## JRA結果取得

本体は `src/fetch_jra_daily_results.py`。取得後は `src/validate_jra_results.py` で検証します。

Chatからの定型取得は `.github/workflows/jra_results_chat.yml` を標準経路とします。Chatがタイトル `[JRA_RESULTS_REQUEST] <request_id>` のGitHub Issueを作成し、本文JSONに対象日を記載すると、Issue作成イベントでActionsが起動します。

ActionsはGit正本のPythonと `requirements.txt` を使用し、CSV・検証レポート・実行状態をartifact化します。完了後、同じIssueへ `JRA_RESULTS_RESULT` コメントとして `run_id`、artifact名、fetch/validation終了コード、validator結果を返し、Issueを自動クローズします。Chatはこのコメントを完了通知として利用し、必要に応じてartifactを回収します。

このIssue経路を日常運用の第一選択とし、Chat実行環境からの直接HTTPS通信や `workflow_dispatch` 起動APIには依存しません。

`.github/workflows/jra_results_manual.yml` の `workflow_dispatch` は人間操作用の予備経路です。直接Python実行はデバッグ・緊急時の補助経路とします。

出走頭数は取消・競走除外前の枠順確定時の頭数を維持することが重要仕様です。

今後OCR・台帳取込等のモジュールが増えた場合も、このプロジェクト配下へ追加します。
