# JRDB Git migration status

Updated: 2026-08-24

## Gitへ移行済み

### src
- `build_jrdb_core.py` — v1.1.2-production
- `fetch_jrdb_history.py`
- `fetch_jrdb_paci.py`
- `racenote_jrdb_pipeline.py`

上記4本は移行元ZIPとGit blobの内容一致を確認済み。

### tools / schema / docs
- `tools/audit_jrdb_core_v1_1_1.py`
- `tools/generate_jrdb_codebooks.py`
- `schema/jrdb_core_schema_v1_1_2.sql`
- 各モジュールREADME
- `docs/reference/整理版_JRDB_ファイル相関・キー定義.md`
- source inventory v2 / v3
- `.env.example`
- `MIGRATION_MANIFEST.json`

## 移行元ZIPには存在するがGit投入未完了

以下はファイル容量が大きく、GitHub連携経由の転送時に内容省略を防ぐため未投入。添付ZIP `JRDB_Git移行_ready_20260824.zip` を移行元正本として扱う。

- `src/racenote_jrdb.py`
- `config/jrdb_codebooks.json`
- `docs/reference/整理版_JRDB_マスタコード定義.md`
- `docs/reference/整理版_JRDB_固定長データ定義.md`

これらがGitへ投入されるまでは、GitだけでRaceNote変換環境が完全には再現できない。

## Git対象外

- `jrdb_secret.py`
- `.env` 実値
- JRDB Raw ZIP
- SQLite DB
- 実行ログ / `.part` / キャッシュ / 日次成果物
- `__pycache__` / `*.pyc`

## 運用上の注意

作業開始時に本ファイルを確認すること。未投入ファイルをGit上に存在するものとして推測・再生成しない。移行完了後、本ファイルを `COMPLETE` 状態へ更新する。
