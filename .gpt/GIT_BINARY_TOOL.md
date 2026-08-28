# GPT Git Binary Tool

GitHub `main` と ChatGPT / Work の実行環境の間で、`.xlsx`、`.sqlite`、`.db`、`.zip` 等のGit管理対象バイナリを1コマンドで読み書きする共通CLIです。

既存の Issue -> GitHub Actions 経路は、監査ログ、検証、通知、main反映の実行基盤としてそのまま使用します。このCLIは、その手順を日常作業から隠蔽する薄い操作層です。

## Source

```text
.gpt/tools/gpt_git_binary_tool.py
```

Python標準ライブラリのみを使用します。外部Pythonパッケージは不要です。

必要条件:

- Python 3.10+
- GitHub CLI `gh`
- `gh auth status` が成功する認証済み環境

## Read

GitHub `main` 上のバイナリを実ファイルとしてローカルへ取得します。

```bash
python .gpt/tools/gpt_git_binary_tool.py read \
  --path "horse-racing/eval/ledger/Eval表集計・検証.xlsx" \
  --output "/tmp/Eval表集計・検証.xlsx"
```

内部では以下を自動実行します。

1. `[gpt-git-binary-read]` Issue作成
2. Actions完了待ち
3. `GIT_BINARY_READ_RESULT` 解析
4. Actions artifact取得・展開
5. `manifest.json` 読み込み
6. サイズ・SHA-256照合
7. 検証済み実ファイルを `--output` へ配置

既存出力を上書きする場合は `--force` を指定します。

## Update

ローカルの実ファイルを、検証済みのバイナリ更新経路でGitHub `main` へ反映します。

```bash
python .gpt/tools/gpt_git_binary_tool.py update \
  --file "/tmp/example-ledger.xlsx" \
  --path "example-project/ledger/example-ledger.xlsx" \
  --message "chore: update example ledger"
```

内部では以下を自動実行します。

1. ローカルファイルのサイズ・SHA-256計算
2. Base64化
3. 48,000文字単位で分割
4. `[gpt-git-binary-update]` Issue作成
5. 全チャンクコメント登録
6. `[gpt-git-binary-commit]` 確定コメント
7. Actions完了待ち
8. 最終結果のパス・SHA-256照合
9. main反映commit SHAを返却

Issue / Actions側のXLSX構造検証、gitignore、保護パス等の既存ルールはそのまま有効です。

## Project-specific external sources of truth

各プロジェクトのREADME / `.gpt/CONTEXT.md` / `.gpt/WORKFLOW.md` でGitHub外を正本と定義した運用ファイルは、このツールの対象外です。

競艇継続台帳はネイティブGoogleスプレッドシート `競艇note販売運用台帳`（Spreadsheet ID `1gEAYJ90Zv3HDi5gh_at0jDWEQrgCSB5tIywJFZjXcFM`）が正本です。Google Drive旧Excel版および GitHub `boat-racing/ledger/競艇note販売運用台帳.xlsx` は移行前スナップショットなので、このCLIで同期・取得しません。

## Output

成功時は標準出力へJSONを1件返します。

Read例:

```json
{
  "status": "success",
  "operation": "read",
  "repository": "yukki0113/GPT",
  "repository_path": "horse-racing/eval/ledger/Eval表集計・検証.xlsx",
  "local_path": "/tmp/Eval表集計・検証.xlsx",
  "issue_number": 123,
  "run_id": 456,
  "artifact_name": "...",
  "size_bytes": 1571685,
  "sha256": "...",
  "source_commit": "..."
}
```

Update例:

```json
{
  "status": "success",
  "operation": "update",
  "repository": "yukki0113/GPT",
  "repository_path": "example-project/ledger/example-ledger.xlsx",
  "local_path": "/tmp/example-ledger.xlsx",
  "issue_number": 124,
  "commit_sha": "...",
  "size_bytes": 1012259,
  "sha256": "...",
  "chunks": 29
}
```

失敗時は標準エラーへ `status=failure` のJSONを返し、終了コード1になります。

## GPT / Work rule

認証済み `gh` CLIを実行できる環境では、Git管理バイナリのread/updateについてIssue本文やBase64チャンクをGPTが手作業で組み立てず、このCLIを第一選択にしてください。

```text
GitHub binary read
  -> gpt_git_binary_tool.py read

GitHub binary update
  -> gpt_git_binary_tool.py update
```

`gh` CLIを実行できないChat環境では、既存のGitHub Connector + `[gpt-git-binary-read]` / `[gpt-git-binary-update]` 経路をフォールバックとして使用します。

このCLIはIssue/Actionsを廃止するものではありません。Issue番号、Actions run、最終通知、commit SHA等の監査可能性を残したまま、ChatGPT / Work側の推論・ツール呼び出し負担を減らすための操作層です。

## Tests

ネットワークを使用しない単体テスト:

```bash
python -m unittest .gpt/tools/tests/test_gpt_git_binary_tool.py
```

テスト対象:

- 危険なリポジトリ相対パスの拒否
- Read結果JSONの解析
- Update成功コメントの解析
- Base64分割・再結合の完全一致
