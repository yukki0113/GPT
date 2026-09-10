# GPT Git Update Issue protocol — Compatibility Fallback

この文書は、`[gpt-git-update]` Issue / Actions経路の**互換・非常時フォールバック仕様**です。
2026-09-10以降、通常のsource / test / docs / config / workflow等のUTF-8テキスト変更では、この経路を標準としません。

上位方針は `.gpt/GITHUB_OPERATION_POLICY.md` を参照してください。

## 標準経路

通常テキスト変更は次を標準とします。

```text
latest main確認
-> path存在確認
-> 現在内容 / blob SHA確認
-> 必要差分
-> GitHub direct create / update / delete
-> remote commit確認
```

GitHub APIによるdirect write成功時点でremote branchへcommit済みです。別途 `git push` は不要です。

## このIssue経路を使う場合

次のような例外時に限ります。

- 現在のChat / Work環境でdirect GitHub text writeが利用できない
- ユーザーに手動pushを依頼する前に、既存Actions互換経路を利用する必要がある
- 既存運用の再現・監査・保守のため、明示的にこのprotocolを使う

「GitHubにmoduleがある」「以前この経路を使っていた」という理由だけでは選びません。

## Trigger

Issue title:

```text
[gpt-git-update] <description>
```

Issue authorは `yukki0113` である必要があります。

## Body

```markdown
commit_message: fix: describe the change

```diff
--- a/README.md
+++ b/README.md
@@ -1,3 +1,4 @@
 ...
```
```

## Preflight

このフォールバックを使う場合も `.gpt/ISSUE_REQUEST_CONTRACTS.md` を適用します。

```bash
python .gpt/tools/gpt_issue_preflight.py \
  --title "[gpt-git-update] describe change" \
  --body-file /tmp/issue-body.md \
  --repo-root .
```

必須ルール:

1. latest `main` からpatchを生成する。
2. diff hunk行数を手作業で推測・編集しない。
3. `git apply --check` が可能ならIssue作成前に通す。
4. patch failure後は旧patchを継ぎ足さず、latest mainから再生成する。
5. failed step未確認のblind rerunをしない。

## Repository scope / security

この経路は特定プロジェクトallowlistを持たず、原則リポジトリ全体を対象とします。ただしActions側では最低限の保護境界を維持します。

代表例:

- `.github/workflows/` — Issue Workflow自身の自己改変防止
- `.git/`
- `.env`
- `jrdb_secret.py`
- path名に `secret` / `credential` / `password` を含むもの
- `.pem` / `.key` / `.p12` / `.pfx`
- 絶対パス / `..`

**注意:** direct Git Changeの許可範囲と、この互換Issue workflowの保護範囲は同一とは限りません。workflow等の通常テキスト変更はB経路のdirect GitHub writeを優先します。

## Binary

このprotocolはunified diffを適用するテキスト経路です。`.xlsx` / `.sqlite` / `.db` / `.zip` 等のバイナリは搬送できません。

GitHub正本バイナリを直接扱えない場合だけ、以下の互換経路を参照します。

- `.gpt/GIT_BINARY_READ_ISSUE.md`
- `.gpt/GIT_BINARY_UPDATE_ISSUE.md`

外部ストレージが正本と定義されているファイルは、各プロジェクト文書に従って外部正本へ直接アクセスします。

## Actions processing

1. Checkout latest `main`.
2. Parse Issue body.
3. Validate patch paths.
4. `git apply --check`.
5. Apply patch.
6. `git diff --check`.
7. changed Pythonの `py_compile`.
8. Commit.
9. latest `origin/main` へrebase.
10. Push `main`.
11. commit SHAをコメントし成功時Close.

失敗時はpushせず、failed runを診断してからrequestを再構築します。

## Positioning

```text
通常テキスト変更
  -> B. Git Change / direct GitHub write

[gpt-git-update]
  -> direct writeが使えない場合の互換フォールバック
```

新規プロジェクト・新規スレッドは、このIssue protocolを標準経路として採用しないでください。
