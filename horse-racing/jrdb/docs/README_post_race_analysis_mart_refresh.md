# JRDB 開催後 Analysis / Mart / Fact Lite 更新

## 正本と責務

Analysisの正本はGoogle Drive上のimmutable Parquet generationであり、`current.json`だけが現行generationを指す。SQLiteはPACI + SEDの既存差分ロジックとStats Mart集計のための一時materializationに限定する。Analysis SQLite ZIPをDrive正本、Fact Lite入力、PWA配布物へ戻してはならない。

Fact Liteの通常配布・PWA runtimeはParquet / DuckDB-Wasmである。Stats MartがSQLiteの間だけ、更新済みAnalysis Parquetから一時SQLiteを作成して対象年をrefreshする。

## 固定順序

1. DriveのAnalysis `current.json`とmanifestを取得し、SHA-256、size、schema、canonical key、row countを検証する。
2. `materialize_jrdb_analysis_sqlite.py`で一時SQLiteを作る。
3. `run_jrdb_analysis_post_race_incremental.py`でPACI + SEDの対象日だけを置換し、対象外行不変・as-of・canonical keyを監査する。
4. `build_jrdb_analysis_post_race_parquet_candidate.py`で新しいshadow generationを作る。ここでは`current.json`を変更しない。
5. generation assetをDriveへ保存し、別途再取得したrootでmanifest・asset SHA・size・row count・auditを検証する。
6. `publish_jrdb_analysis_parquet_drive_generation.py`でのみAnalysis `current.json`を原子的に切り替える。
7. 切替後のParquetから一時SQLiteを作り、Stats Martの対象年をrefresh・検証する。
8. 新Analysis Parquet bundleだけを入力にFact Lite Parquet generationを発行・監査し、Fact Lite current、GitHub Pages、PWAを更新する。

いずれかのgateに失敗した場合、Analysis / Fact Lite / Pagesのcurrentは直前の正常generationを維持する。未参照の候補assetは残ってもよいが、既存generationを編集・上書きしてはならない。

## 実装状態

Parquet resolver、temporary SQLite materialization、日付置換監査、candidate生成、Drive round-trip promotion、Fact LiteのParquet-only入力は実装済みである。新しい開催後workflowによる実データdry-runと、Stats MartからPagesまでの通し実行がGreenになるまでは、旧`jrdb_post_race_refresh_issue.yml`を新正本更新に用いない。

## 完了報告

- 対象日、前後Analysis generation ID、Analysis row countと対象日row count
- canonical key重複・as-of・対象外行不変の監査
- Drive再取得のmanifest / SHA / size検証
- Stats Mart対象年の件数・integrity
- Fact Lite generation ID、6 relation監査、Pages deployment
- PWAでの新generation検出、通常検索、オフライン検索
