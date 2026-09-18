# JRDB 開催後 Analysis / Fact Lite / Pages 更新 Work 引継ぎ

更新日: 2026-09-18

## このWorkの目的

開催後にPACI + SEDをAnalysisへ反映し、Analysis Parquet、Fact Lite Parquet、条件別集計PWAを同一のAnalysis generationに揃える。Analysisの長期正本はParquet generationであり、SQLiteは一時的な互換・生成用途だけである。

Stats Martは旧思想のSQLite資産として現状維持する。このWorkではStats Martを更新・再配布せず、Analysis更新の完了条件にも含めない。

## 使用モジュール

- `jrdb_analysis_parquet_current.py` — current / manifest / asset検証
- `materialize_jrdb_analysis_sqlite.py` — 検証済みParquetの一時SQLite化
- `run_jrdb_analysis_post_race_incremental.py` — PACI + SED対象日の完全置換と不変監査
- `build_jrdb_analysis_post_race_parquet_candidate.py` — shadow generation作成
- `publish_jrdb_analysis_parquet_drive_generation.py` — Drive再取得検証後のcurrent切替
- `build_jrdb_pwa_fact_lite_dual.py` / `audit_jrdb_pwa_fact_lite_dual.py` — Fact Lite SQLite/Parquet同値性監査
- `publish_jrdb_fact_lite_parquet.py` / `package_jrdb_pwa_fact_lite_parquet.py` — Fact Lite generationとbrowser package
- `.github/workflows/jrdb_pwa_fact_lite_publish.yml` — Fact Lite生成・配布・Pages更新

## 実行順序と停止条件

`current resolve → temporary SQLite → PACI/SED replace → candidate → Drive upload → re-fetch verify → Analysis current → Fact Lite → Pages → PWA acceptance`

- candidate、Drive再取得、Fact Lite同値性監査、Pagesのどこかが不合格なら、以降へ進まない。
- 失敗時はAnalysis / Fact Lite / Pagesのcurrentを直前の正常generationから動かさない。
- 既存generation・既存Parquet object・既存current.jsonの直接編集は禁止。
- canonical key、as-of、固定長parserの意味論を変更しない。
- SQLiteをDrive正本、Fact Lite配布、PWA runtime fallbackへ戻さない。
- 旧`jrdb_post_race_refresh_issue.yml`はStats Martを含む旧経路のため、通常の開催後更新には使用しない。

## 次回依頼に必要な入力

- 対象開催日（例: `2026-09-19`）
- Drive上のAnalysis Parquet current bundleは既存current IDを使用
- Fact Liteの`data_version`は最新開催日をYYYYMMDDで指定

依頼後は、Analysis candidate → Drive round-trip → current切替 → Fact Lite / Pages公開までを一連で実行する。
