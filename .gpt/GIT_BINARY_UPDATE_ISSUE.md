# GPT Git Binary Update Issue Protocol — Compatibility Fallback

この文書は、Git管理対象の `.xlsx` / `.sqlite` / `.db` / `.zip` 等をIssue / Actions経由で `main` へ反映するための**互換フォールバック仕様**です。

上位方針は `.gpt/GITHUB_OPERATION_POLICY.md` を参照してください。

## 標準判断

まず対象ファイルの正本所在と現在の書き込み能力を確認します。

- GitHub外が正本: 各プロジェクト定義の外部正本を更新
- GitHub正本で直接安全に更新可能: direct Git経路を優先
- GitHub正本だが直接binary writeが利用できない: このIssue / Actions経路をフォールバックとして使用

通常のUTF-8テキスト変更にはこのprotocolを使いません。B. Git Changeのdirect create / update / deleteを使用します。

## Trigger

Issue title:

```text
[gpt-git-binary-update] <description>
```

Issue author / payload comment authorは `yukki0113` である必要があります。

全chunk登録後:

```text
[gpt-git-binary-commit]
```

を投稿すると復元処理を開始します。

## Issue body

```text
target_path: example-project/path/example.xlsx
commit_message: chore: update example binary
sha256: <64 hex>
size_bytes: <raw byte count>
chunks: <positive integer>
encoding: base64
```

## Preflight

`.gpt/ISSUE_REQUEST_CONTRACTS.md` を適用します。

```bash
python .gpt/tools/gpt_issue_preflight.py \
  --title "[gpt-git-binary-update] update example" \
  --body-file /tmp/issue-body.txt
```

`target_path` / `commit_message` / `sha256` / `size_bytes` / `chunks` / `encoding` は必須です。SHA / size / chunk数は実ファイルから算出し、推測しません。

## Chunk format

```text
[gpt-git-binary-chunk 1/3]
```

に続けてBase64 payloadをコードブロックで登録します。chunk番号の欠落・重複・総数不一致は拒否します。

1コメントのBase64文字列はGitHub上限に余裕を持たせ、おおむね48,000文字以下を推奨します。

## Verification

Actionsはpush前に少なくとも次を検証します。

1. author
2. repository-relative path / protected path
3. 全chunkの完全性
4. raw byte size
5. SHA-256
6. `.xlsx` のZIP CRC / workbook主要entry
7. 新規ファイルの `.gitignore`

既追跡ファイルは `.gitignore` 該当でも更新できる場合があります。

## Processing

1. latest `main` checkout
2. metadata parse
3. chunk collect / Base64 restore
4. size / SHA / format validation
5. target pathへ配置
6. commit
7. latest `origin/main` へrebase
8. push `main`
9. path / SHA / commit SHAをRESULTへ記録
10. success時close

failed step未確認で同じpayloadをblind rerunしません。

## CLI wrapper

`.gpt/tools/gpt_git_binary_tool.py update` はこのIssue / Actions手順を自動化する互換CLIです。

CLI内部もIssue / Actionsを使うため、**現在の環境でdirect binary updateが可能ならdirect経路を優先**します。詳細は `.gpt/GIT_BINARY_TOOL.md` を参照してください。

## Positioning

```text
UTF-8 text change
  -> B. direct GitHub write

GitHub-managed binary change
  -> direct binary writeが可能なら直接
  -> 不可能な場合のみ [gpt-git-binary-update]

external source of truth
  -> project定義の外部正本を更新
```
