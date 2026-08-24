# JRDB Pythonソース棚卸し 2026-08-24 v2

## 1. 実体確認済み（File Library）

| 区分 | ファイル | 用途 | 状態 |
|---|---|---|---|
| 本番運用 | fetch_jrdb_paci.py | JRDB PACI前日一括ZIP取得 | 実体確認済み |
| 本番運用 | racenote_jrdb.py | PACI ZIP→RaceNote JSON v0.2系 | 実体確認済み |
| 本番運用 | racenote_jrdb_pipeline.py | PACI取得→RaceNote 1R変換ラッパー | 実体確認済み |
| 補助生成 | generate_jrdb_codebooks.py | JRDB公式コード表→jrdb_codebooks.json生成 | 実体確認済み |
| 補助データ | jrdb_codebooks.json | TOKKI/ASHIMOTOコードブック | 実体確認済み |
| 過去データ取得 | fetch_jrdb_history.py | 年次ZIP/単日ZIP取得 | 実体確認済み |
| Core PoC | build_jrdb_history_2025_poc.py | 2025年次ZIP→SQLite PoC | 実体確認済み |
| Core Builder v1 | build_jrdb_core.py | 複数年Core SQLite構築 初版 | 実体確認済み |
| Core Builder v1.1 | build_jrdb_core(1).py | 払戻・重複差分・BAC fallback等を追加 | 実体確認済み |
| Core Builder v1.1.1 | build_jrdb_core(2).py | cross-type date解決等を追加 | 実体確認済み |
| Core監査 | audit_jrdb_core_v1_1.py | v1.1監査 | 実体確認済み |
| Core監査 | audit_jrdb_core_v1_1_1.py | v1.1.1/1.1.2系監査 | 実体確認済み |
| 初期PoC | racenote_jrdb_parser.py | RaceNote JRDB初期PoCパーサー | 実体確認済み |

## 2. Core Builder関連の補助実体

| ファイル | 世代 | 状態 |
|---|---|---|
| jrdb_core_schema_v1.sql | v1 | 実体確認済み |
| jrdb_core_schema_v1(1).sql | v1.1 | 実体確認済み |
| jrdb_core_schema_v1(2).sql | v1.1.1 | 実体確認済み |
| jrdb_core_config.json | 1.0.0-poc | 実体確認済み |
| jrdb_core_config(1).json | 1.1.0-poc | 実体確認済み |
| jrdb_core_config(2).json | 1.1.1-poc | 実体確認済み |
| README_build_jrdb_core.md | v1 | 実体確認済み |
| README_build_jrdb_core(1).md | v1.1 | 実体確認済み |
| README_build_jrdb_core(2).md | v1.1.1 | 実体確認済み |

## 3. v1.1.2について確認できたこと

v1.1.2の `build_jrdb_core.py` 本体そのものは、現時点のFile Library検索で直接ヒットしていない。
ただし以下のv1.1.2実行成果物・確定仕様は確認済み。

- jrdb_core_poc_v1.1.2_audit.json
- jrdb_core_poc_v1.1.2_audit.md
- jrdb_core_poc_v1.1.2_duplicate_details.json
- JRDB_CoreBuilder_v1.1.2_最終小改修再PoC依頼_20260822.md
- JRDB_CoreBuilder_v1.1.2_本番2010-2025構築依頼_20260822.md
- JRDB_CoreBuilder_v1.1.2_本番再実行_SQLite成果物出力依頼_20260823.md

確定仕様として確認済み：

- canonical filename完全一致判定
- `bk` / `sv` 等non-canonical sourceのCore投入除外
- `IDENTICAL_COLLAPSED`
- `CROSS_TYPE_DATE_CONFIRMED`
- `RACE_DATE_ALIGNED_SELECTED`
- `MANUAL_REQUIRED`
- BAC欠損時の `SED_FALLBACK`
- SED単勝・複勝払戻解析
- UKC semantic hash圧縮
- provenance保持
- MISSING_SOURCE_DATE / ORPHAN_SOURCE_RECORD監査

PoC監査では `MANUAL_REQUIRED = 0`、`true_unresolved = 0` まで確認されている。

## 4. Git移行時に同梱推奨

### src
- fetch_jrdb_paci.py
- racenote_jrdb.py
- racenote_jrdb_pipeline.py
- generate_jrdb_codebooks.py
- fetch_jrdb_history.py
- build_jrdb_core.py（最終v1.1.2を最優先で回収）
- audit_jrdb_core_v1_1_1.py

### legacy / poc
- racenote_jrdb_parser.py
- build_jrdb_history_2025_poc.py
- build_jrdb_core v1/v1.1/v1.1.1世代
- audit_jrdb_core_v1_1.py

### config / schema
- jrdb_core_schema_v1.sql（最終v1.1.2版を優先）
- jrdb_core_config.json（最終v1.1.2版を優先）
- jrdb_history_fetch_config.json
- jrdb_codebooks.json

### docs
- README_racenote_jrdb_v0.2.md
- README_fetch_jrdb_history.md
- README_build_jrdb_core.md（最終版）
- RaceNote_v0.2.2_information_representation_change_20260821.md
- 整理版_JRDB_固定長データ定義.md
- 整理版_JRDB_マスタコード定義.md
- 整理版_JRDB_ファイル相関・キー定義.md

## 5. Git移行時に除外

- jrdb_secret.py
- .env
- 認証情報を含む設定・ログ
- ダウンロード済みRaw ZIP
- SQLite本体
- `.part` / 一時ファイル

## 6. 現時点の残課題

最優先は **v1.1.2確定版 `build_jrdb_core.py` の直接回収**。
次点で、v1.1.2実行時に更新された可能性のある `jrdb_core_schema_v1.sql` / `jrdb_core_config.json` / README の最終版を確認する。

ただしv1.1.1までの実装本体とv1.1.2の確定仕様・監査結果が揃っているため、万一v1.1.2本体が失われていても、変更差分の再構成は可能な状態。
