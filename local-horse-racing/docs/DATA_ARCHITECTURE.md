# Data architecture

## Principle

NARから取得した原本と、再生成可能な加工データを分離する。
GitHubはコードと仕様の正本、Google Driveはデータ資産の正本とする。

Parquet / DuckDBの共通conversion・validation・query・benchmark処理は `tools/data-storage/` を利用し、Project固有実装はcolumns / keys / partitions / validation rules等に限定する。

## GitHub

~~~text
local-horse-racing/
├─ README.md
├─ .gpt/
├─ docs/
├─ nar/
│  ├─ download/
│  └─ schema/
└─ tests/

shared:
tools/data-storage/
~~~

原本ZIP、展開済み大容量CSV、Parquet、DB、分析出力はGit管理しない。

## Google Drive layout

Driveのデータ正本ルートは `/GPT/local-horse-racing/` とする。

- folder URL: `https://drive.google.com/drive/folders/1FPxtdPfLNy1EW_WoGtk9C867b7CfAmfI`
- folder ID: `1FPxtdPfLNy1EW_WoGtk9C867b7CfAmfI`

2026-09-16時点の実フォルダ構成は次のとおり。

~~~text
GPT/
└─ local-horse-racing/
   ├─ 00_raw/
   │  ├─ race/
   │  └─ odds/
   ├─ 10_canonical/
   ├─ 20_audit/
   ├─ 30_analysis/
   └─ data_pdf_manual.pdf
~~~

Driveにはソースコードを置かず、NARデータ原本、加工後データ、監査データ、分析成果、およびデータ仕様参照資料だけを置く。

## Shared data-storage tooling

リポジトリ共通 `tools/data-storage/` はProject-neutralなParquet / DuckDB処理の正本とする。

- SQLite / CSV -> Parquet conversion
- ZSTD / Snappy、single-file / Hive partitioned dataset
- row count / schema hash / canonical-key uniqueness / NULL / min-max / sample validation
- machine-readable audit JSON
- DuckDB SQL over Parquet
- SQLite / Parquet benchmark

local-horse-racing側で同等のPython処理を複製しない。固有schemaやas-of / leakage-safe rulesなど、Project固有の意味論だけをProject側で定義して共通toolへ渡す。

Durable analytical dataはParquetを基本とする。DuckDBはParquetを直接queryするin-process engineとして利用できるため、persistent `.duckdb` fileはデフォルト正本としない。将来persistent DBが必要になっても、原則としてraw / canonicalから再生成可能な派生物として扱う。

## Layer responsibilities

### 00_raw

NARレスポンスZIPをバイト列のまま保存する不変原本層。

- `00_raw/race/`: レース情報ZIP
- `00_raw/odds/`: オッズ情報ZIP

同名原本を異なる内容で上書きしない。

### 10_canonical

将来、rawから再生成する型付け・キー付与済みの加工後・正規化データ。
rawが残っていれば削除・再生成できるものとする。

次PhaseでParquetを導入する場合は `tools/data-storage/` を利用する。pre-race / post-raceの物理分離やas-of validationなど、地方競馬固有のleakage-safe設計はProject側のschema / configとして保持する。

### 20_audit

取得元URL、対象年月、取得日時、SHA-256、サイズ、ZIP内ファイル一覧、文字コード観測等を保持する。
Parquet変換を導入した場合は `tools/data-storage/` が出力するvalidation / audit JSONもここに保存する候補とする。

### 30_analysis

指数研究、特徴量比較、回収率検証などの成果物。Phase 0では領域のみ確保する。
DuckDBを使う分析は、canonical Parquetを直接参照する方式を第一候補とする。

### data_pdf_manual.pdf

NAR公式データダウンロード機能説明書の参照コピー。
