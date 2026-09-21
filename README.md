# GPT Project Repository

ChatGPT / Work と連携して継続開発するプロジェクトのソース・仕様を管理する正本リポジトリです。

## Active projects

- `horse-racing/jrdb/` — 中央競馬・JRDBデータ基盤 / RaceNote
- `horse-racing/eval/` — 中央競馬・Eval表取得・検証
- `boat-racing/` — 競艇AI予想の取得・運用ツール
- `local-horse-racing/` — 地方競馬・NAR公式CSV取得基盤
- `shared-projects/hoshigaruna-katsitore/` — 「欲しがるな、勝ち取れ」3人共同の中央競馬予想・研究Project

## Legacy

- `horse-racing/legacy/` — 旧JRA-VAN / 検証ラボ等の凍結資産

## Storage policy

GitHubはsource / test / docs / config / schema等、各プロジェクトがGit正本と定義した資産を管理します。認証情報、有料原データ、大容量成果物、日次データ、台帳等は各プロジェクトのREADME / `.gpt/WORKFLOW.md` で定義された外部正本を優先します。

## ChatGPT / WorkからのGitHub運用

リポジトリ横断のGitHub運用正本は次です。

- `.gpt/GITHUB_OPERATION_POLICY.md` — 2026-09-10以降のA/B/C/Dルーティング
- `.gpt/README.md` — 共通入口・実務上の確認順
- `.gpt/ISSUE_REQUEST_CONTRACTS.md` — Actions-native Issueを使う場合のpreflight / retry契約

処理開始時に「本当にGitHub Actions環境が必要か」を判定します。

```text
A. Read / Audit               -> GitHubから直接read/search/fetch
B. Git Change                 -> UTF-8テキストはGitHubへ直接remote commit
C. Pure Deterministic         -> Git正本moduleをGPTローカルで実行
D. Actions-Native Execution   -> 必要な場合のみIssue -> Actions
```

`[gpt-git-update]` は通常テキスト更新の標準経路ではありません。Issue / ActionsはSecrets、artifact chain、長時間・大容量処理、immutable freeze、正式監査run等でActions環境が必要な場合に限定します。

作業開始時は上記共通文書を確認したうえで、対象プロジェクトの `README.md` と `.gpt/CONTEXT.md` / `.gpt/WORKFLOW.md` を確認してください。


## JRDB normalized Parquet Warehouse

JRDBのHistorical normalized warehouseは、NAR canonicalの `CURRENT.json` とは独立した専用namespaceで管理します。参照先はDriveの `GPT/horse-racing/10_warehouse/jrdb/v1/current.json` です。既存のNAR `CURRENT.json` はJRDB用途に変更してはいけません。

2026-09-21に確定したgenerationは `jrdb_normalized_warehouse_v1_2010_2025_g20260921` です。BAC/KYI/CHA/CYB/SED/SKB/ZED/ZKB/HJC/UKCの10 family、2010–2025年、192 Parquet assetを、family staging上のimmutable object参照として束ねています。Parquetのコピー・再生成・再uploadは行いません。

staging evidenceからの検証・final generation作成は `horse-racing/jrdb/src/finalize_jrdb_warehouse_from_staging.py` を使用します。運用契約と再finalize手順は `horse-racing/jrdb/docs/JRDB_Normalized_Warehouse_Operation_v1.md` を参照してください。
