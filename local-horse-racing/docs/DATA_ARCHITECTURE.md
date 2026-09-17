# Data architecture

## Principle

NARから取得した原本と、再生成可能な加工データを分離する。
GitHubはコードと仕様の正本、Google Driveはデータ資産の正本とする。

Parquet / DuckDBの共通conversion・validation・query・benchmark処理は `tools/data-storage/` を利用し、Project固有実装はcolumns / keys / partitions / as-of / leakage rules等に限定する。

最重要の境界は **rawの物理構造をそのままモデルへ渡さないこと**。NARの `racelist.csv` / `horselist.csv` はpre-race情報とpost-race情報を同一行に持つため、canonical layerで必ず分離する。

## GitHub

~~~text
local-horse-racing/
├─ README.md
├─ .gpt/
├─ docs/
│  ├─ NAR_DATA_SPEC.md
│  ├─ DATA_ARCHITECTURE.md
│  └─ CANONICAL_DATA_SPEC.md
├─ nar/
│  ├─ download/
│  ├─ schema/
│  └─ canonical/
│     ├─ field_catalog.py
│     ├─ schema.py
│     ├─ parser.py
│     ├─ leakage.py
│     ├─ storage.py
│     └─ build.py
└─ tests/

shared:
tools/data-storage/
~~~

原本ZIP、展開済み大容量CSV、Parquet、DB、分析出力はGit管理しない。

## Google Drive layout

Driveのデータ正本ルートは `/GPT/local-horse-racing/` とする。

- folder URL: `https://drive.google.com/drive/folders/1FPxtdPfLNy1EW_WoGtk9C867b7CfAmfI`
- folder ID: `1FPxtdPfLNy1EW_WoGtk9C867b7CfAmfI`

~~~text
GPT/
└─ local-horse-racing/
   ├─ 00_raw/
   │  ├─ race/
   │  └─ odds/
   ├─ 10_canonical/
   │  ├─ pre/
   │  │  ├─ race/
   │  │  ├─ runner/
   │  │  └─ runner_history_snapshot/
   │  ├─ post/
   │  │  ├─ race_result/
   │  │  ├─ runner_result/
   │  │  └─ payout/
   │  └─ control/
   │     ├─ race_status/
   │     ├─ field_catalog.json
   │     └─ leakage_validation.json
   ├─ 20_audit/
   │  └─ canonical/
   ├─ 30_analysis/
   └─ data_pdf_manual.pdf
~~~

Driveにはソースコードを置かず、NARデータ原本、canonical Parquet、監査データ、分析成果、およびデータ仕様参照資料だけを置く。

## Shared data-storage tooling

リポジトリ共通 `tools/data-storage/` はProject-neutralなParquet / DuckDB処理の正本とする。

- SQLite / CSV -> Parquet conversion
- ZSTD / Snappy、single-file / Hive partitioned dataset
- row count / schema hash / canonical-key uniqueness / NULL / min-max / sample validation
- machine-readable audit JSON
- DuckDB SQL over Parquet
- SQLite / Parquet benchmark

local-horse-racing側でParquet writer / validator / DuckDB query engineを複製しない。`nar/canonical/storage.py` はProject固有schemaから共通 `data_storage.runner.run_config` のconfigを組み立てるadapterに限定する。

Durable analytical dataはZSTD Parquetを基本とする。DuckDBはParquetを直接queryするin-process engineとして利用し、persistent `.duckdb` fileはデフォルト正本としない。将来persistent DBが必要になっても、raw / canonicalから再生成可能な派生物として扱う。

## Layer responsibilities

### 00_raw

NARレスポンスZIPをバイト列のまま保存する不変原本層。

- `00_raw/race/`: レース情報ZIP
- `00_raw/odds/`: オッズ情報ZIP

Drive搬送制約のため年単位wrapper ZIPへ格納する場合でも、内部のNAR公式月次ZIPバイト列を変更しない。

### 10_canonical/pre

発走前に利用し得る情報だけを保持する。

- `pre/race`: レース条件。天候・馬場はrace-day情報。
- `pre/runner`: 馬・騎手・調教師等。馬体重はweigh-in後情報。
- `pre/runner_history_snapshot`: 累積成績・最高タイム等のas-of候補。初期状態は `PENDING_VALIDATION`。

`pre/runner_history_snapshot` がpre層にあることは「利用許可」を意味しない。field catalog上の `feature_policy=PENDING` を優先し、広期間監査後に明示昇格するまでモデルへ渡さない。

### 10_canonical/post

結果確定後情報を完全隔離する。

- `post/race_result`: 上がり、ハロン、コーナー通過順。
- `post/runner_result`: 着順、タイム、着差、上がり3F、人気。
- `post/payout`: payback 54列を券種long形式へ正規化。回収率評価専用。

モデル特徴量生成はこの層を直接参照しない。

### 10_canonical/control

データ境界・利用可否・監査状態を保持する。

- `race_status`: NORMAL / REFUNDED / CANCELLED / NO_RESULT / DATA_MISSING と `is_model_target` / `is_return_target`。
- `field_catalog.json`: raw fieldからcanonical table/fieldへの対応、availability class、available stage、feature policy。
- `leakage_validation.json`: 前走結果から次走snapshotへの更新整合 evidence。

### Partition / key policy

Parquetは `race_year` Hive partitionを基本とする。canonical keyは以下。

- race tables: `race_id`
- runner tables: `runner_id`
- payout: `race_id + payback_row_no + bet_type + selections`
- race status: `race_id`

`race_id = YYYYMMDD:競馬場:RR`、`runner_id = race_id:馬番` とする。馬にはNAR恒久IDが見当たらないため、現段階では `馬名 + 生年月日 + 父馬名` のSHA-256 surrogate `horse_key` を使用する。これは完全な名寄せ済み恒久IDとはみなさない。

### 20_audit

取得元URL、対象年月、取得日時、SHA-256、サイズ、ZIP内ファイル一覧、文字コード観測等を保持する。

canonical変換では `tools/data-storage/` が出力するrow count / schema / key / NULL validation auditも保存する。

### 30_analysis

指数研究、特徴量比較、回収率検証などの成果物。DuckDBを使う分析はcanonical Parquetを直接参照する方式を第一候補とする。

### data_pdf_manual.pdf

NAR公式データダウンロード機能説明書の参照コピー。

## Data flow

~~~text
NAR official ZIP
    |
    v
00_raw (immutable)
    |
    v
nar.canonical.parser
    |-----------------------------|
    v                             v
10_canonical/pre             10_canonical/post
    |                             |
    v                             +--> labels / payout evaluation
as-of validator
    |
    v
verified feature boundary
    |
    v
future model / backtest
~~~

staging CSVはParquet生成のための一時搬送形式であり、長期正本ではない。
