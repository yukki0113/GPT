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
- `src/build_jrdb_analysis.py` — Core v1.2.1 → Analysis Lite v1.1（reference/regression path）
- `src/build_jrdb_analysis_from_raw.py` — Raw年次ZIP → Analysis Lite v1.1（production routine path）
- `src/build_jrdb_stats_mart.py` — Analysis Lite v1.1 shard群 → 年次Stats Mart v1.1
- `tools/generate_jrdb_codebooks.py` — codebook生成
- `tools/audit_jrdb_core_v1_1_1.py` — Core監査ツール
- `tools/audit_jrdb_core_v1_2_regression.py` — v1.1.2 / v1.2回帰比較
- `tools/audit_jrdb_analysis_equivalence.py` — Core→Analysis / Raw→Analysis 全列等価性比較

## Production data flow

Routine analysis generation no longer requires Core as an intermediate artifact.

```text
canonical Raw ZIPs
  ├─> Core                         # audit / full normalized history / reproducibility
  └─> rolling Analysis Lite       # routine GPT/PWA analysis
        └─> Stats Mart
```

Normal routine path:

```text
Raw -> Analysis Lite -> Stats Mart
```

Core is maintained independently when audit/history/rebuild work requires it. `Core -> Analysis` remains a validated reference/regression path.

## Dependencies

Core v1.2.1:
`build_jrdb_core_v1_2_1.py` → v1.1.2 normalization + v1.2 UKC profile + `schema/jrdb_core_schema_v1_2_1.sql`。

Analysis Lite v1.1:
- production Raw path: `build_jrdb_analysis_from_raw.py` + Raw `BAC/KYI/SED/CYB/UKC`
- reference Core path: `build_jrdb_analysis.py` + Core v1.2.1
- shared schema: `schema/jrdb_analysis_schema_v1_1.sql`

v1.1では旧 `condition_code` の曖昧さを解消し、
- `race_condition_code` = BAC競走条件
- `track_condition_code` = SED実馬場状態
- `frame_no` = KYI枠番
を明示的に分離しています。

Stats Mart v1.1:
`build_jrdb_stats_mart.py` + `schema/jrdb_stats_mart_schema_v1_1.sql`。
`mart_sire_yearly` / `mart_jockey_yearly` / `mart_frame_yearly` を作成します。

## Validation status

Core v1.2 additive regression:
- contiguous 2021-2025: PASS
- v1.1.2の既存正規化部分は行単位差分0
- integrity_check: ok

Raw -> Analysis equivalence:
- 2016-2020: 243,849 rows × 31 columns, differences 0
- 2021-2025: 237,778 rows × 31 columns, differences 0
- combined 2016-2025: **481,627 rows, exact equivalence PASS**

Analysis Lite v1.1 corrected 2016-2025 measurement:
- rows: **481,627**
- sire nonblank: **481,519**
- frame non-null: **481,627**
- track condition nonblank: **481,627**
- SQLite: **177,328,128 bytes (~169.11 MiB)**
- ZIP: **44,011,036 bytes (~41.97 MiB)**
- integrity_check: **ok**

Drive delivery:
- the ~169 MiB 2016-2025 Analysis SQLite was uploaded and fetched back through the ChatGPT Drive connector
- fetched size / row count / integrity / SHA-256 matched: **PASS**

Stats Mart v1.1 corrected 2016-2025 pilot:
- sire rows: 194,656
- jockey rows: 155,118
- frame rows: 38,151
- SQLite: 52,518,912 bytes (~50.09 MiB)
- integrity_check: ok

詳細:
- `docs/JRDB_Core_v1_2_Analysis_Layer_Design.md`
- `docs/README_build_jrdb_core_v1_2.md`
- `docs/README_build_jrdb_analysis.md`
- `docs/README_build_jrdb_stats_mart.md`

## Rolling Analysis operation

A recent ten-year Analysis shard is the normal GPT/PWA flexible-query artifact.

Example rollover:

```text
2016-2025 Analysis
  -> rebuild directly from 2017-2026 Raw
  -> 2017-2026 Analysis
  -> rebuild/update Stats Mart
```

There is no requirement to rebuild Core first.

## Security

認証情報はGit管理しません。
`.env` / `jrdb_secret.py` は `.gitignore` 対象です。
Raw ZIP・大容量SQLite・日次生成物もGit管理対象外です。

## Validation

既存パッケージの移行時スモークテスト結果は `MIGRATION_MANIFEST.json` を参照してください。
追加分の検証条件・結果は各READMEと設計書に記録します。
