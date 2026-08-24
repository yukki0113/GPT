# JRDB Python tools

JRDB関連の取得・RaceNote変換・Core / Analysis / Stats Mart SQLite構築をGitで正本管理するための整理済みパッケージです。

## Current modules

- `src/fetch_jrdb_paci.py` — PACI前日一括ZIP取得
- `src/fetch_jrdb_history.py` — 年次ZIP / 2026年以降の単日ZIP取得
- `src/racenote_jrdb.py` — PACI ZIP → RaceNote v0.2 JSON
- `src/racenote_jrdb_pipeline.py` — PACI取得 → RaceNote 1R一体実行
- `src/build_jrdb_core.py` — JRDB Core Builder v1.1.2-production（rollback baseline）
- `src/jrdb_ukc.py` — UKC 290-byte固定長parser
- `src/build_jrdb_core_v1_2.py` — UKC horse profile追加版
- `src/build_jrdb_core_v1_2_1.py` — v1.2 + KYI枠番 / SED馬場状態を追加
- `src/build_jrdb_analysis.py` — Core v1.2.1 → Analysis Lite v1.2（reference/regression path）
- `src/build_jrdb_analysis_from_raw.py` — Raw年次ZIP → Analysis Lite v1.2（production full-rebuild path）
- `src/update_jrdb_analysis_incremental.py` — PACI+SED または2026+単日Raw → Analysis Lite v1.2 増分置換
- `src/upgrade_jrdb_analysis_v1_1_to_v1_2.py` — 既存v1.1 Analysisへprev1/batch管理を追加
- `src/build_jrdb_stats_mart.py` — Analysis Lite → 年次Stats Mart v1.1
- `src/refresh_jrdb_stats_mart_year.py` — 指定年だけStats Martを再集計・置換
- `tools/generate_jrdb_codebooks.py` — codebook生成
- `tools/audit_jrdb_core_v1_1_1.py` — Core監査ツール
- `tools/audit_jrdb_core_v1_2_regression.py` — v1.1.2 / v1.2回帰比較
- `tools/audit_jrdb_analysis_equivalence.py` — Core→Analysis / Raw→Analysis 全列等価性比較

## Production data flow

Routine analysis generation does not require Core as an intermediate artifact.

```text
canonical Raw ZIPs
  ├─> Core                         # audit / complete normalized history / reproducibility
  └─> rolling Analysis Lite       # routine GPT/PWA analysis
        └─> Stats Mart
```

During the season, the recommended manual/ChatGPT path is:

```text
PACIyymmdd.zip + SEDyymmdd.zip
  -> Analysis incremental replace/add
  -> refresh current-year Stats Mart
```

PACI supplies BAC/KYI/CYB/UKC. SED supplies completed results, payouts and actual track condition. HJC/TYB are not required by the current Analysis schema.

The individual daily-kind layout (`BAC/KYI/SED/CYB/UKC`) remains supported for fetcher-oriented operation.

At year-end:

```text
rolling Analysis
  -> rebuild directly from next 10-year Raw window
  -> compact/VACUUM
  -> full Stats Mart rebuild
```

Core is maintained independently when audit/history/rebuild work requires it. `Core -> Analysis` remains the validated reference/regression path.

## Analysis Lite v1.2

Shared schema:

`schema/jrdb_analysis_schema_v1_2.sql`

Important fields:

- `race_condition_code` = BAC競走条件
- `track_condition_code` = SED実馬場状態
- `frame_no` = KYI枠番
- `sire_name` / `broodmare_sire_name` = UKC血統
- `prev_result_key_1` / `prev_race_key_1` = KYIが明示する前走1リンク

All five previous-result links remain in Raw/Core. Routine Analysis keeps prev1 only to preserve remote-delivery size headroom.

## Validation status

### Raw -> Analysis v1.2 equivalence

- 2016-2020: 243,849 rows × 33 columns, differences 0
- 2021-2025: 237,778 rows × 33 columns, differences 0
- combined 2016-2025: **481,627 rows, exact equivalence PASS**

### Analysis Lite v1.2 2016-2025

After prev1 addition, removal of unnecessary prev-key indexes and VACUUM:

- rows: **481,627**
- sire nonblank: **481,519**
- prev1 populated: **434,622**
- SQLite: **182,439,936 bytes (~173.99 MiB)**
- integrity_check: **ok**

A full normalized previous-link 1-5 child-table benchmark produced ~1.78M rows / ~81.9 MiB by itself, so prev1-only is the production Analysis design.

### Incremental Analysis regression

Historical pseudo-daily 2025-12-28 test:

- 24 races
- 356 rows before replacement
- 356 rows after replacement
- complete row hash identical
- batch status SUCCESS
- integrity_check: ok

### Real 2026 PACI + SED operational test

Actual `PACI260823.zip` + `SED260823.zip` were parsed and added to the accepted 2016-2025 Analysis v1.2 baseline.

- BAC races: 36
- KYI/CYB/UKC/SED rows: 466 each
- resulting Analysis rows for 2026-08-23: **466**
- missing UKC profiles: **0**
- frame/track-condition/sire populated: **466 / 466**
- prev1 populated: **417 / 466**
- total Analysis rows after test: **482,093**
- ingest batch: **SUCCESS**
- integrity_check: **ok**

A Stats Mart build from the updated test Analysis also passed; 2026-08-23 generated 403 sire, 366 jockey and 168 frame yearly aggregate rows for year 2026, with mart integrity `ok`.

### Stats Mart

2016-2025 full mart:

- sire rows: 194,656
- jockey rows: 155,118
- frame rows: 38,151
- SQLite: ~50.09 MiB
- integrity_check: ok

2025 year-only refresh from Analysis v1.2 reproduced the original full-build mart with **zero differences** across sire/jockey/frame tables.

## Rolling operation

Example 2026 operation:

```text
2016-2025 Analysis
  + completed 2026 dates incrementally
  -> 2016-2026 YTD

at year end:
  rebuild directly from 2017-2026 Raw
  -> 2017-2026 rolling Analysis
```

There is no requirement to rebuild Core first.

## Documentation

- `docs/JRDB_Core_v1_2_Analysis_Layer_Design.md`
- `docs/README_build_jrdb_core_v1_2.md`
- `docs/README_build_jrdb_analysis.md`
- `docs/README_update_jrdb_analysis_incremental.md`
- `docs/README_build_jrdb_stats_mart.md`

## Security

認証情報はGit管理しません。
`.env` / `jrdb_secret.py` は `.gitignore` 対象です。
Raw ZIP・大容量SQLite・日次生成物もGit管理対象外です。

## Validation

既存パッケージの移行時スモークテスト結果は `MIGRATION_MANIFEST.json` を参照してください。
追加分の検証条件・結果は各READMEと設計書に記録します。
