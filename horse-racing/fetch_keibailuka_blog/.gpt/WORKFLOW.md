# keibailuka GPT workflow

1. GitHub `main` の最新状態を確認する。
2. `horse-racing/fetch_keibailuka_blog/README.md`、`.gpt/CONTEXT.md`、本ファイル、対象Pythonを確認する。
3. このツールはJRDB / Evalとは独立したブログ予想取得ツールとして扱い、資産を他領域へ混在させない。

## 日次ブログ解析

4. ユーザーから通常受け取るのは対象日と開催場順だけとする。個別記事URLの探索・提示を求めない。
5. 一意の `request_id` を生成し、タイトル `[KEIBAILUKA_REQUEST] <request_id>` のIssueを作成する。
6. Issue本文はJSONとし、`date` と `venues` を渡す。最終出力はR昇順とし、同一R内では `venues` の配列順を維持する。
7. `.github/workflows/keibailuka_chat.yml` がIssue作成をトリガーに `horse-racing/fetch_keibailuka_blog/src/fetch_keibailuka_blog.py` を実行する。
8. モジュール側ではBlogger公開feed本文を第一選択とし、ブログトップ、月別アーカイブ、ブログ内検索、個別記事通常表示、`?m=1` をfallbackとして使う。
9. 各開催場の記事に1R〜12Rが順番どおり12個存在することを必須条件とする。構造不一致や馬名を安全に確定できないRがある場合は推測補完せずfailureとする。
10. `該当無し` は除外する。`勝負レース` やnote有料記事への導入も除外する。`🤡` は馬名欄を `🤡` として残し、公開されているコメントだけを採用する。
11. 対象Issueの `KEIBAILUKA_RESULT` コメントを完了通知として読む。`fetch_exit_code=0`、`validation_exit_code=0`、`validation.validation_status=success` を必須成功条件とする。
12. 成功時は結果コメント内の `entries` またはPlain text TSVを基に、`場所 / R / 馬名 / コメント` を1R→12R順、同一R内は依頼された開催場順でコードブロックとして返す。
13. 同じ成功runのartifactから `keibailuka_YYYYMMDD.csv` を回収し、コードブロックに加えてCSV成果物として返す。CSV列は `日付 / 会場 / R / 馬名 / コメント` とする。
14. 長いコメントだけ意味を変えない範囲でChat側が軽く要約する。Python側で意味を変える要約は行わない。
15. CSV回収または詳細な障害調査・生データ確認では、RESULTの `run_id` と `artifact_name` を完全一致で使ってartifactを回収する。値を推測しない。
16. ユーザーから記事URLが提示された場合も恒常的な入力仕様には変更せず、取得障害やブログ仕様変更の調査材料としてのみ扱う。

## 改修

17. PythonやWorkflowを改修する場合はREADME / `.gpt` の記載も同時に確認・更新する。
18. 改修後は実日付で回帰確認し、少なくとも1R〜12R構造、除外判定、🤡保持、R優先順、CSV列・日付を確認する。
19. 日次JSON / TSV / CSV、validation、ログ、artifactはGitへcommitしない。
