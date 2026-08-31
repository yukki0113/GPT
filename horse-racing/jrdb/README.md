# JRDB Python tools

JRDB関連の取得・RaceNote変換・Core / Analysis / Stats Mart SQLite構築をGitで正本管理するための整理済みパッケージです。

## Current modules

- `src/fetch_jrdb_paci.py` — PACI前日一括ZIP取得
- `src/fetch_jrdb_history.py` — 年次ZIP / 2026年以降の単日ZIP取得
- `src/racenote_jrdb.py` — PACI ZIP → RaceNote base v0.2 JSON
- `src/racenote_history_enrichment.py` — base RaceNote v0.2 + Analysis Lite / Stats Mart → 正式RaceNote v1.0
- `src/racenote_request.py` — 日付・任意の開催場/Rを受ける統一RaceNote request router
- `src/racenote_archive.py` — 月次RaceNote Archive SQLite共通schema/validation/read-write
- `src/racenote_archive_backend.py` — publishable Archiveをbase v0.2へ復元するproduction backend adapter
- `src/build_racenote_archive.py` — base v0.2 bundle群から月次Archive shardを構築
- `src/build_racenote_archive_month_from_raw.py` — annual Raw + Analysis identityからfull-month Archiveを再構築
- `src/resolve_racenote_archive_release.py` — 対象月のlatest compatible publishable Archive Releaseを解決
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
- `src/export_jrdb_eval_race_conditions.py` — Raw BAC → Eval用1レース1行レース条件CSV（Analysis非変更）
- `src/export_jrdb_eval_dataset.py` — Raw BAC + SED → Eval専用1レース1行統合CSV（Analysis/Core非依存）
- `src/export_jrdb_eval_horse_results.py` — Raw SED → Eval「全馬データ」結果用1頭1行CSV + audit JSON
- `src/enrich_eval_csv_with_paci.py` — Eval OCR 5列CSV + PACI → 開催前1頭1行エンリッチCSV（Analysis/Core/SED非依存）
- `tools/generate_jrdb_codebooks.py` — codebook生成
- `tools/audit_jrdb_core_v1_1_1.py` — Core監査ツール
- `tools/audit_jrdb_core_v1_2_regression.py` — v1.1.2 / v1.2回帰比較
- `tools/audit_jrdb_analysis_equivalence.py` — Core→Analysis / Raw→Analysis 全列等価性比較

## RaceNote production v1.0

GPT-facingな正式RaceNote bundleは `schema/racenote_bundle_schema_v1_0.json` に従うv1.0です。

```text
PACI
  -> src/racenote_jrdb.py                 # base schema v0.2
  -> src/racenote_history_enrichment.py   # Analysis Lite / Stats Mart enrichment
  -> final RaceNote schema v1.0
```

通常の取得入口は `src/racenote_request.py`。GPTからは `[RACENOTE_REQUEST]` Issue → GitHub Actions → artifact回収を標準経路とします。

v1.0の主要方針:

- PACI詳細 `recent_runs` 最大5 + Analysis Lite簡略 `older_runs` 最大3
- 固定8件・キャリア上の完全な直近8戦とはみなさず、`history_coverage.run_layers` でsource/coverageを明示
- exact distanceを保持し、1000-1400 / 1400-1800 / 1800-2400 / 2500+ の重複距離レンジを追加
- 1400m / 1800mは隣接レンジへ重複所属、2400mは1800-2400側のみ
- `sample_size_band`: none=0 / small=1-19 / moderate=20-49 / sufficient=50+。統計的有意性ではなく説明用母数帯
- `history_coverage.scope = jrdb_jra_history`。海外所属馬・海外遠征の履歴完全性を推測しない
- 過去日は常に `as_of_exclusive = target_date`。対象日結果・後日結果を使わない

詳細は `docs/README_racenote_v1.md` と `docs/README_racenote_request.md` を参照してください。

## Production data flow

Routine analysis generation does not require Core as an intermediate artifact.

```text
canonical Raw ZIPs
  ├─> Core                         # audit / complete normalized history / reproducibility
  ├─> rolling Analysis Lite       # routine GPT/PWA analysis
  │     └─> Stats Mart
  └─> Eval dataset exporter       # Eval検証専用、Analysis/Core非依存
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

## PWA independent index design

PWA競馬新聞向けの独自指数は、条件集計用Fact Lite / Stats MartやRaceNoteとは分離して設計する。

基本3層は次のとおり。

- `Ability` — 今回条件で平常なら期待される競走能力
- `Edge` — Abilityに対する今回の上振れ / 下振れシグナル
- `Value` — 独自予測と市場オッズとの差。Ability / Edge には人気・オッズを入れない

2010-2025の長期JRDB履歴を用い、2010-2012 warm-up、2013-2023 development walk-forward、2024-2025 locked holdoutを基本検証構成とする。新馬も血統・調教・騎手・厩舎等の事前情報からAbilityを算出し、既走馬と同じRunPerf尺度へ接続する。

設計正本:

- `docs/JRDB_PWA_Index_Design_v0_1.md`
- `docs/JRDB_PWA_Index_Feature_Registry_v0_1.md`
- `docs/JRDB_Training_Index_Definitions.md`

## Eval Raw dataset

Eval用途ではAnalysis Lite / Core SQLiteを中間入力にせず、JRDB Rawを正本入力として専用CSVを生成します。

```text
BAC + SED Raw
  -> src/export_jrdb_eval_dataset.py
  -> 1 race / row CSV
```

外部結合キーは `race_date + venue_code + race_no`。BACからレース条件、SEDから確定馬場状態を取得し、両TYPEの共通レース条件が食い違う場合はエラーにします。詳細は `docs/README_export_jrdb_eval_dataset.md`。

## Eval daily PACI enrichment

開催前の日次Eval分析では、OCR出力とPACIだけを直接結合します。Analysis Lite / Core SQLite / SEDはこの経路の必須依存にしません。

```text
Eval OCR 5列CSV + PACIyymmdd.zip
  -> src/enrich_eval_csv_with_paci.py
  -> 1 horse / row pre-race enriched CSV
```

正式入力5列は `date,venue,race_no,horse_no,eval`、結合キーは `date + venue + race_no + horse_no`。正式馬名はOCRではなくPACI KYIから付与します。PACI内ではBACとKYIだけを読み、対象レースの着順・確定人気・確定オッズ・確定馬場状態・払戻などの事後情報は混ぜません。

別プロジェクトからもスクリプトの絶対パスを指定して実行できます。詳細は `docs/README_enrich_eval_csv_with_paci.md`。

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

### 2026 YTD production backfill through 2026-08-23 — PASS

The accepted 2016-2025 Analysis v1.2 baseline was backfilled from JRDB PACI + SED for every detected 2026 JRA race date through 2026-08-23.

- detected race dates: **70**
- PACI: **70 / 70** downloaded and ZIP-validated
- SED: **70 / 70** downloaded and ZIP-validated
- 2026 Analysis rows added: **31,885**
- total Analysis rows: **513,512**
- 2026 races: **2,298**
- frame / track condition / sire population: **31,885 / 31,885**
- prev_result_key_1 / prev_race_key_1 populated: **29,334 / 31,885**
- duplicate primary keys: **0**
- ingest batch: **SUCCESS 70 / ERROR 0**
- integrity_check: **ok**
- production file: `jrdb_analysis_2016_2026YTD_20260823_v1_2.sqlite`
- size: **197,492,736 bytes (~188.34 MiB)**
- SHA-256: `4df011c74b226ad394a171b71c0841872cb94f3418c8e7f85225a31de89e21b2`

A full Stats Mart rebuilt from this accepted Analysis contains:

- sire rows: **208,885** total / **14,228** for 2026
- jockey rows: **165,739** total / **10,621** for 2026
- frame rows: **40,634** total / **2,483** for 2026
- SQLite size: **56,254,464 bytes (~53.65 MiB)**
- integrity_check: **ok**
- SHA-256: `116ac151b4ed499e81cfb66cfedc6f68f42c456458e2fa6b3160583633d5d874`

The in-season Analysis is now close to the 200 MiB design target. Continue incremental 2026 updates during the season, then at year-end rebuild the rolling window directly from 2017-2026 Raw and drop 2016.

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

- `docs/README_racenote_v1.md`
- `docs/README_racenote_request.md`
- `docs/JRDB_Core_v1_2_Analysis_Layer_Design.md`
- `docs/JRDB_PWA_Index_Design_v0_1.md`
- `docs/JRDB_PWA_Index_Feature_Registry_v0_1.md`
- `docs/JRDB_Training_Index_Definitions.md`
- `docs/README_build_jrdb_core_v1_2.md`
- `docs/README_build_jrdb_analysis.md`
- `docs/README_update_jrdb_analysis_incremental.md`
- `docs/README_build_jrdb_stats_mart.md`
- `docs/README_export_jrdb_eval_race_conditions.md`
- `docs/README_export_jrdb_eval_dataset.md`
- `docs/README_enrich_eval_csv_with_paci.md`

## Security

認証情報はGit管理しません。
`.env` / `jrdb_secret.py` は `.gitignore` 対象です。
Raw ZIP・大容量SQLite・日次生成物もGit管理対象外です。

## Validation

既存パッケージの移行時スモークテスト結果は `MIGRATION_MANIFEST.json` を参照してください。
追加分の検証条件・結果は各READMEと設計書に記録します。
