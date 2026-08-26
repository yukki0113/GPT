# keibailuka GPT workflow

1. GitHub `main` の最新状態を確認する。
2. `horse-racing/fetch_keibailuka_blog/README.md`、`.gpt/CONTEXT.md`、本ファイル、対象Pythonを確認する。
3. このツールはJRDB / Evalとは独立したブログ予想取得ツールとして扱い、資産を他領域へ混在させない。

## 日次ブログ解析

4. ユーザーから通常受け取るのは対象日と開催場順だけとする。個別記事URLの探索・提示を求めない。
5. 一意の `request_id` を生成し、タイトル `[KEIBAILUKA_REQUEST] <request_id>` のIssueを作成する。
6. Issue本文はJSONとし、`date` と `venues` を渡す。`venues` の配列順を最終回答の開催場順として維持する。
7. `.github/workflows/keibailuka_chat.yml` がIssue作成をトリガーに `horse-racing/fetch_keibailuka_blog/src/fetch_keibailuka_blog.py` を実行する。
8. モジュール側ではBlogger公開feed本文を第一選択とし、ブログトップ、月別アーカイブ、ブログ内検索、個別記事通常表示、`?m=1` をfallbackとして使う。
9. 各開催場の記事に1R〜12Rが順番どおり12個存在することを必須条件とする。構造不一致や馬名を安全に確定できないRがある場合は推測補完せずfailureとする。
10. `該当無し` は除外する。`勝負レース` やnote有料記事への導入も除外する。`🤡` は馬名欄を `🤡` として残し、公開されているコメントだけを採用する。
11. 対象Issueの `KEIBAILUKA_RESULT` コメントを完了通知として読む。`fetch_exit_code=0`、`validation_exit_code=0`、`validation.validation_status=success` を必須成功条件とする。
12. 成功時は結果コメント内の `entries` またはPlain text TSVを基に、`場所 / R / 馬名 / コメント` を依頼された開催場順、各場1R〜12R順で返す。
13. 長いコメントだけ意味を変えない範囲でChat側が軽く要約する。Python側で意味を変える要約は行わない。
14. 通常はIssueコメントだけで最終回答を構成する。詳細な障害調査や生データ確認が必要な場合のみ `run_id` と `artifact_name` を使ってartifactを回収する。
15. ユーザーから記事URLが提示された場合も恒常的な入力仕様には変更せず、取得障害やブログ仕様変更の調査材料としてのみ扱う。

## 改修

16. PythonやWorkflowを改修する場合はREADME / `.gpt` の記載も同時に確認・更新する。
17. 改修後は実日付で回帰確認し、少なくとも1R〜12R構造、除外判定、🤡保持、開催順を確認する。
18. 日次JSON / TSV、validation、ログ、artifactはGitへcommitしない。
