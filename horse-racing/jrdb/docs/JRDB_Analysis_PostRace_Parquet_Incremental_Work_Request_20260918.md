# JRDB 開催後 Analysis 差分更新 Work — Parquet正本化 引継ぎ・改修指示

対象: 旧「Analysis DB差分更新 / Stats Mart再発行 / Fact Lite配布」Work

## 1. 背景と結論

Analysisの長期正本は immutable Parquet generation へ移行済みである。Fact LiteのPWAも Parquet / DuckDB-Wasm readerへ切替済みであり、通常配布・通常実行にFact Lite SQLiteを使用しない。

しかし既存の開催後差分更新Workは、`update_jrdb_analysis_incremental.py` が既存Analysis SQLiteを直接 `DELETE / INSERT` する前提であり、運用文書にも「PWA publication remains SQLite-only」とする古い記述が残る。このWorkを、**Parquet currentを唯一のAnalysis正本として更新する経路**へ改修する。

SQLiteは既存の差分結合ロジック、Stats Mart等の未移行consumerに限る一時materializationとして使用してよい。ただし、Drive正本・current pointer・Fact Lite入力・PWA配布をSQLiteへ戻してはならない。

## 2. 正式な開催後更新経路

```text
Analysis current.json / manifest / Parquet
  → temporary compatibility SQLite materialization
  → PACI + SED による既存日付の差分置換
  → full validation
  → Analysis Parquet immutable generationを新規生成
  → Drive保存・再取得・manifest/SHA検証
  → Analysis current.json切替
  → Stats Mart対象年refresh（必要な一時SQLiteを使用可）
  → Fact Lite Parquet generation生成・監査
  → Fact Lite current / Pages配布
  → PWAで新generation検出・検索・オフライン確認
```

既存generation・既存Parquet object・既存current.jsonを直接編集してはならない。途中失敗時はAnalysis current、Fact Lite current、Pages配布をすべて直前の正常generationのまま維持する。

## 3. 実装指示

### 3.1 Analysis差分入力の切替

- 開始時にDrive上のAnalysis `current.json` とgeneration manifestを解決する。
- manifestのSHA-256、size、schema version、canonical key、row countを検証してから入力を使用する。
- `materialize_jrdb_analysis_sqlite.py` を用いて、解決済みParquet generationから作業用SQLiteを一時作成する。
- 既存 `update_jrdb_analysis_incremental.py` のPACI / SED入力、固定長parser、as-of・canonical key・対象日の完全置換ロジックは変更しない。
- 一時SQLite上の更新後に、schema、対象日row count、重複ゼロ、全期間canonical key一意性、履歴as-of、入力SHAを監査する。

### 3.2 Analysis正本の再発行

- 更新済み一時SQLiteから `migrate_jrdb_analysis_parquet.py` で**新しいimmutable generation**を生成する。
- generationは年別content-addressed Parquet、manifest、auditを持つこと。
- Driveへ新generationを保存後、保存物を再取得してmanifest・asset SHA・row countを検証する。
- 再取得検証がPASSした場合のみAnalysis `current.json` を新generationへ切替える。
- SQLiteは比較・一時materialization以外では保存正本にしない。通常運用でSQLite ZIPをAnalysisと二重配布しない。

### 3.3 下流consumer

- Stats MartがSQLite入力を必要とする間は、更新済みAnalysis Parquetから一時SQLiteをmaterializeして対象年refreshを行う。Stats Martの意味論・既存監査は変更しない。
- Fact Lite publishは、新Analysis Parquet generationのbundle / manifestを唯一の入力として起動する。
- Fact Liteの発行はParquet generation、同値性監査、`current.json`、Pagesの順とする。`jrdb-pwa-fact-lite-current` SQLite ReleaseやSQLite runtime fallbackを復活させない。
- Pages配布後は端末側で「最新版を確認」を実行し、新generationの取得・検証・OPFS current切替、通常検索、オフライン検索を確認する。

## 4. 変更対象

- `horse-racing/jrdb/src/update_jrdb_analysis_incremental.py`
  - SQLite更新ロジックは再利用可能にし、直接のDrive正本更新を前提にしない。
- 開催後更新を起動するworkflow / request handler
  - Analysis Parquet current resolver、temporary SQLite materialization、新generation発行、round-trip validation、current切替を順序固定で接続する。
- `horse-racing/jrdb/docs/README_post_race_analysis_mart_refresh.md`
- `horse-racing/jrdb/docs/JRDB_開催後Analysis_Mart更新_Work引継ぎ_20260911.md`
  - SQLite-only PWA、SQLite Release、SQLite OPFSなど切替前の記述を現行Parquet/ DuckDB経路へ更新する。
- 必要なunit / integration test

## 5. 必須受入ゲート

- 対象日だけが置換され、対象外の日付・行が変わらない。
- canonical keyの重複・欠損がない。
- Analysis Parquetのmanifest / asset SHA / size / row count / schemaがPASSする。
- Drive再取得後の検証がPASSするまでAnalysis currentを動かさない。
- Stats Mart refreshが既存集計と整合する。
- Fact Liteの6 relationについて新generationの監査がPASSする。
- Pages配布が成功し、端末が新Fact Lite generationを検出する。
- 更新後も通常検索とオフライン検索が成立する。
- 任意の候補・Drive upload・Pages publish失敗時に、直前のAnalysis / Fact Lite / Pages currentが不変である。

## 6. 禁止事項

- 既存Analysis Parquet generationや`current.json`の直接編集
- canonical key、as-of、固定長parserの意味論変更
- SQLiteを通常のDrive正本・Fact Lite PWA配布・runtime fallbackへ戻すこと
- Analysis current切替前にFact Lite / Pagesを先行更新すること
- 監査不一致を許容・推測補正してpublishすること

## 7. 完了報告に含める項目

- 更新対象日、前後のAnalysis generation ID、Fact Lite generation ID
- Analysis / Fact Liteのrow count、対象日row count、重複・欠損監査
- manifest・SHA-256・Drive再取得検証・Stats Mart・Fact Lite監査の結果
- Pages run、端末で確認した更新検出・通常検索・オフライン検索の結果
- 失敗時にcurrentを維持したか、または実施したrollback
