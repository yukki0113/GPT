# JRDB Git migration status

Updated: 2026-09-06

**Status: Git migration COMPLETE / Common Reader P0 COMPLETE**

## 正本

- Python / SQL / schema / config / docs / tests: GitHub `yukki0113/GPT` の `main`
- JRDB Raw ZIP / PACI / 大容量SQLite / RaceNote Archive等の生成artifact: Git外ストレージ
- 固定長データの読み方: `src/jrdb_raw.py`（Common JRDB Raw Reader）
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

## Regression / CI

Common Readerの主要回帰は以下で固定する。

- `tests/test_jrdb_raw_common.py`
- `tests/test_jrdb_raw_racenote_compat.py`
- `tests/test_enrich_eval_csv_with_paci.py`
- `tests/test_jrdb_index_base_adapter.py`
- `tests/test_jrdb_analysis_raw_adapter.py`
- `tests/test_jrdb_racenote_raw_adapter.py`
- `tests/test_jrdb_eval_horse_result_adapter.py`

CI: `.github/workflows/jrdb_common_reader_tests.yml`

2026-09-06 P0最終確認:

- workflow: `JRDB Common Reader tests`
- run: `34028675390`
- production consumer compile: PASS
- regression tests: PASS
- conclusion: `success`

## 変更時のルール

新しいJRDB Raw fieldが必要になった場合:

1. `src/jrdb_raw.py` にfieldを追加する。
2. 公式固定長仕様と照合する。
3. characterization / consumer regression testを追加する。
4. Consumer adapterから利用する。
5. RaceNote schema・Eval CSV契約・Analysis schema等の変更が必要なら、parser共通化とは別変更として扱う。

unknown code / malformed recordを推測補完しない。Raw codeまたはaudit情報を保持し、必要なconsumer policyで明示的に処理する。

## Git対象外

- `jrdb_secret.py`
- `.env` 実値
- JRDB Raw ZIP / PACI ZIP
- SQLite DB / Archive shard
- 実行ログ / `.part` / cache / 日次成果物
- `__pycache__` / `*.pyc`

## P1として残すもの

P0完了は「JRDB全コードから全legacy parserを削除した」という意味ではない。以下は後続P1として扱う。

- rollback baselineとして残すCore系legacy parserの整理
- Common Reader未利用の小規模helper / race-name reader等の棚卸し
- Drive上の共有artifactを論理名から解決するStore Resolver / local cache層
- 必要になった場合の軽量history locator index

P1を行う場合も、P0で確立したCommon Reader contractと回帰CIを維持する。
