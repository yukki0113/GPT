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

## keibailukaブログ解析

22. Chatから `keibailuka.blogspot.com` の日次ブログ解析を依頼された場合は、原則として `.github/workflows/keibailuka_chat.yml` のIssue経路を使用する。
23. 通常入力は対象日と開催場順だけとし、ユーザーへ個別記事URLの探索・提示を求めない。ユーザーからURLが提示された場合も取得障害や仕様変更の調査材料としてのみ扱い、恒常的な入力仕様にはしない。
24. 一意の `request_id` を生成し、タイトル `[KEIBAILUKA_REQUEST] <request_id>` のIssueを作成する。Issue本文はJSONで `date` と `venues` を渡す。`venues` の配列順を最終回答の開催場順として維持する。
25. ActionsはIssue作成をトリガーにGit正本の `src/fetch_keibailuka_blog.py` を実行する。モジュール側でBlogger公開feed、ブログトップ、対象月・前月アーカイブ、ブログ内検索を利用して記事URLを探索する。個別記事は通常表示と `?m=1` を試し、429/5xxは間隔を置いて再試行する。
26. 各開催場の記事には1R〜12Rが順番どおり12個存在することを必須条件とする。構造不一致や馬名を安全に確定できないRがある場合は推測補完せずfailureとする。
27. `該当無し` は除外する。`勝負レース` や `note.com/keibailuka/n/` への有料導入も除外する。`🤡` は馬名欄を `🤡` として残し、公開されているコメントだけを採用する。
28. Chatは対象Issueの `KEIBAILUKA_RESULT` コメントを完了通知として読む。`fetch_exit_code=0`、`validation_exit_code=0`、`validation.validation_status=success` を必須成功条件とする。
29. 成功時は結果コメント内の `entries` またはPlain text TSVを基に、`場所 / R / 馬名 / コメント` を依頼された開催場順、各場1R〜12R順で返す。長いコメントだけ意味を変えない範囲でChat側が軽く要約する。
30. 通常はIssueコメントだけで最終回答を構成する。詳細な障害調査や生データ確認が必要な場合のみ `run_id` と `artifact_name` を使ってartifactを回収する。
31. 日次ブログ解析JSON/TSV、validation、実行ログはGitへcommitしない。

## 共通

32. 画像、日次CSV、ブログ解析結果、検証レポート、ログ等の運用成果物はcommitしない。ただし継続台帳 `ledger/Eval表集計・検証.xlsx` はGit管理対象とし、更新は最新mainを基準に `[gpt-git-binary-update]` Issue経路で反映する。
33. PythonやWorkflowを改修した場合は対応READMEも同時に更新する。実動テストを行う場合は、日次成果物をGitへcommitせず、テスト条件と結果だけを記録する。
