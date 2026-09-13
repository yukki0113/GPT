# Boat racing thread handoff

Updated: 2026-09-13

このファイルは、Chat / Workのスレッドが長大化して引っ越した場合に、会話履歴へ依存せず `boat-racing` プロジェクトを再開するための入口です。

## 1. 新スレッド開始時の読み順

最新 `main` を確認したうえで、原則として次の順に読む。

1. `boat-racing/README.md`
2. `boat-racing/.gpt/CONTEXT.md`
3. `boat-racing/.gpt/HANDOFF.md`
4. `boat-racing/.gpt/WORKFLOW.md`
5. 対象作業の `docs/` と `src/`
6. D. Actions-Native Executionを使う場合だけ対象 `.github/workflows/`

過去チャットの要約、添付ZIP、一時作業領域は補助情報であり、Git `main` のソース・仕様・運用文書の代わりにしない。

## 2. 正本と不変原則

- Python / tests / docs / config / workflowは GitHub `yukki0113/GPT` の `main` を正本とする。
- 日次の公式出走表、事前予想、予想根拠、販売選別、結果CSVは Google Drive `data` を正本とする。
- 継続台帳はネイティブGoogleスプレッドシート `競艇note販売運用台帳` を正本とする。
- 日次成果物、ログ、HTMLキャッシュ、台帳はGitへcommitしない。
- 予想・販売選別のfreeze前に当該日の結果を参照しない。
- 結果参照後に事前予想、買い目、販売順位、掲載区分を再生成・修正しない。
- 取得不能・解析不能・入力不正・公式未確定を成功扱いしない。推測補完しない。

### Google Drive data

- Folder ID: `11OtFNwroVbgV8BClzoepTKoa81fQJ-A1`
- 主な区分: `racecards` / `predictions` / `prediction-rationales` / `sales-selection` / `results`

### Google Drive analysis

- Folder ID: `19aHo7aKIp0G01SIkk7fcI_uktyaWhW2q`

### Ledger

- Spreadsheet ID: `1gEAYJ90Zv3HDi5gh_at0jDWEQrgCSB5tIywJFZjXcFM`
- タイムゾーン: `Asia/Tokyo`

## 3. 現在の前向き試行

2026-09-01以降は `ForwardTrial_Ver0.1` を現行試行とする。

開始時に次を読む。

1. `boat-racing/docs/競艇AI予想_2連単1点前向き試行仕様書_Ver0.1.md`
2. `boat-racing/docs/競艇AI予想_事前予想仕様書_Ver1.2.1.md`

`ForwardTrial_Ver0.1` を優先し、Ver1.2.1は基礎・履歴仕様として扱う。

## 4. 主要モジュール地図

- `src/fetch_boatrace_racelist_with_meta.py`
  - 公式出走表取得と開催メタ付与を連結する標準入口。
- `src/fetch_boatrace_racelist.py`
  - BOAT RACE公式出走表を取得。
- `src/fetch_boatrace_event_meta.py`
  - 公式日別レース一覧から開催名・グレードを取得。
- `src/enrich_boatrace_racelist_metadata.py`
  - 既存出走表CSVへ開催名・開催グレードを付与。
- `src/fetch_boatrace_pre_race_info.py`
  - 直前情報取得。
- `src/forward_trial_predict.py`
  - ForwardTrialの事前予想・根拠明細・2連単1点販売選別を決定論的に生成。
- `src/fetch_boatrace_results.py`
  - BOAT RACE公式結果取得と事前予想照合。
- `src/ledger_daily_result_import.py`
  - 日次結果取込の検証・集計・Google Sheets反映前JSON更新計画生成。
- `src/forward_trial_analysis_import.py`
  - ForwardTrial専用分析台帳の正規化・真正性監査・全再集計データ生成。
- `src/forward_trial_chat_ledger.py`
  - 日次台帳用stable-key upsert、FT2全再集計、既存販売台帳mirrorの純粋な書込計画を生成。

実装の役割はREADMEと各module/docを正本とし、この一覧だけでCLIや列仕様を推測しない。

## 5. GitHub実行経路

毎回、開始時に次の4系統へ分類する。

- A. Read / Audit
  - repository / file / commit / issue / workflow / artifact / SHA / run状態の確認。
  - Issue不要。
- B. Git Change
  - source / test / docs / config / workflow等のUTF-8テキスト変更。
  - latest main、path、現内容を確認してdirect create/update/deleteする。
  - Git変更だけのIssueは作らない。
- C. Pure Deterministic Execution
  - Git正本moduleと入力をChat側で取得でき、secret・特殊runner・Actions監査証跡が不要な処理。
  - CSV/JSON整形、SHA、差分、集計、scoring、artifact回収後の検証も原則C。
- D. Actions-Native Execution
  - Secrets、認証付き外部取得、artifact chain、長時間・大容量、runner依存、immutable freeze、監査run、またはChatローカルで正本moduleを同一条件実行できない場合。
  - fully validated requestをIssueで1回だけ起動する。

「GitHubにmoduleがある」ことだけを理由にDを選ばない。

## 6. 日次作業の担当境界

### 出走表取得

公式出走表の取得とFreeze。結果は見ない。

### 事前予想

公式出走表のfreezeを入力とし、`forward_trial_predict.py` で事前予想・根拠・販売選別を生成する。結果参照前に確定する。

日次予想の標準ユーザー向け成果物は、同一freeze時点の次の3CSVとする。

1. 24列の事前予想CSV
2. 26列の予想根拠明細CSV（全R×6艇）
3. 21列の2連単1点販売選別CSV

予想根拠明細は任意説明資料ではなく、事前予想と同時点で固定する正本日次成果物である。通常は3CSVをそろえて返す。`forward_trial_predict.py` が生成する実行manifestは監査・再現性の補助物であり、通常のユーザー向け3成果物には数えない。

結果参照前に一時的に表示対象を減らした場合でも、正本保存では事前予想・予想根拠・販売選別の整合性を維持する。結果参照後に欠落した根拠を新規予想として再生成してはならない。根拠CSVの再出力が必要な場合は、結果未参照であること、同一入力・同一freeze・既存予想との一致を確認できる場合に限る。

### 公式結果取得・予想照合

`fetch_boatrace_results.py` を中心に、確定済み事前予想CSVとBOAT RACE公式結果を照合し、結果CSVと取得ログを返す。

この工程では台帳を書き換えない。結果CSV取得後のDrive保存、Google Sheets台帳記帳、分析台帳更新は別工程として扱う。

### 日次台帳記帳

`ledger_daily_result_import.py` で更新計画を生成・検証し、その後ネイティブGoogleスプレッドシートへ反映する。

### ForwardTrial分析

`forward_trial_analysis_import.py` でDrive正本を結合し、`FT2_` 系を全再生成・監査する。部分加算ではなくAtomic Aggregate Setを同一世代で更新する。

## 6A. 出走表取得スレッドの標準再開手順

出走表取得専用スレッドへ引っ越した場合は、会話履歴ではなく次の手順で復元する。

1. latest `main` と本HANDOFFを確認する。
2. `docs/出走表取得依頼_定型作業.txt`、`docs/README_出走表取得.md`、`src/fetch_boatrace_racelist_with_meta.py` を確認する。
3. ユーザー指定の日付・会場名・2桁会場CD・開催日目を確定する。表の `位置づけ` は取得requestへ混入させない。
4. C/Dを判定する。ChatローカルからBOAT RACE公式サイトへ正本fetcherと同一条件で通信できない場合はDとする。
5. Dの場合は `.github/workflows/boatrace_racelist_issue.yml` のrequest parserを確認し、`[BOATRACE_RACELIST_REQUEST] <request_id>` Issueを1回だけ発行する。
6. Issueコメントの `BOATRACE_RACELIST_RESULT`、workflow run、artifactをAで回収する。
7. 正常完了条件として、72R等の期待R数一致、`input_rows = 会場数×12×6`、21列、`開催グレード` / `開催名` 非空、`レース名` 不在、`レース種別` 非空、`errors=[]`、run successを確認する。
8. artifact ZIPは内部作業用に解凍し、通常のユーザー向け完成物は `YYYYMMDD_公式出走表_<会場...>.csv` の21列予想入力CSV単体とする。
9. 原本CSV、取得状況CSV、ログ、validation report、ZIP自体は、障害解析・監査を求められた場合だけ提示する。
10. ChatGPT Libraryへ保存操作を実行・確認できない環境では「Library保存済み」と報告せず、このスレッドからCSV単体を取得できる状態にする。

未完了requestの状態は会話中の「待機中」「実行中」を正本とせず、Issue / Actions / artifactから再判定する。日次の直近run IDや対象日をHANDOFFへ固定しない。

## 7. 結果取得スレッドの標準再開手順

結果取得専用スレッドへ引っ越した場合は、会話履歴ではなく次の手順で復元する。

1. latest `main` と本HANDOFFを確認する。
2. `docs/結果照合取得依頼_定型作業.txt`、`docs/README_公式結果取得.md`、`src/fetch_boatrace_results.py` を確認する。
3. 対象日のfreeze済み事前予想CSVを特定する。
4. 入力CSVのUTF-8、必須列、対象日、会場順、件数、`日付+会場+R` 一意性、SHA-256を固定する。
5. C/Dを判定する。
6. Dの場合は `.github/workflows/boatrace_results_chat.yml` のrequest parserを確認してからIssueを1回だけ発行する。
7. RESULT / run / artifactをAで回収し、CSV / log / validation / SHAをCで再監査する。
8. 結果CSVと取得ログを完成物として返す。台帳更新は行わない。

### freeze済み事前予想CSVの探し方

- 当該スレッドにユーザーがCSVを添付している場合は、その添付原本を最優先する。
- ユーザーが対象日だけを指定した、または日付訂正後に添付が手元にない場合は、Google Drive `data/predictions` から対象日のfreeze済み正本を検索する。
- 現行試行では、対象日・会場集合・`ForwardTrial_Ver0.1` が一致するcanonical prediction CSVを使う。
- 候補が複数あり内容やfreezeのどちらが正本か一意に決められない場合は推測しない。SHA・ファイル名・内容・関連するprediction-rationales / sales-selection等で一意性を確認し、それでも解決しなければ不整合として止める。
- 結果取得のために事前予想CSVを再生成しない。

### D経路の標準証跡

結果取得でDを使った場合、少なくとも次を追跡可能にする。

- request_id
- Issue number
- workflow run ID
- artifact name
- workflow head SHA
- input SHA-256
- validation status / input-output件数
- result CSV SHA-256（可能な場合）

これらは次スレッドで過去会話を読まなくても、GitHub Issue / Actions / artifactから復元できるようにするための証跡である。

## 8. スレッド引越し時の最小チェックリスト

新しいスレッドは、以前の会話内容を前提にせず、以下を確認すれば作業再開できる状態を維持する。

- latest main commit
- このHANDOFFの更新日
- current prediction spec
- Git / Drive / Sheetsのsource of truth
- 対象作業の担当境界
- 使用module / workflow
- 入力原本の所在とSHA
- 日次予想では3CSV（事前予想・予想根拠・販売選別）のfreeze整合性
- Dの場合はrequest/run/artifactの対応
- 未完了状態がある場合は、GitHub Issue / Actions / Drive / Sheetsの正本から再判定する

累計成績や「直近どこまで記帳済みか」のような変動状態をこのファイルへ固定値として持たせない。最新状態は正本Google Sheets / Drive / Actionsから取得する。

## 9. 更新ルール

次の変更を行った場合は、このHANDOFFも影響確認する。

- source of truth変更
- active prediction spec変更
- 日次フォルダ構成変更
- 主要moduleの追加・廃止・役割変更
- GitHub実行経路やIssue contract変更
- 結果取得と台帳記帳の担当境界変更
- 日次予想の標準成果物・freeze運用変更
- 新スレッドで会話履歴がないと再開できない事象が発生した場合

引継ぎに必要な情報は会話メモリだけに残さず、再現可能な範囲をGit正本へ戻す。

## 10. CSV原本保存・月次圧縮

日次CSVの原本保存は、予想・結果・台帳とは別の保全工程として扱う。目的は完成済み原本をGoogle Driveへ安全に保存し、保存漏れを監査することであり、CSV内容の生成・修正・結合は行わない。

### 対象と探索順

- 対象日CSVは、会話添付 → ChatGPT Library → 参照可能な競艇note販売の日次成果物の順に探索する。
- GitHub main は仕様・コード・台帳等の正本であり、日次CSVがGitにないことを未生成の根拠にしない。
- 対象日は作成日時だけでなく、CSVの対象日・ファイル名・内容・当日の運用から判定する。
- 公式出走表、事前予想、予想根拠明細、販売選別、結果、正式な補助CSVを候補とする。log、xlsx、md、HTMLキャッシュは通常の「CSV一式」には含めない。
- 原本が見つからない場合は再生成せず、未発見として報告する。

### Drive区分

data親フォルダ配下の既存区分を維持する。

- racecards: 1zg77_EqlcQon0bPmQK-nSKfzMhKWIscV
- predictions: 1ZHNpPyVQPjs4UvWLhc5ocXFCwLF_ybY2
- prediction-rationales: 10dqQg2aPBtBNnJkPwuPVPZ2dx8mQzUzi
- sales-selection: 1mgsmcJXrKJtjYX8DbAGLsdqSdt5JWRrS
- results: 1P60LF55o1P_1QUqdRd_cqAqLyDidTRUw

アップロード前に対象区分の既存ファイルを確認する。同名・同一内容は保存済みとして再アップロードしない。同名で内容が異なる可能性がある場合は上書き・削除をせず、正式版の根拠を確認できなければ競合として報告する。アップロード後もDrive上の存在を再確認してから完了とする。

### 月次ZIP化

月次ZIP化と元CSV削除は、ユーザーが月・区分・削除を明示した場合だけ実行する。

1. 対象月・対象区分のCSVを全件列挙し、同名重複・既存ZIPを確認する。
2. CSVのバイト列・ファイル名を変更せず、区分ごとに YYYYMM_区分CSV原本.zip を作成する。
3. ZIPテストと収録件数照合を行う。
4. 同じDrive区分へZIPをアップロードし、Drive上の存在を再確認する。
5. 確認済みZIPに収録された元CSVだけを削除する。
6. 最後に対象月CSV残存数とZIP存在を再確認する。

既存ZIPを新しい内容で上書きしない。ZIP確認前の削除、収録漏れがある月の一括削除、原本CSVの変換・再保存は禁止する。

この工程はGoogle Drive直接操作で完結するため、通常はA/C相当でありGitHub Issue/Actionsを使わない。

## 11. Chat日次台帳記帳の再開契約

日次の「台帳記帳」は、結果取得とは別の完結工程である。最新 `main` の `docs/ForwardTrial_Chat日次台帳記帳運用.md`、`.github/workflows/boatrace_ledger_import_issue.yml`、`src/forward_trial_analysis_import.py`、`src/forward_trial_chat_ledger.py`、`src/run_forward_trial_chat_import.py` を確認する。

- Workは対象日を受けたら、Driveの種別別フォルダにあるracecard / prediction / sales-selection / resultを正本として確認し、4 file IDを固定する。
- GitHub `main` の決定論moduleでstable-key upsertと全再集計を生成し、接続済みGoogle Sheetsへ直接書込み・read-backする。手計算やセル単位の場当たり的転記を完了扱いにしない。
- Googleサービスアカウント、`GPT_GDRIVE_SERVICE_ACCOUNT_JSON`、およびGitHub ActionsからのGoogle Drive / Sheetsアクセスは断念・廃止した。台帳記帳でIssue / Actionsを起動しない。
- 完了の根拠は、Issue RESULTの `status=success`、`FT2_取込管理`、`FT2_集計監査` の9タブ同一generation/source、read-back検証の一致である。明細存在、日別集計の最新日、取込管理の表示だけでは不十分である。
- 予想、販売選別、freeze、結果は再評価・再ランキングしない。frozen列差異、grade未解決、世代差、件数差はfail-closedとする。
- 通常は処理完了まで途中報告を出さず、実ブロッカーまたは最終完了時にだけ報告する。最新の対象日・run ID・累計値はこのHANDOFFに固定せず、Drive / Sheets / RESULTから再取得する。
