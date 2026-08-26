# Eval GPT workflow

1. GitHub `main` の最新状態を確認する。
2. `horse-racing/eval/README.md`、`.gpt/CONTEXT.md`、本ファイル、対象モジュールのdocs、対象Pythonを確認する。
3. 既存入出力仕様と重要な業務仕様を維持して実行・改修する。

## Eval表画像取得

4. ChatからEval表画像取得を依頼された場合は、原則として `.github/workflows/eval_media_chat.yml` のIssue経路を使用する。
5. ユーザーから通常は対象日だけを受け取り、Chat側で `@master_eval` の対象投稿を探索して投稿IDを確定する。投稿URLまたは投稿IDが与えられている場合は探索を省略してよい。
6. 一意の `request_id` を生成し、タイトル `[EVAL_MEDIA_REQUEST] <request_id>` のIssueを作成する。Issue本文はJSONとし、対象日と投稿IDの対応を `targets` で渡す。`dates` + `post_ids` の同数配列も利用できる。
7. ActionsはIssue作成をトリガーにGit正本の `src/master_eval_media_collector.py` を実行し、投稿ID別のmetadataとmedia、`resolved_request.json`、`validation_report.json`、`run_status.txt` をartifact化する。
8. Chatは対象Issueの `EVAL_MEDIA_RESULT` コメントを完了通知として読む。`fetch_exit_code=0`、`validation_exit_code=0`、`validation.validation_status=success` を取得工程の成功条件とする。
9. 結果コメントの `run_id` と `artifact_name` を使ってartifactを回収する。
10. artifact内の画像をChatが内容確認し、Eval表本体のみ採用する。注意事項・説明・告知画像を除外する。`media_01` がEval表であることは多いが固定仕様として扱わない。
11. 採用画像を日付が分かる名前に整理し、最終成果物 `eval_YYYYMMDD_YYYYMMDD_Eval表画像.zip` を作成する。通常の土日2日分ならEval表画像2枚を最終ZIPに含める。
12. `.github/workflows/eval_media_manual.yml` の `workflow_dispatch` は人間操作用の予備経路。Chat/ローカルからの直接Python実行はデバッグ・緊急時の補助経路であり、日常運用の第一選択にしない。

## JRA結果取得

13. ChatからJRA結果取得を依頼された場合は、原則として `.github/workflows/jra_results_chat.yml` のIssue経路を使用する。
14. 一意の `request_id` を生成し、タイトル `[JRA_RESULTS_REQUEST] <request_id>` のIssueを作成する。Issue本文はJSONで、`dates` または `date_from` + `date_to`、必要に応じて `request_interval_seconds` を指定する。
15. ActionsはIssue作成をトリガーにGit正本の `src/fetch_jra_daily_results.py` を実行し、`src/validate_jra_results.py` で機械検証する。
16. Chatは対象Issueのコメントを確認し、`JRA_RESULTS_RESULT` コメントを完了通知として読む。`fetch_exit_code=0`、`validation_exit_code=0`、`validation.validation_status=success` を必須成功条件とする。
17. 結果コメントの `run_id` と `artifact_name` を使い、必要に応じてartifactを回収する。成果物のユーザー返却が不要な依頼では、検証結果だけを報告してよい。
18. IssueはActionsが完了時に自動クローズする。失敗時も結果情報を残してクローズし、Chat側で原因を確認する。
19. `.github/workflows/jra_results_manual.yml` の `workflow_dispatch` は人間操作用の予備経路。Chat/ローカルからの直接Python実行はデバッグ・緊急時の補助経路であり、日常運用の第一選択にしない。
20. JRA結果CSVでは全行成功、キー重複なし、出走頭数、1〜3着、単勝・複勝等を確認する。
21. 出走頭数は取消・競走除外前の枠順確定時の頭数を維持する。着順が数値の行だけで数えない。

## 共通

22. 画像、日次CSV、検証レポート、ログ等の運用成果物はcommitしない。ただし継続台帳 `ledger/Eval表集計・検証.xlsx` はGit管理対象とし、更新は最新mainを基準に `[gpt-git-binary-update]` Issue経路で反映する。
23. PythonやWorkflowを改修した場合は対応READMEも同時に更新する。実動テストを行う場合は、日次成果物をGitへcommitせず、テスト条件と結果だけを記録する。
