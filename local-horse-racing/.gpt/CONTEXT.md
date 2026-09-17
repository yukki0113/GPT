# local-horse-racing context

## Purpose

NAR公式CSVを安定取得・保存し、予想時点情報と結果情報を物理分離したリーク安全なcanonicalデータ基盤を構築する。

## Current phase

2026-09-17から Phase 1（canonical foundation）。

Phase 0の取得基盤は維持する。現在の実装対象はfield catalog、canonical schema、pre/post splitter、race status、as-of evidence validation、共有Parquet基盤への接続まで。指数・モデル・自動予想へは自動的に進めない。

## Source of truth

- ソースコード、仕様、スキーマ、テスト: GitHub `yukki0113/GPT` の `local-horse-racing/`
- 共通Parquet / DuckDB処理: GitHub `yukki0113/GPT` の `tools/data-storage/`
- データ資産: Google Drive `/GPT/local-horse-racing/`
- Drive root: `https://drive.google.com/drive/folders/1FPxtdPfLNy1EW_WoGtk9C867b7CfAmfI`

Drive上の役割は次のとおり。

- `00_raw/race/`: NAR公式レース情報ZIPの不変原本
- `00_raw/odds/`: NAR公式オッズ情報ZIPの不変原本
- `10_canonical/`: rawから再生成するParquet canonical
- `20_audit/`: 取得・canonical変換・validation監査
- `30_analysis/`: 将来の分析・研究成果
- `data_pdf_manual.pdf`: NAR公式データダウンロード説明書

Gitに原本ZIP、大容量CSV、Parquet、DuckDB、認証情報を置かない。

## Canonical policy

rawの `racelist.csv` / `horselist.csv` はpre-race情報とpost-race情報を同一行に持つため、バックテストや特徴量生成からrawを直接参照しない。

canonicalの論理層:

- `pre/race`: レース条件。天候・馬場は `RACE_DAY`。
- `pre/runner`: 馬・騎手・調教師等。馬体重は `WEIGH_IN`。
- `pre/runner_history_snapshot`: 累積成績・最高タイム。初期状態は `PENDING_VALIDATION`。
- `post/race_result`: 上がり・ハロン・コーナー通過順等。
- `post/runner_result`: 着順・タイム・着差・上がり・人気。
- `post/payout`: paybackをlong形式へ正規化した評価専用データ。
- `control/race_status`: NORMAL / REFUNDED / CANCELLED / NO_RESULT / DATA_MISSING等とmodel/return対象可否。
- `control/field_catalog.json`: raw fieldごとのavailability / stage / feature policy。
- `control/leakage_validation.json`: as-of検証証跡。

field policy:

- `PRE_SAFE`: stage制約を守れば利用候補。
- `PRE_ASOF_PENDING`: 検証完了まで特徴量利用禁止。
- `POST_ONLY`: 評価用以外へ渡さない。

`horselist.人気` はpre-race特徴量として使用しない。2026-09の結果確定前実測で不安定・placeholder的な値を確認している。

## Shared data-storage policy

Parquet / DuckDB処理は `tools/data-storage/` を共通基盤として優先利用する。

- durable analytical dataはZSTD Parquetを基本とする。
- canonicalは `race_year` Hive partitionを基本候補とする。
- DuckDBはParquetを直接queryするin-process engineとして利用し、persistent `.duckdb` はデフォルト正本にしない。
- conversion / validation / query / benchmark / auditは共通実装をimportまたはCLI経由で利用し、各Projectで同等処理を再実装しない。
- local-horse-racing固有のcolumns / keys / partitions / as-of rulesはProject側に定義する。
- 共通toolの詳細は `tools/data-storage/README.md` を参照する。

## Data source

NAR地方競馬情報サイトの公式データダウンロード機能を利用する。
月次ファイルはレース情報とオッズ情報に分かれる。

- レース情報: 1998-01以降（公式説明書。ただし過去欠損の可能性あり）
- オッズ情報: 2026-03以降
- 月次レースZIP: racelist / horselist / payback
- 月次オッズZIP: 01 / 02 / 03 の3分割CSV

公式説明書: https://www.keiba.go.jp/pdf/manual/data_pdf_manual.pdf

## Important guardrails

- raw ZIPは不変原本。加工・上書きをしない。
- rawをモデルコードから直接読ませない。
- `PRE_ASOF_PENDING` はevidenceが良好でも自動昇格しない。広期間監査後に明示昇格する。
- paybackは同着等で1レース複数行になり得る。
- 中止・返還等は通常の結果欠損と区別する。
- `race_status.is_model_target` と `is_return_target` を分離する。
- 将来の集計特徴量は対象レース発走時刻より前の情報だけから生成する。
