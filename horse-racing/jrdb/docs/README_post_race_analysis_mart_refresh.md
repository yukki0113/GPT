# JRDB 開催後 Analysis / Fact Lite / Pages 更新

## 正本と責務

Analysisの正本はGoogle Drive上のimmutable Parquet generationであり、`current.json`だけが現行generationを指す。SQLiteはPACI + SEDの既存差分ロジックとFact Lite生成に必要な一時materializationに限定する。Analysis SQLite ZIPをDrive正本、Fact Lite入力、PWA配布物へ戻してはならない。

Fact Liteの通常配布・PWA runtimeはParquet / DuckDB-Wasmである。Stats Martは旧思想のSQLite資産として現状維持し、開催後更新の標準工程・完了条件には含めない。

## 次回からの固定順序

1. DriveのAnalysis `current.json`とmanifestを取得し、SHA-256、size、schema、canonical key、row countを検証する。
2. `materialize_jrdb_analysis_sqlite.py`で一時SQLiteを作る。
3. `run_jrdb_analysis_post_race_incremental.py`でPACI + SEDの対象日だけを置換し、対象外行不変・as-of・canonical keyを監査する。
4. `build_jrdb_analysis_post_race_parquet_candidate.py`で新しいshadow generationを作る。ここでは`current.json`を変更しない。
5. generation assetをDriveへ保存し、別途再取得したrootでmanifest・asset SHA・size・row count・auditを検証する。
6. `publish_jrdb_analysis_parquet_drive_generation.py`でAnalysis `current.json`を切り替える。
7. 切替後のAnalysis Parquet bundleだけを入力にFact Lite Parquet generationを発行・同値性監査する。
8. Fact Lite current、GitHub Pages、条件別集計PWAを更新し、通常検索・オフライン検索を確認する。

Stats Martのrefresh・配布・PWA入力への復帰は行わない。必要になった場合は別Workで旧資産として個別に扱う。

いずれかのgateに失敗した場合、Analysis / Fact Lite / Pagesのcurrentは直前の正常generationを維持する。未参照の候補assetは残ってもよいが、既存generationを編集・上書きしてはならない。

## 実装状態

Parquet resolver、temporary SQLite materialization、日付置換監査、candidate生成、Drive round-trip promotion、Fact Liteのcurrent manifest限定入力、Parquet配布、Pages公開まで実装済みである。旧`jrdb_post_race_refresh_issue.yml`はStats Martを含む旧経路のため、通常の開催後更新には用いない。

## 完了報告

- 対象日、前後Analysis generation ID、Analysis row countと対象日row count
- canonical key重複・as-of・対象外行不変の監査
- Drive再取得のmanifest / SHA / size検証
- Fact Lite generation ID、6 relation監査、Pages deployment
- PWAでの新generation検出、通常検索、オフライン検索
