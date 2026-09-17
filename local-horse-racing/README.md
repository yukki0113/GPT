# local-horse-racing

地方競馬のデータ基盤・予想研究を再現可能かつリーク安全に進めるための作業領域です。

NAR（地方競馬全国協会）の公式CSVを一次データ源とし、Webページのスクレイピングは不足項目が明確になった場合のみ検討します。

2026-09-17から **Phase 1（canonical foundation）** に進みます。Phase 0の取得基盤は維持したまま、raw race CSVを予想時情報と結果情報へ物理分離し、as-of検証を通過した情報だけを将来のモデル入力へ昇格できる基盤を実装します。

## Current scope

- NAR月次レース情報ZIP / オッズ情報ZIPの取得と不変保存
- ZIP内ファイル名・CSVヘッダーの検証
- SHA-256 / audit JSON生成
- 公式CSVスキーマのコード化
- canonical field catalogによる `PRE_SAFE` / `PRE_ASOF_PENDING` / `POST_ONLY` 分類
- `pre` / `post` / `control` の物理分離
- race / runner canonical keyの付与
- paybackのlong形式正規化
- 返還・中止等を通常結果欠損と分ける `race_status`
- 累積成績・最高タイム系のas-of evidence検証
- `tools/data-storage/` を利用したZSTD Parquet変換・validation

## Still out of scope

- as-of未検証列のモデル特徴量利用
- 独自指数・機械学習モデル
- 自動予想、買い目生成、販売運用
- oddsを使った市場期待値ロジック
- 永続DuckDBを正本とする運用

## Raw download quick start

プロジェクトルートで実行します。Driveの論理ルートは `/GPT/local-horse-racing/` です。

~~~bash
cd local-horse-racing
python -m nar.download.monthly \
  --year 2026 \
  --month 9 \
  --kind race \
  --output-dir /path/to/Drive/GPT/local-horse-racing/00_raw/race \
  --audit-dir /path/to/Drive/GPT/local-horse-racing/20_audit
~~~

オッズは `--kind odds` に変更し、出力先を `/path/to/Drive/GPT/local-horse-racing/00_raw/odds` にします。

このコマンドはNARから受け取ったZIPを加工せず保存します。同名ファイルが既に存在する場合、内容が同一なら再書き込みせず、内容が異なる場合は原本の上書きを拒否します。

## Canonical build quick start

公式月次race ZIP、またはDriveで年単位に束ねた `NAR_race_YYYY_raw_monthly_zips.zip` を入力できます。

~~~bash
cd local-horse-racing
PYTHONPATH=. python -m nar.canonical.build \
  --input /path/to/NAR_race_2016_raw_monthly_zips.zip \
  --staging-dir /tmp/nar-canonical-stage \
  --validate-asof
~~~

この段階ではUTF-8-SIG staging CSVとcontrol JSONを生成します。Parquetまで生成する場合は、リポジトリルートから共通toolを利用します。

~~~bash
PYTHONPATH="local-horse-racing:tools/data-storage" \
python -m nar.canonical.build \
  --input /path/to/NAR_race_2016_raw_monthly_zips.zip \
  --staging-dir /tmp/nar-canonical-stage \
  --parquet-dir /path/to/Drive/GPT/local-horse-racing/10_canonical \
  --audit-dir /path/to/Drive/GPT/local-horse-racing/20_audit/canonical \
  --validate-asof
~~~

Parquet writer / schema・row-count・canonical-key・NULL validationは `tools/data-storage/` の `data_storage.runner.run_config` をimportして実行し、地方競馬側では同等実装を複製しません。

## Canonical leakage boundary

`racelist.csv` / `horselist.csv` はpre-race情報とpost-race情報が同一行に混在するため、rawをバックテストから直接読みません。

~~~text
10_canonical/
├─ pre/
│  ├─ race/
│  ├─ runner/
│  └─ runner_history_snapshot/
├─ post/
│  ├─ race_result/
│  ├─ runner_result/
│  └─ payout/
└─ control/
   ├─ race_status/
   ├─ field_catalog.json
   └─ leakage_validation.json
~~~

- `PRE_SAFE`: 発走前情報として利用可能。ただし `ENTRY` / `RACE_DAY` / `WEIGH_IN` の段階を守る。
- `PRE_ASOF_PENDING`: 発走前snapshot候補だが、期間横断のas-of検証完了まで特徴量利用禁止。
- `POST_ONLY`: 着順、タイム、人気、上がり、通過順、払戻など。評価用以外へ渡さない。

## Storage responsibilities

Drive root: `https://drive.google.com/drive/folders/1FPxtdPfLNy1EW_WoGtk9C867b7CfAmfI`

- Git: コード、仕様、スキーマ、テスト、運用ルール
- Google Drive `/GPT/local-horse-racing/00_raw/race`: NAR公式レース情報ZIPの不変原本
- Google Drive `/GPT/local-horse-racing/00_raw/odds`: NAR公式オッズ情報ZIPの不変原本
- Google Drive `/GPT/local-horse-racing/10_canonical`: rawから再生成するParquet canonical
- Google Drive `/GPT/local-horse-racing/20_audit`: 取得・canonical変換・validation監査
- Google Drive `/GPT/local-horse-racing/30_analysis`: 将来の指数研究・検証成果

GitにはNAR原本ZIP、大容量CSV、Parquet、DuckDBをcommitしません。

## Shared Parquet / DuckDB tooling

Parquet / DuckDBを使う加工・検証・query・benchmarkは、リポジトリ共通の `tools/data-storage/` を標準実装として利用します。

- durable analytical dataはParquetを基本とする。
- DuckDBはParquetを直接queryするin-process engineとして利用し、永続 `.duckdb` ファイルを必須としない。
- CSV / SQLiteからParquetへの変換、schema / row-count / canonical-key / NULL等の検証、audit JSON、DuckDB query、benchmarkは共通toolを再利用する。
- local-horse-racing固有の列、キー、partition、as-of / leakage ruleはプロジェクト側に置く。
- 共通toolの仕様・test方法は `tools/data-storage/README.md` を正本とする。

## Documents

- `.gpt/CONTEXT.md` — GPT / Work向けの前提
- `.gpt/WORKFLOW.md` — 作業手順・境界
- `docs/NAR_DATA_SPEC.md` — 公式仕様と実測メモ
- `docs/DATA_ARCHITECTURE.md` — Git / Drive / canonicalの責務分離
- `docs/CANONICAL_DATA_SPEC.md` — pre/post schema、field policy、as-of validation仕様
