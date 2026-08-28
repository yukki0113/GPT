# 競艇AI予想ツール

BOAT RACE公式情報を利用する取得・運用Pythonツール群です。

## Current tools
- `src/fetch_boatrace_racelist.py` — 出走表取得
- `src/fetch_boatrace_pre_race_info.py` — 直前情報取得
- `src/fetch_boatrace_results.py` — 公式結果取得

詳細仕様は `docs/` を参照してください。日次CSV、キャッシュ、ログ、運用台帳はGit管理対象外です。

## Ledger source of truth

継続台帳 `競艇note販売運用台帳.xlsx` は **Google Drive `GPT/ledger/競艇note販売運用台帳.xlsx` を正本** とします。Chat / Workで参照・更新する場合はDrive上の正本を取得し、更新後も同一Driveファイルへ反映してください。

GitHub `boat-racing/ledger/競艇note販売運用台帳.xlsx` に同名ファイルが残っている場合、それはDrive移行前の旧スナップショットです。以後の台帳参照・更新に使用せず、GitHubバイナリread/update経路で同期しません。
