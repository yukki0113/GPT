# 競艇AI予想ツール

BOAT RACE公式情報を利用する取得・運用Pythonツール群です。

## Current tools
- `src/ledger_daily_result_import.py` — ForwardTrial日次結果取込の検証・集計・JSON更新計画生成
- `src/fetch_boatrace_racelist.py` — 出走表取得
- `src/fetch_boatrace_pre_race_info.py` — 直前情報取得
- `src/fetch_boatrace_results.py` — 公式結果取得

詳細仕様は `docs/` を参照してください。日次CSV、キャッシュ、ログ、運用台帳はGit管理対象外です。

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
