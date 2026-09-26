# CURRENT STORAGE / HISTORICAL INPUT STATUS — 2026-09-23

> This block supersedes older path/source-of-truth statements below when they conflict. The remainder is retained as migration history/evidence.
>
> - Git code/schema/current docs: `horse-racing/jrdb/` on `main`.
> - Historical normalized canonical (2010–2025): `GPT/horse-racing/10_warehouse/jrdb/v1/current.json`.
> - Raw/reproducibility: `GPT/horse-racing/00_raw` plus retained legacy Raw where still explicitly required.
> - New consumer marts: `GPT/horse-racing/20_mart`.
> - Old top-level `GPT/JRDB` remains active for legacy Analysis/Fact Lite/Stats/store compatibility; do not delete yet.
> - RaceNote direct Historical rebuild is Warehouse-standard; full Archive backfill plumbing is technical debt.
> - RL-T / Training Edge Historical workflow cutover remains pending Index Base equivalence; 2026 PACI/SED stays Raw-direct.

# JRDB Git migration status

Updated: 2026-09-07

**Status: Git migration COMPLETE / Common Reader P0 COMPLETE / Store Resolver + Canonical 2024 P1-1 COMPLETE / Analysis history-index P1-2 COMPLETE**

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
- PWA race-name lookup
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

## Analysis history-index P1-2

RaceNote v1.0の履歴enrichmentがAnalysis Liteへ繰り返し発行する

```sql
WHERE horse_id=? AND race_date<?
```

に対し、Analysis v1.2に以下の物理indexを追加した。

```sql
CREATE INDEX ix_analysis_horse_history
ON fact_entry_result_lite(horse_id, race_date DESC, race_no DESC);
```

これは物理アクセス最適化であり、Analysis logical schemaは **v1.2のまま**とする。列・型・主キー・as-of条件・RaceNote v1.0 JSON契約は変更しない。

2024-12-28 中山11R・18頭・2000mのRaceNote-shaped local benchmark:

- engine-equivalent queries: 303
- baseline: **10.7868 s**
- indexed: **0.0736 s**
- query-result comparison: **完全一致**

1400m/1800mの距離レンジ重複ケース（409 query）でも大幅改善を確認済み。詳細は `docs/JRDB_Analysis_History_Index_Benchmark_20260907.md`。

### production artifact昇格

同一Analysisデータへindexだけを追加したartifactをDriveへZIP transportで配置し、通常 `[RACENOTE_REQUEST]` workflowでE2E比較した。

Baseline:

- Issue #452 / run `34072355676`
- original unindexed Analysis v1.2
- RaceNote request step: 約7.94 s

Indexed:

- Issue #453 / run `34087811996`
- warning 0 / workflow success
- RaceNote request step: 約5.90 s

最終 `race_bundle_20241228_中山11R.json` は **264,682 bytes、SHA-256 `b9e82e8db7d7b514dbf9bde962317d9d7487b93d192fba4dc2e23f645435e46f` でbyte-for-byte一致**した。

昇格後の `jrdb://analysis/current`:

- artifact revision: `historyidx-20260907`
- storage compression: ZIP
- storage size: **60,569,456 bytes**
- storage SHA-256: `0c0d604e331e9afc6ba9c8489b993915f817b41bdb3303a2a8a0fb53dfbbe023`
- payload size: **212,938,752 bytes**
- payload SHA-256: `25e9cb29f0d957f484d4f2daec7a8656a9a7ef0435dde09338f31c61be91457a`
- rows: **513,512**
- SQLite integrity_check: **ok**

2026-09-07にlive Store manifestを更新し、`analysis/current` をこのartifactへ昇格した。旧unindexed Analysisファイルは削除せずrollback用に残す。

## Regression / CI

Common Reader / Store / Canonical / Analysis history-indexの主要回帰は以下で固定する。

- `tests/test_jrdb_raw_common.py`
- `tests/test_jrdb_raw_history_batch.py`
- `tests/test_jrdb_raw_racenote_compat.py`
- `tests/test_jrdb_store.py`
- `tests/test_racenote_store_resolution.py`
- `tests/test_jrdb_canonical_builder.py`
- `tests/test_enrich_eval_csv_with_paci.py`
- `tests/test_jrdb_index_base_adapter.py`
- `tests/test_jrdb_analysis_raw_adapter.py`
- `tests/test_jrdb_racenote_raw_adapter.py`
- `tests/test_jrdb_eval_horse_result_adapter.py`
- `tests/test_racenote_analysis_history_index.py`

CI: `.github/workflows/jrdb_common_reader_tests.yml`

2026-09-06 Canonical追加後確認:

- workflow: `JRDB Common Reader tests`
- run: `34037794467`
- regression tests: **45 tests / 45 PASS**
- conclusion: `success`

2026-09-07 Analysis history-index regression追加後確認:

- workflow: `JRDB Common Reader tests`
- run: `34088419323`
- schema/planner regressionを含む
- conclusion: `success`

## Store live E2E status — COMPLETE

Store Resolver自身のnetwork-enabled live E2Eも2026-09-07に完了した。

- workflow: `.github/workflows/jrdb_store_smoke_issue.yml`
- Issue: #454 `[JRDB_STORE_SMOKE] analysis-current-20260907`
- run: `34088924350`
- workflow conclusion: `success`
- logical name: `analysis/current`
- resolved payload size: **212,938,752 bytes**
- resolved payload SHA-256: `25e9cb29f0d957f484d4f2daec7a8656a9a7ef0435dde09338f31c61be91457a`
- SQLite integrity_check: **ok**
- fact rows: **513,512**
- `ix_analysis_horse_history` presence: confirmed

このsmokeはlive manifestだけを通常downloadした後、`src/jrdb_store.py` の `StoreResolver` 自身に `analysis/current` をresolveさせている。したがって、Drive file ID解決 → storage download → storage SHA/size validation → ZIP member materialization → payload SHA/size validation → SQLite検証というStore Resolverのlive network pathを実際に通している。

これにより、従来のsynthetic Store testとRaceNote互換URL E2Eに加えて、Store Resolver本体のlive direct-download E2Eも確認済みとなった。

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
6. `YTD/current` の昇格でも旧artifactを即削除せず、E2E同値性を確認してからlocatorを切り替える。

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

P0/P1-1/P1-2完了は「JRDB全コードから全legacy parserを削除した」という意味ではない。以下は後続P1として扱う。

- rollback baselineとして残すCore系legacy parserの整理
- Common adapterへ移行済みconsumer内に残る到達不能legacy fixed-width blockのcleanup
- 2024以外のannual Canonical shardは、実際に反復アクセス需要がある年から段階追加
- RaceNote / Eval / PWAへのCanonical利用は、Raw直読より実利益がある経路だけ個別判断

P1を続ける場合も、P0で確立したCommon Reader contractと回帰CIを維持する。
## RL-T production Historical Warehouse cutover — 2026-09-26

The production upstream cutover for RL-T / Training Edge / Training Research is complete at the storage/plumbing layer.

- accepted Historical generation: `jrdb_normalized_warehouse_v1_2010_2025_g20260921`
- daily: 2010–2025 = Warehouse, 2026 = existing PACI + settled SED / Raw direct
- replay: 2010–2025 = Warehouse, 2026 = existing replay PACI / settled SED route
- Training Research: 2010–2025 = Warehouse-only Index Base build
- shared input preparer: `src/prepare_rl_t_historical_warehouse_inputs.py`
- Historical Raw normal fetch in the three production workflows: disabled
- Historical Raw fallback in production: disabled
- static production cutover audit: Issue #1520 / run `36242350903` = PASS
- fixed-date replay/scorer smoke (2026-09-20, settled through 2026-09-19): Issue #1517 / run `36240031550` = SUCCESS
- Training Research full build + audit + Stage1b + Parquet generation: Issue #1518 / run `36240033827` = SUCCESS

Status:

```text
RL_T_PRODUCTION_CUTOVER               = PASS
TRAINING_RESEARCH_UPSTREAM_CUTOVER    = PASS
HISTORICAL_NORMAL_OPERATION           = WAREHOUSE
HISTORICAL_RAW_NORMAL_FETCH           = DISABLED
HISTORICAL_RAW_FALLBACK               = DISABLED
2026_DAILY_ROUTE                      = UNCHANGED
RL_T_OLD_GPT_JRDB_ACTIVE_REFERENCE_COUNT = 0
```

Operational follow-up is tracked separately in Issue #1521: a 2026-09-27 forward smoke reached Warehouse/Drive/bundle/Index/RunPerf/projection successfully, then the unchanged frozen Training Edge v0.2 runtime fingerprint guard failed closed. Do not change the frozen science or re-enable Historical Raw fallback to bypass that guard.

## EdgeDB post-migration execution cleanup — 2026-09-26

Status:

```text
EDGE_FEATURE_MART_SQLITE_BRIDGE = RETIRED
EDGE_FEATURE_MART_EXECUTION = DUCKDB
EDGE_FEATURE_MART_CANONICAL = PARQUET
EDGE_REGISTRY_MUTABLE_BUILD = TRANSIENT_SQLITE_ALLOWED
EDGE_REGISTRY_CANONICAL = PARQUET
EDGE_REGISTRY_CANONICAL_READ = DUCKDB_DIRECT
EDGE_REGISTRY_PARQUET_TO_SQLITE_NORMAL_ROUTE = DISABLED
```

Normal full-build / research operation must not materialize canonical Feature Mart Parquet back into SQLite. One validated DuckDB execution workspace is shared by discovery, temporal validation, HUMAN calibration, and statistical guard.

Registry is intentionally different: its small mutation-heavy build workspace may remain transient SQLite, but a successful v0.2 full build must emit a Registry Parquet candidate in the same run. Current/canonical consumers use Parquet + DuckDB direct reads. SQLite rematerialization is legacy reproduction only.

This cleanup changes storage/execution plumbing only; v0.2 STANDARD, v0.3 SHADOW, matcher/serving semantics, and TRUE_FORWARD leakage boundaries are unchanged.

