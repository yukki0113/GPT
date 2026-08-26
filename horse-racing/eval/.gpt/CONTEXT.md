# Eval project context

## Status

Active。Eval表の画像取得、結果取得、OCR/検証・台帳更新に加え、関連する中央競馬の定型データ取得・解析を支援する領域です。

## Source of truth

Python、README、作業手順、依存関係、GitHub Actions WorkflowはGitHub `yukki0113/GPT` の `main` を正本とします。

Eval画像、OCR途中成果物、日次取得CSV、ブログ解析結果、検証レポート、ログ等の運用成果物はGit外を正本とします。ただし継続台帳 `ledger/Eval表集計・検証.xlsx` はGitHub `main` を正本とします。

## Eval表画像取得

本体は `src/master_eval_media_collector.py`。このPythonはX/Twitterの投稿IDを受け取り、添付メディアを取得します。日付から投稿IDを探索する機能と、Eval表本体・注意事項画像の内容分類機能は持ちません。

Chatからの定型取得は `.github/workflows/eval_media_chat.yml` のIssue経路を標準とします。Chatが対象日の `@master_eval` 投稿を探索して投稿IDを確定し、タイトル `[EVAL_MEDIA_REQUEST] <request_id>` のGitHub Issueを作成します。Issue本文JSONには対象日と投稿IDの対応を記載します。

ActionsはIssue作成をトリガーにGit正本の `src/master_eval_media_collector.py` を実行し、投稿ID別の `metadata.json` と `media_XX.*`、`resolved_request.json`、`validation_report.json`、`run_status.txt` をartifact化します。

完了後、同じIssueへ `EVAL_MEDIA_RESULT` コメントとして `run_id`、artifact名、fetch/validation終了コード、対象日・投稿ID、検証結果を返し、Issueを自動クローズします。Chatはこのコメントを完了通知として利用し、artifactを回収します。

Actions側の検証は各投稿でmetadataと1枚以上のmediaが取得できたかまでです。Eval表本体と注意事項・説明画像の分類はChatがartifact回収後に画像内容を見て行い、Eval表のみを `eval_YYYYMMDD_YYYYMMDD_Eval表画像.zip` にまとめます。

`.github/workflows/eval_media_manual.yml` の `workflow_dispatch` は人間操作用の予備経路です。直接Python実行はデバッグ・緊急時の補助経路とします。

## JRA結果取得

本体は `src/fetch_jra_daily_results.py`。取得後は `src/validate_jra_results.py` で検証します。

Chatからの定型取得は `.github/workflows/jra_results_chat.yml` を標準経路とします。Chatがタイトル `[JRA_RESULTS_REQUEST] <request_id>` のGitHub Issueを作成し、本文JSONに対象日を記載すると、Issue作成イベントでActionsが起動します。

ActionsはGit正本のPythonと `requirements.txt` を使用し、CSV・検証レポート・実行状態をartifact化します。完了後、同じIssueへ `JRA_RESULTS_RESULT` コメントとして `run_id`、artifact名、fetch/validation終了コード、validator結果を返し、Issueを自動クローズします。Chatはこのコメントを完了通知として利用し、必要に応じてartifactを回収します。

このIssue経路を日常運用の第一選択とし、Chat実行環境からの直接HTTPS通信や `workflow_dispatch` 起動APIには依存しません。

`.github/workflows/jra_results_manual.yml` の `workflow_dispatch` は人間操作用の予備経路です。直接Python実行はデバッグ・緊急時の補助経路とします。

出走頭数は取消・競走除外前の枠順確定時の頭数を維持することが重要仕様です。

## keibailukaブログ解析

本体は `src/fetch_keibailuka_blog.py`。対象日と開催場順を受け取り、`keibailuka.blogspot.com` の対象記事URLを自動探索し、各場1R〜12Rを解析します。

通常運用ではユーザーに個別記事URLの探索・提示を求めません。URLがユーザーから提示された場合も、取得障害やブログ仕様変更を調べるための一時的な参考情報として扱い、恒常的な入力仕様にはしません。

Chatからの定型解析は `.github/workflows/keibailuka_chat.yml` のIssue経路を標準とします。Chatがタイトル `[KEIBAILUKA_REQUEST] <request_id>` のIssueを作成し、本文JSONへ `date` と `venues` を記載します。`venues` の配列順は最終出力の開催場順でもあります。

ActionsはGit正本のPythonを実行し、Blogger公開feed、ブログトップ、月別アーカイブ、ブログ内検索を使って記事を探索します。個別記事は通常表示とモバイル表示を試し、429/5xxは間隔を置いて再試行します。

各記事は1R〜12Rの構造を機械検証し、`該当無し` と有料導入を除外、`🤡` は `🤡` のまま公開コメントだけを残します。安全に馬名を確定できない場合は推測せずfailureとします。

完了後は同じIssueへ `KEIBAILUKA_RESULT` コメントとしてsource URL、採用entries、Plain text TSV、validation結果、run/artifact情報を返し、Issueを自動クローズします。Chatは原則としてこの結果コメントからユーザー向けの最終出力を作り、コメントが長い場合のみ意味を保った軽い要約を行います。

日次のブログ解析JSON/TSV、validation、ログはGit管理対象外です。

今後OCR・台帳取込等のモジュールが増えた場合も、このプロジェクト配下へ追加します。
