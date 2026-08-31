# Boat racing GPT workflow

1. READMEと対象ツールのdocsを確認。
2. 公式サイト側の変更に注意し、既存CSV互換性を維持する。
3. 改修後は実日付または保存済みfixtureで回帰確認。
4. キャッシュ、日次成果物、ログ、継続台帳はcommitしない。継続台帳はネイティブGoogleスプレッドシート `競艇note販売運用台帳` を正本とする。
5. Pythonと対応READMEを同時に更新してcommitする。

## 2026-09-01以降の前向き予想試行

日次予想を依頼された場合は、GitHub `main` の以下を開始時に確認する。

1. `boat-racing/README.md`
2. `boat-racing/.gpt/CONTEXT.md`
3. `boat-racing/.gpt/WORKFLOW.md`
4. `boat-racing/docs/競艇AI予想_2連単1点前向き試行仕様書_Ver0.1.md`
5. `boat-racing/docs/競艇AI予想_事前予想仕様書_Ver1.2.1.md`

`ForwardTrial_Ver0.1` の日次処理順は以下とする。

1. Google Drive `data/racecards` の当該日公式出走表だけを取得する。
2. 当該日の `results`、既存結果台帳、外部予想、SNS、展示・直前情報を参照しない。
3. `ForwardTrial_Ver0.1` で全対象Rの事前予想を新規生成する。
4. 24列事前予想CSVと26列予想根拠明細CSVを確定する。
5. 正式A・1号艇軸の対象から2連単1点を仕様通り生成する。
6. 2連単1点専用販売スコアを計算し、有料・無料・CSVのみを結果参照前に固定する。
7. 日次原本をGoogle Drive `data` の対応フォルダへ保存する。
8. 検証用の固定スナップショットが必要な場合はGoogle Drive `analysis` へ保存する。
9. ここまで完了してから当該日の結果を参照する。
10. 結果確認後に予想、2連単1点、販売スコア、掲載区分を変更しない。
11. 結果測定では全対象と掲載群を分離し、的中率、ROI、1号艇1着率、2艇カバー率、内側1点的中率を記録する。

日次Google Drive正本:

- data Folder ID: `11OtFNwroVbgV8BClzoepTKoa81fQJ-A1`
- analysis Folder ID: `19aHo7aKIp0G01SIkk7fcI_uktyaWhW2q`

## Chatでの日次取得実行

- まずGitHub `main` の `boat-racing/` を正本として確認する。
- Chatからの定型実行は、GitHub Issue経由を標準経路とする。
- 出走表取得は `.github/workflows/boatrace_racelist_issue.yml` を使用する。
- Issue title は `[BOATRACE_RACELIST_REQUEST] <request_id>`、Issue本文はraw JSONとする。
- Workflowは `main` の `boat-racing/src/fetch_boatrace_racelist.py` と `boat-racing/requirements.txt` をそのまま使用し、独自ロジックを別実装しない。
- Issueコメントの `BOATRACE_RACELIST_RESULT` JSONから `status` / `run_id` / `artifact_name` を取得し、artifactを回収する。
- artifact内の `resolved_request.json`、`run_status.txt`、`validation_report.json`、取得状況・ログ・CSVを確認してから日常成果物を受け渡す。
- Request Issueは処理終了後に自動Closeする。
- 失敗時もartifactとRESULTコメントを残し、診断可能にする。
- `.github/workflows/boatrace_racelist_manual.yml` は手動フォールバックとして残すが、Chatからの日常実行ではIssue経由を優先する。
- 日次成果物はGitへcommitしない。

## Google Sheets台帳正本の更新・取得

- 継続台帳の正本はネイティブGoogleスプレッドシート `競艇note販売運用台帳` とする。
- Spreadsheet ID: `1gEAYJ90Zv3HDi5gh_at0jDWEQrgCSB5tIywJFZjXcFM`
- URL: `https://docs.google.com/spreadsheets/d/1gEAYJ90Zv3HDi5gh_at0jDWEQrgCSB5tIywJFZjXcFM/edit`
- タイムゾーンは `Asia/Tokyo` とする。
- Chat / Workで台帳を解析する場合はGoogle Sheets API / Google Drive Connectorで正本を直接参照する。
- 更新時は同一ネイティブGoogleスプレッドシートへ直接反映し、必要なキー照合・既存データ不変確認・数式エラー確認を行う。
- Google Driveに残る旧Excel版 `競艇note販売運用台帳.xlsx` と GitHub `boat-racing/ledger/競艇note販売運用台帳.xlsx` は移行前スナップショットとして扱い、通常運用では参照・更新しない。
- `.gpt/tools/gpt_git_binary_tool.py`、`[gpt-git-binary-read]`、`[gpt-git-binary-update]` はGit管理バイナリ用の共通補助経路として残すが、この台帳の同期には使用しない。
- Googleスプレッドシート正本へアクセスできない場合は、旧Excelを最新と推定せず正本取得不能として扱う。
