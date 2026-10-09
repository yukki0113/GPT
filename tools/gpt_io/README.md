# GPT External I/O Bridge

## v0.1 routing status

- **Git direct read/write:** PRODUCTION / STANDARD.
- **Git Issue/Actions transport:** COMPATIBILITY FALLBACK.
- **Google Drive native connector route:** PRODUCTION / STANDARD FOR CHATGPT-WORK.
- **Google Drive authenticated Actions backend:** DISCONTINUED / NOT ACCEPTED.\n- **Public Drive read-only helper:** narrowly ACCEPTED with reviewed manifest and SHA-256.

Repository-wide GitHub routing is defined by `.gpt/GITHUB_OPERATION_POLICY.md`. This bridge must not override the A/B/C/D routing decision.

Use connected native Google Drive tools for normal Drive operations. Google Docs, Sheets and Slides must use their native tools. Do not configure an Actions-side authenticated Drive backend or issue bridge. Direct workflow `gdown` remains prohibited; the manifest-pinned public read-only helper is the sole exception.

See `tools/gpt_io/DRIVE_ROUTING_DECISION_v0_2.md` for the current architecture decision and safety contract.

## GitHub routing

Before using any Issue bridge, classify the task:

```text
A. Read / Audit
  -> GitHub direct read/search/fetch

B. Git Change
  -> UTF-8 source/test/docs/config/workflow via direct create/update/delete

C. Pure Deterministic Execution
  -> fetch canonical repo module and run locally when secrets/Actions-native evidence are unnecessary

D. Actions-Native Execution
  -> Issue -> Actions only when secrets, artifact chain, long runner work, immutable freeze, publication or formal run evidence are required
```

### Publishing GPT text changes to GitHub

For ordinary UTF-8 text/source changes, **do not use `[gpt-git-update]` as the standard route**.

Use:

```text
latest main
-> target path / current content / blob SHA
-> required change only
-> direct GitHub create/update/delete
-> remote commit verification
```

A successful GitHub direct write creates the remote commit; there is no additional local `git push` step.

When multiple interdependent files belong to one logical change, prefer one Git Data API commit when the available Git operation can safely create it. Do not split work merely because an older Issue protocol handled one request at a time.

`.gpt/GIT_UPDATE_ISSUE.md` remains as a compatibility fallback for an environment where direct text write is unavailable. It is not the default publication path.

### Binary Git files

For GitHub-managed binary files, first test whether the current GitHub / connector / Git environment can directly read or write the file. If direct transport is unavailable, the legacy binary route may be used as a fallback:

- `.gpt/GIT_BINARY_READ_ISSUE.md`
- `.gpt/GIT_BINARY_UPDATE_ISSUE.md`
- `.gpt/GIT_BINARY_TOOL.md`

`python tools/gpt_io/gpt_io.py git read|update ...` and `.gpt/tools/gpt_git_binary_tool.py` wrap the existing Issue/Actions binary transport. Because they internally create Issues / Actions runs, they are not an unconditional first choice under the 2026-09-10 policy.

External source-of-truth files are never synchronized through Git binary tooling merely because an old Git copy exists. Project README / `.gpt/WORKFLOW.md` decides the source of truth.

## Issue preflight

Only after D. Actions-Native Execution or an explicit compatibility Issue fallback has been selected, follow `.gpt/ISSUE_REQUEST_CONTRACTS.md`.

The shared validator is:

```bash
python .gpt/tools/gpt_issue_preflight.py \
  --title "[PREFIX] request" \
  --body-file /tmp/issue-body.md
```

The implementation lives at `tools/gpt_io/git/issue_preflight.py`. It validates the common legacy GPT-Git Issue protocols and supports project-specific simple key/value contracts with repeated `--required-key` options.

Do not create an Issue merely to run a preflight. The routing decision comes first.

## Google Drive transport

Decision: `tools/gpt_io/DRIVE_ROUTING_DECISION_v0_2.md`.
Authenticated/private Drive operations, Drive writes and native
Docs/Sheets/Slides stay in ChatGPT/Work's connected native tools.

For **reviewed public, immutable read-only inputs only**, Actions or local
Python may use the manifest-pinned `tools/gpt_io/public_drive/fetch.py`
helper with mandatory SHA-256 verification. See
`tools/gpt_io/public_drive/README.md` for its exact CLI and manifest contract.

Do not put raw `gdown` calls or ad-hoc Drive URLs in workflows.
Do not use authenticated Drive API, service-account secrets, OAuth, or
Drive write/upload from Actions. The retired `gdrive/` backend is not
reactivated. The A/B/C/D routing decision remains prior to transport selection.

## Key rule

The I/O bridge is transport infrastructure. It does not choose whether a task belongs in GitHub Actions. Always make the A/B/C/D decision first, then select the narrowest transport needed by that route.
