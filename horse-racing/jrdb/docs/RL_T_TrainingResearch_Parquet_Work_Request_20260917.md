# RL-T / Training Research Parquet 移行追随 Work Request — 2026-09-17

## 0. 目的

Training Research の長期保存・分析正本が SQLite ZIP から Parquet ZSTD へ移行済みとなったため、RL-T（historical implementation name: Training Edge v0.2）および関連する研究コード・実行経路に残る旧 SQLite / ZIP 前提を解消する。

本作業は **storage / reader plumbing のみ**を対象とし、RL-T の科学仕様、特徴量、モデル、calibration、runtime fingerprint、既存 Freeze / evidence は変更しない。

## 1. 前提として確定済みの資産方針

- Training Research 2010–2025 Full は Parquet ZSTD 正本へ移行済み。
- Drive 発行、再取得 SHA 検証、Stage 1b 回帰確認は PASS 済み。
- `current` は Parquet 世代へ切替済み。
- 旧 Full / Development Lite の SQLite ZIP は削除済み。
- 今後の標準 reader は DuckDB / Parquet。
- 通常の研究・指数開発は `training_development.parquet`（2010–2023）を default とする。
- 2024–2025 HOLDOUT 境界は従来どおり維持する。

## 2. 監査済みの現状

### 2.1 Stage 1b

`horse-racing/jrdb/src/analyze_jrdb_training_stage1b.py`

現行 main は Parquet 入力を DuckDB `read_parquet` で読めるよう既に移行済みであり、2010–2023 の選択と `max year <= 2023` guard も維持されている。

Training Research 本移行時の Stage 1b 回帰も PASS 済みのため、ここは原則変更不要。

### 2.2 Stage 2b

`horse-racing/jrdb/src/analyze_jrdb_training_stage2b.py`

現行 main はまだ次の SQLite 前提を持つ。

- `sqlite3` import
- `sqlite3.connect(...)`
- `PRAGMA table_info(training_runner)`
- `pd.read_sql_query(...)`
- CLI `--db`

一方、Stage 2b の科学ロジックは読み出し後の pandas / sklearn 側で処理されており、SQLite 固有機能を科学ロジックとして必要としていない。

### 2.3 Stage 2b formal workflow

`.github/workflows/jrdb_training_stage2b_issue.yml`

現行 workflow はさらに旧 Development Lite SQLite ZIP に固定されている。

- `DEVELOPMENT_LITE_DRIVE_ID = 1RGRVoUI3utSC3r8Zf5Gk3i9Voq7JZqmj`
- Drive から `development.zip` を取得
- ZIP 内の単一 `.sqlite` member を展開
- SQLite `PRAGMA integrity_check`
- `--db` で Stage2b を実行

この旧 SQLite ZIP は削除済みのため、この workflow は今後の再実行経路としては成立しない。

ただし、この workflow は historical Stage2b evidence を生成した frozen source SHA `58797eddbe5d04d55a7de83d8f8473a4fd7c06cb` を checkout する契約を持つ。既存の証拠 provenance を書き換えないこと。

### 2.4 Training Research build workflow

`.github/workflows/jrdb_training_research_issue.yml`

現行 main は内部生成過程では SQLite を一時 materialization として使用するが、最後に `migrate_jrdb_training_research_parquet.py` を実行して immutable Parquet canonical generation を生成している。

内部 builder の一時 SQLite は今回の「分析正本 Parquet 化」とは別問題であり、直ちに撤去する必要はない。

### 2.5 RL-T production / forward scorer

以下は Training Research canonical を直接読まず、別途 materialize された `training_edge_input` と frozen assets を使うため、今回の移行対象外。

- `horse-racing/jrdb/src/project_training_edge_v0_2_input.py`
- `horse-racing/jrdb/src/evaluate_training_edge_v0_2_oot.py`
- `horse-racing/jrdb/src/score_training_edge_v0_2_daily.py`
- RL-T runtime fingerprint / calibration / frozen model contract

これらを Training Research Parquet 移行を理由に変更してはならない。

## 3. 実装依頼

### 3.1 Stage 2b reader を DuckDB / Parquet 標準へ移行

`analyze_jrdb_training_stage2b.py` の source loader を Stage 1b と同系統の Parquet reader へ変更する。

必須要件:

1. `training_development.parquet` を直接入力できること。
2. DuckDB で Parquet を読むこと。
3. `REQUIRED_SOURCE_COLUMNS` の存在確認を維持すること。
4. `ORDER BY race_date, race_key, horse_no` の決定順序を維持すること。
5. 選択範囲は 2010–2023 のみとし、2024 以降が選択された場合は fail closed とすること。
6. `holdout_rows_selected == 0` を維持すること。
7. scientific/materialization/model/report logic は変更しないこと。

CLI は通常経路を Parquet 前提にする。

推奨:

```text
--input /path/to/training_development.parquet
```

旧 `--db` を compatibility alias として残す場合は、deprecated / legacy と明示すること。新規 workflow / docs では `--input` を使用すること。

### 3.2 Stage 2b 実行経路を新 Parquet canonical へ切替

旧 `.github/workflows/jrdb_training_stage2b_issue.yml` の historical evidence provenance を壊さないように扱う。

推奨は次のいずれか。

- 既存 workflow を historical / retired と明示し、新しい Parquet-backed regression workflow を別名で追加する。
- または、historical frozen source / result を保持したまま storage plumbing のみを更新できることを明確に証明した上で既存 workflow を更新する。

安全側では前者を推奨する。

新規の通常入力は、Training Research `current` の Parquet generation から **`training_development.parquet`** を解決・取得すること。

削除済みの旧 Development Lite Drive ID / ZIP を参照してはならない。

Drive / Store の current resolver、manifest、generation ID、SHA 検証については Training Research Parquet 正本側の既存規約を再利用し、独自の二重管理を作らないこと。

### 3.3 Regression / non-regression

Stage 2b は v0.2 設計根拠となった historical evidence であるため、storage 移行で結果を変えてはならない。

最低限、旧 formal Stage2b evidence に対して以下を比較する。

- selected rows / population
- max selected year = 2023
- 2024–2025 selected rows = 0
- M0–M4 pooled Spearman
- RMSE
- top-bottom mean spread
- yearly 2018–2023 Spearman
- incremental classification
- named pattern diagnostics の決定的部分

浮動小数点差を許容する場合は tolerance を事前固定し、差分 audit に明記すること。classification が変わる差は不可。

### 3.4 Documentation

少なくとも以下を更新する。

`horse-racing/jrdb/docs/Training_Research_Base_v0_1.md`

現在は「reusable SQLite research layer」「canonical artifact = `.sqlite`」「LZMA ZIP transport」等の旧運用記述が残っている。

文書では historical build architecture と current storage canonical を区別して記載すること。

current policy:

```text
analytical canonical = Parquet ZSTD
normal development input = training_development.parquet (2010–2023)
query engine = DuckDB
HOLDOUT = 2024–2025; development reader must not select it
```

過去に SQLite を使って生成・検証した事実や Freeze provenance は消さず、historical implementation として残すこと。

`horse-racing/jrdb/docs/移行判断_training_20260916.md` は移行前判断の記録なので、本文を過去改変せず、必要なら冒頭または末尾に「2026-09-16/17 移行完了後に operational policy が supersede された」旨の追記のみ行うこと。

## 4. HOLDOUT / scientific boundary

本作業中も以下を厳守する。

- normal research default = 2010–2023 development Parquet
- 2024–2025 を通常研究へ混入させない
- historical RL-T / Training Edge v0.2 Freeze を変更しない
- 2026 OOT を fresh / unopened と再解釈しない
- RL-T v0.2 の feature / target / alpha / preprocessing / calibration / eligibility を変更しない
- runtime fingerprint を再生成しない
- market / odds / popularity を加えない
- storage 移行結果を理由に再学習・再調整しない

## 5. Out of scope

今回扱わないもの:

- RL-R（Rebound Lift）の SED / ZED 研究
- 新しい RaceLift 統合式
- RL-T の名称置換による historical source / Freeze の書き換え
- Index Base / RunPerf の内部 SQLite 全廃
- RL-T daily scorer の科学仕様変更
- 2026 結果を使った retuning

## 6. Acceptance criteria

以下をすべて満たして完了とする。

- [ ] Stage 2b main reader が `training_development.parquet` + DuckDB で動く。
- [ ] 新規・通常経路に旧 SQLite ZIP / deleted Development Lite Drive ID 依存がない。
- [ ] selected max year = 2023。
- [ ] 2024–2025 selected rows = 0。
- [ ] historical Stage2b evidence と regression 一致する。
- [ ] Stage 1b の既存 Parquet reader / regression を壊していない。
- [ ] Training Research current Parquet resolver / SHA validation を再利用している。
- [ ] `Training_Research_Base_v0_1.md` が current Parquet canonical を正しく記載する。
- [ ] historical Freeze / evidence provenance を改変していない。
- [ ] frozen RL-T daily scorer / calibration / runtime fingerprint に変更がない。
- [ ] 変更した source / workflow / docs / tests の commit SHA と主要 blob SHA を完了報告する。

## 7. 完了報告で必要な情報

- 変更ファイル一覧
- commit SHA
- Stage 2b Parquet regression の入力 generation / SHA
- row count / min year / max year / duplicate key
- HOLDOUT guard 結果
- historical evidence との差分 summary
- tests / workflow run ID / conclusion
- 今後通常研究で使う canonical path / resolver
- 意図的に残した legacy SQLite compatibility があれば、その理由
