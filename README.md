# GPT Project Repository

ChatGPT / Work と連携して継続開発するプロジェクトのソース・仕様を管理する正本リポジトリです。

## Active projects

- `horse-racing/jrdb/` — 中央競馬・JRDBデータ基盤 / RaceNote
- `horse-racing/eval/` — 中央競馬・Eval表取得・検証
- `boat-racing/` — 競艇AI予想の取得・運用ツール
- `local-horse-racing/` — 地方競馬・NAR公式CSV取得基盤

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
