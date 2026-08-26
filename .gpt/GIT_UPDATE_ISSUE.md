# GPT Git Update Issue protocol

GitHubへ直接commit/pushできないChatGPT / Work環境から、GitHub Issueを経由してリポジトリの更新をmainへ反映するための共通経路です。

## 基本方針

この経路は、特定プロジェクトだけを許可する allowlist 方式ではありません。

- リポジトリ配下は原則として更新可能
- 新規プロジェクト追加時にWorkflowの許可パスを変更する必要はない
- 業務上の配置ルールやGit管理対象は、各README / `.gpt/WORKFLOW.md` / `.gitignore` を正本とする
- Actions側では、事故や権限拡大につながる最低限のセキュリティ境界だけを強制する

## Trigger

Issue title must start with:

```text
[gpt-git-update]
```

Issue author must be `yukki0113`.

## Body format

```markdown
commit_message: fix: describe the change

```diff
--- a/README.md
+++ b/README.md
@@ -1,3 +1,4 @@
 ...
```
```

## Repository scope

原則として、リポジトリ内の通常ファイルはこの経路から更新可能です。

新しいプロジェクトやディレクトリを追加しても、共通Workflow側の許可リスト更新は不要です。

## Protected paths / rejected credential files

Issue経路では、以下を保護対象とします。

- `.github/workflows/` — Workflow自身の自己改変を防ぐため
- `.git/` — Git内部メタデータ
- `.env`
- `jrdb_secret.py`
- ファイル名に `secret` / `credential` / `password` を含むもの
- 秘密鍵・証明書系拡張子 `.pem` / `.key` / `.p12` / `.pfx`
- 絶対パスや `..` を含む危険なパス

これら以外は、拡張子だけを理由に一律拒否しません。

## Excel / SQLite / ZIP等の扱い

`.xlsx`、`.xls`、`.sqlite`、`.db`、`.zip` 等は、このWorkflowのセキュリティ制約としては一律禁止しません。

Gitで管理すべきかどうかは、ファイルの役割・保存先・各プロジェクトの運用ルール・`.gitignore` に従います。

ただし、この `[gpt-git-update]` 経路自体は Issue本文の unified diff を `git apply` するテキスト更新方式です。
そのため、Excel等のバイナリファイルは「Git管理可能」であっても、このdiff方式では転送できません。

バイナリファイルは、実装済みの `[gpt-git-binary-update]` 経路を使用してください。
詳細は `.gpt/GIT_BINARY_UPDATE_ISSUE.md` を参照してください。

## Processing

1. Checkout latest `main`.
2. Parse the Issue body.
3. Validate patch paths against the protected-path rules.
4. Run `git apply --check`.
5. Apply the patch.
6. Run `git diff --check`.
7. Run `py_compile` for changed Python files.
8. Commit with the requested commit message.
9. Rebase onto the latest `origin/main`.
10. Push to `main`.
11. Comment the resulting commit SHA and close the Issue.

If any step fails, nothing is pushed and the Issue remains open with a link to the failed Actions run.

## GPT / Work rule

When direct GitHub commit/push is unavailable, do not ask the user to manually push ordinary source/documentation changes.
Create a `[gpt-git-update]` Issue using this protocol and use the Issue/Actions route instead.

変更対象にバイナリファイルが含まれる場合は `.gpt/GIT_BINARY_UPDATE_ISSUE.md` の経路へ切り替えてください。

古いローカルcommitをそのままpushするのではなく、最新mainを基準として未反映差分を作成してください。
