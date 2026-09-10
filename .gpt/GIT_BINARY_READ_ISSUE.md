# GPT Git Binary Read Issue Protocol — Compatibility Fallback

この文書は、GitHub正本の `.xlsx` / `.sqlite` / `.db` / `.zip` 等をChatGPT / Workへ実ファイルとして取り出すための**互換フォールバック**です。

上位方針は `.gpt/GITHUB_OPERATION_POLICY.md` を参照してください。

## 標準判断

まず対象ファイルの正本所在を確認します。

- GitHub外が正本: 各プロジェクト定義の外部正本へ直接アクセス
- GitHubが正本: 現在のGitHub / connector /実行環境で直接read / download / materialize可能か確認
- 直接取得できない: このIssue / Actions readbackをフォールバックとして使用

「バイナリだから必ずIssue」とはしません。

## 目的

この経路では、Issueを起点にGitHub Actionsがlatest `main` の対象バイナリをartifactへ梱包し、Chat / Workがartifactを取得して実ファイルとして解析します。

## Issue title

```text
[gpt-git-binary-read] <short description>
```

Issue authorは `yukki0113` である必要があります。

## Issue body

```text
path: example-project/path/example.sqlite
request_id: example-read-20260910
```

`path` は必須、`request_id` は省略可能です。

## Preflight

`.gpt/ISSUE_REQUEST_CONTRACTS.md` を適用します。

```bash
python .gpt/tools/gpt_issue_preflight.py \
  --title "[gpt-git-binary-read] read example" \
  --body-file /tmp/issue-body.txt
```

retryではfailed stepを確認し、必要なら新しい `request_id` を使います。

## Actions processing

1. latest `main` checkout
2. path / security validation
3. file existence確認
4. source commit / size / SHA-256記録
5. 元ファイル + `manifest.json` をartifact化
6. `GIT_BINARY_READ_RESULT` へ `run_id` / `artifact_name` / SHA等を返却
7. 成功時Issue close

artifactは搬送用の一時物であり、GitHub正本そのものではありません。

## Chat / Work recovery

1. RESULTの `status=success` を確認
2. `run_id` / `artifact_name` を完全一致で取得
3. workflow artifact一覧から実在確認
4. artifact ZIP取得・展開
5. manifestと実ファイルのsize / SHA-256照合
6. ファイル形式に応じて解析

upstream情報を推測して下流処理を開始しません。

## Security boundary

少なくとも以下は拒否対象です。

- `.git/`
- `.env`
- `jrdb_secret.py`
- path名に `secret` / `credential` / `password` を含むもの
- `.pem` / `.key` / `.p12` / `.pfx`
- 絶対パス / `../`

## CLI wrapper

`.gpt/tools/gpt_git_binary_tool.py read` は、このIssue / Actions手順を包む互換CLIです。

このCLIも内部でIssue / Actionsを使用するため、**現在の環境で直接バイナリ取得できる場合はそちらを優先**します。詳細は `.gpt/GIT_BINARY_TOOL.md` を参照してください。

## Positioning

```text
GitHub text read
  -> A. direct read / fetch

GitHub binary read
  -> direct read / download / materializeが可能なら直接
  -> 不可能な場合のみ [gpt-git-binary-read]

external source of truth
  -> project定義の外部正本へ直接
```
