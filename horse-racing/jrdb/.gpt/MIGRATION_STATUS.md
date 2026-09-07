# JRDB Git migration status

Updated: 2026-09-07

**Status: Git migration COMPLETE / Common Reader P0 COMPLETE / Store Resolver + Canonical 2024 P1-1 COMPLETE**

## 正本

- Python / SQL / schema / config / docs / tests: GitHub `yukki0113/GPT` の `main`
- JRDB Raw ZIP / PACI: データ原典 / reproducibility source
- 固定長データの読み方: `src/jrdb_raw.py`（Common JRDB Raw Reader）
- Analysis Lite / Stats Mart / annual Canonical等の共有artifactの所在: Google Drive `JRDB/manifest/jrdb_store_manifest_v1.json`
- ローカル共有artifact: `src/jrdb_store.py` がmaterializeする検証済みcache。手動管理する正本ではない
- RaceNote Archive: immutable GitHub Release asset + release metadata
- 秘密情報: 環境変数またはローカル `jrdb_secret.py`。Gitへ保存しない

旧移行元ZIPを日常運用の正本として参照しない。Git mainに存在しない実装を旧ZIPから推測して補完しない。

## Git移行完了確認

旧 `MIGRATION_STATUS.md` で未投入としていた以下も現在はGit mainに存在する。

- `src/racenote_jrdb.py`
- `config/jrdb_codebooks.json`
- `docs/reference/整理版_JRDB_マスタコード定義.md`
- `docs/reference/整理版_JRDB_固定長データ定義.md`

RaceNote / Eval / Analysis / PWA/indexを含む現行JRDB Python実装・schema・tests・主要仕様書はGit mainを正本として扱う。

## Common Reader P0

`src/jrdb_raw.py` を次のTYPEの固定長解釈の正本とする。

```text
BAC / KYI / CHA / CYB / SED / SKB / ZED / ZKB / UKC
```

Common Readerの責務:

- CP932 fixed-width field decode
- byte offsetによるneutral parse
- race key / race-horse key / result key
- PACI / annual Raw record split
- canonical ZIP member列挙
- record-length audit

ConsumerはCommon Readerの結果を既存schema / policyへ投影する。Common Reader対応fieldのbyte offsetをRaceNote / Eval / Analysis / PWA側へ重複実装しない。

### P0 production migration済み

- RaceNote PACI/base parser
- RaceNote historical annual Raw fallback
- RaceNote Archive full-month Raw builder
- Eval PACI enrichment
- Eval BAC race-condition exporter
- Eval BAC+SED race dataset exporter
- Eval SED horse-result exporter
- Analysis Lite full rebuild
- Analysis Lite incremental updater
- PWA/index-base Raw builder
- annual Raw horse history access

Consumer-specific adapter:

- `src/jrdb_racenote_raw_adapter.py`
- `src/jrdb_analysis_raw_adapter.py`
- `src/jrdb_eval_raw_adapter.py`
- `src/jrdb_eval_horse_result_adapter.py`
- `src/jrdb_index_base_adapter.py`

## Store Resolver / Canonical P1-1

2026-09-06〜07に次を完了した。

### Shared Store

- `src/jrdb_store.py` を追加。
- Consumerは個別Drive File ID / 恒久ローカルpathではなく `jrdb://...` logical nameを要求する。
- live locator正本はGit外固定名 `JRDB/manifest/jrdb_store_manifest_v1.json`。
- content-addressed local cache、storage/payload size + SHA-256検証、ZIP member限定materialize、offline mode、`FINAL / YTD / PUBLISHED / CANDIDATE` status policyを実装。
- 現行entry:
  - `jrdb://analysis/current`
  - `jrdb://stats/current`
  - `jrdb://canonical/2024`
- RaceNote Routerは明示 `--analysis` / `--mart` の互換動作を維持し、未指定artifactだけStoreから解決可能。

### Canonical Annual Shard v0.1

- schema: `schema/jrdb_canonical_schema_v0_1.sql`
- builder: `src/build_jrdb_canonical.py`
- test: `tests/test_jrdb_canonical_builder.py`
- design: `docs/JRDB_Canonical_Annual_Shard_v0_1.md`
- CanonicalはCommon Reader neutral factsの任意materializationであり、RawやCommon Readerを置換しない。
- BAC/KYI/CHA/CYB/SED/SKB/UKCを保持。KYI previous links / traits、SKB special-note / equipmentはchild table化。
- Raw BLOBは保持せず、source archive/memberとnormalized record SHAをprovenanceとして保持する。

2024実データ:

- source records: **286,540**
- BAC: **3,454**
- KYI / CHA / CYB / SED / SKB / UKC: **各47,181**
- field-level sample comparison: **7 family × 100件 = 700件、mismatch 0**
- SQLite integrity_check: **ok**
- SQLite: **178,450,432 bytes (~170.18 MiB)**
- ZIP transport: **54,815,315 bytes (~52.28 MiB)**
- full build + ANALYZE + VACUUM: **約16.9秒**
- Drive: `JRDB/10_database/canonical/jrdb_canonical_2024_v0_1.sqlite.zip`
- live manifest: `jrdb://canonical/2024`, status `FINAL`

Canonicalは単発RaceNote/Evalを無条件にSQLite化するための層ではない。Raw/PACI直読が十分速い処理は維持し、反復・横断アクセスで利益があるconsumerだけ段階利用する。

## Regression / CI

Common Reader / Store / Canonicalの主要回帰は以下で固定する。

- `tests/test_jrdb_raw_common.py`
- `tests/test_jrdb_raw_racenote_compat.py`
- `tests/test_jrdb_store.py`
- `tests/test_racenote_store_resolution.py`
- `tests/test_jrdb_canonical_builder.py`
- `tests/test_enrich_eval_csv_with_paci.py`
- `tests/test_jrdb_index_base_adapter.py`
- `tests/test_jrdb_analysis_raw_adapter.py`
- `tests/test_jrdb_racenote_raw_adapter.py`
- `tests/test_jrdb_eval_horse_result_adapter.py`

CI: `.github/workflows/jrdb_common_reader_tests.yml`

2026-09-06 Canonical追加後確認:

- workflow: `JRDB Common Reader tests`
- run: `34037794467`
- `build_jrdb_canonical.py` compile: PASS
- regression tests: **45 tests / 45 PASS**
- Canonical synthetic builder test: PASS
- conclusion: `success`

## Store live E2E status

- Drive connector経由でlive manifest、Canonical ZIP metadata、storage size、manifest登録内容を確認済み。
- Store Resolverのdownload/cache/materialize/SHA policyはsynthetic regressionでPASS。
- このChatGPT実行環境のローカルコンテナは外部DNSが閉じているため、`drive.usercontent.google.com` をResolver自身が直接取得するlive network E2Eだけは未確認。これはコード失敗ではなく実行環境制約として記録する。
- 実PCまたはnetwork-enabled Actionsで初回live resolveを実施した際、storage SHA、payload SHA、SQLite integrity_checkまで確認して本項を更新する。

## 変更時のルール

新しいJRDB Raw fieldが必要になった場合:

1. `src/jrdb_raw.py` にfieldを追加する。
2. 公式固定長仕様と照合する。
3. characterization / consumer regression testを追加する。
4. Consumer adapterから利用する。
5. RaceNote schema・Eval CSV契約・Analysis schema等の変更が必要なら、parser共通化とは別変更として扱う。

共有artifactを追加・更新する場合:

1. Git側schema/builder/testを正本化する。
2. 実データvalidationを完了する。
3. 大容量artifactをGitへcommitせずDriveへ配置する。
4. live manifestへlogical name / version / period / status / storage+payload size/SHAを登録する。
5. `FINAL` を同一logical nameで黙って差し替えない。

unknown code / malformed recordを推測補完しない。Raw codeまたはaudit情報を保持し、必要なconsumer policyで明示的に処理する。

## Git対象外

- `jrdb_secret.py`
- `.env` 実値
- JRDB Raw ZIP / PACI ZIP
- SQLite DB / Archive shard / Canonical shard
- live Store manifest（Drive File IDを含む）
- 実行ログ / `.part` / cache / 日次成果物
- `__pycache__` / `*.pyc`

## P1として残すもの

P0/P1-1完了は「JRDB全コードから全legacy parserを削除した」という意味ではない。以下は後続P1として扱う。

- rollback baselineとして残すCore系legacy parserの整理
- Common Reader未利用の小規模helper / race-name reader等の棚卸し
- 必要な場合の軽量history locator index / batch history API拡張
- 2024以外のannual Canonical shardは、実際に反復アクセス需要がある年から段階追加
- RaceNote / Eval / PWAへのCanonical利用は、Raw直読より実利益がある経路だけ個別判断
- network-enabled環境でのStore live direct-download E2E記録

P1を続ける場合も、P0で確立したCommon Reader contractと回帰CIを維持する。
