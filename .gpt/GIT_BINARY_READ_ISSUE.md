# GPT Git Binary Read Issue Protocol

GitHub `main` 上の `.xlsx`、`.sqlite`、`.zip` など、GitHub Connectorだけでは実ファイルとして直接解析しにくいファイルを、ChatGPT / Work の実行環境へ取り出すための共通経路です。

## 目的

通常のテキストファイルは GitHub Connector から直接読めます。
一方、バイナリファイルは GitHub 上に存在していても、そのままExcelやSQLiteとして解析できない場合があります。

この経路では、Issueを起点にGitHub Actionsが最新 `main` の対象ファイルをActions artifactへ梱包します。
Chat側はworkflow runのartifactを取得し、実ファイルとして解析します。

## External source-of-truth exception

各プロジェクトのREADME / `.gpt/CONTEXT.md` / `.gpt/WORKFLOW.md` でGitHub外を正本と定義した運用ファイルは、このreadback経路の対象外です。GitHubに旧コピーが残っていても最新と推定しません。

競艇継続台帳の正本はネイティブGoogleスプレッドシート `競艇note販売運用台帳`（Spreadsheet ID `1gEAYJ90Zv3HDi5gh_at0jDWEQrgCSB5tIywJFZjXcFM`）です。Google Drive旧Excel版および GitHub `boat-racing/ledger/競艇note販売運用台帳.xlsx` は移行前スナップショットなので、このreadback経路で競艇台帳を取得しません。

## 推奨操作層

認証済み `gh` CLIを実行できる環境では、Issue作成・完了待ち・artifact取得・SHA-256照合を手作業で行わず、次の共通CLIを第一選択にします。

```bash
python .gpt/tools/gpt_git_binary_tool.py read \
  --path "horse-racing/eval/ledger/Eval表集計・検証.xlsx" \
  --output "/tmp/Eval表集計・検証.xlsx"
```

詳細は `.gpt/GIT_BINARY_TOOL.md` を参照してください。

`gh` CLIが利用できないChat環境では、以下のIssueプロトコルを直接使用します。

## Issueタイトル

```text
[gpt-git-binary-read] <short description>
```

Issue作成者は `yukki0113` である必要があります。

## Issue本文

```text
path: horse-racing/eval/ledger/Eval表集計・検証.xlsx
request_id: eval-ledger-analysis-20260826
```

`request_id` は省略可能です。省略時はIssue番号から自動生成します。

## Actionsの処理

1. 最新 `main` をcheckout
2. 対象パスを検証
3. 対象ファイルの存在を確認
4. SHA-256・サイズ・source commitを記録
5. 元ファイルと `manifest.json` をartifactへ格納
6. 成功コメントへ `run_id` / `artifact_name` / SHA-256等を返す
7. 成功時にIssueをClose
8. 成否コメントの先頭で `@yukki0113` を一度だけメンション

artifact保持期間は7日です。

## Chat / Work側の回収手順

成功コメントの `GIT_BINARY_READ_RESULT` から `run_id` と `artifact_name` を取得します。

その後、GitHub Connectorで

1. 対象workflow runのartifact一覧を取得
2. `artifact_name` が一致するartifactを特定
3. artifact ZIPをダウンロード
4. ZIP内の元ファイルを実行環境へ展開
5. `manifest.json` のSHA-256と実ファイルのSHA-256を照合
6. ファイル形式に応じたツールで解析

まで行います。

## セキュリティ境界

この経路はリポジトリ全体を原則読み取り対象としますが、以下は拒否します。

- `.git/`
- `.env`
- `jrdb_secret.py`
- パス名に `secret` / `credential` / `password` を含むもの
- `.pem` / `.key` / `.p12` / `.pfx`
- 絶対パス、`../` を含む危険なパス

GitHub公開リポジトリに置くべきでない情報は、そもそもこの経路の対象にしないでください。

## 使い分け

```text
通常テキストを読む
  → GitHub Connectorで直接取得

通常テキストを更新
  → [gpt-git-update]

Git管理バイナリをGitHubへ更新
  → gpt_git_binary_tool.py update
     または [gpt-git-binary-update]

GitHub正本のバイナリをChat / Workへ取得
  → gpt_git_binary_tool.py read
     または [gpt-git-binary-read]

外部ストレージ正本
  → プロジェクト定義の外部正本へ直接アクセス
```

このreadback経路はGitHub正本を変更しません。Actions artifactは一時的な搬送物です。正本の所在は各プロジェクトのREADME / `.gpt/WORKFLOW.md` に従います。
