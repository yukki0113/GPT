# JRDB 開催後 Analysis / Mart 更新 Work 引継ぎ

更新日: 2026-09-18

## このWorkの目的

開催後にPACI + SEDをAnalysisへ反映し、Stats Mart、Fact Lite Parquet、条件別集計PWAまでを同一のAnalysis Parquet generationに揃える。Analysisの長期正本はParquet generationであり、SQLiteは一時的な互換・集計用途だけである。

## 使用モジュール

- `jrdb_analysis_parquet_current.py` — current / manifest / asset検証
- `materialize_jrdb_analysis_sqlite.py` — 検証済みParquetの一時SQLite化
- `run_jrdb_analysis_post_race_incremental.py` — PACI + SED対象日の完全置換と不変監査
- `build_jrdb_analysis_post_race_parquet_candidate.py` — shadow generation作成
- `publish_jrdb_analysis_parquet_drive_generation.py` — Drive再取得検証後のcurrent切替
- `refresh_jrdb_stats_mart_year.py` — 一時SQLiteからのMart対象年refresh
- `publish_jrdb_fact_lite_parquet.py` / `package_jrdb_pwa_fact_lite_parquet.py` — Fact Lite generationとbrowser package

## 実行順序と停止条件

`current resolve → temporary SQLite → PACI/SED replace → candidate → Drive upload → re-fetch verify → Analysis current → Mart → Fact Lite → Pages → PWA acceptance`

- candidate、Drive再取得、Fact Lite監査、Pagesのどこかが不合格なら、以降へ進まない。
- 失敗時はcurrent pointerを戻すのではなく、まだ動かしていないことを確認する。
- 既存generation・既存Parquet object・既存current.jsonの直接編集は禁止。
- canonical key、as-of、固定長parserの意味論を変更しない。
- SQLiteをDrive正本、Fact Lite配布、PWA runtime fallbackへ戻さない。

## 引継ぎ時の確認

1. `JRDB Analysis Parquet post-race tests`がGreenであること。
2. 新開催後workflowのdry-runが、実データをpromoteせずにcandidateまで成功すること。
3. Drive round-trip、Mart、Fact Lite、Pages、PWA通常／オフライン検索を同一generationで確認すること。

上記3が未完了なら、新正本のproduction更新は開始しない。旧SQLite workflowをParquet正本の代替として実行してはならない。
