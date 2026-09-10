# local-horse-racing

地方競馬のデータ基盤・予想研究を将来再開できるようにするための作業領域です。

2026-09時点では **Phase 0（取得基盤のみ）** とし、指数・特徴量・モデル・予想運用には着手しません。
NAR（地方競馬全国協会）の公式CSVを一次データ源とし、Webページのスクレイピングは不足項目が明確になった場合のみ検討します。

## Phase 0 scope

- NAR月次レース情報ZIP / オッズ情報ZIPの取得
- ZIP内ファイル名・CSVヘッダーの検証
- 原本ZIPの不変保存を補助するSHA-256 / audit JSON生成
- 公式CSVスキーマのコード化
- 取得仕様・保存責務の文書化

## Out of scope

- 1998年以降の全件バックフィル
- canonical / DBへの正規化
- as-of特徴量生成
- 独自指数・機械学習モデル
- 日次自動予想、買い目生成、回収率検証
- Google Drive APIへの直接書き込み

## Quick start

プロジェクトルートで実行します。

~~~bash
cd local-horse-racing
python -m nar.download.monthly \
  --year 2026 \
  --month 9 \
  --kind race \
  --output-dir /path/to/Drive/地方競馬/NAR/raw/monthly/race/2026 \
  --audit-dir /path/to/Drive/地方競馬/NAR/audit
~~~

オッズは `--kind odds` に変更します。

このコマンドはNARから受け取ったZIPを加工せず保存します。同名ファイルが既に存在する場合、内容が同一なら再書き込みせず、内容が異なる場合は原本の上書きを拒否します。

## Storage responsibilities

- Git: コード、仕様、スキーマ、テスト、運用ルール
- Google Drive `raw`: NARから取得した原本ZIP
- Google Drive `canonical`: 将来、rawから再生成する正規化データ
- Google Drive `audit`: 取得日時、SHA-256、サイズ、ZIP内ファイル一覧など
- Google Drive `analysis`: 将来の指数研究・検証成果

GitにはNAR原本ZIPや大容量CSVをcommitしません。

## Documents

- `.gpt/CONTEXT.md` — GPT / Work向けの前提
- `.gpt/WORKFLOW.md` — 作業手順・境界
- `docs/NAR_DATA_SPEC.md` — 公式仕様と2026-09実測メモ
- `docs/DATA_ARCHITECTURE.md` — Git / Driveの責務分離
