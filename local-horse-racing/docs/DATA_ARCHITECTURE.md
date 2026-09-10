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

## Google Drive target layout

Drive側の実フォルダ作成・権限管理はユーザー側で行う。
推奨論理構造は次のとおり。

~~~text
地方競馬/
└─ NAR/
   ├─ raw/
   │  ├─ monthly/
   │  │  ├─ race/YYYY/
   │  │  └─ odds/YYYY/
   │  └─ daily/
   │     ├─ race/
   │     └─ odds/
   ├─ canonical/
   │  ├─ race/
   │  ├─ horse/
   │  ├─ payout/
   │  └─ odds/
   ├─ audit/
   └─ reference/
~~~

将来、`地方競馬/analysis/` を別途追加してもよいがPhase 0では不要。

## Layer responsibilities

### raw

NARレスポンスZIPをバイト列のまま保存する不変層。
同名原本を異なる内容で上書きしない。

### canonical

将来、rawから再生成する型付け・キー付与済みデータ。
rawが残っていれば削除・再生成できるものとする。

### audit

取得元URL、対象年月、取得日時、SHA-256、サイズ、ZIP内ファイル一覧、文字コード観測等を保持する。

### analysis

指数研究、特徴量比較、回収率検証などの成果物。Phase 0対象外。
