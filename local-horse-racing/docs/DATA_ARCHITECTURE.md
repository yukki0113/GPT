# Data architecture

## Principle

NARから取得した原本と、再生成可能な加工データを分離する。
GitHubはコードと仕様の正本、Google Driveはデータ資産の正本とする。

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
~~~

原本ZIP、展開済み大容量CSV、DB、分析出力はGit管理しない。

## Google Drive layout

Driveのデータ正本ルートは `/GPT/NAR/` とする。

- folder URL: `https://drive.google.com/drive/folders/1FPxtdPfLNy1EW_WoGtk9C867b7CfAmfI`
- folder ID: `1FPxtdPfLNy1EW_WoGtk9C867b7CfAmfI`

2026-09-10時点の実フォルダ構成は次のとおり。

~~~text
GPT/
└─ NAR/
   ├─ 00_raw/
   │  ├─ race/
   │  └─ odds/
   ├─ 10_canonical/
   ├─ 20_audit/
   ├─ 30_analysis/
   └─ data_pdf_manual.pdf
~~~

Driveにはソースコードを置かず、NARデータ原本、加工後データ、監査データ、分析成果、およびデータ仕様参照資料だけを置く。

## Layer responsibilities

### 00_raw

NARレスポンスZIPをバイト列のまま保存する不変原本層。

- `00_raw/race/`: レース情報ZIP
- `00_raw/odds/`: オッズ情報ZIP

同名原本を異なる内容で上書きしない。

### 10_canonical

将来、rawから再生成する型付け・キー付与済みの加工後・正規化データ。
rawが残っていれば削除・再生成できるものとする。

### 20_audit

取得元URL、対象年月、取得日時、SHA-256、サイズ、ZIP内ファイル一覧、文字コード観測等を保持する。

### 30_analysis

指数研究、特徴量比較、回収率検証などの成果物。Phase 0では領域のみ確保する。

### data_pdf_manual.pdf

NAR公式データダウンロード機能説明書の参照コピー。
