# local-horse-racing context

## Purpose

地方競馬プロジェクトの将来着手に備え、NAR公式CSVを安定して取得・保存できる最小基盤を維持する。

## Current phase

2026-09時点は Phase 0。
中央競馬側の開発・運用を優先しているため、地方競馬では取得基盤より先へ自動的にスコープを広げない。

## Source of truth

- ソースコード、仕様、スキーマ、テスト: GitHub `yukki0113/GPT` の `local-horse-racing/`
- データ資産: Google Drive `/GPT/NAR/`
- Drive root: `https://drive.google.com/drive/folders/1FPxtdPfLNy1EW_WoGtk9C867b7CfAmfI`

Drive上の役割は次のとおり。

- `00_raw/race/`: NAR公式レース情報ZIPの不変原本
- `00_raw/odds/`: NAR公式オッズ情報ZIPの不変原本
- `10_canonical/`: rawから再生成する加工後・正規化データ
- `20_audit/`: 取得・検証監査データ
- `30_analysis/`: 将来の分析・研究成果
- `data_pdf_manual.pdf`: NAR公式データダウンロード説明書

Gitに原本ZIP、大容量CSV、認証情報を置かない。

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
- `horselist.人気` はpre-race特徴量として使用しない。結果確定前の実測で不安定な値を確認している。
- `horselist` の累積成績列はas-ofらしい実測があるが、本格利用前により広い期間で時点性を再検証する。
- paybackは同着等で1レース複数行になり得る。
- 中止・返還等は通常の結果欠損と区別する。
- 将来の特徴量生成では対象レース発走時刻より前の情報だけを利用する。
