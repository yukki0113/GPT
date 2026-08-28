# 競艇AI予想ツール

BOAT RACE公式情報を利用する取得・運用Pythonツール群です。

## Current tools
- `src/fetch_boatrace_racelist.py` — 出走表取得
- `src/fetch_boatrace_pre_race_info.py` — 直前情報取得
- `src/fetch_boatrace_results.py` — 公式結果取得

詳細仕様は `docs/` を参照してください。日次CSV、キャッシュ、ログ、運用台帳はGit管理対象外です。

## Ledger source of truth

継続台帳の正本は **Googleスプレッドシート `競艇note販売運用台帳`** とします。

- Spreadsheet ID: `1gEAYJ90Zv3HDi5gh_at0jDWEQrgCSB5tIywJFZjXcFM`
- URL: `https://docs.google.com/spreadsheets/d/1gEAYJ90Zv3HDi5gh_at0jDWEQrgCSB5tIywJFZjXcFM/edit`
- タイムゾーン: `Asia/Tokyo`

Chat / Workで参照・更新する場合は、Google Sheets API / Google Drive ConnectorでこのネイティブGoogleスプレッドシートを直接読み書きし、同一スプレッドシートへ反映してください。

Google Driveに残る旧Excel版 `競艇note販売運用台帳.xlsx` および GitHub `boat-racing/ledger/競艇note販売運用台帳.xlsx` は移行前スナップショットです。以後の台帳参照・更新には使用せず、Drive旧ExcelやGitHub旧Excelへフォールバックしません。
