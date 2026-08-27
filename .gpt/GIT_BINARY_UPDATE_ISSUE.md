# GPT Git Binary Update Issue protocol

GitHubへ直接commit/pushできないChatGPT / Work環境から、`.xlsx` などテキストdiffでは運べないGit管理対象ファイルをIssue経由で`main`へ反映するための共通経路です。

通常のテキストファイルは `.gpt/GIT_UPDATE_ISSUE.md` の `[gpt-git-update]` を使用してください。

## 推奨操作層

認証済み `gh` CLIを実行できる環境では、Base64化、分割コメント、確定コメント、完了待ちを手作業で行わず、次の共通CLIを第一選択にします。

```bash
python .gpt/tools/gpt_git_binary_tool.py update \
  --file "/tmp/競艇note販売運用台帳.xlsx" \
  --path "boat-racing/ledger/競艇note販売運用台帳.xlsx" \
  --message "chore: update boat racing ledger"
```

詳細は `.gpt/GIT_BINARY_TOOL.md` を参照してください。

`gh` CLIが利用できないChat環境では、以下のIssueプロトコルを直接使用します。

## Trigger

Issue title must start with:

```text
[gpt-git-binary-update]
```

Issue author and payload comments must be `yukki0113`.

全チャンク登録後、次のコメントを投稿するとActionsが復元処理を開始します。

```text
[gpt-git-binary-commit]
```

## Issue body format

```text
target_path: boat-racing/ledger/example.xlsx
commit_message: chore: update example ledger
sha256: <64 hex characters>
size_bytes: <raw file byte count>
chunks: <number of chunk comments>
encoding: base64
```

`target_path` はリポジトリ相対パスです。

## Chunk comment format

Base64文字列を複数コメントに分割して登録できます。

```text
[gpt-git-binary-chunk 1/3]
```text
<base64 chunk 1>
```
```

続けて `2/3`, `3/3` を登録します。チャンク番号の欠落・重複・総数不一致は拒否されます。

1コメントあたりのBase64文字列は、GitHubのコメント上限に余裕を持たせるため、おおむね48,000文字以下を推奨します。

## Verification

Actionsはpush前に以下を検証します。

1. Issue作成者・確定コメント作成者が `yukki0113` であること。
2. `target_path` が安全なリポジトリ相対パスであること。
3. `.github/workflows/`, `.git/`, secrets領域、認証情報・秘密鍵類でないこと。
4. 全Base64チャンクが揃い、番号が一意であること。
5. 復元後のバイト数が `size_bytes` と一致すること。
6. 復元後のSHA-256が `sha256` と一致すること。
7. `.xlsx` の場合、ZIP CRCと主要XLSXエントリ（`[Content_Types].xml`, `xl/workbook.xml`）が正常であること。
8. 新規ファイルの場合、`.gitignore` により除外されていないこと。

既にGit追跡中のファイルは、`.gitignore` に該当していても更新可能です。

## Processing

1. Checkout latest `main`.
2. Issue bodyからメタ情報を取得。
3. Issueコメントから全Base64チャンクを取得。
4. チャンクを順番に結合し、バイナリを復元。
5. サイズ・SHA-256・必要な形式検証を実施。
6. 対象パスへ配置。
7. `git add` / `git commit`。
8. 最新`origin/main`へrebase。
9. `main`へpush。
10. Issueへパス・サイズ・SHA-256・commit SHAをコメントし、成功時Close。

失敗時はpushせず、IssueをOpenのまま残します。

## Scope policy

この経路は特定プロジェクトのallowlistを持ちません。リポジトリ全体を原則対象とし、セキュリティ上保護すべき領域だけを拒否します。

`.xlsx`, `.xls`, `.sqlite`, `.db`, `.zip` 等を拡張子だけで禁止しません。Gitで管理すべきかどうかは、各プロジェクトのREADME / `.gpt/WORKFLOW.md` / `.gitignore` の業務ルールに従います。

## GPT / Work rule

直接GitHubへcommit/pushできず、変更対象にバイナリファイルが含まれる場合、ユーザーへ手動pushを依頼する前にこの経路を使用してください。

認証済み `gh` CLIを実行できる場合は `.gpt/tools/gpt_git_binary_tool.py update` を使い、GPTがBase64チャンクを手作業で組み立てないでください。

`gh` CLIが利用できない場合のみ、ファイルをBase64化し、SHA-256・バイト数を算出し、Issueとチャンクコメントを登録してから `[gpt-git-binary-commit]` を投稿してください。
