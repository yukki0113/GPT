# GPT Git Update Issue protocol

GitHubへ直接commit/pushできないChatGPT / Work環境から、GitHub Issueを経由して3プロジェクトのソース更新をmainへ反映するための共通経路です。

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
--- a/horse-racing/jrdb/README.md
+++ b/horse-racing/jrdb/README.md
@@ -1,3 +1,4 @@
 ...
```
```

## Allowed paths

- `horse-racing/jrdb/`
- `horse-racing/eval/`
- `boat-racing/`

Other paths are rejected.

The update workflow itself (`.github/`) cannot be modified through this route.

## Rejected files

The workflow rejects secrets/credentials and common non-source artifacts, including `.env`, `jrdb_secret.py`, archives, SQLite/DB files, Excel files, private keys and Python bytecode.

## Processing

1. Checkout latest `main`.
2. Parse the Issue body.
3. Validate all patch paths.
4. Run `git apply --check`.
5. Apply the patch.
6. Run `git diff --check`.
7. Run `py_compile` for changed Python files.
8. Commit with the requested commit message.
9. Push to `main`.
10. Comment the resulting commit SHA and close the Issue.

If any step fails, nothing is pushed and the Issue remains open with a link to the failed Actions run.

## GPT / Work rule

When direct GitHub commit/push is unavailable, do not ask the user to manually push ordinary source/documentation changes. Create a `[gpt-git-update]` Issue using this protocol and use the Issue/Actions route instead.
