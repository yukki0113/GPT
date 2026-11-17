# MD正本Gen7移行監査 — モンスター種別（2026-11-17）

## 結果

**PRODUCTION HEAD PROMOTED / INDEPENDENT READBACK PASS**。ユーザー指示により、非公開Drive正本`GPT/MasterDuel/DB/MD_CURRENT_HEAD.json`をGen6からGen7へ更新した。

この監査は**公開用の構造・件数・SHA**のみ。非公開カード個票・所持内容・DriveファイルIDは公開Gitに保存しない。

| 項目 | 監査結果 |
|---|---|
| 正本generation | 6 → **7** |
| SQLiteスキーマ | 1 → **2**（既存表を変更しない追加テーブル） |
| カード総数 | **13,948**、不変 |
| モンスター | **9,114**種類を分類 |
| `card_monster_types` | **12,636**行（複合タイプを分解保存） |
| FUSION / SYNCHRO / XYZ / LINK | **564 / 524 / 588 / 453** |
| PENDULUM / RITUAL | **385 / 145** |
| inventory | **184**種類、不変 |
| banlist_entries | **215**件、不変 |
| card_texts | **13,948**件、不変 |
| 旧11テーブル | 全行を正規化直列化してSHA比較し、前後完全一致 |
| `PRAGMA integrity_check` / `foreign_key_check` | PASS / 0問題 |
| 新SQLite raw SHA-256 | `d3ab2fa3e3c79e455a10dd9ff8aebb407a3bd045fac0d1f50711cc0443906ecb` |
| 新スナップショットZIP SHA-256 | `27acb17a6884aee060268c3d39bcb93650c37a7d87dd8aca486185cc83b85c2a` |
| 新HEAD raw SHA-256 | `248c25c554731492850a94b01911bc21f79d389801fca7175eb3c545c22097c7` |
| 元Gen6 SQLite SHA-256 | `0ac8a2b91a3f05dd87dd4f06d09456f096cf9aef7820c546a2a3c2d0f77133b7` |

元MD JSON SHA `b7bf8e365d293cfa6bc309dbbc5cbefae3a7d1b498d34cdf7c54fc26e5bd152b`、元cards.json SHA `5f71287c55c610c2753e1c6ecade4bdf9f1c7981555a127d03ccd82a493c97b7` をピンし、KONAMI IDとsource subtypeから13,948種類を厳密照合した。曖昧名は候補のID/種別で解決し、未解決を残したまま正本化していない。

## 格納と回復

- Gen7は新しい不変SQLite ZIPとして作成 → Driveへ新規保存 → 再取得してDBとZIP双方のSHA一致を確認。
- 原本のGen6 HEADを**別ファイルにバックアップ**し、読み戻しで元HEADのバイトSHA一致を確認。元Gen6 ZIP・所持・規制表は不変。
- Gen7 accepted MD regulation baselineはGen6の215行、日付、承認状態、差分イベントを維持し、唯一`master_sqlite_sha256`のみGen7へ再ピンした別ファイル。元版を上書きしない。
- 新HEAD提案を不変ファイルとして保存 → 現行HEADが旧SHAと一致することを再確認 → 正本HEADファイルを更新 → 更新後に独立読み戻ししてSHA確認。
- Driveには**atomic CASがない**ため、複数ライターの競合安全性は保証しない。今回の作業は単一ライターで実施。復旧する場合は旧バックアップと旧ZIPを照合した上で手動でHEADを戻す。

## 実装

- `card_master_import/monster_types_migration.py`: ソースSHAピン、13,948件一致、追加テーブル、原本全テーブル保持、整合性検査、オフラインのみ。出力先が既に存在すれば拒否。
- `sqlite_store/schema_v2_monster_types.sql`: v2追加定義。`sqlite_store/store.py`: 旧v1とv2の構造検証を許可するが未知のversionは拒否。
- `card_master_import/importer.py`: 以後のv2へ取り込むカードは`monster_types`を失わない（v1の旧取り込みは履歴再現用）。
- `engine_m6/discovery.py`: v2に`card_monster_types`があれば`FUSION/SYNCHRO/XYZ/LINK`をEX候補として直接判定し、効果本文への単語検索を使用しない。v1では旧動作でリプレイ可能。
- `engine_m6/preflight.py`: 新HEADのschema_version 2対応。
- 実際にデストーイで検索漏れしていた3カードIDはGen7で`FUSION`登録を確認。

## 正本切替後のconsumer注意

Gen7ではSQLiteバイトSHAが変わる。したがってGen6 SHAにピンされた**M5-C sidecar、候補JSON、事前評価ポリシー、カード効果アンカー、旧M6レシピ**を新DBへそのまま渡してはいけない。元ソースとの一致を保ったまま、新Gen7を参照する別世代の成果物を正規の作成工程で再発行し、旧成果物は歴史的リプレイとして保持する。

特にユーザー承認済み禁止制限215件を再審査する必要はない。新しいbaseline SHAへ参照を切り替える。M6-8独立スレッドの正式構築PASSやデストーイ再構築完了は、別途Gen7のM5C/ポリシーを準備して正式実行するまで主張しない。
