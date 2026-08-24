# JRDB Python tools

JRDB関連の取得・RaceNote変換・Core / Analysis / Stats Mart SQLite構築をGitで正本管理するための整理済みパッケージです。

## Current modules

- `src/fetch_jrdb_paci.py` — PACI前日一括ZIP取得
- `src/fetch_jrdb_history.py` — 年次ZIP / 2026年以降の単日ZIP取得
- `src/racenote_jrdb.py` — PACI ZIP → RaceNote v0.2 JSON
- `src/racenote_jrdb_pipeline.py` — PACI取得 → RaceNote 1R一体実行
- `src/build_jrdb_core.py` — JRDB Core Builder v1.1.2-production（rollback baseline）
- `src/jrdb_ukc.py` — UKC 290-byte固定長parser（v1.2用）
- `src/build_jrdb_core_v1_2.py` — v1.1.2を壊さずUKC horse profileを追加するv1.2 wrapper
- `src/build_jrdb_analysis.py` — Core v1.2 → Analysis Lite SQLite
- `src/build_jrdb_analysis_from_raw.py` — Raw年次ZIP → Analysis Lite SQLite（remote-friendly PoC path）
- `src/build_jrdb_stats_mart.py` — Analysis Lite shard群 → 年次Stats Mart
- `tools/generate_jrdb_codebooks.py` — codebook生成
- `tools/audit_jrdb_core_v1_1_1.py` — Core監査ツール
- `tools/audit_jrdb_core_v1_2_regression.py` — v1.1.2 / v1.2回帰比較

## Dependencies

RaceNote:
`racenote_jrdb_pipeline.py` → `fetch_jrdb_paci.py` + `racenote_jrdb.py`
`racenote_jrdb.py` は `config/jrdb_codebooks.json` を利用。

Core v1.1.2:
`build_jrdb_core.py` は `schema/jrdb_core_schema_v1_1_2.sql` とRaw ZIP群を利用。

Core v1.2:
`build_jrdb_core_v1_2.py` → `build_jrdb_core.py` + `jrdb_ukc.py` + `schema/jrdb_core_schema_v1_2.sql`。
`horse_profile_current / horse_profile_history` に父・母・母父等のUKC profileを追加する。

Analysis Lite:
- `build_jrdb_analysis.py` → Core v1.2 + `schema/jrdb_analysis_schema_v1.sql`
- `build_jrdb_analysis_from_raw.py` → Raw `BAC/KYI/SED/CYB/UKC` + 同じAnalysis schema

1出走1行の `fact_entry_result_lite` を作成し、種牡馬・母父・騎手・脚質等の自由条件集計に使用する。

Stats Mart:
`build_jrdb_stats_mart.py` → 1つ以上の非重複Analysis shard + `schema/jrdb_stats_mart_schema_v1.sql`。
初期実装では `mart_sire_yearly` と `mart_jockey_yearly` を作る。

## Validation status

Core v1.2 additive regression:
- contiguous 2021-2025: PASS
- v1.1.2のrace/entry/result/training/workout等は行単位で差分0
- `PRAGMA integrity_check`: ok

Analysis Lite contiguous 2021-2025 PoC:
- rows: 237,778
- sire nonblank: 237,670
- SQLite: 84,582,400 bytes (~80.7 MiB)
- ZIP: 22,687,297 bytes (~21.6 MiB)
- preferred < 100 MiB target: PASS

Raw -> Analysis 2025 pilot:
- rows: 47,884
- races after BAC->SED fallback: 3,455
- sire nonblank: 47,772
- `PRAGMA integrity_check`: ok
- Core->Analysis pilotと主要件数・血統充足数が一致
- row-level equivalenceは今後の明示的回帰項目

Stats Mart 2025 pilot:
- sire rows: 21,281
- jockey rows: 19,329
- SQLite: 5,464,064 bytes (~5.2 MiB)
- `PRAGMA integrity_check`: ok
- representative sire aggregate reproduced Analysis Lite values

詳細は以下を参照してください。

- `docs/JRDB_Core_v1_2_Analysis_Layer_Design.md`
- `docs/README_build_jrdb_core_v1_2.md`
- `docs/README_build_jrdb_analysis.md`
- `docs/README_build_jrdb_stats_mart.md`

次の設計課題は、通常利用の「過去10年」集計を満たすAnalysis shardの実サイズ測定、production shard境界、Stats Martの2021-2025/full-history検証、Raw->AnalysisとCore->Analysisのrow-level equivalence確認です。

## Security

認証情報はGit管理しません。
`.env` / `jrdb_secret.py` は `.gitignore` 対象です。
`.env.example` にキー名のみ収録しています。

## Validation

既存パッケージの移行時スモークテスト結果は `MIGRATION_MANIFEST.json` を参照してください。
v1.2 / Analysis / Mart追加分の検証条件・結果は各READMEと設計書に記録します。
