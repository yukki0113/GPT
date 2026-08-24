# JRDB Python tools

JRDB関連の取得・RaceNote変換・Core SQLite構築をGitで正本管理するための整理済みパッケージです。

## Current modules

- `src/fetch_jrdb_paci.py` — PACI前日一括ZIP取得
- `src/fetch_jrdb_history.py` — 年次ZIP / 2026年以降の単日ZIP取得
- `src/racenote_jrdb.py` — PACI ZIP → RaceNote v0.2 JSON
- `src/racenote_jrdb_pipeline.py` — PACI取得 → RaceNote 1R一体実行
- `src/build_jrdb_core.py` — JRDB Core Builder v1.1.2-production（現行production baseline）
- `src/jrdb_ukc.py` — UKC 290-byte固定長parser（v1.2用）
- `src/build_jrdb_core_v1_2.py` — v1.1.2を壊さずUKC horse profileを追加するv1.2 wrapper（回帰検証中）
- `tools/generate_jrdb_codebooks.py` — codebook生成
- `tools/audit_jrdb_core_v1_1_1.py` — Core監査ツール

## Dependencies

RaceNote:
`racenote_jrdb_pipeline.py` → `fetch_jrdb_paci.py` + `racenote_jrdb.py`
`racenote_jrdb.py` は `config/jrdb_codebooks.json` を利用。

Core v1.1.2:
`build_jrdb_core.py` は `schema/jrdb_core_schema_v1_1_2.sql` とRaw ZIP群を利用。

Core v1.2 (regression phase):
`build_jrdb_core_v1_2.py` → `build_jrdb_core.py` + `jrdb_ukc.py` + `schema/jrdb_core_schema_v1_2.sql`。
`horse_profile_current / horse_profile_history` に父・母・母父等のUKC profileを追加する。

## Design / next stage

- `docs/JRDB_Core_v1_2_Analysis_Layer_Design.md` — UKC血統拡張、Core v1.2、Analysis Lite、Stats Martの設計
- `docs/README_build_jrdb_core_v1_2.md` — v1.2実装方針・実行方法・回帰ゲート

Core v1.2が回帰合格するまではv1.1.2をproduction baselineとして維持します。
回帰合格後は、種牡馬項目を含むAnalysis Lite 2021-2025 PoCへ進みます。

## Security

認証情報はGit管理しません。
`.env` / `jrdb_secret.py` は `.gitignore` 対象です。
`.env.example` にキー名のみ収録しています。

## Validation

既存パッケージの移行時スモークテスト結果は `MIGRATION_MANIFEST.json` を参照してください。
v1.2追加分の実データ検証条件・結果は `docs/README_build_jrdb_core_v1_2.md` に記録します。
