# Boat racing GPT workflow

1. README、`.gpt/HANDOFF.md`、対象ツールのdocsを確認。
2. GitHub作業は開始時に A: Read / Audit、B: Git Change、C: Pure Deterministic Execution、D: Actions-Native Execution の4系統へ分類し、最短かつ再現可能な経路を選ぶ。
3. 公式サイト側の変更に注意し、既存CSV互換性を維持する。
4. 改修後は実日付または保存済みfixtureで回帰確認。
5. キャッシュ、日次成果物、ログ、継続台帳はcommitしない。継続台帳はネイティブGoogleスプレッドシート `競艇note販売運用台帳` を正本とする。
6. source / test / docs / config / workflow等のUTF-8テキスト変更は、latest main、path存在、現内容を確認してからGitHub direct create/update/deleteでremote commitを作成する。Git変更だけを目的としたIssueは原則使用しない。
7. Git正本moduleと必要入力をChat側で取得でき、secret・特殊runner・Actions監査証跡が不要で計算量が許容範囲ならGPTローカル実行を優先する。可能な限り source commit / source file SHA256 / input SHA256 / generated_at / output SHA256 を残す。
8. IssueはSecrets、認証付き外部取得、Actions artifact chain、長時間・大容量処理、runner環境自体が仕様、immutable freeze、監査run、または正本moduleをChatローカルで同一条件実行できない処理に限定する。

## 2026-09-01以降の前向き予想試行

日次予想を依頼された場合は、GitHub `main` の以下を開始時に確認する。

1. `boat-racing/README.md`
2. `boat-racing/.gpt/CONTEXT.md`
3. `boat-racing/.gpt/HANDOFF.md`
4. `boat-racing/.gpt/WORKFLOW.md`
5. `boat-racing/docs/競艇AI予想_2連単1点前向き試行仕様書_Ver0.1.md`
6. `boat-racing/docs/競艇AI予想_事前予想仕様書_Ver1.2.1.md`

`ForwardTrial_Ver0.1` の日次処理順は以下とする。

1. Google Drive `data/racecards` の当該日公式出走表だけを取得する。ユーザーが当該日の公式出走表CSVを添付している場合は、その添付原本を入力候補として優先し、対象日・会場集合・件数・必須列を検証する。
2. 当該日の `results`、既存結果台帳、外部予想、SNS、展示・直前情報を参照しない。
3. GitHub `main` の `src/forward_trial_predict.py` を正本moduleとして、`ForwardTrial_Ver0.1` で全対象Rの事前予想を新規生成する。Chat内に別実装を作らない。
4. 24列事前予想CSVと26列予想根拠明細CSVを同一freeze時点で確定する。予想根拠明細は任意説明資料ではなく日次正本成果物とする。
5. 正式A・1号艇軸の対象から2連単1点を仕様通り生成する。
6. 2連単1点専用販売スコアを計算し、21列販売選別CSVの有料・無料・CSVのみを結果参照前に固定する。
7. 標準ユーザー向け成果物は、事前予想CSV・予想根拠明細CSV・販売選別CSVの3ファイルとする。moduleが生成するmanifestは監査・再現性の補助物であり、この3点には数えない。
8. 日次原本をGoogle Drive `data` の対応フォルダへ保存する。ユーザーが表示物を一時的に絞った場合でも、正本保存では3CSVの整合性を維持する。
9. 予想・販売選別の固定後、結果参照前に、出走表CSVの公式 `締切時刻` と `予想確定日時` / `販売選別確定日時` をレース単位で照合する。freeze日時が締切予定日時以後のレースは、予想・買い目・販売順位・掲載区分を変更せず `締切後freeze` として監査記録し、真正forward集計から分離する。この監査では結果ページを参照しない。
10. 検証用の固定スナップショットが必要な場合はGoogle Drive `analysis` へ保存する。
11. ここまで完了してから当該日の結果を参照する。
12. 結果確認後に予想、予想根拠、2連単1点、販売スコア、掲載区分を再生成・変更しない。
13. 結果測定では全対象と掲載群を分離し、的中率、ROI、1号艇1着率、2艇カバー率、内側1点的中率を記録する。掲載群は有料+無料のみとし、CSVのみは全対象には含めるが掲載成績へは含めない。
14. 構造KPIは条件付き分母とする。1号艇頭成功時のみ2着候補2艇カバーを評価し、2艇カバー成功時のみ内側1点成功を評価する。前段失敗時は後段を `対象外` とし、分母へ入れない。

日次Google Drive正本:

- data Folder ID: `11OtFNwroVbgV8BClzoepTKoa81fQJ-A1`
- analysis Folder ID: `19aHo7aKIp0G01SIkk7fcI_uktyaWhW2q`

## ChatでのGitHub実行経路判定

- まずGitHub `main` の `boat-racing/` と対象workflow / docsを正本として確認する。
- 読み取り、コード検索、commit / issue / workflow / artifact / SHA / run状態確認は A. Read / Audit とし、ChatからGitHub read/searchで直接行う。Issue不要。
- source / test / docs / config / workflow等のテキスト更新は B. Git Change とし、direct create/update/deleteを使う。Git更新のためのIssueは作らない。
- CSV整形、JSON join、集計、scoring、metrics、SHA、差分比較、artifact回収後の検証など、Git正本moduleと必要入力をChat側で取得できる処理は C. Pure Deterministic Execution を第一候補とする。
- BOAT RACE公式サイトへの取得系処理は、正本PythonをChatローカルで同一条件実行でき、公式入力を取得できる場合はCを優先する。ChatローカルのPython実行環境から公式サイトへ通信できず正本fetcherを再現できない場合は D. Actions-Native Execution としてIssue経由Actionsを使用する。
- Dで出走表取得を行う場合は `.github/workflows/boatrace_racelist_issue.yml`、直前情報取得は `.github/workflows/boatrace_pre_race_issue.yml`、結果取得・予想照合は `.github/workflows/boatrace_results_chat.yml` を使用する。
- manual workflowは人手での補助経路として残すが、ChatがDを選択した場合はIssue起動を優先する。
- Actions artifactから回収した後のJSON/CSV整合性検査やSHA計算は、別Actions runを要求する監査仕様がない限りCとしてChatローカルで行う。
- 日次成果物はGitへcommitしない。

### Issue request preflight / retry

Issue駆動ActionsはD. Actions-Native Executionに限定する。ルート `.gpt/README.md` と `.gpt/ISSUE_REQUEST_CONTRACTS.md` を共通正本とし、本節は競艇固有contractを補足する。共通規約と競艇固有規約が競合する場合は、データ意味を変えない範囲で共通のfail-closed / preflight / retry原則を満たし、曖昧なままIssueを作成しない。

Issue作成前は、必ず最新 `main` の共通contract、本ファイル、対象workflowを確認する。Issueを先に作成して不足項目を後から補う運用は行わない。

`[BOATRACE_RACELIST_REQUEST]` のrequest contractは以下とする。

- title: `[BOATRACE_RACELIST_REQUEST] <request_id>`
- `request_id`: `[A-Za-z0-9._-]{1,80}` に完全一致する一意な値。
- body: Markdown fenceを付けないraw JSON object。
- required `date`: `YYYYMMDD` 形式で、実在する暦日。
- required `venues`: 1件以上のarray。各要素はobjectで、`name` / `code` / `day` を必須とする。値は対象workflow / fetcherへ渡す実値を使用し、推測で補完しない。
- optional `request_interval_seconds`: numeric、`0 <= value <= 60`。省略時は `1.0`。
- upstream dependency: なし。別workflowの `run_id` / `artifact_name` / `file_id` を推測して付与しない。
- success marker: Issueコメントの `BOATRACE_RACELIST_RESULT` JSONで `status=success`。
- downstreamで使用する `run_id` / `artifact_name` は、同RESULTから完全一致で転記する。
- `status=partial` / `status=failure` は成功扱いにせず、artifactと `validation_report.json`、runのfailed stepを確認して原因分類する。

直前情報取得をDとして実行する場合のcontractは `boat-racing/docs/直前情報取得_GitHubIssue運用.md` と `.github/workflows/boatrace_pre_race_issue.yml` を正本とする。title prefixは `[BOATRACE_PRE_RACE_REQUEST]`、bodyはraw JSON objectで、`date` / `venue` / `race` / `format` を検証してからIssueを1回だけ作成する。

preflightでは少なくとも title / request_id / JSON parse / 必須キー / 値域をIssue作成前に検証する。upstream artifact chainを使う処理では、さらにupstream run成功、artifact名、SHA、dates / IDs / freeze manifest等を実値照合する。共通 `.gpt/tools/gpt_issue_preflight.py` が当該protocolを直接検証できる環境・版ではそれを使用する。未対応の場合は対象workflow/parserとcontractを読み、同等の事前検証を行う。

retry時は以下を必須とする。

1. RESULT、artifact、failed step / logを確認し、共通failure taxonomyに沿って原因を分類する。
2. `REQUEST_INVALID` はIssue本文を修正してから再作成する。
3. `EXTERNAL_TRANSIENT` は同一Issueの盲目的rerunではなく、必要なbackoff後に最新 `main` を確認し、新しい `request_id` で新規requestを作成する。
4. `DOMAIN_VALIDATION_FAILED` は正常なfail-closedとして扱い、同一入力を盲目的にretryしない。
5. `IMPLEMENTATION_ERROR` / `PERMISSION_ERROR` / `CONCURRENCY_CONFLICT` はrequest再送だけで解決しようとせず、実装・権限・競合原因を修正する。
6. retryで旧requestの `run_id` / `artifact_name` 等を使い回さず、新しいRESULTが発生した場合はその値へ完全一致で更新する。

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
- 日次結果取込では、Google Sheetsへ書き込む前に `boat-racing/src/ledger_daily_result_import.py` で日次原本からJSON更新計画を生成する。対象日・freeze・掲載/CSVのみ/全対象・条件付き構造KPI・失敗構造の検証に失敗した場合は書き込まない。
- 実装変更時は `python -m unittest discover -s boat-racing/tests -v` を実行し、日跨ぎ対象日・日付不一致停止・freeze保持・掲載分離・条件付きKPI・既存日回帰を確認する。

## ForwardTrial専用分析台帳

- 正本Googleスプレッドシート内の `FT2_` 13タブを既存台帳から独立して運用する。既存タブの削除・列変更・名称変更・計算式変更は行わない。
- 日次原本はDriveの `racecards` / `predictions` / `sales-selection` / `results` を使用し、予想根拠明細は任意の監査資料とする。
- 取込前に `forward_trial_analysis_import.py` で日付、対象全R件数、会場集合、キー一意性、仕様版、freeze、結果キー一致を検証する。不成立時はシートへ書き込まない。
- 主キーは `日付×会場×R×仕様版` とし、同一キーは追記せずupsertする。
- `Raw` は仕様上のForwardTrial対象、`Genuine` はRawかつ締切前freeze、`Published` はGenuineかつ有料または無料とする。CSVのみはPublishedに含めない。
- freeze日時は日本時間で公式締切予定日時と比較し、締切後または同時刻は `CONTAMINATED` とする。該当行は削除せず監査タブへ残す。
- 初回再集計（2026-09-01〜09-08）の固定受入値は、全336R、Raw 81R・29的中・投資8,100円・回収7,910円、Genuine 78R・29的中・投資7,800円・回収7,910円、Published 60R・23的中・投資6,000円・回収6,140円、汚染3Rとする。
- 日次処理は、原本preflight、正規化、source/date/key/freeze監査、全R明細upsert、開催メタ、Freeze監査、日別、会場別、会場日目別、グレード別、判定構造別、販売選別、Score、ダッシュボード、既存販売台帳クロスチェック、回帰値検証の順とする。
- `FT2_日別集計`、`FT2_会場別集計`、`FT2_会場日目別集計`、`FT2_グレード別集計`、`FT2_判定構造別集計`、`FT2_販売選別検証`、`FT2_Score検証`、`FT2_Freeze監査`、`FT2_ダッシュボード` は **Atomic Aggregate Set** とする。全R明細更新後は9タブを同一処理で、全GENUINE明細から上書き再生成する。一部タブだけの更新・前日値への加算は禁止する。
- `FT2_集計監査` に各9タブの deterministic `aggregate_generation_id`、source raw/genuine/contaminated/exacta件数、max対象日、出力行数、検証状態を記録する。9行のgeneration IDとsource件数が一致しない場合は `集計不整合` とし、完了にしない。
- 集計タブは前日値への加算を禁止し、毎回 `FT2_全R明細` の非空 `FT2_ID` を正本として全再生成する。物理最終行や空き行を件数判定に使わない。
- `FT2_取込管理.取込状態` は `取込中` → `明細取込済` → `集計再生成中` と遷移し、Atomic Aggregate Set、集計監査、既存販売台帳クロスチェック、受入値検証がすべて成功した場合だけ `完了` とする。1タブでも世代・母数・書込が不一致なら `集計不整合`、実行例外は `エラー`、grade未解決等は `要確認` とする。
- 再実行はstable key upsertと全再生成によりidempotentとし、非空FT2_ID件数、販売明細件数、投資額、回収額を増加させない。
- 開催グレードは `fetch_boatrace_event_meta.py` でBOAT RACE公式日別レース一覧から取得し、日次Freeze資産として開催名、グレード大分類、source URLを保存する。推測は禁止し、未取得は `未分類` のまま `要確認` とする。G1/SGも除外せず分析軸へ含める。
- 完了前に当日の日別行、当日全RのFreeze監査、ダッシュボード累計、会場別合計、販売区分合計、掲載=有料+無料、既存販売台帳重複指標、数式エラーなしを機械検証する。
- 予想ルール・販売ルールの変更判断はこの実装から切り離し、分析台帳は集計・監査に限定する。

## CSV原本保存・月次ZIP化

- 日次CSV原本の保存漏れ監査は、Google Driveを直接参照して行う。GitHub main にCSVが存在しないことを未生成の根拠にしない。
- 原本は会話添付、ChatGPT Library、参照可能な日次成果物の順に探索し、内容・列・文字コード・ファイル名を変更せずに保存する。見つからないファイルは再生成しない。
- アップロード前に既存同名・内容を確認し、アップロード後にDrive上の存在を再確認する。同名異内容は上書きせず競合として扱う。
- 月次ZIP化と元CSV削除は明示依頼時のみ行う。ZIPテスト、収録件数、Drive上の存在を確認できた後に、収録済み元CSVだけを削除する。
- 対象フォルダID、探索順、命名、再開時の詳細は .gpt/HANDOFF.md を正本とする。

## Chat起動の日次台帳記帳

- 日次台帳記帳は `[BOATRACE_LEDGER_IMPORT] <request_id>` Issueと `.github/workflows/boatrace_ledger_import_issue.yml` を使うD. Actions-Native Executionである。理由はGoogle service-account secret、Drive immutable Freeze、Sheets write、run/artifact監査証跡を必要とするため。
- Issue本文はraw JSONで `date`、`source_folder_id`、正本 `spreadsheet_id`、複数候補がある場合の4 `file_ids` を持つ。workflowが一意解決できない原本は推測せずfail-closedとする。
- workflowは `forward_trial_analysis_import.py` → `forward_trial_chat_ledger.py` → `run_forward_trial_chat_import.py` を実行し、Chat内に別の転記・集計ロジックを作らない。
- 対象日はwrite/read-back中 `集計再生成中` とし、Atomic Aggregate Set 9タブの同一generation/source、FT2_ID重複0、既存販売台帳mirror、formula error 0が確認できた場合だけ `完了` とする。
- 新スレッドでは会話履歴の途中状態を使わず、対象日のDrive 4資産、`FT2_取込管理`、`FT2_集計監査`、`FT2_全R明細`、Issue RESULT/artifactを読み直す。通常の途中返信はせず、実ブロッカーまたは完了時だけ報告する。
- 成功条件はIssueコメントの `<!-- BOATRACE_LEDGER_IMPORT_RESULT -->` JSONで `status=success`。artifact `boatrace-ledger-result-<run_id>` は90日保持する。failureはblind rerunせず、failure_class / error_code / failed stepを確認する。
