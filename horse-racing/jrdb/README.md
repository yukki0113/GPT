# JRDB Python tools

JRDB関連の取得・RaceNote変換・Core SQLite構築をGitで正本管理するための整理済みパッケージです。

## Current modules

- `src/fetch_jrdb_paci.py` — PACI前日一括ZIP取得
- `src/fetch_jrdb_history.py` — 年次ZIP / 2026年以降の単日ZIP取得
- `src/racenote_jrdb.py` — PACI ZIP → RaceNote v0.2 JSON
- `src/racenote_jrdb_pipeline.py` — PACI取得 → RaceNote 1R一体実行
- `src/build_jrdb_core.py` — JRDB Core Builder v1.1.2-production
- `tools/generate_jrdb_codebooks.py` — codebook生成
- `tools/audit_jrdb_core_v1_1_1.py` — Core監査ツール

## Dependencies

RaceNote:
`racenote_jrdb_pipeline.py` → `fetch_jrdb_paci.py` + `racenote_jrdb.py`
`racenote_jrdb.py` は `config/jrdb_codebooks.json` を利用。

Core:
`build_jrdb_core.py` は `schema/jrdb_core_schema_v1_1_2.sql` とRaw ZIP群を利用。

## Security

認証情報はGit管理しません。
`.env` / `jrdb_secret.py` は `.gitignore` 対象です。
`.env.example` にキー名のみ収録しています。

## Validation

パッケージ内Pythonについて `py_compile` と `--help` のスモークテストを実施。
結果は `MIGRATION_MANIFEST.json` を参照してください。
