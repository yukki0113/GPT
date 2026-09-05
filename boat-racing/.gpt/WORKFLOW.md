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
8. 予想・販売選別の固定後、結果参照前に、出走表CSVの公式 `締切時刻` と `予想確定日時` / `販売選別確定日時` をレース単位で照合する。freeze日時が締切予定日時以後のレースは、予想・買い目・販売順位・掲載区分を変更せず `締切後freeze` として監査記録し、真正forward集計から分離する。この監査では結果ページを参照しない。
9. 検証用の固定スナップショットが必要な場合はGoogle Drive `analysis` へ保存する。
10. ここまで完了してから当該日の結果を参照する。
11. 結果確認後に予想、2連単1点、販売スコア、掲載区分を変更しない。
12. 結果測定では全対象と掲載群を分離し、的中率、ROI、1号艇1着率、2艇カバー率、内側1点的中率を記録する。掲載群は有料+無料のみとし、CSVのみは全対象には含めるが掲載成績へは含めない。
13. 構造KPIは条件付き分母とする。1号艇頭成功時のみ2着候補2艇カバーを評価し、2艇カバー成功時のみ内側1点成功を評価する。前段失敗時は後段を `対象外` とし、分母へ入れない。

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
- `販売記事台帳` の `対象日` は、現在日付や結果取込の実行日から生成しない。記事ID `YYYYMMDD`、対象データID、`販売掲載明細` の日付を照合して確定し、これらが不一致なら自動補正せず不整合として停止・報告する。
- `販売記事台帳` の `予想確定日時` / `販売選別確定日時` は事前freeze原本の日時を保持し、結果取込日時で上書きしない。集約行へ転記する場合は当該日の予想・販売選別原本から取得し、複数の異なるfreeze値がある場合は現在時刻で補完せず不整合として報告する。
- 日跨ぎ後に結果取込・台帳記帳を実行しても、システムの現在日付・現在時刻は `対象日` / `予想確定日時` / `販売選別確定日時` の生成元に使用しない。処理実行日時は変更履歴・取込ログ・監査記録にのみ使用する。
- ForwardTrialの `掲載対象投資額` / `掲載対象払戻額` / `掲載対象収支` / `掲載対象回収率` および販売記事台帳の全掲載成績は、有料+無料のみを対象とする。CSVのみはForwardTrial全対象成績には含めるが掲載成績には含めない。
- ForwardTrialの構造KPIは条件付き分母で記録し、失敗構造は `的中` / `1号艇頭失敗` / `2着候補2艇外` / `内側1点選択ミス` / `返還` / `対象外` を使用する。1号艇頭失敗時の2着候補カバー・内側1点、2着候補2艇外時の内側1点は `対象外` とする。
- 出走表CSVの公式 `締切時刻` とfreeze日時を照合し、締切後freezeのレースはデータを削除・改変せず監査注記を残し、真正forward集計から分離する。
- ForwardTrial結果取込後は、少なくとも `記事ID→対象日`、`明細日付→対象日`、`事前freeze→販売記事台帳freeze`、`有料+無料→全掲載成績`、`全対象→ForwardTrial集計`、構造KPIの条件付き分母を相互再集計して一致確認してから完了とする。
- Google Driveに残る旧Excel版 `競艇note販売運用台帳.xlsx` と GitHub `boat-racing/ledger/競艇note販売運用台帳.xlsx` は移行前スナップショットとして扱い、通常運用では参照・更新しない。
- `.gpt/tools/gpt_git_binary_tool.py`、`[gpt-git-binary-read]`、`[gpt-git-binary-update]` はGit管理バイナリ用の共通補助経路として残すが、この台帳の同期には使用しない。
- Googleスプレッドシート正本へアクセスできない場合は、旧Excelを最新と推定せず正本取得不能として扱う。
