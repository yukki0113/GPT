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

## Chat画像からJRDB事前情報付き完成CSV

13. ユーザーがChatへEval表画像または画像ZIPを直接渡し「CSV化」「画像からCSV」等を依頼した場合、通常はOCR 5列で止めず、JRDB PACI enrichmentまで連続実行して完成CSVを返す。OCRのみが明示された場合は5列CSVで停止してよい。
14. 直接アップロードされた画像はGitHubへ永続化せず、Chat実行環境でGitHub `main` の `src/extract_eval_table.py` / `src/eval_ocr/` と同等の正本ロジックを使ってOCRする。日付が画像・ファイル名・依頼文から決定できない場合だけ確認する。
15. OCR成功条件は通常のOCR検証と同じとし、5列 `date,venue,race_no,horse_no,eval` を中間成果物として確定する。複数画像・複数日では全日分を1本の5列CSVへまとめてよい。
16. 5列CSVのUTF-8テキストをgzip圧縮し、そのbytesをBase64化する。タイトル `[EVAL_PACI_ENRICH_REQUEST] <request_id>` のIssueを作成し、本文をraw JSONで次の契約にする。

```json
{
  "eval_csv_gzip_b64": "<gzip+Base64 payload>",
  "output_name": "eval_YYYYMMDD_enriched.csv",
  "fail_on_unmatched": true
}
```

17. `output_name` は省略可能。単日なら `eval_YYYYMMDD_enriched.csv`、複数日なら `eval_YYYYMMDD_YYYYMMDD_enriched.csv` がworkflow側の既定名となる。通常は `fail_on_unmatched=true` を使う。
18. `.github/workflows/eval_paci_enrich_chat.yml` はOCR CSV内の日付ごとに `horse-racing/jrdb/src/fetch_jrdb_paci.py` でPACIyymmdd.zipを取得し、`horse-racing/jrdb/src/enrich_eval_csv_with_paci.py` で正式馬名・レース条件・馬単位事前情報を付与する。Analysis Lite / Core / SEDは使用しない。
19. ChatはIssueの `EVAL_PACI_ENRICH_RESULT` コメントを完了通知として読み、`fetch_exit_code=0`、`enrich_exit_code=0`、`collect_exit_code=0` を通常成功条件とする。さらにsummaryで `joined_horses == input_rows`、`unmatched_horses == 0`、`duplicate_keys == 0` を確認する。
20. `race_headcount_mismatches` は警告監査であり、0でなければ完成CSVと一緒に内容をユーザーへ明示する。未結合がある場合は推測結合せず、artifactを確認して原因を切り分ける。
21. 結果コメントの `run_id` と `artifact_name` を使ってartifactを回収し、通常のユーザー返却物はJRDB事前情報付き完成CSVとする。元5列OCR CSV、batch audit、日付別audit/logは監査用補助成果物として扱う。
22. PACI ZIPをユーザーへ再添付依頼しない。Actions側の `JRDB_USER` / `JRDB_PASSWORD` secretsで取得する。直接アップロード画像そのものをIssue本文やGitへ保存しない。

## JRA結果取得

23. ChatからJRA結果取得を依頼された場合は、原則として `.github/workflows/jra_results_chat.yml` のIssue経路を使用する。
24. 一意の `request_id` を生成し、タイトル `[JRA_RESULTS_REQUEST] <request_id>` のIssueを作成する。Issue本文はJSONで、`dates` または `date_from` + `date_to`、必要に応じて `request_interval_seconds` を指定する。
25. ActionsはIssue作成をトリガーにGit正本の `src/fetch_jra_daily_results.py` を実行し、`src/validate_jra_results.py` で機械検証する。
26. Chatは対象Issueのコメントを確認し、`JRA_RESULTS_RESULT` コメントを完了通知として読む。`fetch_exit_code=0`、`validation_exit_code=0`、`validation.validation_status=success` を必須成功条件とする。
27. 結果コメントの `run_id` と `artifact_name` を使い、必要に応じてartifactを回収する。成果物のユーザー返却が不要な依頼では、検証結果だけを報告してよい。
28. IssueはActionsが完了時に自動クローズする。失敗時も結果情報を残してクローズし、Chat側で原因を確認する。
29. `.github/workflows/jra_results_manual.yml` の `workflow_dispatch` は人間操作用の予備経路。Chat/ローカルからの直接Python実行はデバッグ・緊急時の補助経路であり、日常運用の第一選択にしない。
30. JRA結果CSVでは全行成功、キー重複なし、出走頭数、1〜3着、単勝・複勝等を確認する。
31. 出走頭数は取消・競走除外前の枠順確定時の頭数を維持する。着順が数値の行だけで数えない。

## 共通

32. 継続台帳の正本はネイティブGoogleスプレッドシート `Eval表集計・検証`（Spreadsheet ID `1XBOYZrtJFLfY0Q3EmLfImJvughyXdAvdsLnmix8hgo0`）とする。参照・更新はGoogle Drive / Google Sheetsのネイティブスプレッドシート操作で同一Spreadsheet IDへ直接行う。
33. 旧Google Drive Excel版 `Eval表集計・検証.xlsx`（file ID `1EMuKPhyWIiplohWFWbqnIGNmoXMPe0R_`）およびGitHub `horse-racing/eval/ledger/Eval表集計・検証.xlsx` は移行前スナップショットとして扱う。通常運用では `.gpt/tools/gpt_git_binary_tool.py`、`[gpt-git-binary-read]`、`[gpt-git-binary-update]` をEval台帳同期目的に使用しない。
34. ネイティブGoogleスプレッドシート正本へアクセスできない場合は、旧Drive Excel版やGitHub旧スナップショットを最新と推定せず、正本取得不能として扱う。
35. 台帳更新時は必要範囲だけをGoogle Sheets上で更新し、数式・書式・既存集計を維持する。Excel書き出し→再アップロードを通常更新経路にしない。
36. 画像、日次CSV、検証レポート、ログ等の運用成果物は引き続きcommitしない。
37. PythonやWorkflowを改修した場合は対応READMEも同時に更新する。実動テストを行う場合は、日次成果物をGitへcommitせず、テスト条件と結果だけを記録する。
38. Eval `全馬データ` へJRDB SED結果を取り込む依頼では、`docs/README_jrdb_horse_results_import.md` を標準手順として、Google Drive Raw取得 → 馬単位CSV/audit生成 → Google Sheets厳密照合・必要セル更新 → 更新後監査まで実行する。
