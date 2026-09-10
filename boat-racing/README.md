# 競艇AI予想ツール

BOAT RACE公式情報を利用する取得・運用Pythonツール群です。

## Current tools
- `src/forward_trial_predict.py` — ForwardTrial_Ver0.1の事前予想・根拠明細・2連単1点販売選別を公式出走表CSVから純粋決定論的に生成
- `src/ledger_daily_result_import.py` — ForwardTrial日次結果取込の検証・集計・JSON更新計画生成
- `src/forward_trial_analysis_import.py` — ForwardTrial専用分析台帳の正規化・真正性監査・再集計データ生成
- `src/fetch_boatrace_event_meta.py` — BOAT RACE公式日別レース一覧から開催名・グレードを日次Freeze
- `src/fetch_boatrace_racelist.py` — 出走表取得
- `src/fetch_boatrace_pre_race_info.py` — 直前情報取得
- `src/fetch_boatrace_results.py` — 公式結果取得

詳細仕様は `docs/` を参照してください。日次CSV、キャッシュ、ログ、運用台帳はGit管理対象外です。

## GitHub operation routing (2026-09-10)

GitHub上の資産を用いる作業は、開始時に「本当にGitHub Actions環境が必要か」を判定し、次の4系統から最短かつ再現可能な経路を選ぶ。

- A. Read / Audit: repository / file / commit / issue / workflow結果、コード検索、差分、main、artifact / SHA / run状態の確認はChatからGitHub read/searchで直接行う。Issue不要。
- B. Git Change: source / test / docs / config / workflow等のUTF-8テキスト変更は、latest main・path・現内容を確認してからGitHub direct create/update/deleteでremote commitを作成する。原則Issue不要。
- C. Pure Deterministic Execution: Git正本moduleと必要入力をChat側で取得でき、secret・特殊runner・Actions監査証跡が不要で、計算量が許容範囲ならGPTローカル実行を優先する。可能な限り source commit / source file SHA256 / input SHA256 / generated_at / output SHA256 を残す。
- D. Actions-Native Execution: Secrets、認証付き外部取得、Actions artifact chain、長時間・大容量処理、runner環境が仕様の一部、immutable freeze、settlement等でrun ID / artifact / Actions履歴を監査証跡として固定する必要がある場合、または正本moduleをChatローカルで同一条件実行できない場合のみIssue -> GitHub Actionsを使用する。

BOAT RACE公式サイトへ通信する取得系Pythonについても「Gitにmoduleがある」だけではIssueを使わない。正本PythonをChatローカルで同一実行でき、必要な公式入力を取得できる場合はCを優先する。一方、ChatローカルのPython実行環境から公式サイトへ通信できず、正本fetcherを同一条件で再現できない場合はDとして対応Issue Workflowを使用する。

直前情報取得のD経路は `.github/workflows/boatrace_pre_race_issue.yml`、手動補助経路は `.github/workflows/boatrace_pre_race_manual.yml` とする。Issueを作る場合は事前にlatest main、request contract、必須キー、対象workflowを完全検証し、1 requestにつきIssueは1回だけ発行する。

## Prediction specs

### 基礎・履歴仕様
- `docs/競艇AI予想_事前予想仕様書_Ver1.2.1.md`
  - 2026-08-31までの事前予想基礎仕様・履歴正本
  - 24列予想CSV、26列予想根拠明細CSV、相対比較・軸警戒ルールを定義

### 2026-09-01以降の前向き試行
- `docs/競艇AI予想_2連単1点前向き試行仕様書_Ver0.1.md`
  - `ForwardTrial_Ver0.1`
  - 予想スレッドは日次試行開始時にこの仕様を優先して読む
  - Ver1.2.1を基礎資料としつつ、試行用の決定規則、2連単1点、販売選別、結果遮断を固定

### ForwardTrial日次予想の標準実行経路

公式出走表CSVを取得済みの場合、予想・scoring・販売選別は **C. Pure Deterministic Execution** とし、Chat内で同ロジックを再実装せず、GitHub `main` の `src/forward_trial_predict.py` を取得してGPTローカルで実行する。

```bash
python boat-racing/src/forward_trial_predict.py \
  --input 20260910_公式出走表_尼崎_児島_宮島_芦屋_多摩川_大村.csv \
  --output-dir ./out \
  --prediction-time '2026-09-10 08:22:00+09:00' \
  --source-commit <fetched-main-commit>
```

moduleは24列事前予想CSV、26列予想根拠明細CSV、21列2連単1点販売選別CSVに加え、`source_commit`、source/input/output SHA256、generated_atを持つ実行manifestを生成する。公式出走表の取得自体は、Chatローカルから公式サイトへ同一条件で通信できない場合に限りD. Actions-Native ExecutionとしてIssue / Actionsを使用する。Artifact回収後の検証と予想計算はCへ戻す。

## Daily data source of truth

日次原本はGoogle Driveを正本とし、Gitへcommitしません。

### data
- Folder ID: `11OtFNwroVbgV8BClzoepTKoa81fQJ-A1`
- URL: `https://drive.google.com/drive/folders/11OtFNwroVbgV8BClzoepTKoa81fQJ-A1`
- 主な区分:
  - `racecards`
  - `predictions`
  - `prediction-rationales`
  - `sales-selection`
  - `results`

### analysis
- Folder ID: `19aHo7aKIp0G01SIkk7fcI_uktyaWhW2q`
- URL: `https://drive.google.com/drive/folders/19aHo7aKIp0G01SIkk7fcI_uktyaWhW2q`
- バックテスト結果、結果参照前固定、比較資料、仕様改訂判断などを保存

## Ledger source of truth

継続台帳の正本は **Googleスプレッドシート `競艇note販売運用台帳`** とします。

- Spreadsheet ID: `1gEAYJ90Zv3HDi5gh_at0jDWEQrgCSB5tIywJFZjXcFM`
- URL: `https://docs.google.com/spreadsheets/d/1gEAYJ90Zv3HDi5gh_at0jDWEQrgCSB5tIywJFZjXcFM/edit`
- タイムゾーン: `Asia/Tokyo`

Chat / Workで参照・更新する場合は、Google Sheets API / Google Drive ConnectorでこのネイティブGoogleスプレッドシートを直接読み書きし、同一スプレッドシートへ反映してください。

Google Driveに残る旧Excel版 `競艇note販売運用台帳.xlsx` および GitHub `boat-racing/ledger/競艇note販売運用台帳.xlsx` は移行前スナップショットです。以後の台帳参照・更新には使用せず、Drive旧ExcelやGitHub旧Excelへフォールバックしません。

## Ledger daily result-import safeguards

日次結果取込の対象日・freeze固定、掲載成績とCSV-onlyの分離、条件付き構造KPI、失敗構造ラベル、回帰確認は [`docs/競艇note販売運用台帳_日次結果取込再発防止手順.md`](docs/競艇note販売運用台帳_日次結果取込再発防止手順.md) に従います。

## Ledger result-import implementation

`src/ledger_daily_result_import.py` は、日次CSVを基に対象日・freeze・掲載成績・CSVのみ・全対象・条件付き構造KPI・失敗構造を正規化し、Google Sheets反映前のJSON更新計画を生成します。Google認証・書込みは持たず、生成した計画を確認してからネイティブGoogleスプレッドシートへ反映します。

```bash
python boat-racing/src/ledger_daily_result_import.py --input source.json --output update_plan.json
python -m unittest discover -s boat-racing/tests -v
```

## ForwardTrial analysis ledger

正本Googleスプレッドシート内の `FT2_` 接頭辞13タブを、既存台帳とは独立したForwardTrial専用分析台帳として使用します。初回対象は2026-09-01〜2026-09-08の7日・336Rです。

`src/forward_trial_analysis_import.py` は、Drive正本の公式出走表・事前予想・販売選別・結果CSVと公式開催メタCSVを日付×会場×R×仕様版で結合し、締切後freezeを削除せず `CONTAMINATED` として真正forward集計から分離します。入力の欠損、日付不一致、キー重複、freeze欠損はfail-closedとし、Google認証や書込み処理は持ちません。集計は非空FT2_IDの全明細から毎回全再生成し、全後続監査と既存販売台帳クロスチェックが成功するまで取込状態を完了にしません。

~~~bash
python boat-racing/src/forward_trial_analysis_import.py \
  --manifest source_manifest.json \
  --output forward_trial_analysis.json
python boat-racing/src/fetch_boatrace_event_meta.py \
  --date 20260909 --venues 児島,大村,尼崎,平和島,鳴門 \
  --output 20260909_公式開催メタ.csv
~~~

13タブの定義、集計層、固定受入値は [`docs/競艇note販売運用台帳_ForwardTrial専用分析台帳.md`](docs/競艇note販売運用台帳_ForwardTrial専用分析台帳.md) を参照してください。
