# Eval GPT workflow

1. GitHub `main` の最新状態を確認する。
2. `horse-racing/eval/README.md`、`.gpt/CONTEXT.md`、本ファイル、対象モジュールのdocs、対象Pythonを確認する。
3. 既存入出力仕様と重要な業務仕様を維持して実行・改修する。
4. ChatからJRA結果取得を依頼された場合は、原則として `.github/workflows/jra_results_chat.yml` のIssue経路を使用する。
5. 一意の `request_id` を生成し、タイトル `[JRA_RESULTS_REQUEST] <request_id>` のIssueを作成する。Issue本文はJSONで、`dates` または `date_from` + `date_to`、必要に応じて `request_interval_seconds` を指定する。
6. ActionsはIssue作成をトリガーにGit正本の `src/fetch_jra_daily_results.py` を実行し、`src/validate_jra_results.py` で機械検証する。
7. Chatは対象Issueのコメントを確認し、`JRA_RESULTS_RESULT` コメントを完了通知として読む。`fetch_exit_code=0`、`validation_exit_code=0`、`validation.validation_status=success` を必須成功条件とする。
8. 結果コメントの `run_id` と `artifact_name` を使い、必要に応じてartifactを回収する。成果物のユーザー返却が不要な依頼では、検証結果だけを報告してよい。
9. IssueはActionsが完了時に自動クローズする。失敗時も結果情報を残してクローズし、Chat側で原因を確認する。
10. `.github/workflows/jra_results_manual.yml` の `workflow_dispatch` は人間操作用の予備経路。Chat/ローカルからの直接Python実行はデバッグ・緊急時の補助経路であり、日常運用の第一選択にしない。
11. JRA結果CSVでは全行成功、キー重複なし、出走頭数、1〜3着、単勝・複勝等を確認する。
12. 出走頭数は取消・競走除外前の枠順確定時の頭数を維持する。着順が数値の行だけで数えない。
13. 画像、Excel、日次CSV、検証レポート、ログ等の運用成果物はcommitしない。
14. PythonやWorkflowを改修した場合はサンプル日付で実動テストし、対応READMEも同時に更新してcommitする。
