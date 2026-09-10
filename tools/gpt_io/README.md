# GPT External I/O Bridge

## v0.1 routing status

- **Git direct read/write:** PRODUCTION / STANDARD.
- **Git Issue/Actions transport:** COMPATIBILITY FALLBACK.
- **Google Drive native connector route:** PRODUCTION / STANDARD FOR CHATGPT-WORK.
- **Google Drive Actions backend:** DEFERRED / NOT REAL-DRIVE E2E ACCEPTED.

Repository-wide GitHub routing is defined by `.gpt/GITHUB_OPERATION_POLICY.md`. This bridge must not override the A/B/C/D routing decision.

Use connected native Google Drive tools for normal Drive operations. Google Docs, Sheets and Slides must use their native tools. The Actions backend remains in the repository as a future unattended-automation foundation; it is disabled unless repository variable `GPT_GDRIVE_ACTIONS_BRIDGE_ENABLED` is exactly `true`.

`GPT_GDRIVE_SERVICE_ACCOUNT_JSON` is not a standard setup requirement. The current JSON-key implementation is deferred because the environment's key-creation policy does not permit adopting long-lived Service Account keys. If unattended Actions-to-Drive automation becomes necessary, reopen the backend with GitHub Actions OIDC, Google Workload Identity Federation, and short-lived Service Account impersonation credentials.

See `tools/gpt_io/DRIVE_ROUTING_DECISION_v0_1.md` for the architecture decision and safety contract.

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

## Google Drive backend

The bridge transfers stored bytes (SQLite, ZIP, CSV, XLSX, JSON and similar files). It does not edit Google Docs, Sheets or Slides, and never decides whether Git or Drive is the source of truth.

Authentication uses `GPT_GDRIVE_SERVICE_ACCOUNT_JSON`; writes are limited to descendants of `GPT_GDRIVE_AUTOMATION_ROOT_ID`. Share only the dedicated automation root with the Service Account. Secrets must remain in GitHub Actions secrets and must not be placed in source, Issues, logs, artifacts, or reports.

The automation root itself is an allowed destination; no operation may cross above or outside it.

Upload is no-overwrite. `move`, `replace`, and `trash` require an exact file ID. Replace also requires matching `expected.file_id` and optionally checks expected size and modified time. `verify: true` re-downloads uploaded/replaced bytes and compares size and SHA-256 before success.

Optional `format_validation` accepts `zip` (CRC) or `xlsx` (ZIP CRC plus workbook structure).

Use a JSON request file:

```bash
python tools/gpt_io/gpt_io.py gdrive upload --request request.json
python tools/gpt_io/gpt_io.py gdrive download --request request.json
```

`[gpt-gdrive-request]` is for the deferred Actions backend only, not the standard GPT/Work route. Large source bytes use a short-lived Actions artifact referenced by `source_artifact_run_id` and `source_artifact_name`; do not place large Base64 in an Issue and do not commit Drive data to Git.

## Key rule

The I/O bridge is transport infrastructure. It does not choose whether a task belongs in GitHub Actions. Always make the A/B/C/D decision first, then select the narrowest transport needed by that route.
